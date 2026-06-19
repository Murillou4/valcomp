from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import secrets
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from .schemas import CompanionDeviceRecord, LiveCommandRecord, LiveSnapshot


_LIVE_SECRET_KEYS = {
    "access_token",
    "authorization",
    "cookie",
    "cookies",
    "entitlement",
    "id_token",
    "password",
    "puuid",
    "refresh_token",
    "secret",
    "ssid",
    "token",
}
_LIVE_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?\b"
)
_LIVE_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")


class LiveHub:
    """In-process fanout; durable state and commands remain in the repository."""

    def __init__(self) -> None:
        self._companions: dict[str, WebSocket] = {}
        self._mobiles: dict[str, set[WebSocket]] = defaultdict(set)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def attach_companion(self, user_id: str, socket: WebSocket) -> None:
        previous = self._companions.get(user_id)
        self._companions[user_id] = socket
        if previous and previous is not socket:
            try:
                await previous.close(code=4001, reason="Outro Companion foi ativado.")
            except Exception:
                pass

    def detach_companion(self, user_id: str, socket: WebSocket) -> None:
        if self._companions.get(user_id) is socket:
            self._companions.pop(user_id, None)

    def attach_mobile(self, user_id: str, socket: WebSocket) -> None:
        self._mobiles[user_id].add(socket)

    def detach_mobile(self, user_id: str, socket: WebSocket) -> None:
        sockets = self._mobiles.get(user_id)
        if sockets is not None:
            sockets.discard(socket)
            if not sockets:
                self._mobiles.pop(user_id, None)

    async def send_to_companion(self, user_id: str, payload: dict[str, Any]) -> bool:
        socket = self._companions.get(user_id)
        if socket is None:
            return False
        try:
            await socket.send_json(payload)
            return True
        except Exception:
            self.detach_companion(user_id, socket)
            return False

    async def publish_mobile(self, user_id: str, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for socket in tuple(self._mobiles.get(user_id, ())):
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.detach_mobile(user_id, socket)

    def user_lock(self, user_id: str) -> asyncio.Lock:
        return self._locks[user_id]


def hash_companion_secret(secret: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_companion_secret(secret: str, expected_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(hash_companion_secret(secret, pepper), expected_hash)


def new_companion_secret() -> str:
    return secrets.token_urlsafe(32)


def public_companion_device(device: CompanionDeviceRecord) -> dict[str, Any]:
    return device.model_dump(mode="json", exclude={"secret_hash", "user_id"})


def sanitize_live_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Estado ao vivo inválido.")
    sanitized = _sanitize_live_value(raw)
    encoded = json.dumps(sanitized, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 192_000:
        raise ValueError("Estado ao vivo excede o limite permitido.")
    return sanitized


def _sanitize_live_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 7:
        return None
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:120]:
            key = str(raw_key)[:120]
            normalized = key.lower()
            if any(secret in normalized for secret in _LIVE_SECRET_KEYS):
                continue
            result[key] = _sanitize_live_value(raw_value, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_live_value(item, depth=depth + 1) for item in list(value)[:120]]
    if isinstance(value, str):
        text = value[:2048]
        return _LIVE_BEARER_RE.sub(
            "Bearer [REDACTED]", _LIVE_JWT_RE.sub("[REDACTED_JWT]", text)
        )
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:400]


def snapshot_public(snapshot: LiveSnapshot | None, *, offline_after: int) -> dict[str, Any]:
    if snapshot is None:
        return {
            "type": "snapshot",
            "phase": "offline",
            "revision": 0,
            "state": {"reason": "companion_not_connected"},
            "updated_at": None,
            "online": False,
        }
    age = max(0.0, (datetime.now(UTC) - snapshot.updated_at).total_seconds())
    online = age <= offline_after
    return {
        "type": "snapshot",
        "phase": snapshot.phase if online else "offline",
        "revision": snapshot.revision,
        "state": snapshot.state if online else {"reason": "companion_offline"},
        "updated_at": snapshot.updated_at.isoformat(),
        "online": online,
    }


def command_public(command: LiveCommandRecord) -> dict[str, Any]:
    return command.model_dump(mode="json", exclude={"user_id", "device_id"})
