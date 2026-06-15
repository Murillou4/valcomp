import jwt
import pytest

from ares_backend.auth import SupabaseAuth
from ares_backend.errors import UnauthorizedError
from ares_backend.security import CryptoService, redact_secret
from ares_backend.settings import BackendSettings


def test_encrypts_and_decrypts_credential_payload() -> None:
    crypto = CryptoService("unit-test-secret")
    encrypted = crypto.encrypt_json({"ssid": "super-secret", "puuid": "player"})

    assert "super-secret" not in encrypted
    assert crypto.decrypt_json(encrypted) == {"ssid": "super-secret", "puuid": "player"}


def test_redacts_short_and_long_secrets() -> None:
    assert redact_secret("small") == "[redacted]"
    assert redact_secret("abcdef123456") == "abcd...3456"


def test_dev_auth_token_is_accepted_when_enabled() -> None:
    auth = SupabaseAuth(BackendSettings(app_secret_key="secret", allow_dev_auth=True))

    user = auth.verify_authorization("Bearer dev:mobile-user")

    assert user.id == "mobile-user"
    assert user.claims["dev"] is True


def test_supabase_jwt_is_validated_with_configured_secret() -> None:
    settings = BackendSettings(
        app_secret_key="secret",
        allow_dev_auth=False,
        supabase_jwt_secret="jwt-secret",
    )
    token = jwt.encode(
        {"sub": "user-id", "email": "user@example.com", "aud": "authenticated"},
        "jwt-secret",
        algorithm="HS256",
    )

    user = SupabaseAuth(settings).verify_authorization(f"Bearer {token}")

    assert user.id == "user-id"
    assert user.email == "user@example.com"


def test_auth_requires_bearer_token() -> None:
    auth = SupabaseAuth(BackendSettings(app_secret_key="secret"))

    with pytest.raises(UnauthorizedError):
        auth.verify_authorization(None)

