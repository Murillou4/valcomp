from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from .models import Lockfile, RiotContext


REGION_TO_SHARD = {
    "na": "na",
    "latam": "na",
    "br": "na",
    "eu": "eu",
    "ap": "ap",
    "kr": "kr",
}


class SessionDiscoveryError(RuntimeError):
    pass


class RiotSessionDiscovery:
    def __init__(self, local_app_data: Path | None = None) -> None:
        base = local_app_data or Path(os.environ.get("LOCALAPPDATA", ""))
        self.lockfile_path = base / "Riot Games" / "Riot Client" / "Config" / "lockfile"
        self.log_path = base / "VALORANT" / "Saved" / "Logs" / "ShooterGame.log"

    def discover(self) -> RiotContext:
        context = RiotContext(status="connecting")
        try:
            context.lockfile = self.read_lockfile()
            with self._local_client(context.lockfile) as client:
                entitlement_data = self._get_json(client, "entitlements/v1/token")
                region_data = self._get_json(client, "riotclient/region-locale")
                sessions_data = self._get_json(client, "product-session/v1/external-sessions")

            context.token = str(entitlement_data.get("accessToken", ""))
            context.entitlement = str(entitlement_data.get("token", ""))
            context.puuid = str(entitlement_data.get("subject", ""))

            session_info = self._parse_sessions(sessions_data)
            log_info = self._parse_log()
            context.region = (
                session_info.get("region")
                or log_info.get("region")
                or str(region_data.get("region", ""))
            ).lower()
            context.shard = (
                session_info.get("shard")
                or log_info.get("shard")
                or REGION_TO_SHARD.get(context.region, "")
            ).lower()
            context.client_version = (
                log_info.get("client_version")
                or session_info.get("client_version")
                or self._fetch_public_client_version()
            )

            if not context.token or not context.entitlement or not context.puuid:
                raise SessionDiscoveryError("A API local não retornou a sessão autenticada completa.")
            if not context.region or not context.shard:
                raise SessionDiscoveryError("Não foi possível detectar a região e o shard.")

            context.online = True
            context.status = "connected"
            self._discover_live_ids(context)
            return context
        except Exception as exc:
            context.online = False
            context.status = "offline"
            context.error = self._friendly_error(exc)
            return context

    def read_lockfile(self) -> Lockfile:
        if not self.lockfile_path.exists():
            raise SessionDiscoveryError(
                "Lockfile não encontrado. Abra o Riot Client e o VALORANT."
            )
        raw = self.lockfile_path.read_text(encoding="utf-8").strip()
        try:
            name, pid, port, password, protocol = raw.split(":", 4)
            return Lockfile(
                name=name,
                pid=int(pid),
                port=int(port),
                password=password,
                protocol=protocol,
            )
        except (ValueError, TypeError) as exc:
            raise SessionDiscoveryError("O lockfile do Riot Client está inválido.") from exc

    @staticmethod
    def _local_client(lockfile: Lockfile) -> httpx.Client:
        return httpx.Client(
            base_url=f"https://127.0.0.1:{lockfile.port}",
            auth=("riot", lockfile.password),
            verify=False,
            timeout=5.0,
            trust_env=False,
            headers={"User-Agent": ""},
        )

    @staticmethod
    def _get_json(client: httpx.Client, path: str) -> Any:
        response = client.get(path)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_sessions(data: Any) -> dict[str, str]:
        if not isinstance(data, dict):
            return {}
        sessions = [
            value
            for value in data.values()
            if isinstance(value, dict) and value.get("productId") == "valorant"
        ]
        if not sessions:
            return {}
        session = sessions[0]
        arguments = session.get("launchConfiguration", {}).get("arguments", [])
        result: dict[str, str] = {}
        for argument in arguments:
            if not isinstance(argument, str) or "=" not in argument:
                continue
            key, value = argument.split("=", 1)
            normalized = key.lstrip("-").lower()
            if normalized == "ares-deployment":
                result["region"] = value
            elif normalized in {"ares-shard", "ares-platform"}:
                result["shard"] = value
        version = session.get("version")
        if isinstance(version, str):
            result["client_version"] = version
        return result

    def _parse_log(self) -> dict[str, str]:
        if not self.log_path.exists():
            return {}
        try:
            data = self.log_path.read_bytes()
            text = data[-12 * 1024 * 1024 :].decode("utf-8", errors="ignore")
        except OSError:
            return {}

        result: dict[str, str] = {}
        region_matches = re.findall(
            r"https://glz-(.+?)-1\.(.+?)\.a\.pvp\.net", text, re.IGNORECASE
        )
        if region_matches:
            result["region"], result["shard"] = region_matches[-1]

        version_matches = re.findall(r"CI server version: ([^\r\n]+)", text)
        if version_matches:
            version = version_matches[-1].strip()
            result["client_version"] = re.sub(
                r"^(release-\d+\.\d+-)", r"\1shipping-", version
            )
        return result

    @staticmethod
    def _fetch_public_client_version() -> str:
        try:
            response = httpx.get(
                "https://valorant-api.com/v1/version",
                timeout=5.0,
                trust_env=False,
                headers={"User-Agent": ""},
            )
            response.raise_for_status()
            return str(response.json().get("data", {}).get("riotClientVersion", ""))
        except Exception:
            return ""

    def _discover_live_ids(self, context: RiotContext) -> None:
        headers = self.remote_headers(context)
        urls = {
            "party_id": (
                f"https://glz-{context.region}-1.{context.shard}.a.pvp.net/"
                f"parties/v1/players/{context.puuid}",
                "CurrentPartyID",
            ),
            "pregame_match_id": (
                f"https://glz-{context.region}-1.{context.shard}.a.pvp.net/"
                f"pregame/v1/players/{context.puuid}",
                "MatchID",
            ),
            "current_game_match_id": (
                f"https://glz-{context.region}-1.{context.shard}.a.pvp.net/"
                f"core-game/v1/players/{context.puuid}",
                "MatchID",
            ),
        }
        with httpx.Client(timeout=4.0, trust_env=False, headers=headers) as client:
            for attribute, (url, key) in urls.items():
                try:
                    response = client.get(url)
                    if response.is_success:
                        setattr(context, attribute, str(response.json().get(key, "")))
                except Exception:
                    continue

    @staticmethod
    def remote_headers(context: RiotContext) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {context.token}",
            "X-Riot-Entitlements-JWT": context.entitlement,
            "X-Riot-ClientPlatform": context.client_platform,
            "User-Agent": "",
        }
        if context.client_version:
            headers["X-Riot-ClientVersion"] = context.client_version
        return headers

    @staticmethod
    def local_authorization(lockfile: Lockfile) -> str:
        encoded = base64.b64encode(f"riot:{lockfile.password}".encode("utf-8")).decode()
        return f"Basic {encoded}"

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        if isinstance(exc, SessionDiscoveryError):
            return str(exc)
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            return (
                "O lockfile existe, mas a API local recusou a conexão. "
                "Abra o Riot Client e inicie o VALORANT."
            )
        if isinstance(exc, httpx.HTTPStatusError):
            return f"A API local respondeu HTTP {exc.response.status_code}."
        return f"Falha ao detectar a sessão: {exc}"
