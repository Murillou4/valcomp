import json

import pytest

from ares_console.executor import EndpointExecutor, RequestBuildError
from ares_console.models import Lockfile, RiotContext


@pytest.fixture
def context() -> RiotContext:
    return RiotContext(
        online=True,
        lockfile=Lockfile("Riot Client", 1, 54321, "secret", "https"),
        token="auth-token",
        entitlement="entitlement-token",
        puuid="player-uuid",
        region="br",
        shard="na",
        client_version="release-test",
        party_id="party-uuid",
    )


def test_builds_remote_request_with_riot_headers(context: RiotContext) -> None:
    endpoint = {
        "method": "GET",
        "transport": "http",
        "endpoint_type": "pd",
        "url_template": "https://pd.{shard}.a.pvp.net/account-xp/v1/players/{puuid}",
        "requirements": {
            "token": True,
            "entitlement": True,
            "client_version": True,
            "client_platform": True,
            "local_auth": False,
        },
        "headers": {},
    }
    executor = EndpointExecutor()
    try:
        built = executor.build_request(endpoint, context, {}, {}, "")
    finally:
        executor.close()

    assert built["url"].endswith("/players/player-uuid")
    assert built["url"].startswith("https://pd.na.")
    assert built["headers"]["Authorization"] == "Bearer auth-token"
    assert built["headers"]["X-Riot-Entitlements-JWT"] == "entitlement-token"


def test_builds_local_auth_and_json_body(context: RiotContext) -> None:
    endpoint = {
        "method": "POST",
        "transport": "http",
        "endpoint_type": "local",
        "url_template": "https://127.0.0.1:{port}/chat/v6/messages",
        "requirements": {
            "token": False,
            "entitlement": False,
            "client_version": False,
            "client_platform": False,
            "local_auth": True,
        },
        "headers": {},
    }
    executor = EndpointExecutor()
    try:
        built = executor.build_request(
            endpoint,
            context,
            {},
            {},
            json.dumps({"cid": "party", "message": "oi", "type": "groupchat"}),
        )
    finally:
        executor.close()

    assert built["local"] is True
    assert built["url"].startswith("https://127.0.0.1:54321/")
    assert built["headers"]["Authorization"].startswith("Basic ")
    assert built["json"]["message"] == "oi"


def test_missing_route_variable_is_reported(context: RiotContext) -> None:
    endpoint = {
        "method": "GET",
        "transport": "http",
        "endpoint_type": "pd",
        "url_template": "https://pd.{shard}.a.pvp.net/matches/{match id}",
        "requirements": {},
        "headers": {},
    }
    executor = EndpointExecutor()
    try:
        with pytest.raises(RequestBuildError, match="match id"):
            executor.build_request(endpoint, context, {}, {}, "")
    finally:
        executor.close()


def test_optional_url_variable_can_be_omitted(context: RiotContext) -> None:
    endpoint = {
        "method": "GET",
        "transport": "http",
        "endpoint_type": "pd",
        "url_template": "https://pd.{shard}.a.pvp.net/store/v1/entitlements/{puuid}/{ItemTypeID}",
        "variables": [{"name": "ItemTypeID", "optional": True}],
        "requirements": {},
        "headers": {},
    }
    executor = EndpointExecutor()
    try:
        built = executor.build_request(endpoint, context, {}, {}, "")
    finally:
        executor.close()

    assert built["url"] == (
        "https://pd.na.a.pvp.net/store/v1/entitlements/player-uuid"
    )


def test_sensitive_headers_are_redacted() -> None:
    redacted = EndpointExecutor._redact_headers(
        {
            "Authorization": "Bearer secret",
            "X-Riot-Entitlements-JWT": "secret",
            "Content-Type": "application/json",
        }
    )

    assert redacted["Authorization"] == "[oculto]"
    assert redacted["X-Riot-Entitlements-JWT"] == "[oculto]"
    assert redacted["Content-Type"] == "application/json"
