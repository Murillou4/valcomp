from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ares_backend.app import create_app
from ares_backend.repository import InMemoryRepository
from ares_backend.schemas import RiotAccount, RiotCredentialPayload, RiotCredentialRecord
from ares_backend.settings import BackendSettings


def make_live_client(**overrides: object) -> TestClient:
    settings = BackendSettings(
        environment="development",
        allow_dev_auth=True,
        app_secret_key="test-live-secret-that-is-long-enough",
        api_base_url="http://testserver",
        **overrides,
    )
    return TestClient(create_app(settings=settings, repository=InMemoryRepository()))


def auth(user_id: str = "live-user") -> dict[str, str]:
    return {"Authorization": f"Bearer dev:{user_id}"}


def pair(client: TestClient, user_id: str = "live-user") -> dict:
    start = client.post("/companion/pair/start", headers=auth(user_id))
    assert start.status_code == 200
    response = client.post(
        "/companion/pair/complete",
        json={
            "pair_code": start.json()["pair_code"],
            "device_name": "PC de teste",
            "app_version": "2.0.0",
            "protocol_version": 1,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_pair_code_is_single_use_and_only_one_device_stays_active() -> None:
    with make_live_client() as client:
        first_start = client.post("/companion/pair/start", headers=auth())
        body = {
            "pair_code": first_start.json()["pair_code"],
            "device_name": "Primeiro PC",
            "app_version": "2.0.0",
            "protocol_version": 1,
        }
        assert client.post("/companion/pair/complete", json=body).status_code == 200
        assert client.post("/companion/pair/complete", json=body).status_code == 410

        second = pair(client)
        assert "secret_hash" not in second["device"]
        assert "user_id" not in second["device"]
        devices = client.get("/companion/devices", headers=auth()).json()["devices"]
        assert len(devices) == 2
        assert [item["active"] for item in devices].count(True) == 1
        assert next(item for item in devices if item["active"])["device_id"] == second["device"]["device_id"]
        assert all("secret_hash" not in item for item in devices)


def test_expired_pair_code_is_rejected() -> None:
    with make_live_client(companion_pair_code_ttl_seconds=-1) as client:
        start = client.post("/companion/pair/start", headers=auth()).json()
        response = client.post(
            "/companion/pair/complete",
            json={
                "pair_code": start["pair_code"],
                "device_name": "PC expirado",
                "app_version": "2.0.0",
                "protocol_version": 1,
            },
        )
        assert response.status_code == 410


def test_command_payload_is_typed_idempotent_and_scoped() -> None:
    with make_live_client() as client:
        paired = pair(client)
        device_id = paired["device"]["device_id"]
        invalid = client.post(
            "/live/commands",
            headers=auth(),
            json={
                "command_id": "invalid-command",
                "command": "party.join_queue",
                "payload": {"url": "https://example.invalid", "method": "DELETE"},
            },
        )
        assert invalid.status_code == 422

        payload = {
            "command_id": "same-command-id",
            "command": "party.join_queue",
            "payload": {},
        }
        first = client.post("/live/commands", headers=auth(), json=payload)
        second = client.post("/live/commands", headers=auth(), json=payload)
        assert first.status_code == second.status_code == 200
        assert first.json()["command"]["command_id"] == second.json()["command"]["command_id"]
        assert first.json()["command"]["status"] == "queued"
        assert first.json()["command"]["expires_at"] == second.json()["command"]["expires_at"]

        pair(client, "other-user")
        other_user = client.post("/live/commands", headers=auth("other-user"), json=payload)
        assert other_user.status_code == 409
        assert client.delete(f"/companion/devices/{device_id}", headers=auth("other-user")).json() == {"revoked": False}


def test_companion_websocket_publishes_real_snapshot_and_results() -> None:
    with make_live_client() as client:
        paired = pair(client)
        device = paired["device"]
        headers = {
            "X-Companion-ID": device["device_id"],
            "X-Companion-Secret": paired["device_secret"],
        }
        with client.websocket_connect("/ws/live?access_token=dev:live-user") as mobile:
            assert mobile.receive_json()["phase"] == "offline"
            with client.websocket_connect("/ws/companion", headers=headers) as companion:
                ready = companion.receive_json()
                assert ready["type"] == "ready"
                assert ready["next_revision"] == 1
                companion.send_json(
                    {
                        "type": "state",
                        "revision": 1,
                        "phase": "queue",
                        "state": {
                            "queue": {"id": "swiftplay", "elapsed_seconds": 19},
                            "available_agents": [
                                {
                                    "id": "9f0d8ba9-4140-b941-57d3-a7ad57c6b417",
                                    "name": "Brimstone",
                                }
                            ],
                            "access_token": "must-never-leave-the-pc",
                            "capabilities": {"match_accept": False},
                        },
                    }
                )
                snapshot = mobile.receive_json()
                assert snapshot["phase"] == "queue"
                assert snapshot["state"]["queue"]["id"] == "swiftplay"
                assert snapshot["state"]["available_agents"][0]["id"] == "9f0d8ba9-4140-b941-57d3-a7ad57c6b417"
                assert "access_token" not in snapshot["state"]

                queued = client.post(
                    "/live/commands",
                    headers=auth(),
                    json={
                        "command_id": "websocket-command",
                        "command": "party.leave_queue",
                        "payload": {},
                    },
                )
                assert queued.status_code == 200
                command_message = companion.receive_json()
                assert command_message["command"]["command"] == "party.leave_queue"
                companion.send_json(
                    {
                        "type": "command_result",
                        "command_id": "websocket-command",
                        "status": "succeeded",
                        "result": {"observed": True},
                    }
                )
                result = mobile.receive_json()
                while result.get("command", {}).get("status") != "succeeded":
                    result = mobile.receive_json()
                assert result["command"]["result"] == {"observed": True}
        with client.websocket_connect("/ws/companion", headers=headers) as companion:
            ready = companion.receive_json()
            assert ready["next_revision"] == 2


def test_companion_refreshes_linked_riot_session_without_exposing_tokens() -> None:
    with make_live_client() as client:
        paired = pair(client)
        services = client.app.state.services
        now = datetime.now(UTC)
        old_payload = RiotCredentialPayload(
            ssid="persisted-ssid",
            cookies={"ssid": "persisted-ssid", "clid": "persisted-client"},
            access_token="old-access-token-with-enough-length",
            entitlement_token="old-entitlement-with-enough-length",
            puuid="linked-puuid",
            region="br",
            shard="na",
            client_version="release-old",
            game_name="Linked",
            tag_line="BR1",
        )

        async def seed() -> None:
            await services.repo.upsert_riot_account(
                RiotAccount(
                    user_id="live-user",
                    puuid="linked-puuid",
                    game_name="Linked",
                    tag_line="BR1",
                    region="br",
                    shard="na",
                    client_version="release-old",
                    linked_at=now,
                )
            )
            await services.repo.upsert_riot_credentials(
                RiotCredentialRecord(
                    user_id="live-user",
                    encrypted_payload=services.crypto.encrypt_json(old_payload.model_dump()),
                    last_refresh_at=now,
                    updated_at=now,
                )
            )

        asyncio.run(seed())
        access_token = jwt.encode(
            {"exp": now + timedelta(hours=1)}, "desktop-session", algorithm="HS256"
        )
        headers = {
            "X-Companion-ID": paired["device"]["device_id"],
            "X-Companion-Secret": paired["device_secret"],
        }
        with client.websocket_connect("/ws/live?access_token=dev:live-user") as mobile:
            mobile.receive_json()
            with client.websocket_connect("/ws/companion", headers=headers) as companion:
                companion.receive_json()
                companion.send_json(
                    {
                        "type": "riot_session_refresh",
                        "riot": {
                            "access_token": access_token,
                            "entitlement_token": "fresh-entitlement-token-from-local-client",
                            "puuid": "linked-puuid",
                            "region": "br",
                            "shard": "na",
                            "client_version": "release-current",
                        },
                    }
                )
                result = companion.receive_json()
                assert result["status"] == "succeeded"
                event = mobile.receive_json()
                assert event["type"] == "riot_session"
                assert event["valid"] is True
                assert "access_token" not in event
                assert "entitlement_token" not in event

        record = asyncio.run(services.repo.get_riot_credentials("live-user"))
        stored = services.crypto.decrypt_json(record.encrypted_payload)
        assert stored["access_token"] == access_token
        assert stored["ssid"] == "persisted-ssid"
        assert stored["cookies"]["clid"] == "persisted-client"
        assert record.expires_hint is not None

        with client.websocket_connect("/ws/companion", headers=headers) as companion:
            companion.receive_json()
            companion.send_json(
                {
                    "type": "riot_session_refresh",
                    "riot": {
                        "access_token": access_token,
                        "entitlement_token": "fresh-entitlement-token-from-local-client",
                        "puuid": "different-puuid",
                        "region": "br",
                        "shard": "na",
                    },
                }
            )
            assert companion.receive_json()["status"] == "rejected"


def test_revoked_device_cannot_open_websocket() -> None:
    with make_live_client() as client:
        paired = pair(client)
        device_id = paired["device"]["device_id"]
        assert client.delete(f"/companion/devices/{device_id}", headers=auth()).json()["revoked"]
        try:
            with client.websocket_connect(
                "/ws/companion",
                headers={
                    "X-Companion-ID": device_id,
                    "X-Companion-Secret": paired["device_secret"],
                },
            ):
                raise AssertionError("revoked websocket was accepted")
        except WebSocketDisconnect as error:
            assert error.code == 4401


def test_mobile_websocket_without_token_is_rejected_cleanly() -> None:
    with make_live_client() as client:
        try:
            with client.websocket_connect("/ws/live"):
                raise AssertionError("unauthenticated websocket was accepted")
        except WebSocketDisconnect as error:
            assert error.code == 4401
