"""Repair Engine - Diff-based re-scan and fingerprint regeneration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.types import Dossier
from .diff import DossierDiff, compute_diff


@dataclass
class RepairPlan:
    """Plan for repairing a broken fingerprint."""
    site_slug: str
    previous_dossier_path: Path
    current_dossier_path: Path
    diff: DossierDiff
    affected_capabilities: list[str]
    recommended_actions: list[str]


class RepairEngine:
    """Orchestrates the repair flow: detect -> diff -> regenerate -> validate."""

    def __init__(self, scanner_cli) -> None:
        self.scanner = scanner_cli

    def analyze_breakage(self, previous_dossier: Path, current_dossier: Path) -> RepairPlan:
        """Analyze what broke between two dossier versions."""
        prev = Dossier.load(previous_dossier)
        curr = Dossier.load(current_dossier)

        diff = compute_diff(prev, curr)

        # Identify affected capabilities
        affected = self._identify_affected_capabilities(diff, prev)

        # Generate recommended actions
        actions = self._generate_actions(diff, affected)

        return RepairPlan(
            site_slug=prev.site_slug,
            previous_dossier_path=previous_dossier,
            current_dossier_path=current_dossier,
            diff=diff,
            affected_capabilities=affected,
            recommended_actions=actions,
        )

    def _identify_affected_capabilities(self, diff: DossierDiff, prev: Dossier) -> list[str]:
        """Determine which capabilities are likely broken based on the diff."""
        affected = set()

        # Check runtime/handles changes
        for path in diff.changed:
            if "runtime" in path or "handles" in path:
                # All runtime-call/runtime-read capabilities potentially affected
                for cap_name, cap_trace in prev.capability_traces:
                    if cap_trace.observed_binding and cap_trace.observed_binding.get("type") in ("runtime-call", "runtime-read"):
                        affected.add(cap_name)

        # Check network changes
        for path in diff.changed:
            if "network" in path or "aggregated_network" in path:
                for cap_name, cap_trace in prev.capability_traces:
                    if cap_trace.observed_binding and cap_trace.observed_binding.get("type") in ("internal-http", "graphql"):
                        affected.add(cap_name)

        # Check DOM/selector changes
        for path in diff.changed:
            if "dom" in path or "selectors" in path:
                for cap_name, cap_trace in prev.capability_traces:
                    if cap_trace.observed_binding and cap_trace.observed_binding.get("type") in ("dom-action", "dom-read"):
                        affected.add(cap_name)

        return list(affected)

    def _generate_actions(self, diff: DossierDiff, affected: list[str]) -> list[str]:
        """Generate human-readable repair actions."""
        actions = []

        if not diff.changed and not diff.added and not diff.removed:
            actions.append("No significant changes detected")
            return actions

        # Summarize key changes
        for path in diff.changed[:5]:
            if "module_registries" in path or "chunkGlobal" in path:
                actions.append("Webpack chunk global changed - update discovery config")
            elif "handles" in path:
                actions.append("Handle resolution paths changed - re-run shape matching")
            elif "network" in path and "url_pattern" in path:
                actions.append("API endpoint URLs changed - update urlTemplate bindings")
            elif "selectors" in path:
                actions.append("DOM selectors changed - verify stable selectors still exist")

        for path in diff.added[:3]:
            actions.append(f"New screen/module detected: {path}")

        if affected:
            actions.append(f"Re-validate capabilities: {', '.join(affected)}")
        else:
            actions.append("Run full probe suite to verify all capabilities")

        return actions

    async def repair(
        self,
        site_slug: str,
        url: str,
        goals: list[str],
        previous_dossier_path: Path,
        profile: str,
        output_dir: Path,
        headless: bool = False,
    ) -> Dossier:
        """Execute repair: re-scan with previous dossier context, regenerate."""
        # The scanner already supports --prev for diff-aware scanning
        # This method orchestrates the full flow

        # 1. Re-scan with previous dossier attached
        new_dossier = await self.scanner.scan_with_prev(
            url=url,
            goals=goals,
            profile=profile,
            previous_dossier=previous_dossier_path,
            output_dir=output_dir,
            headless=headless,
        )

        # 2. Compute diff
        prev_dossier = Dossier.load(previous_dossier_path)
        diff = compute_diff(prev_dossier, new_dossier)

        # 3. Validate only affected capabilities (or all)
        # (Probe validation would happen here)

        return new_dossier


# Diff computation
def compute_diff(prev: Dossier, curr: Dossier) -> DossierDiff:
    """Compute structural diff between two dossiers."""
    return DossierDiff.from_dossiers(prev, curr)


@dataclass
class DossierDiff:
    changed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_dossiers(cls, prev: Dossier, curr: Dossier) -> DossierDiff:
        prev_dict = prev.to_dict()
        curr_dict = curr.to_dict()

        diff = cls()
        diff._diff_dicts("", prev_dict, curr_dict)
        diff._generate_summary()
        return diff

    def _diff_dicts(self, path: str, prev: Any, curr: Any) -> None:
        if type(prev) != type(curr):
            self.changed.append(path or "root")
            return

        if isinstance(prev, dict):
            all_keys = set(prev.keys()) | set(curr.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                if key not in prev:
                    self.added.append(new_path)
                elif key not in curr:
                    self.removed.append(new_path)
                else:
                    self._diff_dicts(new_path, prev[key], curr[key])

        elif isinstance(prev, list):
            if len(prev) != len(curr):
                self.changed.append(f"{path} (length {len(prev)} -> {len(curr)})")
            else:
                for i, (p, c) in enumerate(zip(prev, curr)):
                    self._diff_dicts(f"{path}[{i}]", p, c)

        elif prev != curr:
            self.changed.append(path)

    def _generate_summary(self) -> None:
        parts = []
        if self.changed:
            parts.append(f"{len(self.changed)} changed")
        if self.added:
            parts.append(f"{len(self.added)} added")
        if self.removed:
            parts.append(f"{len(self.removed)} removed")
        self.summary = "; ".join(parts) if parts else "No changes"