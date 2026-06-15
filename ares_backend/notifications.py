from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import httpx

from .assets import ValorantAssetsClient, asset_display_name, asset_icon, asset_tier
from .repository import Repository
from .schemas import (
    AlertCheckResponse,
    AlertMatch,
    NotificationDelivery,
    PushDevice,
    PushDeviceRegisterRequest,
    SkinWatch,
    StoreDailyResponse,
)
from .settings import BackendSettings
from .store import StoreItem


class ExpoPushClient:
    def __init__(self, settings: BackendSettings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            trust_env=False,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/json",
            },
        )

    async def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not messages:
            return []
        tickets: list[dict[str, Any]] = []
        for index in range(0, len(messages), 100):
            chunk = messages[index : index + 100]
            response = await self.client.post(self.settings.expo_push_endpoint, json=chunk)
            response.raise_for_status()
            data = response.json().get("data", [])
            if isinstance(data, dict):
                tickets.append(data)
            elif isinstance(data, list):
                tickets.extend(item for item in data if isinstance(item, dict))
        return tickets


class StoreAlertService:
    def __init__(
        self,
        settings: BackendSettings,
        repo: Repository,
        assets: ValorantAssetsClient,
        push: ExpoPushClient | None = None,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.assets = assets
        self.push = push or ExpoPushClient(settings)

    async def register_device(
        self, user_id: str, request: PushDeviceRegisterRequest
    ) -> PushDevice:
        now = datetime.now(UTC)
        token = request.expo_push_token.strip()
        device = PushDevice(
            device_id=push_device_id(token),
            user_id=user_id,
            expo_push_token=token,
            masked_token=mask_push_token(token),
            platform=request.platform,
            device_name=request.device_name.strip(),
            app_version=request.app_version.strip(),
            enabled=request.enabled,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.upsert_push_device(device)

    async def add_skin_watch(self, user_id: str, item_id: str, *, enabled: bool = True) -> SkinWatch:
        category, asset = await self.assets.get_item(item_id, self.repo)
        if not asset or category not in {"skins", "skin-levels", "chromas"}:
            raise ValueError("Item is not a known Valorant skin, level or chroma.")
        now = datetime.now(UTC)
        watch = SkinWatch(
            user_id=user_id,
            item_id=item_id,
            item_name=asset_display_name(asset),
            display_icon=asset_icon(asset),
            tier=asset_tier(asset),
            notify_enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.upsert_skin_watch(watch)

    async def check_daily_store(
        self, user_id: str, daily: StoreDailyResponse
    ) -> AlertCheckResponse:
        watches = await self.repo.list_skin_watches(user_id)
        devices = await self.repo.list_push_devices(user_id)
        if not watches:
            return AlertCheckResponse(
                user_id=user_id,
                checked=True,
                device_count=len(devices),
            )

        store_items = {item.item_id.lower(): item for item in daily.items}
        night_items = {item.item_id.lower(): item for item in daily.night_market}
        matched: list[AlertMatch] = []
        errors: list[str] = []
        sent_count = 0

        for watch in watches:
            item = store_items.get(watch.item_id.lower()) or night_items.get(watch.item_id.lower())
            if not item:
                continue
            source = "daily_store" if item.item_id.lower() in store_items else "night_market"
            delivery_key = notification_delivery_key(
                user_id, watch.item_id, daily.expires_at, source
            )
            already = await self.repo.get_notification_delivery(delivery_key)
            match = AlertMatch(
                item_id=watch.item_id,
                item_name=watch.item_name or item.name,
                source=source,
                price=item.price,
                expires_at=daily.expires_at,
                already_notified=already is not None,
            )
            if already:
                matched.append(match)
                continue
            if not devices:
                matched.append(match)
                continue
            try:
                tickets = await self._send_skin_alert(user_id, watch, item, source, devices)
                ticket_ids = [
                    str(ticket.get("id"))
                    for ticket in tickets
                    if ticket.get("status") == "ok" and ticket.get("id")
                ]
                failures = [
                    str(ticket.get("message") or ticket.get("details") or ticket)
                    for ticket in tickets
                    if ticket.get("status") != "ok"
                ]
                await self.repo.upsert_notification_delivery(
                    NotificationDelivery(
                        delivery_key=delivery_key,
                        user_id=user_id,
                        item_id=watch.item_id,
                        item_name=watch.item_name or item.name,
                        source=source,
                        store_expires_at=daily.expires_at,
                        status="sent" if ticket_ids else "failed",
                        ticket_ids=ticket_ids,
                        error="; ".join(failures)[:800],
                        sent_at=datetime.now(UTC),
                    )
                )
                match.sent_count = len(ticket_ids)
                sent_count += len(ticket_ids)
                errors.extend(failures)
            except Exception as exc:
                message = str(exc)
                errors.append(message)
                await self.repo.upsert_notification_delivery(
                    NotificationDelivery(
                        delivery_key=delivery_key,
                        user_id=user_id,
                        item_id=watch.item_id,
                        item_name=watch.item_name or item.name,
                        source=source,
                        store_expires_at=daily.expires_at,
                        status="failed",
                        ticket_ids=[],
                        error=message[:800],
                        sent_at=datetime.now(UTC),
                    )
                )
            matched.append(match)

        return AlertCheckResponse(
            user_id=user_id,
            checked=True,
            matched=matched,
            sent_count=sent_count,
            device_count=len(devices),
            errors=errors,
        )

    async def _send_skin_alert(
        self,
        user_id: str,
        watch: SkinWatch,
        item: StoreItem,
        source: str,
        devices: list[PushDevice],
    ) -> list[dict[str, Any]]:
        title = "Skin desejada na loja"
        source_label = "Mercado Noturno" if source == "night_market" else "Loja diaria"
        price = f" por {item.price} VP" if item.price else ""
        body = f"{watch.item_name or item.name} apareceu na {source_label}{price}."
        messages = [
            {
                "to": device.expo_push_token,
                "title": title,
                "body": body,
                "sound": "default",
                "data": {
                    "type": "skin_store_match",
                    "userId": user_id,
                    "itemId": watch.item_id,
                    "source": source,
                    "price": item.price,
                },
            }
            for device in devices
            if device.enabled and device.expo_push_token
        ]
        return await self.push.send(messages)


def push_device_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]


def mask_push_token(token: str) -> str:
    if len(token) <= 18:
        return "[redacted]"
    return f"{token[:14]}...{token[-6:]}"


def notification_delivery_key(
    user_id: str,
    item_id: str,
    expires_at: datetime | None,
    source: str,
) -> str:
    rotation = str(int(expires_at.timestamp() // 1800)) if expires_at else "unknown"
    raw = f"{user_id}:{item_id.lower()}:{source}:{rotation}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
