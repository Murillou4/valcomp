from __future__ import annotations

import secrets
import json
import ssl
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import asyncpg
import httpx

from .schemas import (
    NotificationDelivery,
    Profile,
    PushDevice,
    RiotAccount,
    RiotCredentialRecord,
    SkinWatch,
)
from .settings import BackendSettings


class Repository(Protocol):
    async def get_profile(self, user_id: str) -> Profile | None: ...
    async def upsert_profile(self, profile: Profile) -> Profile: ...
    async def get_riot_account(self, user_id: str) -> RiotAccount | None: ...
    async def upsert_riot_account(self, account: RiotAccount) -> RiotAccount: ...
    async def get_riot_credentials(self, user_id: str) -> RiotCredentialRecord | None: ...
    async def upsert_riot_credentials(self, record: RiotCredentialRecord) -> RiotCredentialRecord: ...
    async def create_link_code(self, user_id: str, ttl_seconds: int) -> tuple[str, datetime]: ...
    async def consume_link_code(self, code: str) -> str | None: ...
    async def save_store_snapshot(self, user_id: str, payload: dict[str, Any]) -> None: ...
    async def get_store_snapshot(self, user_id: str) -> dict[str, Any] | None: ...
    async def cache_item(self, category: str, item_id: str, payload: dict[str, Any]) -> None: ...
    async def get_cached_item(self, category: str, item_id: str) -> dict[str, Any] | None: ...
    async def upsert_push_device(self, device: PushDevice) -> PushDevice: ...
    async def list_push_devices(self, user_id: str) -> list[PushDevice]: ...
    async def disable_push_device(self, user_id: str, device_id: str) -> bool: ...
    async def upsert_skin_watch(self, watch: SkinWatch) -> SkinWatch: ...
    async def list_skin_watches(self, user_id: str) -> list[SkinWatch]: ...
    async def delete_skin_watch(self, user_id: str, item_id: str) -> bool: ...
    async def list_users_with_skin_watches(self) -> list[str]: ...
    async def get_notification_delivery(self, delivery_key: str) -> NotificationDelivery | None: ...
    async def upsert_notification_delivery(
        self, delivery: NotificationDelivery
    ) -> NotificationDelivery: ...
    async def list_notification_deliveries(
        self, user_id: str, limit: int = 50
    ) -> list[NotificationDelivery]: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self.profiles: dict[str, Profile] = {}
        self.accounts: dict[str, RiotAccount] = {}
        self.credentials: dict[str, RiotCredentialRecord] = {}
        self.link_codes: dict[str, tuple[str, datetime]] = {}
        self.store_snapshots: dict[str, dict[str, Any]] = {}
        self.item_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self.push_devices: dict[str, PushDevice] = {}
        self.skin_watches: dict[tuple[str, str], SkinWatch] = {}
        self.notification_deliveries: dict[str, NotificationDelivery] = {}

    async def get_profile(self, user_id: str) -> Profile | None:
        return self.profiles.get(user_id)

    async def upsert_profile(self, profile: Profile) -> Profile:
        self.profiles[profile.user_id] = profile
        return profile

    async def get_riot_account(self, user_id: str) -> RiotAccount | None:
        return self.accounts.get(user_id)

    async def upsert_riot_account(self, account: RiotAccount) -> RiotAccount:
        self.accounts[account.user_id] = account
        return account

    async def get_riot_credentials(self, user_id: str) -> RiotCredentialRecord | None:
        return self.credentials.get(user_id)

    async def upsert_riot_credentials(self, record: RiotCredentialRecord) -> RiotCredentialRecord:
        self.credentials[record.user_id] = record
        return record

    async def create_link_code(self, user_id: str, ttl_seconds: int) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            if code not in self.link_codes:
                self.link_codes[code] = (user_id, expires_at)
                return code, expires_at
        raise RuntimeError("Could not allocate a link code.")

    async def consume_link_code(self, code: str) -> str | None:
        item = self.link_codes.pop(code, None)
        if item is None:
            return None
        user_id, expires_at = item
        if expires_at < datetime.now(UTC):
            return None
        return user_id

    async def save_store_snapshot(self, user_id: str, payload: dict[str, Any]) -> None:
        self.store_snapshots[user_id] = payload

    async def get_store_snapshot(self, user_id: str) -> dict[str, Any] | None:
        return self.store_snapshots.get(user_id)

    async def cache_item(self, category: str, item_id: str, payload: dict[str, Any]) -> None:
        self.item_cache[(category, item_id)] = payload

    async def get_cached_item(self, category: str, item_id: str) -> dict[str, Any] | None:
        return self.item_cache.get((category, item_id))

    async def upsert_push_device(self, device: PushDevice) -> PushDevice:
        self.push_devices[device.device_id] = device
        return device

    async def list_push_devices(self, user_id: str) -> list[PushDevice]:
        return [
            device
            for device in self.push_devices.values()
            if device.user_id == user_id and device.enabled
        ]

    async def disable_push_device(self, user_id: str, device_id: str) -> bool:
        device = self.push_devices.get(device_id)
        if not device or device.user_id != user_id:
            return False
        self.push_devices[device_id] = device.model_copy(
            update={"enabled": False, "updated_at": datetime.now(UTC)}
        )
        return True

    async def upsert_skin_watch(self, watch: SkinWatch) -> SkinWatch:
        self.skin_watches[(watch.user_id, watch.item_id.lower())] = watch
        return watch

    async def list_skin_watches(self, user_id: str) -> list[SkinWatch]:
        return [
            watch
            for watch in self.skin_watches.values()
            if watch.user_id == user_id and watch.notify_enabled
        ]

    async def delete_skin_watch(self, user_id: str, item_id: str) -> bool:
        return self.skin_watches.pop((user_id, item_id.lower()), None) is not None

    async def list_users_with_skin_watches(self) -> list[str]:
        users = {
            watch.user_id
            for watch in self.skin_watches.values()
            if watch.notify_enabled
        }
        return sorted(users)

    async def get_notification_delivery(self, delivery_key: str) -> NotificationDelivery | None:
        return self.notification_deliveries.get(delivery_key)

    async def upsert_notification_delivery(
        self, delivery: NotificationDelivery
    ) -> NotificationDelivery:
        self.notification_deliveries[delivery.delivery_key] = delivery
        return delivery

    async def list_notification_deliveries(
        self, user_id: str, limit: int = 50
    ) -> list[NotificationDelivery]:
        rows = [
            delivery
            for delivery in self.notification_deliveries.values()
            if delivery.user_id == user_id
        ]
        return sorted(rows, key=lambda item: item.sent_at, reverse=True)[:limit]


class SupabaseRestRepository:
    """Small PostgREST-backed repository for Supabase Free projects."""

    def __init__(self, settings: BackendSettings) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("Supabase URL and service role key are required.")
        self.url = settings.supabase_url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.client = httpx.AsyncClient(timeout=12.0, trust_env=False)

    async def get_profile(self, user_id: str) -> Profile | None:
        row = await self._select_one("profiles", "user_id", user_id)
        return Profile(**row) if row else None

    async def upsert_profile(self, profile: Profile) -> Profile:
        row = await self._upsert_one("profiles", profile.model_dump(mode="json"))
        return Profile(**row)

    async def get_riot_account(self, user_id: str) -> RiotAccount | None:
        row = await self._select_one("riot_accounts", "user_id", user_id)
        return RiotAccount(**row) if row else None

    async def upsert_riot_account(self, account: RiotAccount) -> RiotAccount:
        row = await self._upsert_one("riot_accounts", account.model_dump(mode="json"))
        return RiotAccount(**row)

    async def get_riot_credentials(self, user_id: str) -> RiotCredentialRecord | None:
        row = await self._select_one("riot_credentials", "user_id", user_id)
        return RiotCredentialRecord(**row) if row else None

    async def upsert_riot_credentials(self, record: RiotCredentialRecord) -> RiotCredentialRecord:
        row = await self._upsert_one("riot_credentials", record.model_dump(mode="json"))
        return RiotCredentialRecord(**row)

    async def create_link_code(self, user_id: str, ttl_seconds: int) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            response = await self.client.post(
                f"{self.url}/link_codes",
                headers=self.headers,
                json={"link_code": code, "user_id": user_id, "expires_at": expires_at.isoformat()},
            )
            if response.status_code in (200, 201):
                return code, expires_at
            if response.status_code != 409:
                response.raise_for_status()
        raise RuntimeError("Could not allocate a link code.")

    async def consume_link_code(self, code: str) -> str | None:
        row = await self._select_one("link_codes", "link_code", code)
        if not row:
            return None
        await self.client.delete(
            f"{self.url}/link_codes?link_code=eq.{code}",
            headers=self.headers,
        )
        expires_at = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        if expires_at < datetime.now(UTC):
            return None
        return str(row["user_id"])

    async def save_store_snapshot(self, user_id: str, payload: dict[str, Any]) -> None:
        await self._upsert_one(
            "store_snapshots",
            {"user_id": user_id, "payload": payload, "updated_at": datetime.now(UTC).isoformat()},
        )

    async def get_store_snapshot(self, user_id: str) -> dict[str, Any] | None:
        row = await self._select_one("store_snapshots", "user_id", user_id)
        return row.get("payload") if row else None

    async def cache_item(self, category: str, item_id: str, payload: dict[str, Any]) -> None:
        await self._upsert_one(
            "item_cache",
            {
                "cache_key": f"{category}:{item_id}",
                "category": category,
                "item_id": item_id,
                "payload": payload,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

    async def get_cached_item(self, category: str, item_id: str) -> dict[str, Any] | None:
        row = await self._select_one("item_cache", "cache_key", f"{category}:{item_id}")
        return row.get("payload") if row else None

    async def upsert_push_device(self, device: PushDevice) -> PushDevice:
        row = await self._upsert_one("push_devices", device.model_dump(mode="json"))
        return PushDevice(**row)

    async def list_push_devices(self, user_id: str) -> list[PushDevice]:
        rows = await self._select_many(
            "push_devices",
            {"user_id": f"eq.{user_id}", "enabled": "eq.true"},
        )
        return [PushDevice(**row) for row in rows]

    async def disable_push_device(self, user_id: str, device_id: str) -> bool:
        response = await self.client.patch(
            f"{self.url}/push_devices",
            headers={**self.headers, "Prefer": "return=minimal"},
            params={"user_id": f"eq.{user_id}", "device_id": f"eq.{device_id}"},
            json={"enabled": False, "updated_at": datetime.now(UTC).isoformat()},
        )
        response.raise_for_status()
        return response.status_code in {200, 204}

    async def upsert_skin_watch(self, watch: SkinWatch) -> SkinWatch:
        row = await self._upsert_one("skin_watches", watch.model_dump(mode="json"))
        return SkinWatch(**row)

    async def list_skin_watches(self, user_id: str) -> list[SkinWatch]:
        rows = await self._select_many(
            "skin_watches",
            {"user_id": f"eq.{user_id}", "notify_enabled": "eq.true"},
        )
        return [SkinWatch(**row) for row in rows]

    async def delete_skin_watch(self, user_id: str, item_id: str) -> bool:
        response = await self.client.delete(
            f"{self.url}/skin_watches",
            headers={**self.headers, "Prefer": "return=minimal"},
            params={"user_id": f"eq.{user_id}", "item_id": f"eq.{item_id}"},
        )
        response.raise_for_status()
        return response.status_code in {200, 204}

    async def list_users_with_skin_watches(self) -> list[str]:
        rows = await self._select_many(
            "skin_watches",
            {"select": "user_id", "notify_enabled": "eq.true"},
        )
        return sorted({str(row["user_id"]) for row in rows if row.get("user_id")})

    async def get_notification_delivery(self, delivery_key: str) -> NotificationDelivery | None:
        row = await self._select_one("notification_deliveries", "delivery_key", delivery_key)
        return NotificationDelivery(**row) if row else None

    async def upsert_notification_delivery(
        self, delivery: NotificationDelivery
    ) -> NotificationDelivery:
        row = await self._upsert_one("notification_deliveries", delivery.model_dump(mode="json"))
        return NotificationDelivery(**row)

    async def list_notification_deliveries(
        self, user_id: str, limit: int = 50
    ) -> list[NotificationDelivery]:
        rows = await self._select_many(
            "notification_deliveries",
            {
                "user_id": f"eq.{user_id}",
                "order": "sent_at.desc",
                "limit": str(limit),
            },
        )
        return [NotificationDelivery(**row) for row in rows]

    async def _select_one(self, table: str, column: str, value: str) -> dict[str, Any] | None:
        rows = await self._select_many(table, {column: f"eq.{value}", "limit": "1"})
        return rows[0] if rows else None

    async def _select_many(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = await self.client.get(
            f"{self.url}/{table}",
            headers=self.headers,
            params=params,
        )
        response.raise_for_status()
        rows = response.json()
        return rows if isinstance(rows, list) else []

    async def _upsert_one(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.post(
            f"{self.url}/{table}",
            headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"},
            json=payload,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) else rows


class PostgresRepository:
    """Direct Postgres repository for Supabase projects without service_role key."""

    def __init__(self, settings: BackendSettings) -> None:
        if not settings.database_url:
            raise ValueError("DATABASE_URL is required.")
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def _pool(self) -> asyncpg.Pool:
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self.settings.database_url,
                ssl=postgres_ssl_context(self.settings.database_ssl),
                min_size=1,
                max_size=5,
            )
        return self.pool

    async def get_profile(self, user_id: str) -> Profile | None:
        row = await self._fetchrow("select * from public.profiles where user_id=$1", user_id)
        return _profile_from_row(row) if row else None

    async def upsert_profile(self, profile: Profile) -> Profile:
        row = await self._fetchrow(
            """
            insert into public.profiles (user_id, display_name, avatar_url, preferences, updated_at)
            values ($1, $2, $3, $4::jsonb, now())
            on conflict (user_id) do update set
              display_name=excluded.display_name,
              avatar_url=excluded.avatar_url,
              preferences=excluded.preferences,
              updated_at=now()
            returning *
            """,
            profile.user_id,
            profile.display_name,
            profile.avatar_url,
            json.dumps(profile.preferences),
        )
        assert row is not None
        return _profile_from_row(row)

    async def get_riot_account(self, user_id: str) -> RiotAccount | None:
        row = await self._fetchrow("select * from public.riot_accounts where user_id=$1", user_id)
        return _riot_account_from_row(row) if row else None

    async def upsert_riot_account(self, account: RiotAccount) -> RiotAccount:
        row = await self._fetchrow(
            """
            insert into public.riot_accounts
              (user_id, puuid, game_name, tag_line, region, shard, client_version, linked_at)
            values ($1, $2, $3, $4, $5, $6, $7, $8)
            on conflict (user_id) do update set
              puuid=excluded.puuid,
              game_name=excluded.game_name,
              tag_line=excluded.tag_line,
              region=excluded.region,
              shard=excluded.shard,
              client_version=excluded.client_version,
              linked_at=excluded.linked_at
            returning *
            """,
            account.user_id,
            account.puuid,
            account.game_name,
            account.tag_line,
            account.region,
            account.shard,
            account.client_version,
            account.linked_at,
        )
        assert row is not None
        return _riot_account_from_row(row)

    async def get_riot_credentials(self, user_id: str) -> RiotCredentialRecord | None:
        row = await self._fetchrow("select * from public.riot_credentials where user_id=$1", user_id)
        return _riot_credentials_from_row(row) if row else None

    async def upsert_riot_credentials(self, record: RiotCredentialRecord) -> RiotCredentialRecord:
        row = await self._fetchrow(
            """
            insert into public.riot_credentials
              (user_id, encrypted_payload, last_refresh_at, expires_hint, updated_at)
            values ($1, $2, $3, $4, $5)
            on conflict (user_id) do update set
              encrypted_payload=excluded.encrypted_payload,
              last_refresh_at=excluded.last_refresh_at,
              expires_hint=excluded.expires_hint,
              updated_at=excluded.updated_at
            returning *
            """,
            record.user_id,
            record.encrypted_payload,
            record.last_refresh_at,
            record.expires_hint,
            record.updated_at,
        )
        assert row is not None
        return _riot_credentials_from_row(row)

    async def create_link_code(self, user_id: str, ttl_seconds: int) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            try:
                await self._execute(
                    """
                    insert into public.link_codes (link_code, user_id, expires_at)
                    values ($1, $2, $3)
                    """,
                    code,
                    user_id,
                    expires_at,
                )
                return code, expires_at
            except asyncpg.UniqueViolationError:
                continue
        raise RuntimeError("Could not allocate a link code.")

    async def consume_link_code(self, code: str) -> str | None:
        row = await self._fetchrow(
            """
            delete from public.link_codes
            where link_code=$1
            returning user_id, expires_at
            """,
            code,
        )
        if not row or row["expires_at"] < datetime.now(UTC):
            return None
        return str(row["user_id"])

    async def save_store_snapshot(self, user_id: str, payload: dict[str, Any]) -> None:
        await self._execute(
            """
            insert into public.store_snapshots (user_id, payload, updated_at)
            values ($1, $2::jsonb, now())
            on conflict (user_id) do update set
              payload=excluded.payload,
              updated_at=now()
            """,
            user_id,
            json.dumps(payload),
        )

    async def get_store_snapshot(self, user_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow("select payload from public.store_snapshots where user_id=$1", user_id)
        return _json_value(row["payload"]) if row else None

    async def cache_item(self, category: str, item_id: str, payload: dict[str, Any]) -> None:
        await self._execute(
            """
            insert into public.item_cache (cache_key, category, item_id, payload, updated_at)
            values ($1, $2, $3, $4::jsonb, now())
            on conflict (cache_key) do update set
              category=excluded.category,
              item_id=excluded.item_id,
              payload=excluded.payload,
              updated_at=now()
            """,
            f"{category}:{item_id}",
            category,
            item_id,
            json.dumps(payload),
        )

    async def get_cached_item(self, category: str, item_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            "select payload from public.item_cache where cache_key=$1",
            f"{category}:{item_id}",
        )
        return _json_value(row["payload"]) if row else None

    async def upsert_push_device(self, device: PushDevice) -> PushDevice:
        row = await self._fetchrow(
            """
            insert into public.push_devices
              (device_id, user_id, expo_push_token, masked_token, platform, device_name,
               app_version, enabled, created_at, updated_at)
            values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            on conflict (device_id) do update set
              user_id=excluded.user_id,
              expo_push_token=excluded.expo_push_token,
              masked_token=excluded.masked_token,
              platform=excluded.platform,
              device_name=excluded.device_name,
              app_version=excluded.app_version,
              enabled=excluded.enabled,
              updated_at=excluded.updated_at
            returning *
            """,
            device.device_id,
            device.user_id,
            device.expo_push_token,
            device.masked_token,
            device.platform,
            device.device_name,
            device.app_version,
            device.enabled,
            device.created_at,
            device.updated_at,
        )
        assert row is not None
        return _push_device_from_row(row)

    async def list_push_devices(self, user_id: str) -> list[PushDevice]:
        rows = await self._fetch(
            "select * from public.push_devices where user_id=$1 and enabled=true order by updated_at desc",
            user_id,
        )
        return [_push_device_from_row(row) for row in rows]

    async def disable_push_device(self, user_id: str, device_id: str) -> bool:
        result = await self._execute(
            """
            update public.push_devices
            set enabled=false, updated_at=now()
            where user_id=$1 and device_id=$2
            """,
            user_id,
            device_id,
        )
        return result.endswith("1")

    async def upsert_skin_watch(self, watch: SkinWatch) -> SkinWatch:
        row = await self._fetchrow(
            """
            insert into public.skin_watches
              (user_id, item_id, item_name, display_icon, tier, notify_enabled, created_at, updated_at)
            values ($1,$2,$3,$4,$5,$6,$7,$8)
            on conflict (user_id, item_id) do update set
              item_name=excluded.item_name,
              display_icon=excluded.display_icon,
              tier=excluded.tier,
              notify_enabled=excluded.notify_enabled,
              updated_at=excluded.updated_at
            returning *
            """,
            watch.user_id,
            watch.item_id,
            watch.item_name,
            watch.display_icon,
            watch.tier,
            watch.notify_enabled,
            watch.created_at,
            watch.updated_at,
        )
        assert row is not None
        return _skin_watch_from_row(row)

    async def list_skin_watches(self, user_id: str) -> list[SkinWatch]:
        rows = await self._fetch(
            """
            select * from public.skin_watches
            where user_id=$1 and notify_enabled=true
            order by created_at desc
            """,
            user_id,
        )
        return [_skin_watch_from_row(row) for row in rows]

    async def delete_skin_watch(self, user_id: str, item_id: str) -> bool:
        result = await self._execute(
            "delete from public.skin_watches where user_id=$1 and item_id=$2",
            user_id,
            item_id,
        )
        return result.endswith("1")

    async def list_users_with_skin_watches(self) -> list[str]:
        rows = await self._fetch(
            "select distinct user_id from public.skin_watches where notify_enabled=true"
        )
        return [str(row["user_id"]) for row in rows]

    async def get_notification_delivery(self, delivery_key: str) -> NotificationDelivery | None:
        row = await self._fetchrow(
            "select * from public.notification_deliveries where delivery_key=$1",
            delivery_key,
        )
        return _notification_delivery_from_row(row) if row else None

    async def upsert_notification_delivery(
        self, delivery: NotificationDelivery
    ) -> NotificationDelivery:
        row = await self._fetchrow(
            """
            insert into public.notification_deliveries
              (delivery_key, user_id, item_id, item_name, source, store_expires_at,
               status, ticket_ids, error, sent_at)
            values ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10)
            on conflict (delivery_key) do update set
              status=excluded.status,
              ticket_ids=excluded.ticket_ids,
              error=excluded.error,
              sent_at=excluded.sent_at
            returning *
            """,
            delivery.delivery_key,
            delivery.user_id,
            delivery.item_id,
            delivery.item_name,
            delivery.source,
            delivery.store_expires_at,
            delivery.status,
            json.dumps(delivery.ticket_ids),
            delivery.error,
            delivery.sent_at,
        )
        assert row is not None
        return _notification_delivery_from_row(row)

    async def list_notification_deliveries(
        self, user_id: str, limit: int = 50
    ) -> list[NotificationDelivery]:
        rows = await self._fetch(
            """
            select * from public.notification_deliveries
            where user_id=$1
            order by sent_at desc
            limit $2
            """,
            user_id,
            limit,
        )
        return [_notification_delivery_from_row(row) for row in rows]

    async def _fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        pool = await self._pool()
        return await pool.fetchrow(query, *args)

    async def _fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        pool = await self._pool()
        return list(await pool.fetch(query, *args))

    async def _execute(self, query: str, *args: Any) -> str:
        pool = await self._pool()
        return await pool.execute(query, *args)


def _json_value(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        decoded = json.loads(value)
        return decoded if isinstance(decoded, dict) else {}
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> list[str]:
    if isinstance(value, str):
        decoded = json.loads(value)
        return [str(item) for item in decoded] if isinstance(decoded, list) else []
    return [str(item) for item in value] if isinstance(value, list) else []


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _stringify_user_id(data: dict[str, Any]) -> dict[str, Any]:
    if "user_id" in data and data["user_id"] is not None:
        data["user_id"] = str(data["user_id"])
    return data


def _profile_from_row(row: Any) -> Profile:
    data = _stringify_user_id(_row_dict(row))
    data["preferences"] = _json_value(data.get("preferences", {}))
    return Profile(**data)


def _riot_account_from_row(row: Any) -> RiotAccount:
    return RiotAccount(**_stringify_user_id(_row_dict(row)))


def _riot_credentials_from_row(row: Any) -> RiotCredentialRecord:
    return RiotCredentialRecord(**_stringify_user_id(_row_dict(row)))


def _push_device_from_row(row: Any) -> PushDevice:
    return PushDevice(**_stringify_user_id(_row_dict(row)))


def _skin_watch_from_row(row: Any) -> SkinWatch:
    return SkinWatch(**_stringify_user_id(_row_dict(row)))


def _notification_delivery_from_row(row: asyncpg.Record) -> NotificationDelivery:
    data = _stringify_user_id(_row_dict(row))
    data["ticket_ids"] = _json_list(data.get("ticket_ids", []))
    return NotificationDelivery(**data)


def postgres_ssl_context(enabled: bool) -> ssl.SSLContext | bool:
    if not enabled:
        return False
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def build_repository(settings: BackendSettings) -> Repository:
    if settings.database_url:
        return PostgresRepository(settings)
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseRestRepository(settings)
    return InMemoryRepository()
