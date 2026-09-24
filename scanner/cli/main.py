"""Main CLI entry point for the scanner."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import click
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ..core.types import Dossier
from ..crawl.crawler import Crawler, CrawlConfig, URLNormalizer
from ..dimensions.network_storage import NetworkMonitor, StorageCapture
from ..redaction.engine import redact_dossier, verify_redaction
from ..probe.runner import ExtensionProbeValidator
from ..repair.engine import RepairEngine, compute_diff

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

            # Run crawl (without Progress bar to avoid Windows encoding issues)
            console.print("[cyan]Crawling...[/cyan]")
            async with Crawler(browser, config, url) as crawler:
                nav_graph = await crawler.crawl(url)
                console.print(f"[green]Crawled {len(nav_graph.nodes)} screens[/green]")

                # Capture network & storage per screen
                for screen_id, screen in nav_graph.nodes.items():
                    console.print(f"[cyan]Capturing {screen_id}...[/cyan]")

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

    # Screen list
    console.print("\nScreens Discovered:")
    for screen in dossier.screens.values():
        console.print(f"  {screen.screen_id}: {screen.title or 'N/A'} (depth={screen.depth}, actions={len(screen.actions)})")

    # Network summary
    if dossier.aggregated_network.requests:
        console.print("\nNetwork Patterns:")
        for req in dossier.aggregated_network.requests[:20]:
            console.print(f"  {req.method} {req.url_pattern[:70]} {'(GraphQL)' if req.is_graphql else ''}")


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


@cli.command()
@click.option("--ext", required=True, type=click.Path(exists=True, path_type=Path), help="Extension dist directory")
@click.option("--dossier", required=True, type=click.Path(exists=True, path_type=Path), help="Dossier.json path")
@click.option("--goals", help="Comma-separated goals to test")
@click.option("--consent", is_flag=True, help="Allow write probes (requires --sandbox-target)")
@click.option("--sandbox-target", help="Conversation ID for write probes")
@click.option("--headless/--no-headless", default=True, help="Run headless")
def probe(ext: Path, dossier: Path, goals: str, consent: bool, sandbox_target: str, headless: bool) -> None:
    """Run probes against a generated extension."""
    goal_list = goals.split(",") if goals else None
    asyncio.run(_run_probe(ext, dossier, goal_list, consent, sandbox_target, headless))


async def _run_probe(
    ext: Path,
    dossier: Path,
    goals: list[str] | None,
    consent: bool,
    sandbox_target: str | None,
    headless: bool,
) -> None:
    validator = ExtensionProbeValidator()
    report = await validator.validate(
        extension_dist=ext,
        dossier_path=dossier,
        goals=goals,
        consent_write=consent,
        sandbox_conversation_id=sandbox_target,
        headless=headless,
    )

    console.print(json.dumps(report.to_json(), indent=2))

    if report.overall_passed == report.overall_total:
        console.print("[bold green]✅ All probes passed[/bold green]")
    else:
        console.print(f"[bold red]❌ {report.overall_total - report.overall_passed} probes failed[/bold red]")
        raise SystemExit(1)


@cli.command()
@click.option("--url", required=True, help="Starting URL to scan")
@click.option("--goals", required=True, help="Comma-separated capabilities to repair")
@click.option("--profile", default="default", help="Browser profile name")
@click.option("--prev", "previous_dossier", required=True, type=click.Path(exists=True, path_type=Path), help="Previous dossier.json for diff")
@click.option("--out", "output_dir", default="./dossier", help="Output directory for new dossier")
@click.option("--headless/--no-headless", default=False, help="Run browser headless")
def repair(url: str, goals: str, profile: str, previous_dossier: Path, output_dir: Path, headless: bool) -> None:
    """Repair a broken fingerprint by re-scanning with diff context."""
    asyncio.run(_run_repair(url, goals, profile, previous_dossier, output_dir, headless))


async def _run_repair(
    url: str,
    goals: str,
    profile: str,
    previous_dossier: Path,
    output_dir: Path,
    headless: bool,
) -> None:
    goal_list = [g.strip() for g in goals.split(",")]

    # Analyze diff first
    prev = Dossier.load(previous_dossier)
    console.print(f"[cyan]Analyzing breakage against {prev.scan_id}...[/cyan]")

    # For now, run a fresh scan with --prev context
    # The scanner already handles previous dossier
    config = CrawlConfig()

    # We need to run scan with previous dossier context
    # This is a simplified version - in practice would use the RepairEngine
    console.print("[yellow]Running repair scan...[/yellow]")

    # Reuse scan logic with previous dossier
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path.home() / ".metamorph" / "profiles" / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check"],
        )

        try:
            network_monitor = NetworkMonitor()
            page = browser.pages[0] if browser.pages else await browser.new_page()
            network_monitor.attach(page)

            async with Crawler(browser, config, url) as crawler:
                nav_graph = await crawler.crawl(url)

                for screen_id, screen in nav_graph.nodes.items():
                    await page.goto(screen.normalized_url, wait_until="networkidle", timeout=config.timeout_ms)
                    await page.wait_for_timeout(config.settle_ms)
                    network_data = network_monitor.capture.to_catalogue()
                    screen.network = type('obj', (object,), network_data)()
                    storage_data = await StorageCapture.capture(page)
                    screen.storage = type('obj', (object,), storage_data)()

            # Build new dossier
            new_dossier = Dossier(
                site_slug=URLNormalizer.normalize_url(url, urlparse(url).netloc).replace("https://", "").replace("http://", "").replace("/", "_"),
                base_url=url,
                nav_graph=nav_graph,
                screens=nav_graph.nodes,
                requested_goals=goal_list,
                coverage_estimate=min(1.0, len(nav_graph.nodes) / config.max_screens),
                previous_dossier_version=prev.scan_id,
            )

            # Compute diff
            diff = compute_diff(prev.to_dict(), new_dossier.to_dict())
            new_dossier.diff_from_previous = diff.to_dict()

            console.print(f"[cyan]Diff: {diff.summary}[/cyan]")
            for path in diff.changed[:10]:
                console.print(f"  ~ {path}")
            for path in diff.added[:5]:
                console.print(f"  + {path}")

            # Redact and save
            redacted, redaction_report = redact_dossier(new_dossier.to_dict())
            clean, violations = verify_redaction(redacted)
            if not clean:
                console.print("[red]REDACTION FAILED[/red]")
                raise SystemExit(1)

            dossier_file = output_dir / "dossier.json"
            dossier_file.write_text(json.dumps(redacted, indent=2, ensure_ascii=False))

            console.print(f"[green]Repair dossier saved to {dossier_file}[/green]")
            console.print("[yellow]Next: Use the skill to regenerate extension from this dossier[/yellow]")

        finally:
            await browser.close()


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