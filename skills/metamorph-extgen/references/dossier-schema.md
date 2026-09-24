# Dossier Schema Reference

Complete JSON structure of the Metamorph scanner dossier.

## Top-Level

```json
{
  "site_slug": "discord",
  "base_url": "https://discord.com/channels/@me",
  "generated_at": "2026-09-24T13:06:00Z",
  "scanner_version": "0.1.0",
  "scan_id": "scn_01J8XQ4M2P",
  "nav_graph": { ... },
  "screens": { ... },
  "aggregated_runtime": { ... },
  "aggregated_network": { ... },
  "aggregated_storage": { ... },
  "behavioral_correlations": [ ... ],
  "requested_goals": ["getMessages", "sendMessage", "getConversations"],
  "capability_traces": [ ... ],
  "coverage_estimate": 0.94,
  "redaction_report": [ ... ],
  "warnings": [],
  "previous_dossier_version": null,
  "diff_from_previous": null
}
```

## NavGraph

```json
{
  "nodes": { "scr_a1b2c3d4": { ... Screen ... } },
  "edges": [
    { "from_screen": "scr_a1b2c3d4", "to_screen": "scr_e5f6g7h8", "action": { "type": "click", "target": "Conversation link", "description": "Navigate to conversation" }, "deterministic": true }
  ],
  "entry_screen_id": "scr_a1b2c3d4"
}
```

## Screen

```json
{
  "screen_id": "scr_a1b2c3d4",
  "normalized_url": "https://discord.com/channels/@me",
  "url_signature": "a1b2c3d4e5f6",
  "dom_signature": "f6e5d4c3b2a1",
  "title": "Discord",
  "depth": 0,
  "parent_screen_id": null,
  "actions": [
    { "type": "anchor", "target": "General", "leads_to_url": "https://discord.com/channels/123/456", "description": "Click channel: General" }
  ],
  "static": { "framework": "React", "framework_version": "18.2", "bundler": "Webpack", "build_hash": "a3f9c1e", "module_system": "webpack-require" },
  "runtime": { "window_globals": ["webpackChunkdiscord_app", "DiscordNative"], "module_registries": [...], "state_stores": [...], "event_bus": [...] },
  "network": { "requests": [...], "websocket_endpoints": [...], "sse_endpoints": [...] },
  "storage": { "local_storage_keys": {}, "session_storage_keys": {}, "indexed_dbs": [...], "cookie_names": ["__cf_bm", "__dcfduid"], "cache_storage_entries": [] },
  "behavioral": [ ... BehavioralCorrelation ... ],
  "dom": { "stable_selectors": { ... }, "input_targets": [...], "list_containers": [...], "action_buttons": [...] },
  "probes": [ ... CapabilityProbeTrace ... ],
  "warnings": []
}
```

## StaticSurface

```json
{
  "scripts": [{ "url": "https://discord.com/assets/abc.js", "async": true, "defer": false, "type": "module" }],
  "framework": "React",
  "framework_version": "18.2",
  "bundler": "Webpack",
  "build_hash": "a3f9c1e",
  "module_system": "webpack-require"
}
```

## RuntimeTopology

```json
{
  "window_globals": ["webpackChunkdiscord_app", "webpackChunkdiscord_app_v2", "__webpack_require__", "DiscordNative"],
  "module_registries": [
    { "type": "webpack-chunk", "global_name": "webpackChunkdiscord_app", "shape": "object" }
  ],
  "state_stores": [
    { "path": "window.DiscordNative._stores", "type": "custom", "keys": ["getMessage", "getMessages", "getChannel"] }
  ],
  "event_bus": [
    { "path": "window.DiscordNative.EventEmitter", "methods": ["on", "emit", "off"] }
  ]
}
```

## NetworkCatalogue

```json
{
  "requests": [
    {
      "method": "GET",
      "url_pattern": "/api/v9/channels/:id/messages",
      "request_shape": {},
      "response_shape": { "type": "array", "items": { "type": "object", "properties": { "id": "string", "content": "string", "author": "object", "timestamp": "string" } } },
      "headers": { "accept": "application/json" },
      "is_graphql": false
    }
  ],
  "websocket_endpoints": [
    { "url": "wss://gateway.discord.gg/?v=9&encoding=json", "messages_sample": [{ "type": "text", "data": "{\"t\":\"MESSAGE_CREATE\",\"d\":{...}}" }] }
  ],
  "sse_endpoints": []
}
```

## StorageInventory

```json
{
  "local_storage_keys": { "theme": "string", "locale": "string" },
  "session_storage_keys": {},
  "indexed_dbs": [{ "name": "discord_db", "version": 1, "stores": [{ "name": "messages", "keyPath": "id", "indexes": ["channelId", "timestamp"] }] }],
  "cookie_names": ["__cf_bm", "__dcfduid", "locale"],
  "cache_storage_entries": ["https://discord.com/assets/"]
}
```

## BehavioralCorrelation

```json
{
  "action": "open_conversation",
  "passes": [
    { "action": "open_conversation", "pass_number": 1, "changed_handles": ["window.DiscordNative._stores.MessageStore", "window.DiscordNative._stores.SelectedChannelStore"], "network_delta": [...], "dom_mutations": [], "duration_ms": 1500 },
    { "action": "open_conversation", "pass_number": 2, "changed_handles": ["window.DiscordNative._stores.MessageStore", "window.DiscordNative._stores.SelectedChannelStore"], "network_delta": [...], "dom_mutations": [], "duration_ms": 1400 },
    { "action": "open_conversation", "pass_number": 3, "changed_handles": ["window.DiscordNative._stores.MessageStore", "window.DiscordNative._stores.SelectedChannelStore"], "network_delta": [...], "dom_mutations": [], "duration_ms": 1450 }
  ],
  "intersected_handles": ["window.DiscordNative._stores.MessageStore", "window.DiscordNative._stores.SelectedChannelStore"],
  "noise_floor_handles": ["window.performance", "window.scrollY"],
  "ranked_candidates": [
    { "handle": "window.DiscordNative._stores.MessageStore", "specificity": 1.0, "confidence": 0.95 },
    { "handle": "window.DiscordNative._stores.SelectedChannelStore", "specificity": 0.8, "confidence": 0.9 }
  ]
}
```

## DOMStructure

```json
{
  "stable_selectors": {
    "composer": { "css": "[data-slate-editor='true']", "fragility": "low", "last_verified": "2026-09-24", "description": "div" },
    "messageList": { "css": "[data-list-id='chat-messages']", "fragility": "low", "last_verified": "2026-09-24", "description": "div" }
  },
  "input_targets": [{ "selector": "[data-slate-editor='true']", "type": "div", "placeholder": "" }],
  "list_containers": [{ "selector": "div[data-list-id='chat-messages']", "tag": "div" }],
  "action_buttons": [{ "selector": "button[data-testid='send-button']", "text": "Send", "tag": "button" }]
}
```

## CapabilityProbeTrace

```json
{
  "capability": "getMessages",
  "steps": [{ "action": "navigate", "target": "conversation" }],
  "observed_binding": { "type": "internal-http", "method": "GET", "url_pattern": "/api/v9/channels/:id/messages" },
  "success": true,
  "error": null
}
```

## RedactionEntry

```json
{
  "path": "$.screens.scr_123.network.requests[0].headers.authorization",
  "reason": "secret field name: authorization",
  "original_type": "string"
}
```

## Diff (from previous version)

```json
{
  "changed": ["aggregated_runtime.module_registries[0].global_name", "behavioral_correlations[0].ranked_candidates[0].handle"],
  "added": ["screens.scr_new"],
  "removed": [],
  "summary": "Webpack chunk global renamed from webpackChunkdiscord_app to webpackChunkdiscord_app_v2; MessageStore handle path changed"
}
```