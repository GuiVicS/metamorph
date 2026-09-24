# METAMORPH - Development Memory

## Current State: Phase 3 Complete (Probes + Repair Flow)

### What's Done ✅

**Phase 1: Scanner Foundation + Fixture Testbed** (commit 85b8d05)
- Core dossier types, baseline, redaction, crawler, network/storage capture, CLI
- Fixture testbed with baseline + 2 breakage variants (v2 renamed-store, v3 moved-endpoint)

**Phase 2: Skill + Extension Template** (commit 30fa9b9)
- Skill (`skills/metamorph-extgen/`) with SKILL.md, references
- Extension Template (MV3) with bridge, content script, service worker, popup

**Phase 3: Probes + Repair Flow** (this commit)

**Probe Runner (`scanner/probe/runner.py`)**
- `ExtensionProbeValidator` - Loads extension dist + dossier, runs probes via Playwright
- `ProbeRunner` - Injects bridge/content script, executes capabilities via postMessage
- Validates assertions (equals, nonEmpty, type, minLength)
- CLI: `metamorph probe --ext <dir> --dossier <file> --goals <list> [--consent --sandbox-target]`

**Repair Engine (`scanner/repair/`)**
- `diff.py` - Structural diff between dossiers (changed/added/removed paths)
- `engine.py` - `RepairEngine` analyzes breakage, identifies affected capabilities, generates actions
- CLI: `metamorph repair --url <url> --goals <list> --prev <dossier> --out <dir>`
- Re-scans with previous dossier context, computes diff, saves new dossier

**Fixture Variants Ready for Testing**
- `v2-renamed-store` - Webpack chunk global + export renames + method renames
- `v3-moved-endpoint` - GraphQL endpoint switch (REST → /graphql)

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

### How to Test End-to-End

```bash
cd C:\Users\User\metamorph

# Install deps
pip install -e .[dev]
playwright install chromium

# 1. Start baseline fixture server (terminal 1)
python -m fixtures.testbed.server 8765

# 2. Scan baseline → dossier
python -m scanner.cli.main scan \
  --url http://localhost:8765 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --out ./dossier_baseline \
  --headless

# 3. Generate extension using skill (Claude CLI)
#    - Follow skills/metamorph-extgen/SKILL.md
#    - Output: extensions/testbed/
#    - Build: cd extensions/testbed && npx esbuild --config=esbuild.config.mjs

# 4. Run probes against baseline extension
python -m scanner.cli.main probe \
  --ext ./extensions/testbed/dist \
  --dossier ./dossier_baseline/dossier.json \
  --goals getMessages,getConversations \
  --headless

# 5. Test REPAIR: Switch to v2 variant (renamed store)
#    Terminal 1: python -m fixtures.testbed.variants.v2-renamed-store.server 8765
#    (or modify server.py to serve variant)

# 6. Run repair scan
python -m scanner.cli.main repair \
  --url http://localhost:8765 \
  --goals getMessages,sendMessage,getConversations \
  --profile testbed \
  --prev ./dossier_baseline/dossier.json \
  --out ./dossier_v2_repair \
  --headless

# 7. Check diff output shows: webpack chunk global changed, handle paths changed
# 8. Regenerate extension from new dossier using skill
# 9. Run probes again - should pass!

# 10. Repeat for v3 (moved endpoint)
```

### Git Status
- Local repo at `C:\Users\User\metamorph`
- 3 commits: Phase 1, Phase 2, Phase 3
- **Ready for GitHub push**

### Next Steps
1. Push to GitHub: `git remote add origin https://github.com/guivics/metamorph.git && git push -u origin master`
2. Test full repair loop on fixture variants
3. Optional: Add GitHub Actions for CI