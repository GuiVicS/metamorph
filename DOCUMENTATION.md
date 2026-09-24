# Metamorph — Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [Product Requirements Summary](#product-requirements-summary)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Usage Guide](#usage-guide)
6. [CLI Reference](#cli-reference)
7. [Scanner Details](#scanner-details)
8. [Extension Development](#extension-development)
9. [Skill (Claude CLI)](#skill-claude-cli)
10. [Fixture Testbed](#fixture-testbed)
11. [Auth Barrier Detection](#auth-barrier-detection)
12. [Repair Flow](#repair-flow)
12. [Probe Validation](#probe-validation)
13. [Security Model](#security-model)
14. [Project Structure](#project-structure)
15. [Troubleshooting](#troubleshooting)

---

## Overview

**Metamorph** is an adaptive web connector engine that turns any web application into a programmable, normalized API — without official APIs, without per-site code, and without breaking every time the site ships an update.

### Core Insight
> **Don't generate code. Generate a recipe, and ship one runtime that can cook any recipe.**

Traditional approach: Site → Analyze → Generate code → Ship extension → Breaks → Human fixes
Metamorph: Site → Scan → Generate Dossier (JSON) → Skill generates Extension → Breaks → Machine re-scans → Re-generates

### Three-Layer Mental Model
```
┌──────────────────────────────────────────┐
│  LAYER 3 — KNOWLEDGE  (changes weekly)   │
│  Dossiers. Pure data. Regenerable.       │
├──────────────────────────────────────────┤
│  LAYER 2 — RUNTIME    (changes monthly)  │
│  Extension. Interpreter. Versioned code. │
├──────────────────────────────────────────┤
│  LAYER 1 — CONTRACT   (changes yearly)   │
│  Domain model. Adapter interface.        │
└──────────────────────────────────────────┘
```

### Design Principles
1. **Configuration over code generation** — Site knowledge lives in versioned JSON
2. **One runtime, infinite targets** — Single extension binary, never ships new code per platform
3. **Normalize at the boundary** — `Message`, `Conversation`, `Contact` never `IGThread` or `WAChat`
4. **Assume breakage; design for repair** — Health checking and regeneration are first-class
5. **Authorized sessions only** — Operates in user's existing authenticated browser session
6. **Behavior over names** — Module discovery infers identity from what changes, not symbol names
7. **Observable by default** — Every function call emits structured telemetry

---

## Product Requirements Summary

### Target Users
- **Integration Engineers** — Maintain browser automations, want to stop being paged
- **Platform Builders** — Need multi-channel (WhatsApp, Instagram, Discord) on day one
- **Internal Tools Teams** — Legacy apps with no API, no docs, no source access

### In Scope (MVP)
- Full-platform scanner (7 dimensions)
- Dossier generation with redaction
- Extension generation via Claude CLI skill
- Probe validation
- Diff-based repair
- 3 reference platforms (fixture + 2 variants)

### Out of Scope
- Firefox/Safari support
- Mobile app automation
- Credential entry/login automation
- Headless operation without user session
- Bulk automation/spam platforms

---

## Architecture

### System Components

```
┌──────────────┐
│   Operator   │
└──────┬───────┘
       │ browser
┌──────▼─────────────────────┐
│   Metamorph Console        │
│   (Next.js - future)       │
└──────┬─────────────────────┘
       │ HTTPS / WSS
┌──────▼─────────────────────┐
│   Metamorph Backend        │
│                            │
│  API · Scanner · Generator │
│  Repair · Registry         │
└──┬────────────┬────────────┘
   │            │
┌──▼─────┐  ┌───▼──────────┐
│Claude  │  │ Headless     │
│API     │  │ Chromium     │
└────────┘  └───┬──────────┘
                │
         ┌──────▼──────┐
         │ Target site │
         └─────────────┘

┌──────────────────────────┐
│  Operator's Chrome       │
│  ┌────────────────────┐  │
│  │ Metamorph Runtime  │◄─┼── WSS ── Backend
│  └─────────┬──────────┘  │
│            │             │
│  ┌─────────▼──────────┐  │
│  │ Target site (tab)  │  │
│  └────────────────────┘  │
└──────────────────────────┘
```

### Service Decomposition

| Service | Language | Responsibility |
|---------|----------|----------------|
| `scanner` | Python/Playwright | Scan execution (7 dimensions) |
| `generator` | TypeScript | Dossier → Extension (via skill) |
| `repair` | Python/Celery | Detection, re-scan, regeneration |
| `extension` | TypeScript/esbuild | MV3 runtime (bridge, worker, content) |
| `skill` | Markdown | Claude CLI instructions |

### Data Flow: Scan to Extension

```
Scan (Python)                    Generate (Skill)              Runtime (Extension)
─────────────────                ──────────────────             ───────────────────
1. Crawl all screens             1. Load dossier.json           1. Load fingerprint
2. 7 dimensions capture          2. Identify bindings           2. Build adapter
3. Behavioral correlation        3. Generate extension          3. Execute capabilities
4. Redaction                     4. Build MV3                   4. Emit telemetry
5. Save dossier.json             5. Run probes                  5. Hot-swap on update
```

---

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ (for extension build)
- Chrome/Chromium
- Playwright Chromium: `playwright install chromium`

### Install
```bash
git clone https://github.com/GuiVicS/metamorph.git
cd metamorph
pip install -e .[dev]
playwright install chromium
```

### Verify Install
```bash
metamorph --help
# Should show: scan, report, probe, repair, open, clear-profile
```

---

## Usage Guide

### Basic Flow

#### 1. Start Target (Fixture or Real Site)
```bash
# Local fixture (for testing)
python -m fixtures.testbed.server 8765

# Real site - log in first
metamorph open --profile meu_perfil --url https://app.exemplo.com
# Browser opens → you log in manually → close browser
```

#### 2. Run Scan
```bash
metamorph scan \
  --url http://localhost:8765 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --out ./dossier_test \
  --headless
```

**Parameters:**
| Flag | Required | Description |
|------|----------|-------------|
| `--url` | ✅ | Starting URL |
| `--goals` | ✅ | Comma-separated capabilities |
| `--profile` | ❌ | Browser profile (persistent session) |
| `--out` | ❌ | Output directory (default: `./dossier`) |
| `--headless` | ❌ | Headless mode (default: false) |
| `--max-screens` | ❌ | Max screens (default: 50) |
| `--max-depth` | ❌ | Crawl depth (default: 5) |

#### 3. View Report
```bash
metamorph report ./dossier_test/dossier.json
```

#### 4. Generate Extension (via Skill)
```bash
# Install skill (once)
ln -s $(pwd)/skills/metamorph-extgen ~/.claude/skills/metamorph-extgen

# In Claude CLI:
# "Use a skill metamorph-extgen para gerar uma extensão a partir do dossier em ./dossier_test/dossier.json"
# Creates: extensions/testbed/
```

#### 5. Build Extension
```bash
cd extensions/testbed
npm install
npx esbuild --config=esbuild.config.mjs
# Output: dist/
```

#### 6. Load in Chrome
1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select `extensions/testbed/dist/`

#### 7. Validate with Probes
```bash
metamorph probe \
  --ext ./extensions/testbed/dist \
  --dossier ./dossier_test/dossier.json \
  --goals getMessages,getConversations \
  --headless
```

#### 8. Repair After Site Changes
```bash
# Start variant (simulates site change)
python -m fixtures.testbed.variants.v2-renamed-store.server 8766

metamorph repair \
  --url http://localhost:8766 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --prev ./dossier_test/dossier.json \
  --out ./dossier_v2_repair \
  --headless

# Output shows diff: webpack chunks, handles, endpoints changed
# Re-generate extension from new dossier
```

---

## CLI Reference

### `metamorph scan`
Full-platform scan producing a dossier.
```bash
metamorph scan --url <URL> --goals <goals> [options]

Options:
  --url TEXT              Starting URL [required]
  --goals TEXT            Comma-separated capabilities [required]
  --profile TEXT          Browser profile name [default: default]
  --out PATH              Output directory [default: ./dossier]
  --max-screens INT       Max screens to crawl [default: 50]
  --max-depth INT         Max crawl depth [default: 5]
  --include PATTERN       Include URL patterns (regex)
  --exclude PATTERN       Exclude URL patterns (regex)
  --timeout INT           Navigation timeout ms [default: 30000]
  --settle INT            Settle time after navigation ms [default: 1500]
  --behavioral-passes INT Behavioral correlation passes [default: 3]
  --headless / --no-headless  Headless mode [default: false]
```

### `metamorph report`
Human-readable dossier summary.
```bash
metamorph report <dossier.json>
```

### `metamorph probe`
Validate generated extension against live site.
```bash
metamorph probe --ext <dir> --dossier <file> [options]

Options:
  --ext PATH              Extension dist directory [required]
  --dossier PATH          Dossier.json path [required]
  --goals TEXT            Comma-separated goals to test
  --consent               Allow write probes (requires --sandbox-target)
  --sandbox-target TEXT   Conversation ID for write probes
  --headless / --no-headless  Headless mode [default: true]
```

### `metamorph repair`
Re-scan with previous dossier context, compute diff.
```bash
metamorph repair --url <URL> --goals <goals> --prev <dossier.json> [options]

Options:
  --url TEXT              Starting URL [required]
  --goals TEXT            Capabilities to repair [required]
  --profile TEXT          Browser profile [default: default]
  --prev PATH             Previous dossier.json [required]
  --out PATH              Output directory [default: ./dossier]
  --headless / --no-headless  Headless mode [default: false]
```

### `metamorph open`
Open URL in browser profile for manual login/setup.
```bash
metamorph open --profile <name> --url <URL>
```

### `metamorph clear-profile`
Clear browser profile (removes cookies/storage).
```bash
metamorph clear-profile --profile <name>
```

---

## Scanner Details

### 7 Scan Dimensions

| Dimension | Captures |
|-----------|----------|
| **1. Static Surface** | Scripts, framework, bundler, build hash, module system |
| **2. Runtime Topology** | Non-baseline globals, module registries, state stores, event bus |
| **3. Network Catalogue** | All requests (method, URL pattern, shapes), GraphQL ops, WebSocket, SSE |
| **4. Storage Inventory** | localStorage/sessionStorage keys, IndexedDB, cookie names (no values) |
| **5. Behavioral Correlation** | Drive app, record what changes (stores, network, DOM, events) — 3 passes + noise floor |
| **6. DOM Structure** | Stable selectors (`data-testid`, `aria-*`, `role`), inputs, lists, buttons |
| **7. Capability Probing** | Attempt to observe/execute each requested goal, capture full trace |

### Crawler
- Multi-screen crawl with navigation graph
- URL normalization (removes volatile params/IDs)
- DOM signature hashing for screen deduplication
- Screen graph: nodes = screens, edges = actions (clicks, tabs, navigation)

### Behavioral Correlation Algorithm
```
BASELINE → capture full runtime state hash
ACTION   → "open a conversation"
DELTA    → which stores mutated, which requests fired, DOM changes, events emitted
REPEAT   → 3× to eliminate noise
CORRELATE → stores mutating on EXACTLY this action are candidates
CONTROL  → no-op action establishes noise floor
```

### Redaction (Fail-Closed)
**Removes before persistence:**
- All cookie values
- Authorization, Cookie, X-CSRF-*, X-Auth-* headers
- Token heuristics (JWT, ≥32-char hex/base64 in `*token*`, `*key*`, `*secret*`, `*session*`)
- Message bodies, contact PII → shapes retained, values replaced with type placeholders

**Verification:** Automated scanner over output + adversarial test suite. Scan fails closed if any secret leaks.

---

## Extension Development

### MV3 Extension Structure
```
extensions/<site-slug>/
├── manifest.json              # MV3, optional host permissions
├── worker.js                  # Service worker (bundled)
├── content.js                 # Content script (ISOLATED world)
├── bridge.js                  # MAIN world bridge (injected)
├── popup.html / popup.js      # Status UI
├── config/origins.json        # Platform origins
└── probes.json                # Validation probes
```

### Bridge (MAIN World) — `bridge.js`
- Injected into page's own JS context
- **Structural path resolution** — no eval, no Function constructor
- Forbidden segments: `__proto__`, `constructor`, `prototype`
- Discovery strategies: webpack-chunk-injection, window-path
- Handle resolution by **shape matching** (`hasKeys`, `hasMethods`)
- Interceptors: fetch, WebSocket, function wrapping
- Communicates via `postMessage` to ISOLATED world

### Content Script (ISOLATED World) — `content.js`
- Chrome runtime port to service worker
- `postMessage` bridge to MAIN world
- DOM actor for `dom-action` bindings
- MutationObserver for selector verification

### Service Worker — `worker.js`
- `FingerprintStore` — IndexedDB (versioned, keeps previous for rollback)
- `AdapterEngine` — Builds `ChannelAdapter` from fingerprint
- `BindingExecutor` — Executes: `internal-http`, `runtime-call`, `runtime-read`, `dom-action`
- `Normalizer` — Closed transform set
- `EventBus` — 60s dedupe window
- `HealthMonitor` — Probe runner, telemetry queue
- `Transport` — WebSocket to backend (ack/reconnect)

### Binding Types (Priority Order)
1. **internal-http** — fetch to app's own API (same-origin credentials)
2. **runtime-call** — Invoke method on discovered store
3. **runtime-read** — Read property from store
4. **graphql** — POST known operation to GraphQL endpoint
5. **function-intercept** — Wrap function for events
6. **network-intercept** — Observe fetch/XHR/WS for events
7. **dom-action** — Click/type/submit (fragile, last resort)
8. **dom-read** — Read text/attributes (fragile)

### Normalizer — Closed Transform Set
| Transform | Signature |
|-----------|-----------|
| `identity` | `(v) => v` |
| `toString` | `(v) => String(v)` |
| `toNumber` | `(v) => Number(v)` |
| `toBoolean` | `(v) => Boolean(v)` |
| `iso8601ToEpochMs` | `(v) => Date.parse(v)` |
| `epochSecToEpochMs` | `(v) => v * 1000` |
| `snowflakeToEpochMs` | `(v) => Number(BigInt(v) >> 22n) + 1420070400000` |
| `mapEach` | `(arr, entity) => arr.map(mapEntity)` |
| `pick` | `(obj, keys) => subset` |
| `coalesce` | `(...vals) => first non-null` |
| `constant` | `() => literal` |
| `enumMap` | `(v, table) => table[v] ?? fallback` |

---

## Skill (Claude CLI)

### Location
```
skills/metamorph-extgen/
├── SKILL.md              # Main instructions
├── templates/extension/  # MV3 template
└── references/
    ├── dossier-schema.md
    ├── binding-preferences.md
    └── redlines.md
```

### Install
```bash
ln -s $(pwd)/skills/metamorph-extgen ~/.claude/skills/metamorph-extgen
```

### Usage
```bash
# In Claude CLI:
"Use a skill metamorph-extgen para gerar uma extensão a partir do dossier em ./dossier_test/dossier.json"
```

### Skill Workflow
1. **Load dossier** — Read `dossier.json` + relevant screens
2. **Identify bindings** — For each goal, find best binding (priority: internal-http > runtime-call > intercept > DOM)
3. **Generate extension** — Fill template placeholders, write `extensions/<slug>/`
4. **Build** — `npx esbuild --config=esbuild.config.mjs`
5. **Validate** — Run probes via `metamorph probe`

### Binding Selection Rules
- **Evidence required** — Every binding must be justified by dossier evidence
- **Shape matching** — Modules by exported keys, never numeric IDs
- **Closed transforms** — Only the 12 transforms above
- **Honest gaps** — No binding found → `supported: false` with reason
- **Probes mandatory** — Every `supported: true` capability needs passing probe

### Redlines (Non-Negotiable)
- **NO EVAL** — No `eval`, `new Function`, `innerHTML` with user data
- **NO CREDENTIALS** — Extension never reads cookies/tokens
- **SHAPE MATCHING ONLY** — No numeric module IDs
- **CLOSED TRANSFORMS** — Only the 12 defined transforms
- **MINIMAL PERMISSIONS** — `optional_host_permissions` only
- **FORBIDDEN PATH SEGMENTS** — `__proto__`, `constructor`, `prototype` rejected at load

---

## Fixture Testbed

### Baseline (`fixtures/testbed/`)
Messaging SPA with:
- 4 conversations (Direct, Groups, Channels tabs)
- Stores: `MessageStore`, `ChannelStore`, `CurrentUserStore`, `ConnectionStore`, `WebSocketManager`
- Webpack-like registration: `window.webpackChunktestbed_app`
- Internal API: `TestbedAPI.getConversations()`, `getMessages()`, `sendMessage()`, `markAsRead()`
- WS simulation: `MESSAGE_CREATE` events

### Variants
| Variant | Change | Tests |
|---------|--------|-------|
| **v2-renamed-store** | Chunk global `webpackChunktestbed_app_v2`, exports renamed (`getMessageRepository`), methods renamed (`fetchMessages`) | Shape matching works despite renames |
| **v3-moved-endpoint** | Chunk global `webpackChunktestbed_app_v3`, API switched to GraphQL `/graphql` | internal-http → graphql binding switch |

### Run Fixtures
```bash
# Baseline
python -m fixtures.testbed.server 8765

# Variant v2
python -m fixtures.testbed.variants.v2-renamed-store.server 8766

# Variant v3
python -m fixtures.testbed.variants.v3-moved-endpoint.server 8767
```

### Test Repair Flow
```bash
# 1. Scan baseline
metamorph scan --url http://localhost:8765 --goals getMessages,sendMessage,getConversations --profile testbed --out ./dossier_base --headless

# 2. Switch to v2, repair
python -m fixtures.testbed.variants.v2-renamed-store.server 8766
metamorph repair --url http://localhost:8766 --goals getMessages,sendMessage,getConversations --profile testbed --prev ./dossier_base/dossier.json --out ./dossier_v2 --headless
# Diff shows: webpack chunk global changed, handles renamed

# 3. Re-generate extension from new dossier
```

---

## Auth Barrier Detection

The scanner detects and records authentication barriers per screen.

### Detected Barriers

| Barrier | Detection Method |
|---------|------------------|
| **Login Page** | email + password inputs, form action="login", text "entrar/acessar/login" |
| **CAPTCHA** | reCAPTCHA (`.g-recaptcha`, `[data-sitekey]`), hCaptcha, Cloudflare, Turnstile, generic |
| **2FA** | `autocomplete=one-time-code`, 6-digit maxlength inputs, "autenticator/google auth" text |
| **Email Verification** | "verifique email", "confirme email", "check inbox" |
| **Phone/SMS** | "verifique telefone", "código SMS", "sms code" |
| **Access Denied** | "acesso negado", "access denied", "rate limit", "muitas tentativas" |
| **Cloudflare** | "Just a moment", "Checking your browser", `#challenge-running` |

### Behavior
- **Login page** → Crawl stops, screen not created
- **Other barriers** → Screen created with `auth_barrier` dict populated
- **Field in Screen**: `auth_barrier: {"isLoginPage": false, "hasCaptcha": true, "has2FA": false, ...}`

### Integration
```python
# In _visit_screen():
auth_barrier = await self._detect_auth_barrier(page)
if auth_barrier.get("isLoginPage"):
    return None  # Stop crawl
# ... create screen with auth_barrier
```

---

## Repair Flow

### Trigger
- Probe failures from deployed extensions
- Scheduled health checks
- Manual trigger via CLI

### Process
```
1. DETECT     → Error spike (distinct instances, error rate, window)
2. RE-SCAN    → Scan with previous_dossier attached
3. DIFF       → Compute structural diff (changed/added/removed paths)
4. REGENERATE → Skill generates new extension (diff-oriented prompt)
5. VALIDATE   → Run probes (read-only; write probes skipped unattended)
6. GATE       → 7 conditions (no regression, grade maintained, ≤3 blocks changed, etc.)
7. ROLLOUT    → Staged: 1 instance → 10% → 50% → 100% (auto-rollback on failure)
```

### Promotion Gate (All Required)
| Gate | Condition |
|------|-----------|
| G1 | Schema valid |
| G2 | No previously-supported capability became unsupported |
| G3 | Overall grade ≥ previous grade |
| G4 | All runnable probes pass |
| G5 | Diff touches ≤ 3 top-level blocks |
| G6 | No new DOM binding for previously non-DOM capability |
| G7 | Overall confidence ≥ previous - 5 |

### CLI
```bash
metamorph repair \
  --url http://localhost:8766 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --prev ./dossier_base/dossier.json \
  --out ./dossier_v2 \
  --headless
```

### Diff Output
```json
{
  "changed": ["scan_id", "nav_graph.entry_screen_id", "aggregated_runtime.module_registries[0].global_name"],
  "added": ["nav_graph.nodes.scr_xxx", "screens.scr_xxx"],
  "removed": ["screens.scr_yyy"],
  "summary": "4 changed; 2 added; 1 removed"
}
```

---

## Probe Validation

### Probe Types
| Type | Runs When | Consent |
|------|-----------|---------|
| **Read** | Generation, Health, Repair | No |
| **Write** | Generation only | Yes (`--consent --sandbox-target`) |

### Probe Format
```json
{
  "id": "probe.getMessages",
  "capability": "getMessages",
  "steps": [{"invoke": "getMessages", "args": {"conversationId": "conv_1"}}],
  "assert": [
    {"path": ["items"], "type": "array", "minLength": 1},
    {"path": ["items", 0, "externalId"], "type": "string", "nonEmpty": true}
  ],
  "sideEffects": "none",
  "runOn": ["generation", "health", "repair"]
}
```

### Assertion Types
- `equals` — Exact match (supports `{{probeToken}}` template)
- `nonEmpty` — String/array/object not empty
- `type` — `string`, `array`, `number`, `object`
- `minLength` — Array/string minimum length

### CLI
```bash
# Read probes
metamorph probe --ext ./extensions/testbed/dist --dossier ./dossier_test/dossier.json --goals getMessages,getConversations --headless

# Write probes (requires consent + sandbox)
metamorph probe --ext ./extensions/testbed/dist --dossier ./dossier_test/dossier.json --goals sendMessage --consent --sandbox-target "conv_1" --headless
```

---

## Security Model

### Threat Mitigations

| Threat | Vector | Mitigation |
|--------|--------|------------|
| Malicious Fingerprint executes code | Compromised registry/MITM | No eval anywhere; closed binding types; closed transforms; structural path resolution |
| Prototype pollution | `__proto__` in path | Forbidden segments rejected at load |
| Credential exfiltration | Binding reads cookies/storage | No binding reads cookies/headers; enforced at schema |
| Secrets in snapshot | Scanner captures tokens | Mandatory redaction, fail-closed verifier |
| Over-broad permissions | `<all_urls>` at install | Optional host permissions, requested per platform |
| Unauthorized accounts | Misuse | Operates only in existing user sessions |
| Backend compromise | Malicious fingerprint push | Schema validation client-side, probe-before-trust, staged rollout |

### No-Eval Guarantee
> **No string from a Fingerprint is ever passed to `eval`, `new Function`, `setTimeout(string)`, `document.write`, `innerHTML`, or any string-to-code sink.**

Enforced by:
1. Schema — bindings are typed objects, not expressions
2. Transforms — closed set, implemented in runtime source
3. Paths — arrays of strings, resolved by property access with forbidden-segment denylist
4. CSP — `script-src 'self'`, no `unsafe-eval`
5. CI — lint rule fails build on dynamic-code sinks

### Data Handling

| Data Class | Collected | Stored | Transmitted |
|------------|-----------|--------|-------------|
| Credentials, cookies, tokens | **Never** | **Never** | **Never** |
| Message content | Read at runtime | **Never persisted** | Only to operator's destination |
| Contact PII | Read at runtime | **Never persisted** | Only to operator's destination |
| Site structure (shapes, paths) | Yes | Yes (Dossier) | Yes |
| Telemetry metadata | Yes | Yes | Yes |
| Snapshots | Yes, redacted | 30 days, S3 | Backend only |

### Compliance
- SEC-1: Redaction verifier runs before persistence; failure discards snapshot
- SEC-2: Fingerprint signing (Ed25519) — Phase 2
- SEC-3: Per-org isolation on all reads
- SEC-4: Audit log for promote, deprecate, rollback, force-promote, manual repair
- SEC-5: Annual external security review before public release
- SEC-6: Documented ToS acceptance flow before first scan

---

## Project Structure

```
metamorph/
├── pyproject.toml              # Python package config
├── README.md                   # Quick start guide
├── DOCUMENTATION.md            # This file
├── MEMORY.md                   # Development memory (for AI continuity)
├── scanner/                    # Python scanner package
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── types.py           # Dossier, Screen, NavGraph, etc.
│   │   └── baseline.py        # 1000+ standard browser globals
│   ├── crawl/
│   │   ├── __init__.py
│   │   └── crawler.py         # Multi-screen crawler + nav graph
│   ├── dimensions/
│   │   ├── __init__.py
│   │   └── network_storage.py # Network + storage capture
│   ├── redaction/
│   │   ├── __init__.py
│   │   └── engine.py          # Redaction + verifier
│   ├── probe/
│   │   ├── __init__.py
│   │   └── runner.py          # Probe runner (Playwright)
│   ├── repair/
│   │   ├── __init__.py
│   │   ├── diff.py            # Dossier diff utility
│   │   └── engine.py          # Repair engine
│   └── cli/
│       ├── __init__.py
│       └── main.py            # Click CLI (scan, report, probe, repair, open, clear-profile)
├── fixtures/
│   └── testbed/
│       ├── public/index.html
│       ├── src/stores.js, main.js
│       ├── server.py          # aiohttp static server
│       └── variants/
│           ├── v2-renamed-store/
│           └── v3-moved-endpoint/
├── skills/
│   └── metamorph-extgen/
│       ├── SKILL.md
│       ├── templates/extension/
│       │   ├── manifest.json
│       │   ├── esbuild.config.mjs
│       │   ├── config/origins.json
│       │   └── src/
│       │       ├── main-world/bridge.js
│       │       ├── content/content.js
│       │       ├── worker/
│       │       │   ├── worker.js
│       │       │   ├── fingerprint-store.js
│       │       │   ├── adapter-engine.js
│       │       │   ├── binding-executor.js
│       │       │   ├── normalizer.js
│       │       │   ├── event-bus.js
│       │       │   ├── health.js
│       │       │   └── transport.js
│       │       └── popup/popup.html, popup.js
│       └── references/
│           ├── dossier-schema.md
│           ├── binding-preferences.md
│           └── redlines.md
└── templates/                  # Reserved for future
```

---

## Troubleshooting

### Common Issues

#### "SyntaxError: Unexpected token ']'" in DOM capture
**Cause:** Regex in bridge/selector key sanitization
**Fix:** Already fixed in `scanner/crawl/crawler.py` — uses character iteration instead of regex

#### "UnicodeEncodeError: 'charmap' codec can't encode"
**Cause:** Rich Progress bar on Windows cp1252
**Fix:** Replaced Progress bars with simple `console.print()` in CLI

#### "ModuleNotFoundError: scanner.cli.crawler"
**Cause:** Relative imports in CLI
**Fix:** Use `from ..crawl.crawler import ...` not `from .crawler import ...`

#### StorageCapture "await is only valid in async functions"
**Cause:** IIFE not async for IndexedDB
**Fix:** Changed to `async () => { ... }` in `network_storage.py`

#### Repair: "output_dir.mkdir() AttributeError"
**Cause:** Click `Path` type not applied to `--out`
**Fix:** Added `type=click.Path(path_type=Path)` to `--out` option

#### Repair: "DossierDiff has no attribute to_dict"
**Cause:** Missing method
**Fix:** Added `to_dict()` to `DossierDiff` class

#### "Cannot read properties of undefined (reading 'meta')" on visit
**Cause:** Page.evaluate error in runtime topology capture
**Fix:** Added try/except around each capture; continues on failure

### Windows-Specific Notes
- Use `python -m module` not `python module.py`
- Rich Progress bars cause encoding issues → use simple prints
- PowerShell doesn't support `&&` — use separate commands or `;`
- Background processes: `start /b python ...` or background shell

### Debug Tips
```bash
# Run with verbose output
python -m scanner.cli.main scan --url ... --headless 2>&1

# Check dossier structure
python -c "import json; d=json.load(open('dossier.json')); print(json.dumps(d['aggregated_runtime'], indent=2))"

# Test auth barrier detection
python test_auth.py

# Test fixture directly
python -c "
import asyncio
from playwright.async_api import async_playwright
async def t():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto('http://localhost:8765', wait_until='networkidle')
        print(await pg.evaluate('() => Object.keys(window).filter(k=>k.includes(\"testbed\"))'))
        await b.close()
asyncio.run(t())
"
```

---

## License

MIT License — See LICENSE file.

---

## Links

- **Repository:** https://github.com/GuiVicS/metamorph
- **Issues:** https://github.com/GuiVicS/metamorph/issues
- **PRD (original):** `metamorph_prd_massive.md` (in Downloads)

---

*Last updated: 2026-09-24*