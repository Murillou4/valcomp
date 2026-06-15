from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CryptoService:
    def __init__(self, secret: str) -> None:
        self._fernet = Fernet(self._normalize_key(secret))

    def encrypt_json(self, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(data).decode("ascii")

    def decrypt_json(self, token: str) -> dict[str, Any]:
        try:
            data = self._fernet.decrypt(token.encode("ascii"))
        except InvalidToken as exc:
            raise ValueError("Encrypted payload could not be decrypted.") from exc
        value = json.loads(data.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Encrypted payload must contain a JSON object.")
        return value

    @staticmethod
    def _normalize_key(secret: str) -> bytes:
        raw = secret.strip()
        if raw:
            try:
                decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
                if len(decoded) == 32:
                    return raw.encode("ascii")
            except Exception:
                pass
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)


def redact_secret(value: str, *, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "[redacted]"
    return f"{value[:keep]}...{value[-keep:]}"
