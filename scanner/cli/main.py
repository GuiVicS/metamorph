"""Main CLI entry point for the scanner."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional

import click
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ..core.types import Dossier
from .crawler import Crawler, CrawlConfig, URLNormalizer
from .dimensions.network_storage import NetworkMonitor, StorageCapture
from .redaction.engine import redact_dossier, verify_redaction

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Metamorph Scanner - Full-platform web application scanner."""
    pass


@cli.command()
@click.option("--url", required=True, help="Starting URL to scan")
@click.option("--goals", required=True, help="Comma-separated list of capabilities to probe (e.g., getMessages,sendMessage)")
@click.option("--profile", default="default", help="Browser profile name (uses persistent context)")
@click.option("--out", "output_dir", default="./dossier", help="Output directory for dossier")
@click.option("--max-screens", default=50, help="Maximum screens to crawl")
@click.option("--max-depth", default=5, help="Maximum crawl depth")
@click.option("--include", "include_patterns", multiple=True, help="URL patterns to include (regex)")
@click.option("--exclude", "exclude_patterns", multiple=True, help="URL patterns to exclude (regex)")
@click.option("--timeout", default=30000, help="Navigation timeout (ms)")
@click.option("--settle", default=1500, help="Settle time after navigation (ms)")
@click.option("--behavioral-passes", default=3, help="Number of behavioral correlation passes")
@click.option("--headless/--no-headless", default=False, help="Run browser headless")
def scan(
    url: str,
    goals: str,
    profile: str,
    output_dir: str,
    max_screens: int,
    max_depth: int,
    include_patterns: tuple,
    exclude_patterns: tuple,
    timeout: int,
    settle: int,
    behavioral_passes: int,
    headless: bool,
) -> None:
    """Scan a web application and produce a dossier."""
    asyncio.run(_run_scan(
        url=url,
        goals=[g.strip() for g in goals.split(",")],
        profile=profile,
        output_dir=Path(output_dir),
        max_screens=max_screens,
        max_depth=max_depth,
        include_patterns=list(include_patterns),
        exclude_patterns=list(exclude_patterns),
        timeout=timeout,
        settle=settle,
        behavioral_passes=behavioral_passes,
        headless=headless,
    ))


async def _run_scan(
    url: str,
    goals: list[str],
    profile: str,
    output_dir: Path,
    max_screens: int,
    max_depth: int,
    include_patterns: list[str],
    exclude_patterns: list[str],
    timeout: int,
    settle: int,
    behavioral_passes: int,
    headless: bool,
) -> None:
    """Run the full scan."""
    # Prepare output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    screens_dir = output_dir / "screens"
    screens_dir.mkdir(exist_ok=True)

    # Browser profile directory
    profile_dir = Path.home() / ".metamorph" / "profiles" / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    config = CrawlConfig(
        max_screens=max_screens,
        max_depth=max_depth,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        timeout_ms=timeout,
        settle_ms=settle,
        behavioral_passes=behavioral_passes,
    )

    console.print(f"[bold cyan]Starting scan of {url}[/bold cyan]")
    console.print(f"Profile: {profile} ({profile_dir})")
    console.print(f"Goals: {', '.join(goals)}")

    async with async_playwright() as p:
        # Use persistent context for authenticated session
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        try:
            # Set up network monitor
            network_monitor = NetworkMonitor()
            page = browser.pages[0] if browser.pages else await browser.new_page()
            network_monitor.attach(page)

            # Run crawl
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                crawl_task = progress.add_task("Crawling...", total=max_screens)

                async with Crawler(browser, config, url) as crawler:
                    nav_graph = await crawler.crawl(url)

                    # Update progress
                    progress.update(crawl_task, completed=len(nav_graph.nodes))

                    # Capture network & storage per screen
                    for screen_id, screen in nav_graph.nodes.items():
                        progress.add_task(f"Capturing {screen_id}", total=3)

                        # Navigate to screen for detailed capture
                        await page.goto(screen.normalized_url, wait_until="networkidle", timeout=config.timeout_ms)
                        await page.wait_for_timeout(config.settle_ms)

                        # Network for this screen
                        network_data = network_monitor.capture.to_catalogue()
                        screen.network = type('obj', (object,), network_data)()

                        # Storage
                        storage_data = await StorageCapture.capture(page)
                        screen.storage = type('obj', (object,), storage_data)()

                        # Save individual screen
                        screen_file = screens_dir / f"{screen_id}.json"
                        screen_file.write_text(json.dumps({
                            "screen_id": screen.screen_id,
                            "normalized_url": screen.normalized_url,
                            "url_signature": screen.url_signature,
                            "dom_signature": screen.dom_signature,
                            "title": screen.title,
                            "depth": screen.depth,
                            "actions": screen.actions,
                            "static": screen.static.__dict__ if screen.static else None,
                            "runtime": screen.runtime.__dict__ if screen.runtime else None,
                            "network": network_data,
                            "storage": storage_data,
                            "dom": {
                                "stable_selectors": {k: v.to_dict() for k, v in screen.dom.stable_selectors.items()} if screen.dom else {},
                                "input_targets": screen.dom.input_targets if screen.dom else [],
                                "list_containers": screen.dom.list_containers if screen.dom else [],
                                "action_buttons": screen.dom.action_buttons if screen.dom else [],
                            } if screen.dom else None,
                        }, indent=2, ensure_ascii=False))

                        progress.update(crawl_task, advance=0)  # Just keep track

            # Build dossier
            dossier = Dossier(
                site_slug=URLNormalizer.normalize_url(url, urlparse(url).netloc).replace("https://", "").replace("http://", "").replace("/", "_"),
                base_url=url,
                nav_graph=nav_graph,
                screens=nav_graph.nodes,
                requested_goals=goals,
                coverage_estimate=min(1.0, len(nav_graph.nodes) / max_screens),
            )

            # Convert to dict for redaction
            dossier_dict = dossier.to_dict()

            # Redact
            console.print("[yellow]Redacting sensitive data...[/yellow]")
            redacted, redaction_report = redact_dossier(dossier_dict)
            dossier.redaction_report = [type('obj', (object,), r)() for r in redaction_report]

            # Verify redaction
            clean, violations = verify_redaction(redacted)
            if not clean:
                console.print("[red]REDACTION FAILED - VIOLATIONS FOUND:[/red]")
                for v in violations:
                    console.print(f"  {v['path']}: {v['reason']}")
                console.print("[red]Aborting - dossier not saved.[/red]")
                return

            # Save dossier
            dossier_file = output_dir / "dossier.json"
            dossier_file.write_text(json.dumps(redacted, indent=2, ensure_ascii=False))

            # Save redaction report
            report_file = output_dir / "redaction-report.json"
            report_file.write_text(json.dumps(redaction_report, indent=2, ensure_ascii=False))

            # Summary
            _print_summary(dossier, output_dir)

        finally:
            await browser.close()


@cli.command()
@click.argument("dossier_path", type=click.Path(exists=True, path_type=Path))
def report(dossier_path: Path) -> None:
    """Print a summary report of a dossier."""
    data = json.loads(dossier_path.read_text())
    dossier = Dossier.from_dict(data)
    _print_summary(dossier, dossier_path.parent)


def _print_summary(dossier: Dossier, output_dir: Path) -> None:
    """Print a nice summary table."""
    console.print(f"\n[bold green]Scan Complete[/bold green]")
    console.print(f"Site: {dossier.site_slug}")
    console.print(f"Scan ID: {dossier.scan_id}")
    console.print(f"Base URL: {dossier.base_url}")
    console.print(f"Screens visited: {len(dossier.screens)}")
    console.print(f"Coverage estimate: {dossier.coverage_estimate:.1%}")
    console.print(f"Goals requested: {', '.join(dossier.requested_goals) if dossier.requested_goals else 'None'}")
    console.print(f"Redaction entries: {len(dossier.redaction_report)}")
    console.print(f"Warnings: {len(dossier.warnings)}")
    console.print(f"\nOutput: {output_dir}")
    console.print(f"  - dossier.json (main dossier)")
    console.print(f"  - redaction-report.json")
    console.print(f"  - screens/ (per-screen details)")

    # Screen table
    table = Table(title="Screens Discovered")
    table.add_column("Screen ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("URL", style="blue")
    table.add_column("Depth", style="yellow")
    table.add_column("Actions", style="green")

    for screen in dossier.screens.values():
        table.add_row(
            screen.screen_id,
            screen.title or "N/A",
            screen.normalized_url[:60] + ("..." if len(screen.normalized_url) > 60 else ""),
            str(screen.depth),
            str(len(screen.actions)),
        )
    console.print(table)

    # Network summary
    if dossier.aggregated_network.requests:
        net_table = Table(title="Network Patterns")
        net_table.add_column("Method", style="cyan")
        net_table.add_column("URL Pattern", style="blue")
        net_table.add_column("GraphQL", style="yellow")
        for req in dossier.aggregated_network.requests[:20]:
            net_table.add_row(
                req.method,
                req.url_pattern[:70],
                "✓" if req.is_graphql else "",
            )
        console.print(net_table)


@cli.command()
@click.option("--profile", default="default", help="Browser profile to clear")
def clear_profile(profile: str) -> None:
    """Clear a browser profile (removes all cookies/storage)."""
    profile_dir = Path.home() / ".metamorph" / "profiles" / profile
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
        console.print(f"[green]Cleared profile: {profile}[/green]")
    else:
        console.print(f"[yellow]Profile not found: {profile}[/yellow]")


@cli.command()
@click.option("--profile", default="default", help="Browser profile to use")
@click.option("--url", required=True, help="URL to open")
def open(profile: str, url: str) -> None:
    """Open a URL in the browser profile (for manual login/setup)."""
    asyncio.run(_open_browser(profile, url))


async def _open_browser(profile: str, url: str) -> None:
    profile_dir = Path.home() / ".metamorph" / "profiles" / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
        )
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        console.print(f"[green]Opened {url} in profile '{profile}'[/green]")
        console.print("[yellow]Press Ctrl+C to close[/yellow]")
        try:
            await page.wait_for_event("close", timeout=0)
        except KeyboardInterrupt:
            pass
        finally:
            await browser.close()


if __name__ == "__main__":
    cli()