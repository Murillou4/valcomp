from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .assets import ValorantAssetsClient, asset_display_name, asset_icon, asset_tier
from .repository import Repository
from .riot import RiotRemoteClient, RiotSession
from .schemas import (
    ItemStatusResponse,
    NightMarketResponse,
    StoreDailyResponse,
    StoreItem,
)


VP_CURRENCY_ID = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"
SKIN_ITEM_TYPE_ID = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"


class StoreService:
    def __init__(
        self,
        riot: RiotRemoteClient,
        assets: ValorantAssetsClient,
        repo: Repository,
    ) -> None:
        self.riot = riot
        self.assets = assets
        self.repo = repo

    async def daily_store(self, user_id: str, session: RiotSession) -> StoreDailyResponse:
        raw = await self.riot.storefront(session)
        item_ids, seconds_remaining = extract_daily_offer_ids(raw)
        night_market_offers, night_market_seconds = extract_night_market_offers(raw)
        prices = extract_prices(raw, include_bonus=False)
        items = [await self._enriched_item(item_id, prices.get(item_id), "daily_store") for item_id in item_ids]
        night_market = [
            await self._enriched_item(
                offer["item_id"],
                offer["price"],
                "night_market",
                original_price=offer["original_price"],
                discount_percent=offer["discount_percent"],
                is_seen=offer["is_seen"],
                bonus_offer_id=offer["bonus_offer_id"],
            )
            for offer in night_market_offers
        ]
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=seconds_remaining)
            if seconds_remaining is not None
            else None
        )
        night_market_expires_at = (
            datetime.now(UTC) + timedelta(seconds=night_market_seconds)
            if night_market_seconds is not None
            else None
        )
        response = StoreDailyResponse(
            expires_at=expires_at,
            seconds_remaining=seconds_remaining,
            items=items,
            night_market=night_market,
            night_market_expires_at=night_market_expires_at,
            night_market_seconds_remaining=night_market_seconds,
            night_market_active=bool(night_market_offers),
            raw=raw,
        )
        await self.repo.save_store_snapshot(user_id, response.model_dump(mode="json"))
        return response

    async def night_market(
        self, user_id: str, session: RiotSession
    ) -> NightMarketResponse:
        daily = await self.daily_store(user_id, session)
        return NightMarketResponse(
            active=daily.night_market_active,
            expires_at=daily.night_market_expires_at,
            seconds_remaining=daily.night_market_seconds_remaining,
            items=daily.night_market,
        )

    async def item_status(self, user_id: str, session: RiotSession, item_id: str) -> ItemStatusResponse:
        inventory = await self.riot.inventory(session)
        owned = item_id.lower() in inventory_item_ids(inventory)
        daily = await self.daily_store(user_id, session)
        daily_items = {item.item_id.lower(): item for item in daily.items}
        night_items = {item.item_id.lower(): item for item in daily.night_market}
        category, asset = await self.assets.get_item(item_id, self.repo)
        store_item = daily_items.get(item_id.lower()) or night_items.get(item_id.lower())
        return ItemStatusResponse(
            item_id=item_id,
            owned=owned,
            in_daily_store=item_id.lower() in daily_items,
            in_night_market=item_id.lower() in night_items,
            price=store_item.price if store_item else None,
            expires_at=(
                daily.night_market_expires_at
                if store_item and store_item.source == "night_market"
                else daily.expires_at if store_item else None
            ),
            source=store_item.source if store_item else "inventory" if owned else "none",
            item={"category": category, **asset} if asset else None,
        )

    async def _enriched_item(
        self,
        item_id: str,
        price: int | None,
        source: str,
        *,
        original_price: int | None = None,
        discount_percent: int | None = None,
        is_seen: bool | None = None,
        bonus_offer_id: str = "",
    ) -> StoreItem:
        _, asset = await self.assets.resolve_store_item(item_id, self.repo)
        return StoreItem(
            item_id=item_id,
            item_type_id=SKIN_ITEM_TYPE_ID,
            name=asset_display_name(asset),
            display_icon=asset_icon(asset),
            full_render=str(asset.get("fullRender") or "") if asset else "",
            tier=asset_tier(asset),
            price=price,
            original_price=original_price,
            discount_percent=discount_percent,
            is_seen=is_seen,
            bonus_offer_id=bonus_offer_id,
            currency_id=VP_CURRENCY_ID if price is not None else "",
            source=source,
        )


def extract_daily_offer_ids(raw: dict[str, Any]) -> tuple[list[str], int | None]:
    layout = raw.get("SkinsPanelLayout", {}) if isinstance(raw, dict) else {}
    offers = layout.get("SingleItemOffers", [])
    if not offers:
        offers = _recursive_collect(raw, "SingleItemOffers")
    ids = [_coerce_offer_id(item) for item in offers]
    ids = [item for item in ids if item]
    seconds = layout.get("SingleItemOffersRemainingDurationInSeconds")
    if seconds is None:
        seconds = _first_recursive(raw, "SingleItemOffersRemainingDurationInSeconds")
    return unique_preserve_order(ids), int(seconds) if isinstance(seconds, int) else None


def extract_night_market_offer_ids(raw: dict[str, Any]) -> list[str]:
    offers, _ = extract_night_market_offers(raw)
    return [str(offer["item_id"]) for offer in offers]


def extract_night_market_offers(
    raw: dict[str, Any],
) -> tuple[list[dict[str, Any]], int | None]:
    bonus = raw.get("BonusStore") if isinstance(raw, dict) else None
    if not isinstance(bonus, dict):
        bonus = _first_recursive(raw, "BonusStore")
    if not isinstance(bonus, dict):
        return [], None
    raw_offers = bonus.get("BonusStoreOffers", [])
    if not isinstance(raw_offers, list):
        raw_offers = []
    seconds = bonus.get("BonusStoreRemainingDurationInSeconds")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_offer in raw_offers:
        if not isinstance(raw_offer, dict):
            continue
        nested = raw_offer.get("Offer")
        if not isinstance(nested, dict):
            nested = {}
        item_id = _coerce_offer_id(nested)
        if not item_id or item_id.lower() in seen:
            continue
        seen.add(item_id.lower())
        discount_costs = raw_offer.get("DiscountCosts")
        original_costs = nested.get("Cost")
        normalized.append(
            {
                "item_id": item_id,
                "price": _currency_value(discount_costs),
                "original_price": _currency_value(original_costs),
                "discount_percent": _optional_int(
                    raw_offer.get("DiscountPercent")
                ),
                "is_seen": (
                    bool(raw_offer.get("IsSeen"))
                    if raw_offer.get("IsSeen") is not None
                    else None
                ),
                "bonus_offer_id": str(raw_offer.get("BonusOfferID") or ""),
            }
        )
    return normalized, _optional_int(seconds)


def extract_prices(
    raw: dict[str, Any], *, include_bonus: bool = True
) -> dict[str, int]:
    prices: dict[str, int] = {}
    for offer in _recursive_collect(raw, "Offers") + _recursive_collect(raw, "StoreOffers"):
        if not isinstance(offer, dict):
            continue
        item_id = _coerce_offer_id(offer)
        cost = offer.get("Cost") or offer.get("cost") or {}
        price = cost.get(VP_CURRENCY_ID) if isinstance(cost, dict) else None
        if item_id and isinstance(price, int):
            prices[item_id] = price
    if include_bonus:
        for offer in _recursive_collect(raw, "BonusStoreOffers"):
            if not isinstance(offer, dict):
                continue
            nested = offer.get("Offer") or {}
            item_id = _coerce_offer_id(nested)
            price = offer.get("DiscountCosts", {}).get(VP_CURRENCY_ID)
            if item_id and isinstance(price, int):
                prices[item_id] = price
    return prices


def inventory_item_ids(raw: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for group in raw.get("EntitlementsByTypes", []) if isinstance(raw, dict) else []:
        for item in group.get("Entitlements", []) if isinstance(group, dict) else []:
            item_id = str(item.get("ItemID") or "").lower()
            if item_id:
                ids.add(item_id)
    return ids


def _coerce_offer_id(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    if value.get("OfferID"):
        return str(value["OfferID"])
    rewards = value.get("Rewards") or value.get("rewards") or []
    if rewards and isinstance(rewards, list) and isinstance(rewards[0], dict):
        return str(rewards[0].get("ItemID") or rewards[0].get("itemId") or "")
    item = value.get("Item") or value.get("item") or {}
    if isinstance(item, dict):
        return str(item.get("ItemID") or item.get("itemId") or "")
    return ""


def _recursive_collect(value: Any, key: str) -> list[Any]:
    results: list[Any] = []
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key:
                if isinstance(current_value, list):
                    results.extend(current_value)
                else:
                    results.append(current_value)
            results.extend(_recursive_collect(current_value, key))
    elif isinstance(value, list):
        for item in value:
            results.extend(_recursive_collect(item, key))
    return results


def _first_recursive(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            result = _first_recursive(child, key)
            if result is not None:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _first_recursive(child, key)
            if result is not None:
                return result
    return None


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        lowered = value.lower()
        if lowered not in seen:
            seen.add(lowered)
            result.append(value)
    return result


def _currency_value(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    return _optional_int(value.get(VP_CURRENCY_ID))


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
