"""Core types for the Metamorph scanner dossier."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


class Fragility(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CapabilityKind(str, Enum):
    READ = "read"
    WRITE = "write"
    EVENT = "event"


class BindingType(str, Enum):
    INTERNAL_HTTP = "internal-http"
    RUNTIME_CALL = "runtime-call"
    RUNTIME_READ = "runtime-read"
    RUNTIME_SUBSCRIBE = "runtime-subscribe"
    GRAPHQL = "graphql"
    FUNCTION_INTERCEPT = "function-intercept"
    NETWORK_INTERCEPT = "network-intercept"
    DOM_ACTION = "dom-action"
    DOM_READ = "dom-read"


@dataclass
class Selector:
    css: str
    fragility: Fragility
    last_verified: str  # ISO date
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NetworkRequest:
    method: str
    url_pattern: str
    request_shape: dict
    response_shape: dict
    headers: dict = field(default_factory=dict)
    is_graphql: bool = False
    graphql_op_name: str | None = None
    graphql_doc_hash: str | None = None


@dataclass
class NetworkCatalogue:
    requests: list[NetworkRequest] = field(default_factory=list)
    websocket_endpoints: list[dict] = field(default_factory=list)
    sse_endpoints: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "requests": [r.__dict__ for r in self.requests],
            "websocket_endpoints": self.websocket_endpoints,
            "sse_endpoints": self.sse_endpoints,
        }


@dataclass
class StorageInventory:
    local_storage_keys: dict[str, str] = field(default_factory=dict)  # key -> shape
    session_storage_keys: dict[str, str] = field(default_factory=dict)
    indexed_dbs: list[dict] = field(default_factory=list)  # {name, stores: [{name, keyPath, indexes}]}
    cookie_names: list[str] = field(default_factory=list)
    cache_storage_entries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StaticSurface:
    scripts: list[dict] = field(default_factory=list)  # {url, size, has_source_map}
    framework: str | None = None
    framework_version: str | None = None
    bundler: str | None = None
    build_hash: str | None = None
    module_system: str | None = None  # "webpack-require", "vite", "next", "esm", "custom"


@dataclass
class RuntimeTopology:
    window_globals: list[str] = field(default_factory=list)  # non-baseline globals
    module_registries: list[dict] = field(default_factory=list)  # {type, global_name, shape}
    state_stores: list[dict] = field(default_factory=list)  # {path, shape, type: redux/mobx/zustand/unknown}
    event_bus: list[dict] = field(default_factory=list)  # {path, methods}


@dataclass
class BehavioralPass:
    action: str
    pass_number: int
    changed_handles: list[str] = field(default_factory=list)
    network_delta: list[dict] = field(default_factory=list)
    dom_mutations: list[dict] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class BehavioralCorrelation:
    action: str
    passes: list[BehavioralPass] = field(default_factory=list)
    intersected_handles: list[str] = field(default_factory=list)
    noise_floor_handles: list[str] = field(default_factory=list)
    ranked_candidates: list[dict] = field(default_factory=list)  # {handle, specificity, confidence}


@dataclass
class DOMStructure:
    stable_selectors: dict[str, Selector] = field(default_factory=dict)
    input_targets: list[dict] = field(default_factory=list)
    list_containers: list[dict] = field(default_factory=list)
    action_buttons: list[dict] = field(default_factory=list)


@dataclass
class CapabilityProbeTrace:
    capability: str
    steps: list[dict] = field(default_factory=list)
    observed_binding: dict | None = None
    success: bool = False
    error: str | None = None


@dataclass
class RedactionEntry:
    path: str
    reason: str
    original_type: str


@dataclass
class Screen:
    screen_id: str
    normalized_url: str
    url_signature: str  # normalized URL without volatile parts
    dom_signature: str  # hash of key DOM structure
    title: str | None = None
    depth: int = 0
    parent_screen_id: str | None = None
    actions: list[dict] = field(default_factory=list)  # {type, target, leads_to_screen_id}
    static: StaticSurface | None = None
    runtime: RuntimeTopology | None = None
    network: NetworkCatalogue | None = None
    storage: StorageInventory | None = None
    behavioral: list[BehavioralCorrelation] = field(default_factory=list)
    dom: DOMStructure | None = None
    probes: list[CapabilityProbeTrace] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    auth_barrier: dict | None = None  # Login, CAPTCHA, 2FA, etc.


@dataclass
class NavEdge:
    from_screen: str
    to_screen: str
    action: dict  # {type, target, description}
    deterministic: bool = True


@dataclass
class NavGraph:
    nodes: dict[str, Screen] = field(default_factory=dict)  # screen_id -> Screen
    edges: list[NavEdge] = field(default_factory=list)
    entry_screen_id: str | None = None


@dataclass
class Dossier:
    """The complete dossier for a platform."""
    site_slug: str
    base_url: str
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    scanner_version: str = "0.1.0"
    scan_id: str = field(default_factory=lambda: uuid4().hex[:12])

    # Crawl results
    nav_graph: NavGraph = field(default_factory=NavGraph)
    screens: dict[str, Screen] = field(default_factory=dict)  # screen_id -> Screen

    # Aggregated dimensions
    aggregated_runtime: RuntimeTopology = field(default_factory=RuntimeTopology)
    aggregated_network: NetworkCatalogue = field(default_factory=NetworkCatalogue)
    aggregated_storage: StorageInventory = field(default_factory=StorageInventory)
    behavioral_correlations: list[BehavioralCorrelation] = field(default_factory=list)

    # Goals & capabilities
    requested_goals: list[str] = field(default_factory=list)
    capability_traces: list[CapabilityProbeTrace] = field(default_factory=list)

    # Metadata
    coverage_estimate: float = 0.0  # 0-1
    redaction_report: list[RedactionEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    previous_dossier_version: str | None = None
    diff_from_previous: dict | None = None

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "site_slug": self.site_slug,
            "base_url": self.base_url,
            "generated_at": self.generated_at,
            "scanner_version": self.scanner_version,
            "scan_id": self.scan_id,
            "nav_graph": self._nav_graph_to_dict(),
            "screens": {k: self._screen_to_dict(v) for k, v in self.screens.items()},
            "aggregated_runtime": self.aggregated_runtime.__dict__,
            "aggregated_network": self.aggregated_network.to_dict(),
            "aggregated_storage": self.aggregated_storage.to_dict(),
            "behavioral_correlations": [c.__dict__ for c in self.behavioral_correlations],
            "requested_goals": self.requested_goals,
            "capability_traces": [c.__dict__ for c in self.capability_traces],
            "coverage_estimate": self.coverage_estimate,
            "redaction_report": [r.__dict__ for r in self.redaction_report],
            "warnings": self.warnings,
            "previous_dossier_version": self.previous_dossier_version,
            "diff_from_previous": self.diff_from_previous,
        }

    def _nav_graph_to_dict(self) -> dict:
        return {
            "nodes": {k: self._screen_to_dict(v) for k, v in self.nav_graph.nodes.items()},
            "edges": [e.__dict__ for e in self.nav_graph.edges],
            "entry_screen_id": self.nav_graph.entry_screen_id,
        }

    def _screen_to_dict(self, screen: Screen) -> dict:
        d = asdict(screen)
        # Convert nested dataclasses
        if screen.static:
            d["static"] = screen.static.__dict__
        if screen.runtime:
            d["runtime"] = screen.runtime.__dict__
        if screen.network:
            d["network"] = screen.network.to_dict() if hasattr(screen.network, 'to_dict') else screen.network.__dict__
        if screen.storage:
            d["storage"] = screen.storage.to_dict() if hasattr(screen.storage, 'to_dict') else screen.storage.__dict__
        if screen.dom:
            d["dom"] = asdict(screen.dom)
        d["behavioral"] = [b.__dict__ for b in screen.behavioral]
        d["probes"] = [p.__dict__ for p in screen.probes]
        return d

    @classmethod
    def from_json(cls, data: str) -> Dossier:
        return cls.from_dict(json.loads(data))

    @classmethod
    def from_dict(cls, data: dict) -> Dossier:
        # Minimal reconstruction for loading; full reconstruction not needed for MVP
        dossier = cls(
            site_slug=data["site_slug"],
            base_url=data["base_url"],
            generated_at=data.get("generated_at", ""),
            scanner_version=data.get("scanner_version", ""),
            scan_id=data.get("scan_id", ""),
            requested_goals=data.get("requested_goals", []),
            coverage_estimate=data.get("coverage_estimate", 0.0),
            warnings=data.get("warnings", []),
            previous_dossier_version=data.get("previous_dossier_version"),
            diff_from_previous=data.get("diff_from_previous"),
        )
        # Reconstruct screens (simplified)
        for sid, sd in data.get("screens", {}).items():
            screen = Screen(
                screen_id=sd["screen_id"],
                normalized_url=sd["normalized_url"],
                url_signature=sd["url_signature"],
                dom_signature=sd["dom_signature"],
                title=sd.get("title"),
                depth=sd.get("depth", 0),
                parent_screen_id=sd.get("parent_screen_id"),
                actions=sd.get("actions", []),
                warnings=sd.get("warnings", []),
            )
            dossier.screens[sid] = screen
        return dossier

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Dossier:
        return cls.from_json(path.read_text(encoding="utf-8"))