# METAMORPH - Development Memory

## Current State: Phase 2 Complete (Skill + Extension Template)

### What's Done ✅

**Phase 1: Scanner Foundation + Fixture Testbed** (commit 85b8d05)
- Core dossier types, baseline, redaction, crawler, network/storage capture, CLI
- Fixture testbed with baseline + 2 breakage variants (v2 renamed-store, v3 moved-endpoint)

**Phase 2: Skill + Extension Template** (this commit)

**Skill (`skills/metamorph-extgen/`)**
- `SKILL.md` - Complete instructions for Claude CLI to generate MV3 extension from dossier
- `references/dossier-schema.md` - Full dossier JSON structure reference
- `references/binding-preferences.md` - Binding selection guide with priority flowchart
- `references/redlines.md` - Security redlines (no-eval, no-credentials, shape-matching, closed transforms, etc.)

**Extension Template (`skills/metamorph-extgen/templates/extension/`)**
- `manifest.json` - MV3 with placeholders, optional host permissions
- `src/main-world/bridge.js` - MAIN world bridge with:
  - Structural path resolver (no eval, forbidden segments: `__proto__`, `constructor`, `prototype`)
  - Discovery strategies: webpack-chunk-injection, window-path
  - Handle resolution by shape matching (hasKeys/hasMethods)
  - Interceptors: fetch, WebSocket, function
  - Message protocol via postMessage to ISOLATED world
  - Capability execution: runtime-call, runtime-read, internal-http, dom-action
- `src/content/content.js` - ISOLATED world content script:
  - Chrome runtime port to service worker
  - postMessage bridge to MAIN world
  - DOM actor for dom-action bindings
  - MutationObserver for selector verification
- `src/worker/worker.js` - Service worker:
  - FingerprintStore (IndexedDB)
  - AdapterEngine (builds ChannelAdapter from fingerprint)
  - BindingExecutor (executes all binding types)
  - Normalizer (closed transform set)
  - EventBus (60s dedupe window)
  - HealthMonitor (probes, telemetry)
  - Transport (WebSocket to backend with ack/reconnect)
- `src/popup/popup.html` + `popup.js` - Status UI
- `config/origins.json` - Platform origins template
- `esbuild.config.mjs` - Bundles worker modules

### Project Structure
```
metamorph/
├── pyproject.toml
├── MEMORY.md
├── scanner/ (Phase 1)
├── fixtures/testbed/ (Phase 1)
├── skills/
│   └── metamorph-extgen/
│       ├── SKILL.md
│       ├── references/
│       │   ├── dossier-schema.md
│       │   ├── binding-preferences.md
│       │   └── redlines.md
│       └── templates/extension/
│           ├── manifest.json
│           ├── esbuild.config.mjs
│           ├── config/origins.json
│           └── src/
│               ├── main-world/bridge.js
│               ├── content/content.js
│               ├── worker/
│               │   ├── worker.js
│               │   ├── fingerprint-store.js
│               │   ├── adapter-engine.js
│               │   ├── binding-executor.js
│               │   ├── normalizer.js
│               │   ├── event-bus.js
│               │   ├── health.js
│               │   └── transport.js
│               └── popup/popup.html, popup.js
└── templates/ (empty)
```

### How to Use (End-to-End)

```bash
# 1. Start fixture server
python -m fixtures.testbed.server 8765

# 2. Scan the fixture (creates dossier)
python -m scanner.cli.main scan \
  --url http://localhost:8765 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --out ./dossier_testbed \
  --headless

# 3. Use the skill in Claude CLI:
#    - Open Claude Code in the repo root
#    - The skill is at skills/metamorph-extgen/
#    - Follow SKILL.md to generate extension from dossier_testbed/dossier.json

# 4. Build generated extension:
#    cd extensions/testbed
#    npm install
#    npx esbuild --config=esbuild.config.mjs

# 5. Load in Chrome (chrome://extensions → Developer mode → Load unpacked → dist/)
```

### Next Phase: Phase 3 - Probes + Repair Flow
- Probe runner (Playwright-based) to validate generated extension against live site
- Diff-based re-scan for repair flow
- Demonstrate v2/v3 variant repair automatically

### Open Decisions for Phase 3
1. Probe runner: standalone CLI or integrated into scanner CLI?
2. Extension output location: `extensions/<site-slug>/` in repo?
3. Repair flow: auto-detect breakage from probe failures → re-scan with prev dossier → regenerate