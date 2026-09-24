# Metamorph

**Adaptive Web Connector Engine** — Turn any web application into a programmable API through automated scanning and generated Chrome extensions.

## Overview

Metamorph scans a web application (with your authenticated session), produces a structured **dossier** of its internals (runtime, network, storage, DOM), and a **Claude CLI skill** generates a **Manifest V3 Chrome extension** that exposes the app through a unified interface. When the site changes, re-scan → diff → regenerate.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for extension build)
- Chrome/Chromium

### Install
```bash
git clone https://github.com/GuiVicS/metamorph.git
cd metamorph
pip install -e .[dev]
playwright install chromium
```

---

## Usage

### 1. Scan a Web Application

**Start the target** (fixture or real site):
```bash
# Local fixture (for testing)
python -m fixtures.testbed.server 8765

# OR real site - first log in manually:
metamorph open --profile meu_perfil --url https://app.exemplo.com
# (browser opens, you log in, then close)
```

**Run the scan:**
```bash
metamorph scan \
  --url http://localhost:8765 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --out ./dossier_test \
  --headless
```

**View results:**
```bash
metamorph report ./dossier_test/dossier.json
```

### 2. Generate Chrome Extension

**Install the skill (once):**
```bash
ln -s $(pwd)/skills/metamorph-extgen ~/.claude/skills/metamorph-extgen
```

**Generate via Claude CLI:**
```bash
# In Claude CLI:
# "Use a skill metamorph-extgen para gerar uma extensão a partir do dossier em ./dossier_test/dossier.json"
# Output: extensions/testbed/
```

**Build & load in Chrome:**
```bash
cd extensions/testbed
npm install
npx esbuild --config=esbuild.config.mjs
# Chrome: chrome://extensions → Developer mode → Load unpacked → dist/
```

### 3. Validate with Probes
```bash
metamorph probe \
  --ext ./extensions/testbed/dist \
  --dossier ./dossier_test/dossier.json \
  --goals getMessages,getConversations \
  --headless
```

### 4. Repair After Site Changes
```bash
# Site changed? Re-scan with previous dossier:
metamorph repair \
  --url http://localhost:8766 \
  --goals getMessages,sendMessage \
  --profile testbed \
  --prev ./dossier_test/dossier.json \
  --out ./dossier_v2_repair \
  --headless

# Shows diff: webpack chunks, handles, endpoints changed
# Re-generate extension from new dossier
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `metamorph scan` | Full-platform scan → dossier |
| `metamorph report` | Human-readable dossier summary |
| `metamorph probe` | Validate generated extension |
| `metamorph repair` | Re-scan + diff against previous dossier |
| `metamorph open` | Open browser in profile for manual login |
| `metamorph clear-profile` | Clear profile cookies/storage |

### Scan Options
| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--url` | ✅ | — | Starting URL |
| `--goals` | ✅ | — | Capabilities (comma-separated) |
| `--profile` | ❌ | `default` | Browser profile name |
| `--out` | ❌ | `./dossier` | Output directory |
| `--headless` | ❌ | `false` | Headless browser |
| `--max-screens` | ❌ | `50` | Max screens to crawl |
| `--max-depth` | ❌ | `5` | Crawl depth |

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Scanner   │────▶│   Dossier   │────▶│  Skill (Claude) │
│  (Python)   │     │   (JSON)    │     │  generates MV3  │
└─────────────┘     └─────────────┘     └────────┬────────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Probe     │◀───│  Extension  │◀───│  Template (MV3) │
│  (Playwright)   │  (Chrome)   │     │  (bridge/worker) │
└─────────────┘     └─────────────┘     └─────────────────┘
```

**Key Principles:**
- **No eval** — Path resolution via structural traversal only
- **Shape matching** — Modules identified by export keys, never build IDs
- **Closed transforms** — Fixed set: `iso8601ToEpochMs`, `snowflakeToEpochMs`, `mapEach`, etc.
- **Auth barriers detected** — Login, CAPTCHA, 2FA, email/phone verification logged per screen
- **Minimal permissions** — Optional host permissions only for target origins

---

## Fixture Testbed

For development/testing without real sites:
```bash
# Baseline
python -m fixtures.testbed.server 8765

# Variant v2: renamed stores/exports
python -m fixtures.testbed.variants.v2-renamed-store.server 8766

# Variant v3: GraphQL endpoint
python -m fixtures.testbed.variants.v3-moved-endpoint.server 8767
```

---

## Project Structure
```
metamorph/
├── scanner/           # Python scanner package
│   ├── crawl/         # Multi-screen crawler + nav graph
│   ├── dimensions/    # Network, storage capture
│   ├── redaction/     # Secret redaction + verifier
│   ├── probe/         # Extension probe runner
│   ├── repair/        # Diff + repair engine
│   └── cli/           # Click CLI commands
├── fixtures/testbed/  # Messaging SPA + variants
├── skills/
│   └── metamorph-extgen/  # Skill + MV3 template
└── templates/         # (reserved)
```

---

## Security

- **No credential handling** — Operates only in your existing authenticated session
- **Redaction fail-closed** — Scans with unredacted secrets are discarded
- **No eval** — Bridge uses structural path resolution only
- **CSP enforced** — `script-src 'self'` in extension
- **Minimal permissions** — `optional_host_permissions` only

---

## License

MIT — See LICENSE file.