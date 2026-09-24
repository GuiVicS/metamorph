---
name: metamorph-extgen
description: Generate a Manifest V3 Chrome extension from a Metamorph dossier.json
version: 0.1.0
author: Metamorph Team
---

# Metamorph Extension Generator Skill

This skill guides you through generating a complete, installable Chrome MV3 extension from a Metamorph scanner dossier.

## When to Use

- You have run `metamorph scan` and have a `dossier.json` output
- You want to create a working extension for a specific platform
- You need to regenerate an extension after a site change (repair flow)

## Prerequisites

- A dossier directory at `dossier/<site-slug>/` containing:
  - `dossier.json` - the full scan dossier
  - `screens/*.json` - per-screen details
  - `redaction-report.json` - redaction audit
- Node.js 18+ and npm/pnpm for building the extension

## Workflow

### 1. Load the Dossier

```bash
# First, examine the dossier structure
cat dossier/<site-slug>/dossier.json | jq '.'
```

Key sections to review:
- `nav_graph.nodes` - discovered screens and their signatures
- `aggregated_runtime.module_registries` - webpack/Vite module systems detected
- `aggregated_runtime.state_stores` - candidate stores (Redux, Zustand, custom)
- `aggregated_network.requests` - API endpoints with shapes
- `behavioral_correlations` - handles correlated to actions
- `capability_traces` - observed bindings for requested goals

### 2. Identify Capability Bindings

For EACH requested goal, find the BEST binding in this priority order:

1. **internal-http** - Direct fetch to the app's own API (most stable)
   - Look in `aggregated_network.requests` for matching URL patterns
   - Check request/response shapes match the capability
   - Prefer REST endpoints with clear URL templates

2. **runtime-call** - Invoke a function on a discovered store
   - Look in `aggregated_runtime.state_stores` for stores with matching methods
   - Use `behavioral_correlations` to confirm which handle responds to the action
   - Match by SHAPE (exported keys), never by module ID

3. **function-intercept** / **network-intercept** - For events only
   - WebSocket messages: check `aggregated_network.websocket_endpoints`
   - Function calls: check `behavioral_correlations` for emitting functions

4. **dom-action** / **dom-read** - LAST RESORT, mark `fragile: true`
   - Use only stable selectors from `screens/*.dom.stable_selectors`
   - Must have `data-testid`, `role`, `aria-*` attributes

### 3. Generate the Extension

Run the generator template with the identified bindings:

```bash
# From the skills/metamorph-extgen/templates/extension directory
# The generator will create: extensions/<site-slug>/
```

**You must provide these values for the template:**

| Placeholder | Source |
|-------------|--------|
| `__EXTENSION_NAME__` | `"Metamorph: " + platform.displayName` |
| `__EXTENSION_DESCRIPTION__` | `"Metamorph connector for " + platform.displayName` |
| `__PLATFORM_SLUG__` | `dossier.site_slug` |
| `__PLATFORM_DISPLAY_NAME__` | `dossier.platform.displayName` |
| `__ORIGINS__` | `dossier.platform.origins` (JSON array) |
| `__MATCH_PATTERNS__` | `dossier.platform.matchPatterns` (JSON array) |
| `__DISCOVERY_CONFIG__` | From `aggregated_runtime.module_registries` → discovery array |
| `__HANDLES_CONFIG__` | From `behavioral_correlations` + `state_stores` → handles map |
| `__READY_CHECK_CONFIG__` | From `readyCheck` in dossier or default poll |
| `__OPTIONAL_HOST_PERMISSIONS__` | `dossier.platform.origins` |
| `__CONTENT_SCRIPT_MATCHES__` | `dossier.platform.matchPatterns` |
| `__BRIDGE_MATCHES__` | `dossier.platform.origins` |

### 4. Discovery Config Examples

**Webpack (chunk injection):**
```json
{
  "id": "webpack",
  "strategy": "webpack-chunk-injection",
  "chunkGlobal": "webpackChunkdiscord_app",
  "priority": 1
}
```

**Window path:**
```json
{
  "id": "global-store",
  "strategy": "window-path",
  "path": ["window", "DiscordNative", "_stores"],
  "priority": 2
}
```

### 5. Handles Config Examples

```json
{
  "messageStore": {
    "via": "webpack",
    "moduleMatch": { "hasKeys": ["getMessages", "getMessage"], "hasMethods": ["getMessages"] }
  },
  "channelStore": {
    "via": "webpack",
    "moduleMatch": { "hasKeys": ["getChannel", "getDMFromUserId"] }
  }
}
```

### 6. Capability Binding Examples

**internal-http (getMessages):**
```json
{
  "type": "internal-http",
  "method": "GET",
  "urlTemplate": "/api/v9/channels/{conversationId}/messages",
  "credentials": "same-origin",
  "query": {
    "limit": { "from": "param:limit", "default": 50 },
    "before": { "from": "param:cursor", "optional": true }
  }
}
```

**runtime-call (getCurrentUser):**
```json
{
  "type": "runtime-call",
  "handle": "currentUserStore",
  "method": "getCurrentUser",
  "args": []
}
```

**internal-http (sendMessage):**
```json
{
  "type": "internal-http",
  "method": "POST",
  "urlTemplate": "/api/v9/channels/{conversationId}/messages",
  "credentials": "same-origin",
  "headers": { "content-type": "application/json" },
  "body": {
    "content": { "from": "param:text" },
    "nonce": { "transform": "generateNonce" }
  }
}
```

### 7. Event Binding Examples

**WebSocket (message.received):**
```json
{
  "type": "network-intercept",
  "channel": "websocket",
  "match": { "path": ["t"], "equals": "MESSAGE_CREATE" },
  "payloadPath": ["d"]
}
```

**runtime-subscribe (connection.changed):**
```json
{
  "type": "runtime-subscribe",
  "handle": "connectionStore",
  "subscribeMethod": "addChangeListener",
  "unsubscribeMethod": "removeChangeListener",
  "readMethod": "isConnected"
}
```

### 8. Entity Mapping (Normalizer)

Use ONLY these transforms (CLOSED SET):

| Transform | Use Case |
|-----------|----------|
| `identity` | Pass through |
| `toString` | ID fields |
| `toNumber` | Numeric fields |
| `iso8601ToEpochMs` | ISO timestamps → epoch ms |
| `epochSecToEpochMs` | Unix seconds → epoch ms |
| `snowflakeToEpochMs` | Discord snowflake → epoch ms |
| `mapEach` | Array of entities |
| `pick` | Subset of object keys |
| `coalesce` | First non-null |
| `constant` | Static value |
| `enumMap` | Map enum values |

Example Message mapping:
```json
{
  "externalId": { "from": "id" },
  "conversationId": { "from": "channel_id" },
  "senderId": { "from": "author.id" },
  "text": { "from": "content" },
  "timestamp": { "from": "id", "transform": "snowflakeToEpochMs" },
  "editedAt": { "from": "edited_timestamp", "transform": "iso8601ToEpochMs", "nullable": true },
  "attachments": { "from": "attachments", "transform": "mapEach", "entity": "Attachment" }
}
```

### 9. Probes (Validation)

Generate probes for EACH supported capability:

**Read probe (always runs):**
```json
{
  "id": "probe.getConversations",
  "capability": "getConversations",
  "steps": [{ "invoke": "getConversations" }],
  "assert": [
    { "path": ["items"], "type": "array", "minLength": 1 },
    { "path": ["items", 0, "externalId"], "type": "string", "nonEmpty": true }
  ],
  "sideEffects": "none",
  "runOn": ["generation", "health", "repair"]
}
```

**Write probe (requires consent):**
```json
{
  "id": "probe.sendMessage",
  "capability": "sendMessage",
  "steps": [{
    "invoke": "sendMessage",
    "args": { "conversationId": "{{probeConversationId}}", "text": "{{probeToken}}" }
  }],
  "assert": [
    { "path": ["externalId"], "type": "string", "nonEmpty": true },
    { "path": ["text"], "equals": "{{probeToken}}" }
  ],
  "sideEffects": "writes",
  "requiresConsent": true,
  "runOn": ["generation"]
}
```

### 10. Build and Test

```bash
cd extensions/<site-slug>
npm install
npm run build  # runs esbuild

# Load in Chrome:
# 1. chrome://extensions → Developer mode
# 2. Load unpacked → select extensions/<site-slug>/dist
```

### 11. Validate with Probes

```bash
# Run read probes against live site
metamorph probe --ext extensions/<site-slug> --goals getMessages,getConversations

# For write probes, specify consent target
metamorph probe --ext extensions/<site-slug> --goals sendMessage --consent --sandbox-target "test-channel-id"
```

## Redlines (MUST NOT VIOLATE)

1. **NO EVAL** - Never use `eval`, `new Function`, `setTimeout(string)`, `innerHTML` with user data
2. **NO CREDENTIALS** - Extension never reads/writes cookies, tokens, auth headers
3. **SHAPE MATCHING ONLY** - Identify modules by exported keys, never by numeric IDs
4. **CLOSED TRANSFORMS** - Only use transforms from the defined set
5. **MINIMAL PERMISSIONS** - Host permissions only for the platform's origins
6. **HONEST GAPS** - If no binding found, mark `supported: false` with reason

## Repair Flow

When a site breaks:

1. Re-scan: `metamorph scan --url <url> --goals <failed> --prev dossier/<slug>/`
2. Review `diff-from-<v>.json` - shows exactly what changed
3. Re-run this skill with the diff context: "Only fix the broken bindings, keep everything else"
4. Rebuild and validate

## Output Structure

```
extensions/<site-slug>/
├── manifest.json
├── worker.js          # Bundled service worker
├── content.js         # Content script
├── bridge.js          # MAIN world bridge
├── popup.html
├── popup.js
├── config/
│   └── origins.json
└── probes.json        # Validation probes
```

## References

- `references/dossier-schema.md` - Full dossier JSON structure
- `references/binding-preferences.md` - Binding selection guide
- `references/redlines.md` - Security redlines
- `templates/extension/` - Extension template source