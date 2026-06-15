from __future__ import annotations

from typing import Any

import httpx

from .repository import Repository
from .settings import BackendSettings


ASSET_ENDPOINTS = {
    "weapons": "weapons",
    "skins": "weapons/skins",
    "skin-levels": "weapons/skinlevels",
    "chromas": "weapons/skinchromas",
    "buddies": "buddies",
    "cards": "playercards",
    "titles": "playertitles",
}


class ValorantAssetsClient:
    def __init__(self, settings: BackendSettings, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(
            base_url="https://valorant-api.com/v1",
            timeout=settings.http_timeout_seconds,
            trust_env=False,
        )
        self._memory: dict[str, list[dict[str, Any]]] = {}

    async def list_items(self, category: str, repo: Repository | None = None) -> list[dict[str, Any]]:
        if category not in ASSET_ENDPOINTS:
            raise ValueError(f"Unknown item category: {category}")
        if category in self._memory:
            return self._memory[category]
        response = await self.client.get(f"/{ASSET_ENDPOINTS[category]}")
        response.raise_for_status()
        data = response.json().get("data", [])
        items = data if isinstance(data, list) else []
        self._memory[category] = items
        if repo:
            for item in items:
                item_id = str(item.get("uuid") or "")
                if item_id:
                    await repo.cache_item(category, item_id, item)
        return items

    async def get_item(
        self, item_id: str, repo: Repository | None = None
    ) -> tuple[str, dict[str, Any] | None]:
        for category in ASSET_ENDPOINTS:
            if repo:
                cached = await repo.get_cached_item(category, item_id)
                if cached:
                    return category, cached
            for item in await self.list_items(category, repo):
                if str(item.get("uuid", "")).lower() == item_id.lower():
                    return category, item
        return "", None


def asset_display_name(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    return str(item.get("displayName") or item.get("titleText") or "")


def asset_icon(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    return str(
        item.get("displayIcon")
        or item.get("smallArt")
        or item.get("largeArt")
        or item.get("fullRender")
        or ""
    )


def asset_tier(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    tier = item.get("contentTierUuid") or item.get("contentTier", {}).get("uuid", "")
    return str(tier or "")
