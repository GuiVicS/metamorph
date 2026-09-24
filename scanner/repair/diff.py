"""Diff utilities for dossier comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DossierDiff:
    changed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_dossiers(cls, prev_dict: dict, curr_dict: dict) -> DossierDiff:
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

    def to_dict(self) -> dict:
        return {
            "changed": self.changed,
            "added": self.added,
            "removed": self.removed,
            "summary": self.summary,
        }


def compute_diff(prev_dict: dict, curr_dict: dict) -> DossierDiff:
    """Convenience function to compute diff."""
    return DossierDiff.from_dossiers(prev_dict, curr_dict)


def format_diff_for_llm(diff: DossierDiff, max_items: int = 20) -> str:
    """Format diff for LLM repair prompt."""
    lines = ["DIFF SUMMARY:", diff.summary, ""]

    if diff.changed:
        lines.append("CHANGED:")
        for path in diff.changed[:max_items]:
            lines.append(f"  - {path}")
        if len(diff.changed) > max_items:
            lines.append(f"  ... and {len(diff.changed) - max_items} more")
        lines.append("")

    if diff.added:
        lines.append("ADDED:")
        for path in diff.added[:max_items]:
            lines.append(f"  + {path}")
        lines.append("")

    if diff.removed:
        lines.append("REMOVED:")
        for path in diff.removed[:max_items]:
            lines.append(f"  - {path}")
        lines.append("")

    return "\n".join(lines)