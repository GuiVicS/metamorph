"""Redaction engine for sanitizing dossiers before persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


# Patterns that indicate secrets
TOKEN_PATTERNS = [
    (re.compile(r"^eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*$"), "JWT"),
    (re.compile(r"^[A-Za-z0-9+/]{32,}={0,2}$"), "base64-long"),
    (re.compile(r"^[0-9a-f]{32,}$"), "hex-long"),
    (re.compile(r"^sk-[A-Za-z0-9]{32,}$"), "openai-key"),
    (re.compile(r"^gh[ps]_[A-Za-z0-9]{36,}$"), "github-token"),
    (re.compile(r"^xox[baprs]-[A-Za-z0-9-]{10,}$"), "slack-token"),
    (re.compile(r"^Bearer\s+[A-Za-z0-9_-]{20,}$", re.IGNORECASE), "bearer-token"),
]

SECRET_FIELD_NAMES = frozenset([
    "token", "access_token", "refresh_token", "id_token", "auth_token",
    "api_key", "apikey", "secret", "password", "passwd", "pwd",
    "session", "session_id", "sessionid", "sid", "csrf", "xsrf",
    "authorization", "proxy-authorization", "x-csrf-token", "x-xsrf-token",
    "x-auth-token", "x-api-key", "cookie", "set-cookie",
    "private_key", "privatekey", "secret_key", "secretkey",
    "client_secret", "clientsecret", "signing_secret", "signingsecret",
    "webhook_secret", "webhooksecret", "encryption_key", "encryptionkey",
])

SECRET_FIELD_REGEX = re.compile(r".*(token|secret|key|password|passwd|pwd|session|csrf|xsrf|auth|credential).*", re.IGNORECASE)


@dataclass
class RedactionEntry:
    path: str
    reason: str
    original_type: str


class RedactionEngine:
    """Redacts sensitive data from dossier structures."""

    def __init__(self) -> None:
        self.entries: list[RedactionEntry] = []
        self._token_cache: dict[str, str] = {}

    def redact(self, obj: Any, path: str = "$") -> Any:
        """Recursively redact sensitive data from any JSON-serializable object."""
        if isinstance(obj, dict):
            return self._redact_dict(obj, path)
        elif isinstance(obj, list):
            return [self.redact(item, f"{path}[{i}]") for i, item in enumerate(obj)]
        elif isinstance(obj, str):
            return self._redact_string(obj, path)
        else:
            return obj

    def _redact_dict(self, d: dict, path: str) -> dict:
        result = {}
        for k, v in d.items():
            new_path = f"{path}.{k}"
            # Check if the key itself suggests a secret
            if self._is_secret_key(k):
                result[k] = self._placeholder_for_value(v, new_path, f"secret field name: {k}")
            else:
                result[k] = self.redact(v, new_path)
        return result

    def _redact_string(self, s: str, path: str) -> str:
        # Check for token patterns
        for pattern, label in TOKEN_PATTERNS:
            if pattern.match(s.strip()):
                return self._placeholder_for_value(s, path, f"token pattern: {label}")
        return s

    def _is_secret_key(self, key: str) -> bool:
        kl = key.lower()
        if kl in SECRET_FIELD_NAMES:
            return True
        if SECRET_FIELD_REGEX.match(kl):
            return True
        return False

    def _placeholder_for_value(self, value: Any, path: str, reason: str) -> str:
        """Generate a type-preserving placeholder."""
        if isinstance(value, str):
            if value.isdigit():
                placeholder = "<string:numeric>"
            elif re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", value):
                placeholder = "<string:uuid>"
            elif re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
                placeholder = "<string:iso8601>"
            elif len(value) > 100:
                placeholder = "<string:long>"
            else:
                placeholder = "<string>"
        elif isinstance(value, (int, float)):
            placeholder = "<number>"
        elif isinstance(value, bool):
            placeholder = "<boolean>"
        elif value is None:
            placeholder = "<null>"
        elif isinstance(value, dict):
            placeholder = "<object>"
        elif isinstance(value, list):
            placeholder = "<array>"
        else:
            placeholder = f"<{type(value).__name__}>"

        self.entries.append(RedactionEntry(path=path, reason=reason, original_type=type(value).__name__))
        return placeholder

    def get_report(self) -> list[dict]:
        return [{"path": e.path, "reason": e.reason, "original_type": e.original_type} for e in self.entries]

    def clear(self) -> None:
        self.entries.clear()
        self._token_cache.clear()


class RedactionVerifier:
    """Verifies that no secrets leaked in a dossier. Fail-closed."""

    def __init__(self) -> None:
        self.violations: list[dict] = []

    def verify(self, obj: Any, path: str = "$") -> bool:
        """Returns True if clean, False if violations found."""
        self.violations.clear()
        self._verify_recursive(obj, path)
        return len(self.violations) == 0

    def _verify_recursive(self, obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_path = f"{path}.{k}"
                # Check if key suggests secret but value is not a placeholder
                if self._is_secret_key(k) and isinstance(v, str) and not v.startswith("<"):
                    # Allow known placeholder patterns
                    if not re.match(r"^<.*>$", v):
                        self.violations.append({
                            "path": new_path,
                            "reason": f"Potential secret in field '{k}': value not redacted",
                            "value_preview": v[:50] + "..." if len(v) > 50 else v
                        })
                self._verify_recursive(v, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._verify_recursive(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            # Check for token patterns in strings that aren't placeholders
            if not obj.startswith("<") and not obj.endswith(">"):
                for pattern, label in TOKEN_PATTERNS:
                    if pattern.match(obj.strip()):
                        self.violations.append({
                            "path": path,
                            "reason": f"Token pattern detected: {label}",
                            "value_preview": obj[:50] + "..." if len(obj) > 50 else obj
                        })

    def _is_secret_key(self, key: str) -> bool:
        kl = key.lower()
        return kl in SECRET_FIELD_NAMES or SECRET_FIELD_REGEX.match(kl) is not None

    def get_violations(self) -> list[dict]:
        return self.violations


def redact_dossier(dossier_dict: dict) -> tuple[dict, list[dict]]:
    """Convenience function to redact a dossier dict."""
    engine = RedactionEngine()
    redacted = engine.redact(dossier_dict)
    report = engine.get_report()
    return redacted, report


def verify_redaction(obj: Any) -> tuple[bool, list[dict]]:
    """Verify no secrets leaked. Returns (clean, violations)."""
    verifier = RedactionVerifier()
    clean = verifier.verify(obj)
    return clean, verifier.get_violations()