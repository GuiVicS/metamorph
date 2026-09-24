# Security Redlines - Non-Negotiable

These rules are enforced by the skill and the extension runtime. Violations = rejected extension.

## 1. NO EVAL - Zero Dynamic Code Execution

**Forbidden:**
- `eval()`, `new Function()`, `setTimeout(string)`, `setInterval(string)`
- `document.write()`, `document.writeln()`, `innerHTML = userData`
- `outerHTML = userData`, `insertAdjacentHTML()`, `DOMParser().parseFromString(userData)`
- `ScriptElement.text = userData`, `Function.prototype.constructor(userData)`
- Any string-to-code sink

**Required:**
- All Fingerprint data → structured objects only
- Path resolution → property access only (`obj[segment]`)
- Transforms → closed set of pure functions
- CSP: `script-src 'self'` (no `unsafe-eval`)

## 2. NO CREDENTIAL ACCESS

**Forbidden:**
- Reading `document.cookie`, `localStorage`, `sessionStorage`, `indexedDB` for auth tokens
- Accessing `Authorization`, `Cookie`, `X-CSRF-*`, `X-Auth-*` headers
- `fetch`/`XMLHttpRequest` with explicit credentials from storage
- Storing any secret in extension storage (IndexedDB, chrome.storage)

**Required:**
- `internal-http` uses `credentials: "same-origin"` (browser sends cookies automatically)
- Extension only stores: fingerprint config, telemetry metadata, dedupe keys
- Redaction strips all secrets from dossier before persistence

## 3. SHAPE MATCHING ONLY - No Numeric IDs

**Forbidden:**
- `require(12345)` - webpack module IDs
- `webpackChunkdiscord_app[123]` - chunk indices
- Any hardcoded numeric identifier from build output

**Required:**
- Module discovery by `hasKeys: ["getMessages", "getMessage"]`
- Export shape matching: `{ hasKeys: [...], hasMethods: [...] }`
- Window path by string array: `["window", "DiscordNative", "_stores"]`

## 4. CLOSED TRANSFORM SET

**Allowed transforms ONLY:**
```
identity, toString, toNumber, toBoolean,
iso8601ToEpochMs, epochSecToEpochMs, snowflakeToEpochMs,
mapEach, pick, coalesce, constant, enumMap
```

**Forbidden:**
- Arbitrary expressions: `"a + b"`, `"v * 1000"`, `"v.toUpperCase()"`
- Custom functions in Fingerprint
- Template strings with interpolation
- Any transform not in the above list

## 5. MINIMAL HOST PERMISSIONS

**Required:**
- `optional_host_permissions` in manifest (not `host_permissions`)
- Only the platform's origins from dossier: `["https://discord.com", "https://*.discord.com"]`
- Request permission at runtime via `chrome.permissions.request()`

**Forbidden:**
- `<all_urls>` or `*://*/*` in manifest
- Broad patterns like `https://*/*`

## 6. FORBIDDEN PATH SEGMENTS

**Rejected at load time:**
- `__proto__`
- `constructor`
- `prototype`

**Enforcement:**
- Bridge resolver checks every path segment
- Extension rejects Fingerprint at load if any segment matches
- No prototype pollution possible

## 7. NO EXFILTRATION

**Forbidden:**
- Sending message content, contacts, PII to any domain not in `optional_host_permissions`
- `fetch` to external analytics/telemetry without user consent
- Storing platform data in chrome.storage.sync

**Required:**
- Telemetry only: capability name, outcome, duration, error code (NO payloads)
- All platform data stays in browser memory
- User controls data flow via their own backend integration

## 8. HONEST GAPS OVER GUESSES

**Required:**
- If no binding evidence → `supported: false` with `"reason": "No binding found during scan"`
- Never invent a binding that "should work"
- Confidence scores reflect evidence quality, not optimism

**Forbidden:**
- Confidence ≥ 70 without passing probe
- `supported: true` with `binding` that references non-existent paths

## 9. PROBE VALIDATION MANDATORY

**Required:**
- Every `supported: true` capability MUST have at least one probe
- Read probes run automatically on generation, health, repair
- Write probes require explicit `--consent` + sandbox target
- Failed probe → capability marked `supported: false`

## 10. REDACTION FAIL-CLOSED

**Required:**
- Scanner redaction runs BEFORE any persistence
- Redaction verifier scans entire dossier after redaction
- Any violation → scan ABORTED, dossier DISCARDED
- Adversarial test suite must pass (injected secrets in all dimensions)

## Enforcement Points

| Layer | Check |
|-------|-------|
| Scanner | Redaction engine + verifier |
| Generator (Skill) | SKILL.md redlines + template validation |
| Extension Load | Schema validation + forbidden segment check + CSP |
| Extension Runtime | Path resolver denylist + binding executor allowlist |
| CI/CD | `ruff`/`eslint` no-eval rules + security tests |

## Violation Consequences

| Violation | Result |
|-----------|--------|
| Eval sink in template | Build fails |
| Forbidden segment in Fingerprint | Extension refuses to load |
| Credential access attempt | Runtime throws SecurityError |
| Custom transform | Normalizer throws UnknownTransformError |
| Missing probe for supported capability | Generator rejects Fingerprint |
| Redaction verifier finds leak | Scan aborted, no dossier written |

## Testing Compliance

Run these checks before any release:

```bash
# 1. No-eval lint
npm run lint:security

# 2. Schema validation
npm run validate:fingerprint

# 3. Redaction adversarial test
python -m pytest tests/redaction_adversarial.py

# 4. Probe validation
metamorph probe --ext extensions/<slug> --goals all

# 5. CSP verification (load extension, check console for violations)
```