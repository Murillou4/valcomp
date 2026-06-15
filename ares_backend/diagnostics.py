from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .schemas import DiagnosticEventCreate, DiagnosticEventRecord


LOGGER = logging.getLogger("valcomp")
_SECRET_KEYS = {
    "access_token",
    "authorization",
    "cookie",
    "cookies",
    "encrypted_payload",
    "entitlement_token",
    "id_token",
    "password",
    "puuid",
    "refresh_token",
    "secret",
    "service_role_key",
    "ssid",
    "token",
}
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def configure_logging() -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def emit_log(event: str, **fields: Any) -> None:
    configure_logging()
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **sanitize_context(fields),
    }
    LOGGER.info(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str))


def redact_text(value: str, *, max_length: int = 8000) -> str:
    text = value[:max_length]
    text = _JWT_RE.sub("[REDACTED_JWT]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _UUID_RE.sub("[REDACTED_ID]", text)
    return text


def sanitize_context(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[MAX_DEPTH]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:80]:
            key = str(raw_key)[:120]
            if any(secret in key.lower() for secret in _SECRET_KEYS):
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize_context(raw_value, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [sanitize_context(item, depth=depth + 1) for item in list(value)[:80]]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value))


def user_fingerprint(user_id: str | None) -> str:
    if not user_id:
        return ""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]


def diagnostic_record(
    payload: DiagnosticEventCreate,
    *,
    user_id: str | None,
    fallback_request_id: str = "",
) -> DiagnosticEventRecord:
    return DiagnosticEventRecord(
        event_id=payload.event_id or str(uuid4()),
        user_id=user_id,
        source=payload.source,
        level=payload.level,
        category=payload.category,
        message=redact_text(payload.message, max_length=4000),
        context=sanitize_context(payload.context),
        stack_trace=redact_text(payload.stack_trace, max_length=16000),
        request_id=payload.request_id or fallback_request_id,
        app_version=redact_text(payload.app_version, max_length=80),
        device_id=hash_device_id(payload.device_id),
        occurred_at=payload.occurred_at,
    )


def hash_device_id(device_id: str) -> str:
    if not device_id:
        return ""
    return f"sha256:{hashlib.sha256(device_id.encode('utf-8')).hexdigest()[:16]}"
