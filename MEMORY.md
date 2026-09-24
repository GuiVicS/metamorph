# METAMORPH - Development Memory

## Current State: Phase 1 Complete (Scanner Foundation + Fixture Testbed)

### What's Done ✅

**Scanner Package (`scanner/`)**
- Core types: `Dossier`, `Screen`, `NavGraph`, `NavEdge`, `StaticSurface`, `RuntimeTopology`, `NetworkCatalogue`, `StorageInventory`, `DOMStructure`, `BehavioralCorrelation`, `CapabilityProbeTrace`, `Selector`, `RedactionEntry`
- Browser baseline: 1000+ standard globals for detecting non-baseline properties
- Redaction engine: Token pattern detection (JWT, base64, hex, API keys), secret field names, fail-closed verifier
- Crawler: Multi-screen crawl with navigation graph, URL normalization, DOM signatures, screen deduplication
- Dimensions: Network capture (requests, responses, WS, SSE), storage capture (localStorage, sessionStorage, IndexedDB, cookies)
- CLI: `scan`, `report`, `clear-profile`, `open` commands with Rich progress output

**Fixture Testbed (`fixtures/testbed/`)**
- Baseline variant: Working messaging SPA with 4 conversations, 3 tabs (Direct/Groups/Channels)
- Stores: `MessageStore`, `ChannelStore`, `CurrentUserStore`, `ConnectionStore`, `WebSocketManager`
- Webpack-like module registration: `webpackChunktestbed_app` with shape-based exports
- Internal API: `TestbedAPI` with `getConversations`, `getMessages`, `sendMessage`, `markAsRead`
- WebSocket simulation: Incoming `MESSAGE_CREATE` events
- Variant v2 (renamed-store): Different chunk global (`webpackChunktestbed_app_v2`), renamed exports (`getMessageRepository` vs `getMessageStore`), renamed methods (`fetchMessages` vs `getMessages`)
- Variant v3 (moved-endpoint): Different chunk global (`webpackChunktestbed_app_v3`), same exports but internal API switched to GraphQL-style `/graphql` endpoint
- Simple aiohttp server (`server.py`) serves static files

### Project Structure
```
metamorph/
├── pyproject.toml
├── MEMORY.md
├── scanner/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── types.py       # All dataclasses
│   │   └── baseline.py    # Clean browser globals
│   ├── crawl/
│   │   ├── __init__.py
│   │   └── crawler.py     # Multi-screen crawl + nav graph
│   ├── dimensions/
│   │   ├── __init__.py
│   │   └── network_storage.py
│   ├── redaction/
│   │   ├── __init__.py
│   │   └── engine.py      # Redaction + verification
│   └── cli/
│       ├── __init__.py
│       └── main.py        # Click CLI
├── fixtures/
│   └── testbed/
│       ├── public/index.html
│       ├── src/stores.js, main.js
│       ├── server.py
│       └── variants/
│           ├── v2-renamed-store/  # Export renames + method renames
│           └── v3-moved-endpoint/ # GraphQL endpoint switch
└── templates/ (empty - for Phase 2)
└── skills/ (empty - for Phase 2)
```

### How to Run (Local)
```bash
cd C:\Users\User\metamorph

# Install deps
pip install -e .[dev]
playwright install chromium

# Start fixture server (terminal 1)
python -m fixtures.testbed.server 8765

# Run scan (terminal 2)
python -m scanner.cli.main scan \
  --url http://localhost:8765 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --out ./dossier_testbed \
  --headless

# View report
python -m scanner.cli.main report ./dossier_testbed/dossier.json
```

### Git Status
- Local repo initialized at `C:\Users\User\metamorph`
- **No GitHub remote configured yet** - need to create repo on GitHub and add remote

### Next Phase: Phase 2 - Skill + Extension Template
- Create `SKILL.md` for Claude CLI (instructions to generate MV3 extension from dossier)
- Create MV3 extension template in `templates/extension/`
- Manifest, bridge (MAIN world), content script, service worker, popup
- Path resolver with security guarantees (no eval, forbidden segments)
- Binding executors for: `internal-http`, `runtime-call`, `runtime-read`, `dom-action`

### Open Decisions for Phase 2
1. Where does the skill live? Repo `skills/metamorph-extgen/` + symlink to `~/.claude/skills/`
2. Extension output: `extensions/<site-slug>/` in repo, or separate repo per site?
3. Probe format: JSON assertions run via Playwright against live site?