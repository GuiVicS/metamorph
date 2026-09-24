"""Probe Runner - Validates generated extension capabilities against live site."""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from playwright.async_api import Page, BrowserContext, async_playwright

from ..core.types import Dossier, CapabilityProbeTrace, Selector, Fragility
from ..crawl.crawler import CrawlConfig, URLNormalizer
from ..redaction.engine import verify_redaction


@dataclass
class ProbeResult:
    probe_id: str
    capability: str
    passed: bool
    assertions_passed: int
    assertions_total: int
    error: str | None = None
    duration_ms: int = 0
    details: list[dict] = field(default_factory=list)


@dataclass
class ProbeRunReport:
    dossier_path: str
    extension_path: str
    results: list[ProbeResult]
    overall_passed: int
    overall_total: int
    capabilities_tested: list[str]

    def to_json(self) -> dict:
        return {
            "dossier_path": self.dossier_path,
            "extension_path": self.extension_path,
            "results": [r.__dict__ for r in self.results],
            "summary": {
                "probes_passed": self.overall_passed,
                "probes_total": self.overall_total,
                "capabilities_tested": self.capabilities_tested,
            },
        }


class ProbeRunner:
    """Runs probes against a live site using the generated extension."""

    def __init__(self, context: BrowserContext, config: CrawlConfig) -> None:
        self.context = context
        self.config = config
        self.page: Page | None = None
        self.extension_loaded = False

    async def __aenter__(self) -> ProbeRunner:
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.config.timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.page:
            await self.page.close()

    async def load_extension(self, extension_dist_path: Path) -> None:
        """Load the unpacked extension into the browser context."""
        # Note: Playwright doesn't directly support loading unpacked extensions
        # We simulate by injecting the bridge and content script manually
        # For full extension testing, use Chrome with --load-extension
        # Here we inject the bridge.js and test capabilities via the same mechanisms
        manifest_path = extension_dist_path / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Extension manifest not found: {manifest_path}")

        # Inject bridge (MAIN world)
        bridge_path = extension_dist_path / "bridge.js"
        if bridge_path.exists():
            bridge_code = bridge_path.read_text()
            await self.page.add_init_script(bridge_code)

        # Inject content script (ISOLATED world simulation)
        content_path = extension_dist_path / "content.js"
        if content_path.exists():
            content_code = content_path.read_text()
            await self.page.add_init_script(content_code)

        self.extension_loaded = True

    async def run_probes(
        self,
        dossier: Dossier,
        probes: list[dict],
        goals: list[str] | None = None,
        consent_write: bool = False,
        sandbox_conversation_id: str | None = None,
    ) -> ProbeRunReport:
        """Run all probes for the given goals."""
        if not self.extension_loaded:
            raise RuntimeError("Extension not loaded. Call load_extension() first.")

        results = []
        capabilities_tested = []

        # Filter probes by goals
        if goals:
            probes = [p for p in probes if p.get("capability") in goals]

        for probe in probes:
            capability = probe.get("capability")
            if capability:
                capabilities_tested.append(capability)

            # Skip write probes without consent
            if probe.get("sideEffects") == "writes" and not consent_write:
                results.append(ProbeResult(
                    probe_id=probe.get("id", ""),
                    capability=capability or "",
                    passed=False,
                    assertions_passed=0,
                    assertions_total=0,
                    error="Write probe skipped (no consent)",
                ))
                continue

            result = await self._run_single_probe(probe, dossier, sandbox_conversation_id)
            results.append(result)

        return ProbeRunReport(
            dossier_path="",
            extension_path="",
            results=results,
            overall_passed=sum(1 for r in results if r.passed),
            overall_total=len(results),
            capabilities_tested=capabilities_tested,
        )

    async _run_single_probe(
        self,
        probe: dict,
        dossier: Dossier,
        sandbox_conversation_id: str | None,
    ) -> ProbeResult:
        import time
        start = time.perf_counter()

        probe_id = probe.get("id", "unknown")
        capability = probe.get("capability", "")
        steps = probe.get("steps", [])
        assertions = probe.get("assert", [])

        details = []
        passed = True
        error = None
        assertions_passed = 0

        try:
            # Execute steps
            context_data = {}
            for step in steps:
                if "invoke" in step:
                    cap_name = step["invoke"]
                    args = step.get("args", {})

                    # Substitute template variables
                    if sandbox_conversation_id:
                        args = {k: (sandbox_conversation_id if v == "{{probeConversationId}}" else v) for k, v in args.items()}
                    args = {k: (f"probe_{int(time.time())}" if v == "{{probeToken}}" else v) for k, v in args.items()}

                    # Execute capability via bridge
                    result = await self._invoke_capability(cap_name, args)
                    context_data["last_result"] = result
                    context_data["last_capability"] = cap_name

            # Run assertions
            for assertion in assertions:
                assertion_passed = await self._check_assertion(assertion, context_data)
                details.append({"assertion": assertion, "passed": assertion_passed})
                if assertion_passed:
                    assertions_passed += 1
                else:
                    passed = False

        except Exception as e:
            passed = False
            error = str(e)
            details.append({"error": error})

        duration_ms = int((time.perf_counter() - start) * 1000)

        return ProbeResult(
            probe_id=probe_id,
            capability=capability,
            passed=passed,
            assertions_passed=assertions_passed,
            assertions_total=len(assertions),
            error=error,
            duration_ms=duration_ms,
            details=details,
        )

    async def _invoke_capability(self, capability: str, args: dict) -> Any:
        """Invoke a capability via the bridge in MAIN world."""
        # Send postMessage to MAIN world bridge
        request_id = f"probe_{capability}_{int(asyncio.get_event_loop().time() * 1000)}"

        # Create a promise that resolves when response comes back
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        # Send to bridge
        await self.page.evaluate("""
            (msg) => window.postMessage({ source: 'metamorph_bridge', type: 'invoke', payload: msg }, '*')
        """, {"requestId": request_id, "capability": capability, "binding": self._get_binding_for_capability(capability), "args": args})

        try:
            result = await asyncio.wait_for(future, timeout=10)
            return result
        except asyncio.TimeoutError:
            raise RuntimeError(f"Capability {capability} timed out")

    def _get_binding_for_capability(self, capability: str) -> dict:
        """Get binding config for a capability from the injected fingerprint."""
        # In real implementation, this comes from the fingerprint
        # For probe runner, we use a simplified version
        return {"type": "runtime-call", "handle": "messageStore", "method": "getMessages"}

    async def _check_assertion(self, assertion: dict, context: dict) -> bool:
        """Check a single assertion against the last result."""
        assertion_type = assertion.get("type", "equals")
        path = assertion.get("path", [])

        # Get value from context
        value = context.get("last_result")
        if path:
            for segment in path:
                if value is None: return False
                value = value.get(segment) if isinstance(value, dict) else None

        expected = assertion.get("equals")
        if expected == "{{probeToken}}":
            expected = context.get("last_args", {}).get("text", f"probe_{int(asyncio.get_event_loop().time())}")

        if assertion_type == "equals":
            return value == expected
        elif assertion_type == "nonEmpty":
            return bool(value and (isinstance(value, str) and len(value) > 0 or isinstance(value, (list, dict)) and len(value) > 0))
        elif assertion_type == "type":
            expected_type = assertion.get("type")
            if expected_type == "string": return isinstance(value, str)
            if expected_type == "array": return isinstance(value, list)
            if expected_type == "number": return isinstance(value, (int, float))
            if expected_type == "object": return isinstance(value, dict)
            return True
        elif assertion_type == "minLength":
            return isinstance(value, (list, str)) and len(value) >= assertion.get("minLength", 1)

        return True


class ExtensionProbeValidator:
    """High-level validator that loads extension, runs probes, generates report."""

    def __init__(self, config: CrawlConfig | None = None) -> None:
        self.config = config or CrawlConfig()

    async def validate(
        self,
        extension_dist: Path,
        dossier_path: Path,
        goals: list[str] | None = None,
        consent_write: bool = False,
        sandbox_conversation_id: str | None = None,
        headless: bool = False,
    ) -> ProbeRunReport:
        """Run full probe validation."""

        # Load dossier
        dossier = Dossier.load(dossier_path)

        # Load probes from extension (probes.json)
        probes_file = extension_dist / "probes.json"
        if not probes_file.exists():
            # Fallback: generate probes from dossier capability_traces
            probes = [p.__dict__ for p in dossier.capability_traces]
        else:
            probes = json.loads(probes_file.read_text())

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()

            try:
                async with ProbeRunner(context, self.config) as runner:
                    await runner.load_extension(extension_dist)

                    # Navigate to the site
                    page = runner.page
                    assert page is not None
                    await page.goto(dossier.base_url, wait_until="networkidle", timeout=self.config.timeout_ms)
                    await page.wait_for_timeout(self.config.settle_ms)

                    # Run probes
                    report = await runner.run_probes(
                        dossier, probes, goals, consent_write, sandbox_conversation_id
                    )
                    report.dossier_path = str(dossier_path)
                    report.extension_path = str(extension_dist)
                    return report

            finally:
                await context.close()
                await browser.close()


async def main():
    """CLI entry point for probe validation."""
    import argparse
    parser = argparse.ArgumentParser(description="Run probes against generated extension")
    parser.add_argument("--ext", required=True, type=Path, help="Extension dist directory")
    parser.add_argument("--dossier", required=True, type=Path, help="Dossier.json path")
    parser.add_argument("--goals", help="Comma-separated goals to test")
    parser.add_argument("--consent", action="store_true", help="Allow write probes")
    parser.add_argument("--sandbox-target", help="Conversation ID for write probes")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    args = parser.parse_args()

    goals = args.goals.split(",") if args.goals else None

    validator = ExtensionProbeValidator()
    report = await validator.validate(
        extension_dist=args.ext,
        dossier_path=args.dossier,
        goals=goals,
        consent_write=args.consent,
        sandbox_conversation_id=args.sandbox_target,
        headless=args.headless,
    )

    print(json.dumps(report.to_json(), indent=2))

    # Exit code based on results
    if report.overall_passed == report.overall_total:
        print("✅ All probes passed")
        return 0
    else:
        print(f"❌ {report.overall_total - report.overall_passed} probes failed")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))