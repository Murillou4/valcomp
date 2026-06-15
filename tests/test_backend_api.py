import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi.testclient import TestClient

from ares_backend.app import create_app
from ares_backend.repository import InMemoryRepository
from ares_backend.riot import RiotSession
from ares_backend.schemas import RiotAccount, RiotCredentialPayload, RiotCredentialRecord
from ares_backend.security import CryptoService
from ares_backend.settings import BackendSettings
from ares_backend.store import VP_CURRENCY_ID


class FakeRiotAuth:
    async def session_for_user(self, user_id: str, repo: InMemoryRepository) -> RiotSession:
        return RiotSession(
            access_token="access",
            entitlement_token="entitlement",
            puuid="puuid-123",
            region="br",
            shard="na",
            client_version="release-test",
            client_platform="platform",
            game_name="Player",
            tag_line="BR1",
        )


class FakeRiotClient:
    async def storefront(self, session: RiotSession) -> dict[str, Any]:
        return {
            "_source_version": "v3",
            "SkinsPanelLayout": {
                "SingleItemOffers": ["skin-daily"],
                "SingleItemOffersRemainingDurationInSeconds": 900,
            },
            "Offers": [{"OfferID": "skin-daily", "Cost": {VP_CURRENCY_ID: 1775}}],
            "BonusStore": {
                "BonusStoreOffers": [
                    {
                        "BonusOfferID": "bonus-daily",
                        "Offer": {
                            "OfferID": "skin-daily",
                            "Cost": {VP_CURRENCY_ID: 1775},
                            "Rewards": [{"ItemID": "skin-daily"}],
                        },
                        "DiscountPercent": 31,
                        "DiscountCosts": {VP_CURRENCY_ID: 1225},
                        "IsSeen": False,
                    }
                ],
                "BonusStoreRemainingDurationInSeconds": 7200,
            },
        }

    async def wallet(self, session: RiotSession) -> dict[str, Any]:
        return {"Balances": {VP_CURRENCY_ID: 3000}}

    async def inventory(self, session: RiotSession, item_type_id: str = "") -> dict[str, Any]:
        return {"EntitlementsByTypes": [{"Entitlements": [{"ItemID": "skin-owned"}]}]}

    async def offers(self, session: RiotSession) -> dict[str, Any]:
        return {"Offers": [{"OfferID": "skin-daily"}]}

    async def account_xp(self, session: RiotSession) -> dict[str, Any]:
        return {"Progress": {"Level": 100}}

    async def mmr(self, session: RiotSession) -> dict[str, Any]:
        return {"QueueSkills": {}}

    async def match_history(
        self, session: RiotSession, *, start_index: int = 0, end_index: int = 20
    ) -> dict[str, Any]:
        return {"History": [], "startIndex": start_index, "endIndex": end_index}

    async def match_details(
        self, session: RiotSession, match_id: str
    ) -> dict[str, Any]:
        return {
            "matchInfo": {
                "matchId": match_id,
                "mapId": "/Game/Maps/Ascent/Ascent",
                "queueID": "competitive",
                "isRanked": True,
                "isCompleted": True,
                "completionState": "Completed",
                "gameStartMillis": 1_700_000_000_000,
                "gameLengthMillis": 2_100_000,
            },
            "players": [
                {
                    "subject": session.puuid,
                    "gameName": "Player",
                    "tagLine": "BR1",
                    "teamId": "Blue",
                    "characterId": "agent-jett",
                    "competitiveTier": 16,
                    "accountLevel": 100,
                    "isObserver": False,
                    "stats": {
                        "score": 5200,
                        "roundsPlayed": 20,
                        "kills": 24,
                        "deaths": 15,
                        "assists": 6,
                    },
                    "roundDamage": [{"round": 0, "receiver": "enemy", "damage": 180}],
                }
            ],
            "teams": [
                {
                    "teamId": "Blue",
                    "won": True,
                    "roundsPlayed": 20,
                    "roundsWon": 13,
                    "numPoints": 13,
                },
                {
                    "teamId": "Red",
                    "won": False,
                    "roundsPlayed": 20,
                    "roundsWon": 7,
                    "numPoints": 7,
                },
            ],
            "roundResults": [
                {
                    "roundNum": 0,
                    "winningTeam": "Blue",
                    "roundResult": "Eliminated",
                    "roundCeremony": "CeremonyDefault",
                    "plantSite": "",
                    "playerStats": [
                        {
                            "subject": session.puuid,
                            "damage": [
                                {
                                    "receiver": "enemy",
                                    "damage": 180,
                                    "headshots": 1,
                                    "bodyshots": 2,
                                    "legshots": 0,
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    async def loadout(self, session: RiotSession) -> dict[str, Any]:
        return {"Guns": []}

    async def contracts(self, session: RiotSession) -> dict[str, Any]:
        return {"Contracts": []}

    async def item_upgrades(self, session: RiotSession) -> dict[str, Any]:
        return {"Definitions": []}

    async def content(self, session: RiotSession) -> dict[str, Any]:
        return {"Seasons": []}


class FakePushClient:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.messages.extend(messages)
        return [
            {"status": "ok", "id": f"ticket-{index}"}
            for index, _ in enumerate(messages, start=len(self.messages))
        ]


class FakeAssets:
    async def list_items(
        self, category: str, repo: InMemoryRepository | None = None
    ) -> list[dict[str, Any]]:
        if category == "agents":
            return [
                {
                    "uuid": "agent-jett",
                    "displayName": "Jett",
                    "displayIcon": "https://assets.example/jett.png",
                }
            ]
        if category == "maps":
            return [
                {
                    "uuid": "map-ascent",
                    "displayName": "Ascent",
                    "mapUrl": "/Game/Maps/Ascent/Ascent",
                    "listViewIcon": "https://assets.example/ascent-list.png",
                    "splash": "https://assets.example/ascent.png",
                }
            ]
        if category == "weapons":
            return [
                {
                    "uuid": "weapon-vandal",
                    "displayName": "Vandal",
                    "displayIcon": "https://assets.example/vandal.png",
                    "category": "EEquippableCategory::Rifle",
                    "shopData": {"category": "Rifles"},
                    "skins": [
                        {
                            "uuid": "skin-daily-parent",
                            "displayName": "Vandal Daily Skin",
                            "displayIcon": "https://assets.example/icon.png",
                            "contentTierUuid": "premium",
                            "levels": [
                                {
                                    "uuid": "skin-daily",
                                    "displayName": "Vandal Daily Skin",
                                }
                            ],
                        }
                    ],
                }
            ]
        return [
            {
                "uuid": "skin-daily",
                "displayName": "Daily Skin",
                "displayIcon": "https://assets.example/icon.png",
                "fullRender": "https://assets.example/full.png",
                "contentTierUuid": "premium",
            }
        ]

    async def skin_catalog(
        self, repo: InMemoryRepository | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "item_id": "skin-daily",
                "skin_id": "skin-daily-parent",
                "name": "Vandal Daily Skin",
                "display_icon": "https://assets.example/icon.png",
                "wallpaper": "",
                "tier": "premium",
                "weapon_id": "weapon-vandal",
                "weapon_name": "Vandal",
                "weapon_icon": "https://assets.example/vandal.png",
                "category": "rifle",
                "category_name": "Fuzis",
            }
        ]

    async def get_item(
        self, item_id: str, repo: InMemoryRepository | None = None
    ) -> tuple[str, dict[str, Any] | None]:
        for item in await self.list_items("skins", repo):
            if item["uuid"] == item_id:
                return "skins", item
        return "", None

    async def resolve_store_item(
        self, item_id: str, repo: InMemoryRepository | None = None
    ) -> tuple[str, dict[str, Any] | None]:
        return await self.get_item(item_id, repo)

    async def canonical_store_item(
        self, item_id: str, repo: InMemoryRepository | None = None
    ) -> tuple[str, str, dict[str, Any] | None]:
        category, item = await self.get_item(item_id, repo)
        return category, item_id, item


def make_client() -> tuple[TestClient, InMemoryRepository, BackendSettings, FakePushClient]:
    settings = BackendSettings(
        app_secret_key="unit-test-secret",
        allow_dev_auth=True,
        default_client_version="release-test",
    )
    repo = InMemoryRepository()
    push = FakePushClient()
    app = create_app(
        settings=settings,
        repository=repo,
        riot_auth=FakeRiotAuth(),
        riot_client=FakeRiotClient(),
        assets=FakeAssets(),
        push_client=push,
    )
    return TestClient(app), repo, settings, push


def auth_headers(user_id: str = "mobile-user") -> dict[str, str]:
    return {"Authorization": f"Bearer dev:{user_id}"}


def seed_linked_user(
    repo: InMemoryRepository, settings: BackendSettings, user_id: str = "mobile-user"
) -> None:
    async def _seed() -> None:
        now = datetime.now(UTC)
        payload = RiotCredentialPayload(
            access_token="access",
            entitlement_token="entitlement",
            puuid="puuid-123",
            region="br",
            shard="na",
            client_version="release-test",
            game_name="Player",
            tag_line="BR1",
        )
        await repo.upsert_riot_account(
            RiotAccount(
                user_id=user_id,
                puuid=payload.puuid,
                game_name=payload.game_name,
                tag_line=payload.tag_line,
                region=payload.region,
                shard=payload.shard,
                client_version=payload.client_version,
                linked_at=now,
            )
        )
        await repo.upsert_riot_credentials(
            RiotCredentialRecord(
                user_id=user_id,
                encrypted_payload=CryptoService(settings.app_secret_key).encrypt_json(
                    payload.model_dump()
                ),
                last_refresh_at=now,
                expires_hint=None,
                updated_at=now,
            )
        )

    asyncio.run(_seed())


def test_password_auth_signup_login_and_session_verify() -> None:
    client, _, _, _ = make_client()

    signup = client.post(
        "/auth/signup",
        json={
            "email": "player@example.com",
            "password": "secret123",
            "display_name": "Player",
        },
    )
    assert signup.status_code == 200
    assert signup.json()["user"]["email"] == "player@example.com"
    assert signup.json()["email_confirmation_required"] is False
    token = signup.json()["session"]["access_token"]
    refresh_token = signup.json()["session"]["refresh_token"]

    verify = client.post("/auth/session/verify", headers={"Authorization": f"Bearer {token}"})
    assert verify.status_code == 200
    assert verify.json()["profile"]["display_name"] == "Player"

    login = client.post(
        "/auth/login",
        json={"email": "player@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["session"]["access_token"] != token

    refresh = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 200
    assert refresh.json()["session"]["access_token"]


def test_link_start_complete_and_me_flow() -> None:
    client, _, _, _ = make_client()

    start = client.post("/riot/link/start", headers=auth_headers())
    assert start.status_code == 200
    code = start.json()["link_code"]

    complete = client.post(
        "/riot/link/complete",
        json={
            "link_code": code,
            "riot": {
                "access_token": "access",
                "entitlement_token": "entitlement",
                "puuid": "puuid-123",
                "region": "br",
                "shard": "na",
                "client_version": "release-test",
                "game_name": "Player",
                "tag_line": "BR1",
            },
        },
    )

    assert complete.status_code == 200
    assert complete.json()["riot_account"]["puuid"] == "puuid-123"
    me = client.get("/me", headers=auth_headers())
    assert me.json()["riot_account"]["game_name"] == "Player"


def test_link_complete_rejects_expired_riot_access_token() -> None:
    client, _, _, _ = make_client()
    expired_token = jwt.encode(
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        "unused-test-key",
        algorithm="HS256",
    )

    start = client.post("/riot/link/start", headers=auth_headers())
    assert start.status_code == 200

    complete = client.post(
        "/riot/link/complete",
        json={
            "link_code": start.json()["link_code"],
            "riot": {
                "access_token": expired_token,
                "entitlement_token": "entitlement",
                "puuid": "puuid-123",
                "region": "br",
                "shard": "na",
                "client_version": "release-test",
            },
        },
    )

    assert complete.status_code == 409
    assert complete.json()["error"]["code"] == "relink_required"


def test_daily_store_wallet_items_and_status_routes() -> None:
    client, repo, settings, _ = make_client()
    seed_linked_user(repo, settings)

    daily = client.get("/valorant/store/daily", headers=auth_headers())
    assert daily.status_code == 200
    assert daily.json()["items"][0]["name"] == "Daily Skin"
    assert daily.json()["items"][0]["price"] == 1775
    assert daily.json()["night_market_active"] is True
    assert daily.json()["night_market"][0]["price"] == 1225

    night_market = client.get("/valorant/store/night-market", headers=auth_headers())
    assert night_market.status_code == 200
    assert night_market.json()["active"] is True
    assert night_market.json()["seconds_remaining"] == 7200
    assert night_market.json()["items"][0]["original_price"] == 1775
    assert night_market.json()["items"][0]["discount_percent"] == 31

    wallet = client.get("/valorant/store/wallet", headers=auth_headers())
    assert wallet.json()["Balances"][VP_CURRENCY_ID] == 3000

    items = client.get("/valorant/items/skins", headers=auth_headers())
    assert items.json()["items"][0]["uuid"] == "skin-daily"

    status = client.get("/valorant/items/skin-daily/status", headers=auth_headers())
    assert status.json()["owned"] is False
    assert status.json()["in_daily_store"] is True
    assert status.json()["price"] == 1775


def test_skin_catalog_has_real_weapon_filters() -> None:
    client, _, _, _ = make_client()
    catalog = client.get(
        "/valorant/skins/catalog?category=rifle&weapon=weapon-vandal&q=vandal",
        headers=auth_headers(),
    )
    assert catalog.status_code == 200
    payload = catalog.json()
    assert payload["total"] == 1
    assert payload["items"][0]["item_id"] == "skin-daily"
    assert payload["items"][0]["weapon_name"] == "Vandal"
    assert payload["items"][0]["category_name"] == "Fuzis"
    assert payload["filters"]["weapons"][0]["id"] == "weapon-vandal"


def test_match_details_are_normalized_for_mobile() -> None:
    client, repo, settings, _ = make_client()
    seed_linked_user(repo, settings)

    response = client.get(
        "/valorant/player/matches/match-current",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["match"]["map_name"] == "Ascent"
    assert payload["match"]["duration_seconds"] == 2100
    assert payload["self"]["agent_name"] == "Jett"
    assert payload["self"]["stats"]["kills"] == 24
    assert payload["self"]["stats"]["headshot_percent"] == 33.3
    assert payload["teams"][0]["rounds_won"] == 13


def test_routes_list_and_non_remote_execution_are_structured() -> None:
    client, repo, settings, _ = make_client()
    seed_linked_user(repo, settings)

    routes = client.get("/valorant/routes", headers=auth_headers()).json()
    assert routes["total"] == 82
    assert routes["counts"]["remote_supported"] > 0
    assert routes["counts"]["local_only"] > 0

    local = client.post(
        "/valorant/routes/sendChatEndpoint",
        headers=auth_headers(),
        json={"body": {"message": "oi"}},
    )
    assert local.status_code == 200
    assert local.json()["executed"] is False
    assert local.json()["error"]["code"] == "requires_live_client"

    mutation = client.post(
        "/valorant/routes/activateContractEndpoint",
        headers=auth_headers(),
        json={"variables": {"contract id": "contract"}},
    )
    assert mutation.json()["executed"] is False
    assert mutation.json()["error"]["code"] == "unsafe_mutation_blocked"


def test_skin_watchlist_sends_daily_store_notification_once() -> None:
    client, repo, settings, push = make_client()
    seed_linked_user(repo, settings)

    device = client.post(
        "/notifications/devices",
        headers=auth_headers(),
        json={
            "push_token": "fcm-unit-test-token-12345678901234567890",
            "provider": "fcm",
            "platform": "android",
            "device_name": "Pixel test",
            "app_version": "1.0.0",
        },
    )
    assert device.status_code == 200
    assert "push_token" not in device.json()["device"]
    assert device.json()["device"]["masked_token"].startswith("fcm-unit-test-")

    watch = client.post(
        "/valorant/skins/watchlist",
        headers=auth_headers(),
        json={"item_id": "skin-daily"},
    )
    assert watch.status_code == 200
    assert watch.json()["item"]["item_name"] == "Daily Skin"

    first_daily = client.get("/valorant/store/daily", headers=auth_headers()).json()
    assert first_daily["alerts"]["sent_count"] == 1
    assert first_daily["alerts"]["matched"][0]["item_id"] == "skin-daily"
    assert len(push.messages) == 1
    assert push.messages[0]["data"]["itemId"] == "skin-daily"

    second_daily = client.get("/valorant/store/daily", headers=auth_headers()).json()
    assert second_daily["alerts"]["sent_count"] == 0
    assert second_daily["alerts"]["matched"][0]["already_notified"] is True
    assert len(push.messages) == 1

    deliveries = client.get("/notifications/deliveries", headers=auth_headers()).json()
    assert deliveries["deliveries"][0]["status"] == "sent"


def test_authenticated_user_can_send_push_test_to_own_device() -> None:
    client, _, _, push = make_client()
    blocked = client.post("/notifications/test")
    assert blocked.status_code == 401

    empty = client.post("/notifications/test", headers=auth_headers())
    assert empty.status_code == 200
    assert empty.json()["device_count"] == 0

    client.post(
        "/notifications/devices",
        headers=auth_headers(),
        json={
            "push_token": "fcm-test-device-token-12345678901234567890",
            "provider": "fcm",
            "platform": "android",
        },
    )
    result = client.post("/notifications/test", headers=auth_headers())
    assert result.status_code == 200
    assert result.json()["sent_count"] == 1
    assert len(push.messages) == 1
    assert push.messages[0]["data"]["type"] == "push_test"


def test_store_alert_job_is_protected_and_runs_watchlists() -> None:
    client, repo, settings, push = make_client()
    settings.job_secret_token = "job-secret"
    seed_linked_user(repo, settings)
    client.post(
        "/notifications/devices",
        headers=auth_headers(),
        json={
            "push_token": "fcm-job-token-123456789012345678901234",
            "provider": "fcm",
        },
    )
    client.post(
        "/valorant/skins/watchlist",
        headers=auth_headers(),
        json={"item_id": "skin-daily"},
    )

    blocked = client.post("/jobs/store-alerts/run")
    assert blocked.status_code == 401

    result = client.post("/jobs/store-alerts/run", headers={"X-Job-Token": "job-secret"})
    assert result.status_code == 200
    assert result.json()["checked_users"] == 1
    assert result.json()["sent_count"] == 1
    assert len(push.messages) == 1


def test_diagnostics_are_sanitized_scoped_and_exportable() -> None:
    client, _, settings, _ = make_client()
    settings.job_secret_token = "job-secret"

    created = client.post(
        "/diagnostics/events",
        headers=auth_headers(),
        json={
            "source": "mobile",
            "level": "error",
            "category": "api_error",
            "message": "Falhou para player@example.com com Bearer super-secret-token-value",
            "context": {
                "path": "/valorant/store/daily",
                "access_token": "never-store-this",
                "puuid": "00000000-0000-4000-8000-000000000000",
            },
            "request_id": "mob-request-123",
            "app_version": "1.0.2+3",
            "device_id": "physical-device-id",
        },
    )
    assert created.status_code == 200
    assert created.headers["x-request-id"]

    listed = client.get("/diagnostics/events", headers=auth_headers()).json()["events"]
    assert len(listed) == 1
    event = listed[0]
    assert event["context"]["access_token"] == "[REDACTED]"
    assert event["context"]["puuid"] == "[REDACTED]"
    assert event["device_id"].startswith("sha256:")
    assert "player@example.com" not in event["message"]
    assert "super-secret-token-value" not in event["message"]
    assert "user_id" not in event

    blocked = client.get("/jobs/diagnostics/export")
    assert blocked.status_code == 401
    exported = client.get(
        "/jobs/diagnostics/export",
        headers={"X-Job-Token": "job-secret"},
    )
    assert exported.status_code == 200
    mobile_event = next(
        event for event in exported.json()["events"] if event["source"] == "mobile"
    )
    assert mobile_event["user"]
