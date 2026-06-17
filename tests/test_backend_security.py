import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest

from ares_backend.auth import SupabaseAuth
from ares_backend.errors import RelinkRequiredError, UnauthorizedError
from ares_backend.riot import (
    RiotAuthService,
    RiotRemoteClient,
    RiotSession,
    access_token_needs_refresh,
)
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


def test_expired_riot_access_token_requires_refresh() -> None:
    expired = jwt.encode(
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        "unused-test-key",
        algorithm="HS256",
    )
    valid = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=10)},
        "unused-test-key",
        algorithm="HS256",
    )

    assert access_token_needs_refresh(expired) is True
    assert access_token_needs_refresh(valid) is False


def test_bad_claims_from_riot_becomes_relink_required() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errorCode": "BAD_CLAIMS"})

    async def run() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = RiotRemoteClient(
            BackendSettings(app_secret_key="unit-test-secret"),
            client=http,
        )
        session = RiotSession(
            access_token="expired",
            entitlement_token="expired",
            puuid="player",
            region="br",
            shard="na",
            client_version="release-test",
            client_platform="platform",
        )

        with pytest.raises(RelinkRequiredError):
            await client.mmr(session)

        await http.aclose()

    asyncio.run(run())


def test_mobile_web_login_entitlement_403_becomes_relink_required() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "auth.riotgames.com" and request.url.path == "/authorize":
            assert request.url.params.get("client_id") == "riot-client"
            assert request.url.params.get("redirect_uri") == "http://localhost/redirect"
            return httpx.Response(
                302,
                headers={
                    "location": (
                        "http://localhost/redirect#access_token=riot-client-access"
                        "&id_token=riot-client-id"
                    )
                },
            )
        if request.url.host == "entitlements.auth.riotgames.com":
            return httpx.Response(403, json={"error": "forbidden"})
        return httpx.Response(200, json={})

    async def run() -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = RiotAuthService(
            BackendSettings(app_secret_key="unit-test-secret"),
            CryptoService("unit-test-secret"),
            client=http,
        )

        with pytest.raises(RelinkRequiredError):
            await service.payload_from_web_login(
                access_token="web-access-token",
                id_token="web-id-token",
                ssid="ssid-cookie",
                cookies={"ssid": "ssid-cookie"},
            )

        await http.aclose()

    asyncio.run(run())
