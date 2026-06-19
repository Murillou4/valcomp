from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Protocol

import firebase_admin
from firebase_admin import credentials, messaging

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


class PushClient(Protocol):
    async def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class FirebasePushClient:
    def __init__(self, settings: BackendSettings) -> None:
        self.settings = settings
        self._app: firebase_admin.App | None = None

    async def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not messages:
            return []
        if not self.settings.firebase_service_account_json:
            return [
                {"status": "error", "message": "FCM is not configured on the backend."}
                for _ in messages
            ]
        return await asyncio.to_thread(self._send_sync, messages)

    def _send_sync(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        firebase_messages = [
            messaging.Message(
                token=str(payload.get("token") or ""),
                notification=messaging.Notification(
                    title=str(payload.get("title") or ""),
                    body=str(payload.get("body") or ""),
                    image=payload.get("image") or None,
                ),
                data={
                    str(key): "" if value is None else str(value)
                    for key, value in (payload.get("data") or {}).items()
                },
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id=str(payload.get("channel_id") or "skin_alerts"),
                        click_action="FLUTTER_NOTIFICATION_CLICK",
                        icon="ic_notification",
                        sound="default",
                    ),
                ),
            )
            for payload in payloads
            if payload.get("token")
        ]
        response = messaging.send_each(firebase_messages, app=self._firebase_app())
        return [
            (
                {"status": "ok", "id": result.message_id or ""}
                if result.success
                else {
                    "status": "error",
                    "message": str(result.exception or "FCM delivery failed."),
                }
            )
            for result in response.responses
        ]

    def _firebase_app(self) -> firebase_admin.App:
        if self._app is not None:
            return self._app
        raw = self.settings.firebase_service_account_json.strip()
        if not raw.startswith("{"):
            raw = base64.b64decode(raw).decode("utf-8")
        service_account = json.loads(raw)
        project_id = self.settings.firebase_project_id or service_account.get("project_id")
        self._app = firebase_admin.initialize_app(
            credentials.Certificate(service_account),
            {"projectId": project_id} if project_id else None,
            name="valcomp-backend",
        )
        return self._app


class StoreAlertService:
    def __init__(
        self,
        settings: BackendSettings,
        repo: Repository,
        assets: ValorantAssetsClient,
        push: PushClient | None = None,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.assets = assets
        self.push = push or FirebasePushClient(settings)
        self._relink_notification_locks: dict[str, asyncio.Lock] = {}

    async def register_device(
        self, user_id: str, request: PushDeviceRegisterRequest
    ) -> PushDevice:
        now = datetime.now(UTC)
        token = request.push_token.strip()
        device = PushDevice(
            device_id=push_device_id(token),
            user_id=user_id,
            push_token=token,
            provider=request.provider,
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
        category, canonical_id, asset = await self.assets.canonical_store_item(
            item_id, self.repo
        )
        if not asset or category not in {"skins", "skin-levels", "chromas"}:
            raise ValueError("Item is not a known Valorant skin, level or chroma.")
        now = datetime.now(UTC)
        watch = SkinWatch(
            user_id=user_id,
            item_id=canonical_id,
            item_name=asset_display_name(asset),
            display_icon=asset_icon(asset),
            tier=asset_tier(asset),
            notify_enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.upsert_skin_watch(watch)

    async def send_test_notification(self, user_id: str) -> dict[str, Any]:
        devices = [
            device
            for device in await self.repo.list_push_devices(user_id)
            if device.enabled and device.provider == "fcm" and device.push_token
        ]
        if not devices:
            return {
                "device_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "errors": [],
            }
        results = await self.push.send(
            [
                {
                    "token": device.push_token,
                    "title": "Notificações ativadas",
                    "body": "Pronto. O Valcomp pode avisar quando uma skin desejada aparecer.",
                    "data": {
                        "type": "push_test",
                        "userId": user_id,
                    },
                }
                for device in devices
            ]
        )
        errors = [
            str(result.get("message") or "FCM delivery failed.")
            for result in results
            if result.get("status") != "ok"
        ]
        sent_count = sum(result.get("status") == "ok" for result in results)
        return {
            "device_count": len(devices),
            "sent_count": sent_count,
            "failed_count": len(errors),
            "errors": errors,
        }

    async def notify_riot_relink_required(self, user_id: str) -> int:
        lock = self._relink_notification_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            return await self._notify_riot_relink_required(user_id)

    async def _notify_riot_relink_required(self, user_id: str) -> int:
        credentials = await self.repo.get_riot_credentials(user_id)
        rotation = credentials.updated_at.isoformat() if credentials else "missing"
        delivery_key = hashlib.sha256(
            f"{user_id}:riot_relink_required:{rotation}".encode("utf-8")
        ).hexdigest()
        if await self.repo.get_notification_delivery(delivery_key):
            return 0

        devices = [
            device
            for device in await self.repo.list_push_devices(user_id)
            if device.enabled and device.provider == "fcm" and device.push_token
        ]
        if not devices:
            return 0

        results = await self.push.send(
            [
                {
                    "token": device.push_token,
                    "title": "Entre novamente na Riot",
                    "body": "Sua sessão expirou. Reconecte a conta para atualizar rank, loja e histórico.",
                    "channel_id": "account_status",
                    "data": {
                        "type": "riot_relink_required",
                        "route": "riot_setup",
                        "userId": user_id,
                    },
                }
                for device in devices
            ]
        )
        ticket_ids = [
            str(result.get("id"))
            for result in results
            if result.get("status") == "ok" and result.get("id")
        ]
        failures = [
            str(result.get("message") or "FCM delivery failed.")
            for result in results
            if result.get("status") != "ok"
        ]
        await self.repo.upsert_notification_delivery(
            NotificationDelivery(
                delivery_key=delivery_key,
                user_id=user_id,
                item_id="riot_session",
                item_name="Conta Riot desconectada",
                source="riot_relink_required",
                status="sent" if ticket_ids else "failed",
                ticket_ids=ticket_ids,
                error="; ".join(failures)[:800],
                sent_at=datetime.now(UTC),
            )
        )
        return len(ticket_ids)

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
                "token": device.push_token,
                "title": title,
                "body": body,
                "image": item.display_icon or None,
                "data": {
                    "type": "skin_store_match",
                    "route": "store",
                    "userId": user_id,
                    "itemId": watch.item_id,
                    "source": source,
                    "price": item.price,
                },
            }
            for device in devices
            if device.enabled and device.provider == "fcm" and device.push_token
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
