# METAMORPH - Development Memory

## Current State: Scanner End-to-End Working (Phase 3+)

### What's Done ✅

**Phase 1: Scanner Foundation + Fixture Testbed**
- Core dossier types: `Dossier`, `Screen`, `NavGraph`, `NavEdge`, `StaticSurface`, `RuntimeTopology`, `NetworkCatalogue`, `StorageInventory`, `DOMStructure`, `BehavioralCorrelation`, `CapabilityProbeTrace`, `Selector`, `RedactionEntry`
- Browser baseline: 1000+ standard globals for detecting non-baseline properties
- Redaction engine: Token pattern detection (JWT, base64, hex, API keys), secret field names, fail-closed verifier
- Crawler: Multi-screen crawl with navigation graph, URL normalization, DOM signatures, screen deduplication
- Dimensions: Network capture (requests, responses, WS, SSE), storage capture (localStorage, sessionStorage, IndexedDB, cookies)
- CLI: `scan`, `report`, `clear-profile`, `open` commands

**Phase 2: Skill + Extension Template**
- Skill (`skills/metamorph-extgen/`) with `SKILL.md`, references (`dossier-schema.md`, `binding-preferences.md`, `redlines.md`)
- Extension Template (MV3) with bridge, content script, service worker, popup, esbuild config

**Phase 3: Probes + Repair Flow**
- Probe Runner (`scanner/probe/runner.py`) - validates extension against live site
- Repair Engine (`scanner/repair/`) - diff-based re-scan and regeneration
- CLI: `probe`, `repair` commands

**Phase 3+ Fixes (this commit): Scanner End-to-End Working**
- Fixed DOM structure capture key sanitization (removed problematic regex causing "Unexpected token ']'")
- Fixed StorageCapture async IIFE for IndexedDB
- Fixed network/storage object serialization (dynamic objects -> proper dicts)
- Removed rich Progress bars (Windows cp1252 encoding issues)
- Added error handling for DOM capture (non-blocking, continues scan)
- Scanner now completes end-to-end on fixture testbed

### Fixture Testbed (`fixtures/testbed/`)
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
│   ├── core/ (types, baseline)
│   ├── crawl/ (crawler, URLNormalizer)
│   ├── dimensions/ (network_storage)
│   ├── redaction/ (engine, verifier)
│   ├── probe/ (runner)
│   ├── repair/ (engine, diff)
│   └── cli/ (main: scan, report, probe, repair, clear-profile, open)
├── fixtures/testbed/ (baseline + v2 + v3 variants)
├── skills/metamorph-extgen/ (SKILL.md + extension template)
└── templates/ (empty)
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
  --out ./dossier_test \
  --headless

# View report
python -m scanner.cli.main report ./dossier_test/dossier.json

# Test repair with v2 variant (renamed store)
# Terminal 1: python -m fixtures.testbed.variants.v2-renamed-store.server 8766
# Terminal 2: python -m scanner.cli.main repair \
#   --url http://localhost:8766 \
#   --goals getMessages,sendMessage,getConversations \
#   --profile testbed \
#   --prev ./dossier_test/dossier.json \
#   --out ./dossier_v2_repair \
#   --headless

# Use skill to generate extension from dossier
# Follow skills/metamorph-extgen/SKILL.md
```

### Git Status
- Repo: https://github.com/GuiVicS/metamorph
- Latest commit: `eea30b9` - Phase 3 fixes: Scanner end-to-end working

### Next Steps
1. **Test repair flow** with v2/v3 variants - run repair scan and verify diff detection
2. **Generate extension** using skill from dossier - follow `skills/metamorph-extgen/SKILL.md`
3. **Run probe validation** - `python -m scanner.cli.main probe --ext ./extensions/testbed/dist --dossier ./dossier_test/dossier.json`
4. **Improve fixture detection** - add webpack chunk detection, store detection for vanilla JS apps
5. **GitHub Actions CI** - lint, typecheck, pytest, build extension