from __future__ import annotations

import unicodedata
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

WEAPON_CATEGORY_NAMES = {
    "heavy": "Armas pesadas",
    "rifle": "Fuzis",
    "shotgun": "Escopetas",
    "sidearm": "Pistolas",
    "sniper": "Fuzis de precisão",
    "smg": "Submetralhadoras",
    "melee": "Corpo a corpo",
}

CONTENT_TIERS = {
    "12683d76-48d7-84a3-4e09-6985794f0445": {
        "name": "Select Edition",
        "color": "#5A9FE2",
    },
    "0cebb8be-46d7-c12a-d306-e9907bfc5a25": {
        "name": "Deluxe Edition",
        "color": "#009587",
    },
    "60bca009-4182-7998-dee7-b8a2558dc369": {
        "name": "Premium Edition",
        "color": "#D1548D",
    },
    "e046854e-406c-37f4-6607-19a9ba8426fc": {
        "name": "Exclusive Edition",
        "color": "#F5955B",
    },
    "411e4a55-4e59-7757-41f0-86a53f101bb5": {
        "name": "Ultra Edition",
        "color": "#FAD663",
    },
}


class ValorantAssetsClient:
    def __init__(self, settings: BackendSettings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            base_url="https://valorant-api.com/v1",
            timeout=settings.http_timeout_seconds,
            trust_env=False,
        )
        self._memory: dict[str, list[dict[str, Any]]] = {}
        self._skin_catalog: list[dict[str, Any]] | None = None

    async def list_items(self, category: str, repo: Repository | None = None) -> list[dict[str, Any]]:
        if category not in ASSET_ENDPOINTS:
            raise ValueError(f"Unknown item category: {category}")
        if category in self._memory:
            return self._memory[category]
        response = await self.client.get(
            f"/{ASSET_ENDPOINTS[category]}",
            params={"language": self.settings.valorant_assets_language},
        )
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

    async def resolve_store_item(
        self, item_id: str, repo: Repository | None = None
    ) -> tuple[str, dict[str, Any] | None]:
        category, asset = await self.get_item(item_id, repo)
        if not asset or category not in {"skin-levels", "chromas"}:
            return category, asset

        relation_key = "levels" if category == "skin-levels" else "chromas"
        for skin in await self.list_items("skins", repo):
            related = skin.get(relation_key, [])
            if not isinstance(related, list):
                continue
            if any(
                isinstance(item, dict)
                and str(item.get("uuid", "")).lower() == item_id.lower()
                for item in related
            ):
                return category, {
                    **skin,
                    **asset,
                    "contentTierUuid": skin.get("contentTierUuid") or "",
                    "parentSkinUuid": skin.get("uuid") or "",
                }
        return category, asset

    async def canonical_store_item(
        self, item_id: str, repo: Repository | None = None
    ) -> tuple[str, str, dict[str, Any] | None]:
        category, asset = await self.get_item(item_id, repo)
        if not asset:
            return category, item_id, None
        if category == "skins":
            levels = asset.get("levels", [])
            if isinstance(levels, list) and levels and isinstance(levels[0], dict):
                canonical_id = str(levels[0].get("uuid") or item_id)
                _, merged = await self.resolve_store_item(canonical_id, repo)
                return "skin-levels", canonical_id, merged or asset
        _, merged = await self.resolve_store_item(item_id, repo)
        return category, item_id, merged or asset

    async def skin_catalog(self, repo: Repository | None = None) -> list[dict[str, Any]]:
        if self._skin_catalog is not None:
            return self._skin_catalog
        catalog: list[dict[str, Any]] = []
        for weapon in await self.list_items("weapons", repo):
            weapon_id = str(weapon.get("uuid") or "")
            weapon_name = str(weapon.get("displayName") or "")
            category = weapon_category_id(weapon)
            skins = weapon.get("skins", [])
            if not isinstance(skins, list):
                continue
            for skin in skins:
                if not isinstance(skin, dict):
                    continue
                tier = str(skin.get("contentTierUuid") or "")
                levels = skin.get("levels", [])
                if not tier or not isinstance(levels, list) or not levels:
                    continue
                first_level = levels[0] if isinstance(levels[0], dict) else {}
                item_id = str(first_level.get("uuid") or skin.get("uuid") or "")
                image = str(
                    skin.get("displayIcon")
                    or first_level.get("displayIcon")
                    or first_level.get("fullRender")
                    or ""
                )
                if not item_id or not image:
                    continue
                catalog.append(
                    {
                        "item_id": item_id,
                        "skin_id": str(skin.get("uuid") or ""),
                        "name": str(skin.get("displayName") or ""),
                        "display_icon": image,
                        "wallpaper": str(skin.get("wallpaper") or ""),
                        "tier": tier,
                        "weapon_id": weapon_id,
                        "weapon_name": weapon_name,
                        "weapon_icon": str(weapon.get("displayIcon") or ""),
                        "category": category,
                        "category_name": WEAPON_CATEGORY_NAMES.get(
                            category, category.title()
                        ),
                    }
                )
        self._skin_catalog = catalog
        return catalog


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


def weapon_category_id(weapon: dict[str, Any]) -> str:
    raw = str(weapon.get("category") or "")
    if "::" in raw:
        return raw.rsplit("::", 1)[-1].lower()
    shop = weapon.get("shopData")
    if isinstance(shop, dict):
        return search_key(str(shop.get("category") or "")).replace(" ", "-")
    return "other"


def search_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def skin_catalog_filters(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    category_counts: dict[str, int] = {}
    weapon_data: dict[str, dict[str, Any]] = {}
    tier_counts: dict[str, int] = {}
    for item in items:
        category = str(item.get("category") or "other")
        category_counts[category] = category_counts.get(category, 0) + 1
        weapon_id = str(item.get("weapon_id") or "")
        if weapon_id:
            weapon = weapon_data.setdefault(
                weapon_id,
                {
                    "id": weapon_id,
                    "name": str(item.get("weapon_name") or ""),
                    "icon": str(item.get("weapon_icon") or ""),
                    "category": category,
                    "count": 0,
                },
            )
            weapon["count"] += 1
        tier = str(item.get("tier") or "")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    categories = [
        {
            "id": category,
            "name": WEAPON_CATEGORY_NAMES.get(category, category.title()),
            "count": count,
        }
        for category, count in category_counts.items()
    ]
    tiers = [
        {
            "id": tier,
            "name": CONTENT_TIERS.get(tier, {}).get("name", "Sem classificação"),
            "color": CONTENT_TIERS.get(tier, {}).get("color", "#44505D"),
            "count": count,
        }
        for tier, count in tier_counts.items()
        if tier
    ]
    return {
        "categories": sorted(categories, key=lambda item: str(item["name"])),
        "weapons": sorted(weapon_data.values(), key=lambda item: str(item["name"])),
        "tiers": tiers,
    }
