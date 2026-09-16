"""Deterministic credential redaction for diagnostics, not retained run payloads."""

import re
import traceback


REDACTED = "[REDACTED]"
_FIELDS = (
    "api_key", "openai_api_key", "access_token", "refresh_token",
    "authorization", "password", "client_secret",
)
_FIELD_PATTERN = "|".join(_FIELDS)
_ASSIGNMENT = re.compile(
    rf"(?P<prefix>\b(?:{_FIELD_PATTERN})\b[\"']?\s*[:=]\s*)"
    r"(?:\[REDACTED\]|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;\}\]]+)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer[ \t]+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_BASIC = re.compile(r"\bBasic[ \t]+[A-Za-z0-9+/=]+", re.IGNORECASE)
_OPENAI_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")


def redact_text(text: str) -> str:
    """Redact supported assignments, Bearer/Basic tokens, and sk- shaped tokens."""
    text = _BEARER.sub("Bearer " + REDACTED, text)
    text = _BASIC.sub("Basic " + REDACTED, text)
    text = _ASSIGNMENT.sub(lambda match: match["prefix"] + REDACTED, text)
    return _OPENAI_KEY.sub(REDACTED, text)


def redact_diagnostic(value):
    """Copy JSON-like diagnostic context, replacing sensitive field values."""
    if isinstance(value, dict):
        return {
            redact_text(key) if isinstance(key, str) else key: (
                REDACTED if isinstance(key, str) and key.casefold() in _FIELDS
                else redact_diagnostic(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_diagnostic(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def render_exception(exc: BaseException) -> str:
    """Render the full exception chain, then redact without mutating exceptions."""
    return redact_text("".join(traceback.format_exception(exc)))
