from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

from ares_console.session import RiotSessionDiscovery


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def read_riot_ssid(local_app_data: Path | None = None) -> str:
    base = local_app_data or Path(os.environ.get("LOCALAPPDATA", ""))
    settings_path = (
        base / "Riot Games" / "Riot Client" / "Data" / "RiotGamesPrivateSettings.yaml"
    )
    if not settings_path.exists():
        return ""
    text = settings_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(
        r'name:\s*["\']?ssid["\']?.{0,800}?value:\s*["\']([^"\']+)["\']',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def build_riot_payload() -> dict[str, Any]:
    context = RiotSessionDiscovery().discover()
    if not context.online:
        raise RuntimeError(context.error or "Nao foi possivel detectar a sessao Riot local.")
    ssid = read_riot_ssid()
    payload = {
        "ssid": ssid,
        "cookies": {"ssid": ssid} if ssid else {},
        "access_token": context.token,
        "entitlement_token": context.entitlement,
        "puuid": context.puuid,
        "region": context.region,
        "shard": context.shard,
        "client_version": context.client_version,
    }
    return payload


def submit_link(backend_url: str, link_code: str, riot_payload: dict[str, Any]) -> dict[str, Any]:
    payload = {"link_code": link_code.strip(), "riot": riot_payload}
    response = httpx.post(
        f"{backend_url.rstrip('/')}/riot/link/complete",
        json=payload,
        timeout=25.0,
        trust_env=False,
        headers={"User-Agent": "ares-companion"},
    )
    if not response.is_success:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise RuntimeError(f"Backend respondeu HTTP {response.status_code}: {detail}")
    return response.json()


def complete_link(backend_url: str, link_code: str) -> dict[str, Any]:
    return submit_link(backend_url, link_code, build_riot_payload())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ares-companion",
        description="Vincula a sessao Riot local a um usuario autenticado no backend Ares.",
    )
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("ARES_API_BASE_URL", DEFAULT_BACKEND_URL),
        help="URL base do backend FastAPI.",
    )
    parser.add_argument("--code", default="", help="Codigo de vinculo gerado pelo app mobile.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    code = args.code.strip() or input("Codigo de vinculo: ").strip()
    if not code:
        print("Codigo de vinculo obrigatorio.", file=sys.stderr)
        return 2
    try:
        result = complete_link(args.backend_url, code)
    except Exception as exc:
        print(f"Falha ao vincular: {exc}", file=sys.stderr)
        return 1
    account = result.get("riot_account", {})
    name = account.get("game_name") or account.get("puuid", "")[:8] or "conta Riot"
    tag = account.get("tag_line", "")
    suffix = f"#{tag}" if tag else ""
    print(f"Vinculo concluido para {name}{suffix}. Pode fechar esta janela.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
