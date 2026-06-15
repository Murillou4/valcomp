from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from ares_console.models import RiotContext

from .errors import RelinkRequiredError, RiotRequestError
from .repository import Repository
from .schemas import RiotCredentialPayload, RiotCredentialRecord
from .security import CryptoService
from .settings import BackendSettings


REGION_TO_SHARD = {
    "na": "na",
    "latam": "na",
    "br": "na",
    "eu": "eu",
    "ap": "ap",
    "kr": "kr",
}


@dataclass(slots=True)
class RiotSession:
    access_token: str
    entitlement_token: str
    puuid: str
    region: str
    shard: str
    client_version: str
    client_platform: str
    id_token: str = ""
    game_name: str = ""
    tag_line: str = ""

    def to_console_context(self) -> RiotContext:
        return RiotContext(
            online=True,
            status="remote",
            token=self.access_token,
            entitlement=self.entitlement_token,
            puuid=self.puuid,
            region=self.region,
            shard=self.shard,
            client_version=self.client_version,
            client_platform=self.client_platform,
        )


class RiotAuthService:
    def __init__(
        self,
        settings: BackendSettings,
        crypto: CryptoService,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.crypto = crypto
        self.client = client or httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": ""},
        )

    async def session_for_user(self, user_id: str, repo: Repository) -> RiotSession:
        record = await repo.get_riot_credentials(user_id)
        if not record:
            raise RelinkRequiredError("Riot account is not linked.")
        payload = RiotCredentialPayload(**self.crypto.decrypt_json(record.encrypted_payload))
        if payload.access_token and payload.entitlement_token and payload.puuid:
            return self._session_from_payload(payload)
        refreshed = await self.refresh_payload(payload)
        await self._save_refreshed(user_id, repo, refreshed)
        return self._session_from_payload(refreshed)

    async def refresh_payload(self, payload: RiotCredentialPayload) -> RiotCredentialPayload:
        ssid = payload.ssid or payload.cookies.get("ssid", "")
        if not ssid:
            raise RelinkRequiredError("Riot reauth cookie is missing; relink required.")
        auth_data = await self._reauth_with_ssid(ssid)
        access_token = auth_data.get("access_token", "")
        id_token = auth_data.get("id_token", "")
        if not access_token:
            raise RelinkRequiredError("Riot reauth did not return an access token.")

        entitlement = await self._fetch_entitlement(access_token)
        userinfo = await self._fetch_userinfo(access_token)
        region, shard = await self._fetch_region(access_token, id_token)

        account = userinfo.get("acct", {}) if isinstance(userinfo, dict) else {}
        return payload.model_copy(
            update={
                "access_token": access_token,
                "id_token": id_token,
                "entitlement_token": entitlement,
                "puuid": str(userinfo.get("sub") or payload.puuid),
                "region": region or payload.region,
                "shard": shard or payload.shard,
                "client_version": payload.client_version or self.settings.default_client_version,
                "game_name": str(account.get("game_name") or payload.game_name or ""),
                "tag_line": str(account.get("tag_line") or payload.tag_line or ""),
            }
        )

    def _session_from_payload(self, payload: RiotCredentialPayload) -> RiotSession:
        region = payload.region.lower()
        shard = (payload.shard or REGION_TO_SHARD.get(region, "")).lower()
        if not payload.access_token or not payload.entitlement_token or not payload.puuid:
            raise RelinkRequiredError("Riot credential payload is incomplete.")
        if not region or not shard:
            raise RelinkRequiredError("Riot region/shard are missing; relink required.")
        return RiotSession(
            access_token=payload.access_token,
            entitlement_token=payload.entitlement_token,
            puuid=payload.puuid,
            region=region,
            shard=shard,
            client_version=payload.client_version or self.settings.default_client_version,
            client_platform=self.settings.riot_client_platform,
            id_token=payload.id_token,
            game_name=payload.game_name,
            tag_line=payload.tag_line,
        )

    async def _save_refreshed(
        self, user_id: str, repo: Repository, payload: RiotCredentialPayload
    ) -> None:
        await repo.upsert_riot_credentials(
            RiotCredentialRecord(
                user_id=user_id,
                encrypted_payload=self.crypto.encrypt_json(payload.model_dump()),
                last_refresh_at=datetime.now(UTC),
                expires_hint=None,
                updated_at=datetime.now(UTC),
            )
        )

    async def _reauth_with_ssid(self, ssid: str) -> dict[str, str]:
        response = await self.client.get(
            "https://auth.riotgames.com/authorize",
            params={
                "redirect_uri": "https://playvalorant.com/opt_in",
                "client_id": "play-valorant-web-prod",
                "response_type": "token id_token",
                "nonce": "1",
                "scope": "account openid",
            },
            headers={"Cookie": f"ssid={ssid}", "User-Agent": ""},
        )
        location = response.headers.get("location", "")
        if not location:
            raise RelinkRequiredError("Riot reauth failed; no redirect location.")
        parsed = urlparse(location)
        fragment = parse_qs(parsed.fragment)
        return {key: values[0] for key, values in fragment.items() if values}

    async def _fetch_entitlement(self, access_token: str) -> str:
        response = await self.client.post(
            "https://entitlements.auth.riotgames.com/api/token/v1",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={},
        )
        response.raise_for_status()
        return str(response.json().get("entitlements_token") or "")

    async def _fetch_userinfo(self, access_token: str) -> dict[str, Any]:
        response = await self.client.get(
            "https://auth.riotgames.com/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": ""},
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def _fetch_region(self, access_token: str, id_token: str) -> tuple[str, str]:
        if not id_token:
            return "", ""
        response = await self.client.put(
            "https://riot-geo.pas.si.riotgames.com/pas/v1/product/valorant",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": ""},
            json={"id_token": id_token},
        )
        response.raise_for_status()
        region = str(response.json().get("affinities", {}).get("live") or "").lower()
        return region, REGION_TO_SHARD.get(region, "")


class RiotRemoteClient:
    def __init__(self, settings: BackendSettings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            trust_env=False,
            headers={"User-Agent": ""},
        )

    def headers(self, session: RiotSession, *, include_client_version: bool = True) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "X-Riot-Entitlements-JWT": session.entitlement_token,
            "X-Riot-ClientPlatform": session.client_platform,
            "User-Agent": "",
        }
        if include_client_version and session.client_version:
            headers["X-Riot-ClientVersion"] = session.client_version.replace(
                "shipping-shipping-", "shipping-"
            )
        return headers

    async def request_json(
        self,
        method: str,
        url: str,
        session: RiotSession,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> Any:
        response = await self.client.request(
            method,
            url,
            headers=self.headers(session),
            json=json_body,
            params=params,
        )
        if response.status_code in {401, 403}:
            raise RelinkRequiredError("Riot token was rejected; relink required.")
        if not response.is_success:
            raise RiotRequestError(
                f"Riot returned HTTP {response.status_code}.",
                riot_status=response.status_code,
            )
        if not response.content:
            return {} if allow_empty else None
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise RiotRequestError("Riot response was not JSON.") from exc

    async def storefront(self, session: RiotSession) -> dict[str, Any]:
        base = f"https://pd.{session.shard}.a.pvp.net"
        v3_url = f"{base}/store/v3/storefront/{session.puuid}"
        try:
            data = await self.request_json("POST", v3_url, session, json_body={}, allow_empty=True)
            if isinstance(data, dict) and data:
                data["_source_version"] = "v3"
                return data
        except RiotRequestError as exc:
            if exc.riot_status not in {404, 405}:
                raise
        v2_url = f"{base}/store/v2/storefront/{session.puuid}"
        data = await self.request_json("GET", v2_url, session, allow_empty=True)
        if isinstance(data, dict):
            data["_source_version"] = "v2"
            return data
        return {}

    async def wallet(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/store/v1/wallet/{session.puuid}",
            session,
        )

    async def inventory(self, session: RiotSession, item_type_id: str = "") -> dict[str, Any]:
        suffix = f"/{item_type_id}" if item_type_id else ""
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/store/v1/entitlements/{session.puuid}{suffix}",
            session,
        )

    async def offers(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/store/v1/offers/",
            session,
            allow_empty=True,
        )

    async def account_xp(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/account-xp/v1/players/{session.puuid}",
            session,
        )

    async def mmr(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/mmr/v1/players/{session.puuid}",
            session,
            allow_empty=True,
        )

    async def matches(self, session: RiotSession) -> dict[str, Any]:
        return await self.match_history(session, start_index=0, end_index=20)

    async def match_history(
        self, session: RiotSession, *, start_index: int = 0, end_index: int = 20
    ) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/match-history/v1/history/{session.puuid}",
            session,
            params={"startIndex": start_index, "endIndex": end_index},
        )

    async def loadout(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/personalization/v2/players/{session.puuid}/playerloadout",
            session,
        )

    async def content(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://shared.{session.shard}.a.pvp.net/content-service/v3/content",
            session,
        )

    async def contracts(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/contracts/v1/contracts/{session.puuid}",
            session,
            allow_empty=True,
        )

    async def item_upgrades(self, session: RiotSession) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/contract-definitions/v3/item-upgrades",
            session,
            allow_empty=True,
        )
