# Binding Preferences Reference

Guide for selecting the correct binding type for each capability.

## Priority Order

**Always prefer higher-priority bindings.** Only fall back when evidence is insufficient.

| Priority | Binding | Stability | Use When |
|----------|---------|-----------|----------|
| 1 | `internal-http` | ★★★★★ | App has a clear internal REST/GraphQL API; endpoints visible in network tab with stable URL patterns |
| 2 | `runtime-call` | ★★★★☆ | A store/module with the needed method is discoverable by shape; behavioral correlation confirms it |
| 3 | `function-intercept` | ★★★☆☆ | Events only; need to observe function calls (e.g., store.emit) |
| 4 | `network-intercept` | ★★★☆☆ | Events only; WebSocket/SSE/Fetch traffic carries the events |
| 5 | `dom-action` | ★★☆☆☆ | **Last resort**; no internal API accessible; only for write operations |
| 6 | `dom-read` | ★★☆☆☆ | **Last resort**; only for reading visible text when no store exposes it |

## Decision Flowchart

```
CAPABILITY NEEDED
       │
       ▼
Is there a NETWORK REQUEST that does this?
       │
       ├─ YES → Does it have stable URL pattern + same-origin auth?
       │         │
       │         ├─ YES → USE internal-http
       │         └─ NO  → Check next
       │
       ▼
Is there a STORE MODULE with the method?
       │
       ├─ YES → Does behavioral correlation confirm this handle?
       │         │
       │         ├─ YES → USE runtime-call (read) or runtime-call (write)
       │         └─ NO  → Check next
       │
       ▼
Is this an EVENT (subscribe)?
       │
       ├─ YES → WebSocket/SSE with identifiable frames?
       │         ├─ YES → USE network-intercept
       │         └─ NO  → Function emitter on store?
       │                  ├─ YES → USE function-intercept
       │                  └─ NO  → Check next
       │
       ▼
Is DOM the ONLY option?
       │
       ├─ YES → Stable selectors exist (data-testid, role, aria)?
       │         ├─ YES → USE dom-action (write) / dom-read (read) + MARK FRAGILE
       │         └─ NO  → UNSUPPORTED - document limitation
       │
       ▼
UNSUPPORTED - No binding found
```

## Binding Specifications

### internal-http

**Best for:** `getConversations`, `getMessages`, `sendMessage`, `markAsRead`, `getCurrentUser` (if API exists)

```json
{
  "type": "internal-http",
  "method": "GET|POST|PUT|DELETE|PATCH",
  "urlTemplate": "/api/v9/channels/{conversationId}/messages",
  "credentials": "same-origin",
  "headers": { "content-type": "application/json" },
  "query": {
    "limit": { "from": "param:limit", "default": 50 },
    "before": { "from": "param:cursor", "optional": true }
  },
  "body": {
    "content": { "from": "param:text" },
    "nonce": { "transform": "generateNonce" }
  }
}
```

**Evidence required:**
- Network request observed in `aggregated_network.requests`
- URL pattern stable (IDs replaced with `:param`)
- Request/response shapes documented
- Same-origin credentials work (cookies sent automatically)

### runtime-call

**Best for:** `getCurrentUser`, `getMessages` (from store), `createConversation`, store mutations

```json
{
  "type": "runtime-call",
  "handle": "messageStore",
  "method": "getMessages",
  "args": [{ "from": "param:conversationId" }],
  "resultPath": ["_array"]
}
```

**Evidence required:**
- Handle resolved in `handles` config (shape-matched)
- Method exists on handle (`typeof handle.method === 'function'`)
- Behavioral correlation shows handle mutates on this action
- Args serializable

### runtime-read

**Best for:** `getCurrentUser` (if property), reading config/state

```json
{
  "type": "runtime-read",
  "handle": "currentUserStore",
  "path": ["currentUser", "id"]
}
```

### graphql

**Best for:** Apps using GraphQL internally (Discord, GitHub, Linear, etc.)

```json
{
  "type": "graphql",
  "urlTemplate": "/graphql",
  "query": "query GetMessages($channelId: ID!) { messages(channelId: $channelId) { id content author { id } timestamp } }",
  "variables": { "channelId": { "from": "param:conversationId" } },
  "resultPath": ["data", "messages"]
}
```

**Evidence required:**
- GraphQL endpoint in network catalogue (`is_graphql: true`)
- Operation name and document hash captured
- Variables map cleanly to capability params

### function-intercept

**Best for:** Event observation only (`message.received`, `typing.start`)

```json
{
  "type": "function-intercept",
  "targetPath": ["window", "DiscordNative", "EventEmitter"],
  "methodName": "emit",
  "filter": { "argIndex": 0, "equals": "MESSAGE_CREATE" }
}
```

### network-intercept

**Best for:** WebSocket/SSE events

```json
{
  "type": "network-intercept",
  "channel": "websocket",
  "match": { "path": ["t"], "equals": "MESSAGE_CREATE" },
  "payloadPath": ["d"]
}
```

### dom-action

**Only when:** No internal API, no store method, write operation required

```json
{
  "type": "dom-action",
  "selector": "[data-testid='send-button']",
  "action": "click",
  "valueParam": "text",
  "waitFor": 500
}
```

**Requirements:**
- Selector from `stable_selectors` (data-testid, role, aria-label)
- `fragility: "high"` in capability
- Documented in `limitations` block
- Probe requires explicit consent

### dom-read

**Only when:** No internal API exposes the data

```json
{
  "type": "dom-read",
  "selector": "[data-testid='unread-count']",
  "attribute": "textContent",
  "transform": "toNumber"
}
```

## Capability-Specific Guidance

| Capability | Preferred Binding | Fallback | Notes |
|------------|-------------------|----------|-------|
| `getCurrentUser` | runtime-read (store) | internal-http | Often in currentUserStore |
| `getConversations` | internal-http | runtime-call (channelStore.list) | Usually REST endpoint |
| `getMessages` | internal-http (paginated) | runtime-call (messageStore.get) | Prefer HTTP for pagination |
| `sendMessage` | internal-http | runtime-call (messageStore.send) | HTTP more reliable |
| `markAsRead` | internal-http | runtime-call | Often simple POST |
| `message.received` | network-intercept (WS) | function-intercept | WebSocket most common |
| `connection.changed` | runtime-subscribe | network-intercept | Store usually has listener |

## Anti-Patterns to Avoid

1. **Using module IDs** - `require(12345)` - IDs change every build
2. **Guessing paths** - `window.foo.bar.baz` without evidence
3. **DOM for reads when store exists** - If `messageStore.getMessages` works, don't scrape DOM
4. **Hardcoding URLs** - Always use `urlTemplate` with params
5. **Skipping behavioral correlation** - It's the proof the handle is correct
6. **Using `dom-action` for reads** - Use `dom-read` instead (or better, find internal API)

## Fragility Marking

Any capability using `dom-action` or `dom-read` MUST have:
```json
"fragility": "high",
"limitations": [{
  "code": "DOM_BINDING",
  "capability": "sendMessage",
  "severity": "high",
  "description": "Uses DOM fallback; breaks on UI changes",
  "workaround": "Migrate to internal-http when API discovered"
}]
```