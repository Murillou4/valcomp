from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt

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

RIOT_CLIENT_AUTH_PARAMS = {
    "redirect_uri": "http://localhost/redirect",
    "client_id": "riot-client",
    "response_type": "token id_token",
    "nonce": "1",
    "scope": "openid link ban lol_region account",
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
        complete = bool(
            payload.access_token and payload.entitlement_token and payload.puuid
        )
        if complete and not access_token_needs_refresh(
            payload.access_token,
            leeway_seconds=self.settings.riot_token_proactive_refresh_seconds,
        ):
            return self._session_from_payload(payload)
        try:
            refreshed = await self.refresh_payload(payload)
        except RelinkRequiredError:
            if complete and not access_token_needs_refresh(payload.access_token):
                return self._session_from_payload(payload)
            raise
        await self._save_refreshed(user_id, repo, refreshed)
        return self._session_from_payload(refreshed)

    async def refresh_payload(self, payload: RiotCredentialPayload) -> RiotCredentialPayload:
        ssid = payload.ssid or payload.cookies.get("ssid", "")
        if not ssid:
            raise RelinkRequiredError("Riot reauth cookie is missing; relink required.")
        auth_data = await self._reauth_with_ssid(ssid, payload.cookies)
        access_token = auth_data.get("access_token", "")
        id_token = auth_data.get("id_token", "")
        if not access_token:
            raise RelinkRequiredError("Riot reauth did not return an access token.")

        entitlement = await self._fetch_entitlement(access_token)
        userinfo = await self._fetch_userinfo(access_token)
        region, shard = await self._fetch_region(access_token, id_token)

        account = userinfo.get("acct", {}) if isinstance(userinfo, dict) else {}
        refreshed_cookies = {
            **payload.cookies,
            **{
                str(key): str(value)
                for key, value in auth_data.get("cookies", {}).items()
                if str(key) and str(value)
            },
        }
        refreshed_ssid = refreshed_cookies.get("ssid") or ssid
        if refreshed_ssid:
            refreshed_cookies["ssid"] = refreshed_ssid
        return payload.model_copy(
            update={
                "ssid": refreshed_ssid,
                "cookies": refreshed_cookies,
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

    async def payload_from_web_login(
        self,
        *,
        access_token: str,
        id_token: str = "",
        entitlement_token: str = "",
        puuid: str = "",
        region: str = "",
        shard: str = "",
        game_name: str = "",
        tag_line: str = "",
        ssid: str = "",
        cookies: dict[str, str] | None = None,
        client_version: str = "",
    ) -> RiotCredentialPayload:
        cookie_map = {
            str(key): str(value)
            for key, value in (cookies or {}).items()
            if str(key) and str(value)
        }
        clean_ssid = ssid or cookie_map.get("ssid", "")
        if clean_ssid:
            cookie_map["ssid"] = clean_ssid

        supplied_payload = self._payload_from_supplied_web_session(
            access_token=access_token,
            id_token=id_token,
            entitlement_token=entitlement_token,
            puuid=puuid,
            region=region,
            shard=shard,
            game_name=game_name,
            tag_line=tag_line,
            ssid=clean_ssid,
            cookies=cookie_map,
            client_version=client_version,
        )
        if supplied_payload is not None:
            return supplied_payload

        if access_token_needs_refresh(access_token, leeway_seconds=300):
            if not clean_ssid:
                raise RelinkRequiredError("A sessão Riot retornada pelo login já veio expirada.")
            auth_data = await self._reauth_with_ssid(clean_ssid, cookie_map)
            access_token = auth_data.get("access_token", "")
            id_token = auth_data.get("id_token", id_token)

        try:
            return await self._payload_from_web_tokens(
                access_token=access_token,
                id_token=id_token,
                ssid=clean_ssid,
                cookies=cookie_map,
                client_version=client_version,
            )
        except RelinkRequiredError:
            raise

    def _payload_from_supplied_web_session(
        self,
        *,
        access_token: str,
        id_token: str,
        entitlement_token: str,
        puuid: str,
        region: str,
        shard: str,
        game_name: str,
        tag_line: str,
        ssid: str,
        cookies: dict[str, str],
        client_version: str,
    ) -> RiotCredentialPayload | None:
        clean_region = region.strip().lower()
        clean_shard = (shard.strip().lower() or REGION_TO_SHARD.get(clean_region, ""))
        if not (entitlement_token and puuid and clean_region and clean_shard):
            return None
        if access_token_needs_refresh(access_token, leeway_seconds=300):
            return None
        return RiotCredentialPayload(
            ssid=ssid,
            cookies=cookies,
            access_token=access_token,
            id_token=id_token,
            entitlement_token=entitlement_token,
            puuid=puuid,
            region=clean_region,
            shard=clean_shard,
            client_version=client_version or self.settings.default_client_version,
            game_name=game_name,
            tag_line=tag_line,
        )

    async def _payload_from_web_tokens(
        self,
        *,
        access_token: str,
        id_token: str,
        ssid: str,
        cookies: dict[str, str],
        client_version: str,
    ) -> RiotCredentialPayload:
        if access_token_needs_refresh(access_token, leeway_seconds=300):
            raise RelinkRequiredError("A sessão Riot retornada pelo login já veio expirada.")
        entitlement = await self._fetch_entitlement(access_token)
        userinfo = await self._fetch_userinfo(access_token)
        region, shard = await self._fetch_region(access_token, id_token)
        account = userinfo.get("acct", {}) if isinstance(userinfo, dict) else {}
        return RiotCredentialPayload(
            ssid=ssid,
            cookies=cookies,
            access_token=access_token,
            id_token=id_token,
            entitlement_token=entitlement,
            puuid=str(userinfo.get("sub") or ""),
            region=region,
            shard=shard,
            client_version=client_version or self.settings.default_client_version,
            game_name=str(account.get("game_name") or ""),
            tag_line=str(account.get("tag_line") or ""),
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
                expires_hint=access_token_expiration(payload.access_token),
                updated_at=datetime.now(UTC),
            )
        )

    async def _reauth_with_ssid(
        self, ssid: str, cookies: dict[str, str] | None = None
    ) -> dict[str, Any]:
        cookie_header = _cookie_header(ssid, cookies)
        response = await self.client.get(
            "https://auth.riotgames.com/authorize",
            params=RIOT_CLIENT_AUTH_PARAMS,
            headers={"Cookie": cookie_header, "User-Agent": ""},
        )
        if response.status_code in {401, 403}:
            raise RelinkRequiredError("O cookie de renovação da Riot não é mais válido.")
        location = _riot_auth_redirect(response)
        if not location:
            raise RelinkRequiredError(
                "A Riot não aceitou a renovação silenciosa desta sessão."
            )
        parsed = urlparse(location)
        parameters = {**parse_qs(parsed.query), **parse_qs(parsed.fragment)}
        data: dict[str, Any] = {
            key: values[0] for key, values in parameters.items() if values
        }
        if not data.get("access_token"):
            raise RelinkRequiredError("Riot reauth did not return an access token.")
        data["cookies"] = {
            str(key): str(value)
            for key, value in response.cookies.items()
            if str(key) and str(value)
        }
        return data

    async def _fetch_entitlement(self, access_token: str) -> str:
        response = await self.client.post(
            "https://entitlements.auth.riotgames.com/api/token/v1",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={},
        )
        _raise_for_riot_auth(response, "buscar entitlement")
        return str(response.json().get("entitlements_token") or "")

    async def _fetch_userinfo(self, access_token: str) -> dict[str, Any]:
        response = await self.client.get(
            "https://auth.riotgames.com/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": ""},
        )
        _raise_for_riot_auth(response, "buscar dados da conta")
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
        _raise_for_riot_auth(response, "buscar região da conta")
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
        self._resolved_client_version = ""
        self._client_version_refresh_after: datetime | None = None

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
        if not session.client_version:
            await self._refresh_client_version(session)
        response = await self.client.request(
            method,
            url,
            headers=self.headers(session),
            json=json_body,
            params=params,
        )
        error_code = riot_error_code(response)
        if error_code == "INVALID_HEADERS":
            await self._refresh_client_version(session, force=True)
            response = await self.client.request(
                method,
                url,
                headers=self.headers(session),
                json=json_body,
                params=params,
            )
            error_code = riot_error_code(response)
        if response.status_code in {401, 403} or error_code == "BAD_CLAIMS":
            raise RelinkRequiredError(
                "Sua sessão Riot expirou. Abra o companion no PC para vincular novamente."
            )
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

    async def _refresh_client_version(
        self, session: RiotSession, *, force: bool = False
    ) -> None:
        now = datetime.now(UTC)
        if (
            not force
            and self._resolved_client_version
            and self._client_version_refresh_after is not None
            and now < self._client_version_refresh_after
        ):
            session.client_version = self._resolved_client_version
            return

        try:
            response = await self.client.get("https://valorant-api.com/v1/version")
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            version = str(data.get("riotClientVersion", "")).strip()
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError):
            version = ""

        if not version:
            version = (session.client_version or self.settings.default_client_version).strip()
        if not version:
            raise RiotRequestError("Could not determine the current Riot client version.")

        version = version.replace("shipping-shipping-", "shipping-")
        self._resolved_client_version = version
        self._client_version_refresh_after = now + timedelta(minutes=30)
        session.client_version = version

    async def storefront(self, session: RiotSession) -> dict[str, Any]:
        base = f"https://pd.{session.shard}.a.pvp.net"
        v3_url = f"{base}/store/v3/storefront/{session.puuid}"
        try:
            data = await self.request_json("POST", v3_url, session, json_body={}, allow_empty=True)
            if isinstance(data, dict) and data:
                data["_source_version"] = "v3"
                return data
        except RiotRequestError as exc:
            if exc.riot_status not in {400, 404, 405}:
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

    async def match_details(
        self, session: RiotSession, match_id: str
    ) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            f"https://pd.{session.shard}.a.pvp.net/match-details/v1/matches/{match_id}",
            session,
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


def access_token_needs_refresh(token: str, *, leeway_seconds: int = 60) -> bool:
    expires_at = access_token_expiration(token)
    if expires_at is None:
        return False
    return expires_at <= datetime.now(UTC) + timedelta(seconds=leeway_seconds)


def access_token_expiration(token: str) -> datetime | None:
    try:
        claims = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
            },
            algorithms=["RS256", "HS256"],
        )
    except jwt.PyJWTError:
        return None
    expires_at = claims.get("exp")
    if not isinstance(expires_at, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(float(expires_at), UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _riot_auth_redirect(response: httpx.Response) -> str:
    location = response.headers.get("location", "").strip()
    if location:
        return location
    try:
        payload = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = None

    def find(value: Any, depth: int = 0) -> str:
        if depth > 5:
            return ""
        if isinstance(value, dict):
            for key in ("uri", "redirect_uri", "location", "url"):
                candidate = value.get(key)
                if isinstance(candidate, str) and "access_token=" in candidate:
                    return candidate
            for nested in value.values():
                candidate = find(nested, depth + 1)
                if candidate:
                    return candidate
        elif isinstance(value, list):
            for nested in value[:20]:
                candidate = find(nested, depth + 1)
                if candidate:
                    return candidate
        return ""

    return find(payload)


def _raise_for_riot_auth(response: httpx.Response, action: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if response.status_code in {401, 403}:
            raise RelinkRequiredError(
                f"A Riot recusou a sessão ao {action}. Faça login Riot novamente pelo celular."
            ) from exc
        raise RiotRequestError(
            f"Riot returned HTTP {response.status_code} ao {action}.",
            riot_status=response.status_code,
        ) from exc


def riot_error_code(response: httpx.Response) -> str:
    if not response.content:
        return ""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(
        payload.get("errorCode")
        or payload.get("error_code")
        or payload.get("code")
        or ""
    ).upper()


def _cookie_header(ssid: str, cookies: dict[str, str] | None = None) -> str:
    merged = {
        str(key): str(value)
        for key, value in (cookies or {}).items()
        if str(key) and str(value)
    }
    if ssid:
        merged["ssid"] = ssid
    return "; ".join(f"{key}={value}" for key, value in merged.items())
