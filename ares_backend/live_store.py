from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from .repository import PostgresRepository, Repository, SupabaseRestRepository
from .schemas import CompanionDeviceRecord, LiveCommandRecord, LiveSnapshot


class LiveStore:
    def __init__(self, repository: Repository) -> None:
        self.repo = repository
        self._pair_codes: dict[str, tuple[str, datetime]] = {}
        self._devices: dict[str, CompanionDeviceRecord] = {}
        self._snapshots: dict[str, LiveSnapshot] = {}
        self._commands: dict[str, LiveCommandRecord] = {}

    async def ensure_schema(self) -> None:
        if not isinstance(self.repo, PostgresRepository):
            return
        await self.repo._execute(LIVE_SCHEMA_SQL)

    async def create_pair_code(
        self, user_id: str, code_hash_factory: Any, expires_at: datetime
    ) -> str:
        for _ in range(30):
            code = f"{secrets.randbelow(1_000_000):06d}"
            code_hash = code_hash_factory(code)
            if isinstance(self.repo, PostgresRepository):
                try:
                    await self.repo._execute(
                        """
                        insert into public.companion_pair_codes(code_hash, user_id, expires_at)
                        values ($1, $2, $3)
                        """,
                        code_hash,
                        user_id,
                        expires_at,
                    )
                    return code
                except Exception as exc:
                    if "unique" not in str(exc).lower():
                        raise
            elif isinstance(self.repo, SupabaseRestRepository):
                response = await self.repo.client.post(
                    f"{self.repo.url}/companion_pair_codes",
                    headers=self.repo.headers,
                    json={
                        "code_hash": code_hash,
                        "user_id": user_id,
                        "expires_at": expires_at.isoformat(),
                    },
                )
                if response.status_code in {200, 201}:
                    return code
                if response.status_code != 409:
                    response.raise_for_status()
            elif code_hash not in self._pair_codes:
                self._pair_codes[code_hash] = (user_id, expires_at)
                return code
        raise RuntimeError("Não foi possível gerar um código de pareamento.")

    async def consume_pair_code(self, code_hash: str) -> str | None:
        now = datetime.now(UTC)
        if isinstance(self.repo, PostgresRepository):
            row = await self.repo._fetchrow(
                """
                delete from public.companion_pair_codes
                where code_hash = $1 and consumed_at is null and expires_at >= $2
                returning user_id
                """,
                code_hash,
                now,
            )
            return str(row["user_id"]) if row else None
        if isinstance(self.repo, SupabaseRestRepository):
            row = await self.repo._select_one("companion_pair_codes", "code_hash", code_hash)
            if not row:
                return None
            await self.repo.client.delete(
                f"{self.repo.url}/companion_pair_codes",
                headers=self.repo.headers,
                params={"code_hash": f"eq.{code_hash}"},
            )
            expires_at = _dt(row.get("expires_at"))
            return str(row.get("user_id")) if expires_at and expires_at >= now else None
        item = self._pair_codes.pop(code_hash, None)
        return item[0] if item and item[1] >= now else None

    async def pair_device(self, device: CompanionDeviceRecord) -> CompanionDeviceRecord:
        now = datetime.now(UTC)
        if isinstance(self.repo, PostgresRepository):
            async with (await self.repo._pool()).acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        """
                        update public.companion_devices
                        set active = false, updated_at = $2
                        where user_id = $1 and revoked_at is null
                        """,
                        device.user_id,
                        now,
                    )
                    row = await connection.fetchrow(
                        """
                        insert into public.companion_devices(
                          device_id, user_id, device_name, app_version, protocol_version,
                          secret_hash, active, last_seen_at, created_at, updated_at
                        ) values ($1,$2,$3,$4,$5,$6,true,$7,$8,$9)
                        on conflict (device_id) do update set
                          user_id=excluded.user_id, device_name=excluded.device_name,
                          app_version=excluded.app_version,
                          protocol_version=excluded.protocol_version,
                          secret_hash=excluded.secret_hash, active=true, revoked_at=null,
                          last_seen_at=excluded.last_seen_at, updated_at=excluded.updated_at
                        returning *
                        """,
                        device.device_id,
                        device.user_id,
                        device.device_name,
                        device.app_version,
                        device.protocol_version,
                        device.secret_hash,
                        device.last_seen_at,
                        device.created_at,
                        device.updated_at,
                    )
            return _device(row)
        if isinstance(self.repo, SupabaseRestRepository):
            await self.repo.client.patch(
                f"{self.repo.url}/companion_devices",
                headers={**self.repo.headers, "Prefer": "return=minimal"},
                params={"user_id": f"eq.{device.user_id}", "revoked_at": "is.null"},
                json={"active": False, "updated_at": now.isoformat()},
            )
            row = await self.repo._upsert_one(
                "companion_devices", device.model_dump(mode="json")
            )
            return CompanionDeviceRecord(**row)
        for key, existing in tuple(self._devices.items()):
            if existing.user_id == device.user_id:
                self._devices[key] = existing.model_copy(
                    update={"active": False, "updated_at": now}
                )
        self._devices[device.device_id] = device
        return device

    async def get_device(self, device_id: str) -> CompanionDeviceRecord | None:
        if isinstance(self.repo, PostgresRepository):
            return _device(
                await self.repo._fetchrow(
                    "select * from public.companion_devices where device_id=$1", device_id
                )
            )
        if isinstance(self.repo, SupabaseRestRepository):
            row = await self.repo._select_one("companion_devices", "device_id", device_id)
            return CompanionDeviceRecord(**row) if row else None
        return self._devices.get(device_id)

    async def list_devices(self, user_id: str) -> list[CompanionDeviceRecord]:
        if isinstance(self.repo, PostgresRepository):
            rows = await self.repo._fetch(
                """
                select * from public.companion_devices
                where user_id=$1 order by active desc, updated_at desc
                """,
                user_id,
            )
            return [_device(row) for row in rows]
        if isinstance(self.repo, SupabaseRestRepository):
            rows = await self.repo._select_many(
                "companion_devices",
                {"user_id": f"eq.{user_id}", "order": "active.desc,updated_at.desc"},
            )
            return [CompanionDeviceRecord(**row) for row in rows]
        return sorted(
            (item for item in self._devices.values() if item.user_id == user_id),
            key=lambda item: (item.active, item.updated_at),
            reverse=True,
        )

    async def activate_device(self, user_id: str, device_id: str) -> CompanionDeviceRecord | None:
        device = await self.get_device(device_id)
        if not device or device.user_id != user_id or device.revoked_at:
            return None
        return await self.pair_device(
            device.model_copy(update={"active": True, "updated_at": datetime.now(UTC)})
        )

    async def revoke_device(self, user_id: str, device_id: str) -> bool:
        now = datetime.now(UTC)
        device = await self.get_device(device_id)
        if not device or device.user_id != user_id:
            return False
        if isinstance(self.repo, PostgresRepository):
            await self.repo._execute(
                """
                update public.companion_devices
                set active=false, revoked_at=$3, updated_at=$3
                where user_id=$1 and device_id=$2
                """,
                user_id,
                device_id,
                now,
            )
        elif isinstance(self.repo, SupabaseRestRepository):
            response = await self.repo.client.patch(
                f"{self.repo.url}/companion_devices",
                headers={**self.repo.headers, "Prefer": "return=minimal"},
                params={"user_id": f"eq.{user_id}", "device_id": f"eq.{device_id}"},
                json={"active": False, "revoked_at": now.isoformat(), "updated_at": now.isoformat()},
            )
            response.raise_for_status()
        else:
            self._devices[device_id] = device.model_copy(
                update={"active": False, "revoked_at": now, "updated_at": now}
            )
        return True

    async def touch_device(self, device_id: str, app_version: str = "") -> None:
        now = datetime.now(UTC)
        device = await self.get_device(device_id)
        if not device:
            return
        if isinstance(self.repo, PostgresRepository):
            await self.repo._execute(
                """
                update public.companion_devices set last_seen_at=$2,
                  app_version=case when $3='' then app_version else $3 end, updated_at=$2
                where device_id=$1
                """,
                device_id,
                now,
                app_version,
            )
        elif isinstance(self.repo, SupabaseRestRepository):
            await self.repo.client.patch(
                f"{self.repo.url}/companion_devices",
                headers={**self.repo.headers, "Prefer": "return=minimal"},
                params={"device_id": f"eq.{device_id}"},
                json={
                    "last_seen_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    **({"app_version": app_version} if app_version else {}),
                },
            )
        else:
            self._devices[device_id] = device.model_copy(
                update={
                    "last_seen_at": now,
                    "updated_at": now,
                    "app_version": app_version or device.app_version,
                }
            )

    async def save_snapshot(self, snapshot: LiveSnapshot) -> LiveSnapshot:
        if isinstance(self.repo, PostgresRepository):
            row = await self.repo._fetchrow(
                """
                insert into public.live_snapshots(user_id,device_id,revision,phase,state,updated_at)
                values($1,$2,$3,$4,$5::jsonb,$6)
                on conflict(user_id) do update set
                  device_id=excluded.device_id, revision=excluded.revision,
                  phase=excluded.phase, state=excluded.state, updated_at=excluded.updated_at
                where public.live_snapshots.revision < excluded.revision
                   or public.live_snapshots.device_id <> excluded.device_id
                returning *
                """,
                snapshot.user_id,
                snapshot.device_id,
                snapshot.revision,
                snapshot.phase,
                _json(snapshot.state),
                snapshot.updated_at,
            )
            return _snapshot(row) if row else (await self.get_snapshot(snapshot.user_id)) or snapshot
        if isinstance(self.repo, SupabaseRestRepository):
            current = await self.get_snapshot(snapshot.user_id)
            if current and current.device_id == snapshot.device_id and current.revision >= snapshot.revision:
                return current
            row = await self.repo._upsert_one("live_snapshots", snapshot.model_dump(mode="json"))
            return LiveSnapshot(**row)
        current = self._snapshots.get(snapshot.user_id)
        if current and current.device_id == snapshot.device_id and current.revision >= snapshot.revision:
            return current
        self._snapshots[snapshot.user_id] = snapshot
        return snapshot

    async def get_snapshot(self, user_id: str) -> LiveSnapshot | None:
        if isinstance(self.repo, PostgresRepository):
            return _snapshot(
                await self.repo._fetchrow(
                    "select * from public.live_snapshots where user_id=$1", user_id
                )
            )
        if isinstance(self.repo, SupabaseRestRepository):
            row = await self.repo._select_one("live_snapshots", "user_id", user_id)
            return LiveSnapshot(**row) if row else None
        return self._snapshots.get(user_id)

    async def create_command(self, command: LiveCommandRecord) -> LiveCommandRecord:
        existing = await self.get_command(command.command_id)
        if existing:
            if existing.user_id != command.user_id:
                raise ValueError("command_id já utilizado por outro usuário.")
            return existing
        if isinstance(self.repo, PostgresRepository):
            row = await self.repo._fetchrow(
                """
                insert into public.live_commands(
                  command_id,user_id,device_id,command,payload,status,result,
                  created_at,expires_at,delivered_at,completed_at
                ) values($1,$2,$3,$4,$5::jsonb,$6,$7::jsonb,$8,$9,$10,$11)
                returning *
                """,
                command.command_id,
                command.user_id,
                command.device_id,
                command.command,
                _json(command.payload),
                command.status,
                _json(command.result),
                command.created_at,
                command.expires_at,
                command.delivered_at,
                command.completed_at,
            )
            return _command(row)
        if isinstance(self.repo, SupabaseRestRepository):
            row = await self.repo._upsert_one("live_commands", command.model_dump(mode="json"))
            return LiveCommandRecord(**row)
        self._commands[command.command_id] = command
        return command

    async def get_command(self, command_id: str) -> LiveCommandRecord | None:
        if isinstance(self.repo, PostgresRepository):
            return _command(
                await self.repo._fetchrow(
                    "select * from public.live_commands where command_id=$1", command_id
                )
            )
        if isinstance(self.repo, SupabaseRestRepository):
            row = await self.repo._select_one("live_commands", "command_id", command_id)
            return LiveCommandRecord(**row) if row else None
        return self._commands.get(command_id)

    async def pending_commands(self, user_id: str, device_id: str) -> list[LiveCommandRecord]:
        now = datetime.now(UTC)
        if isinstance(self.repo, PostgresRepository):
            await self.repo._execute(
                """
                update public.live_commands set status='expired', completed_at=$1
                where user_id=$2 and status in ('queued','delivered') and expires_at < $1
                """,
                now,
                user_id,
            )
            rows = await self.repo._fetch(
                """
                select * from public.live_commands
                where user_id=$1 and device_id=$2 and status='queued' and expires_at >= $3
                order by created_at asc limit 30
                """,
                user_id,
                device_id,
                now,
            )
            return [_command(row) for row in rows]
        if isinstance(self.repo, SupabaseRestRepository):
            rows = await self.repo._select_many(
                "live_commands",
                {
                    "user_id": f"eq.{user_id}",
                    "device_id": f"eq.{device_id}",
                    "status": "eq.queued",
                    "expires_at": f"gte.{now.isoformat()}",
                    "order": "created_at.asc",
                    "limit": "30",
                },
            )
            return [LiveCommandRecord(**row) for row in rows]
        result = []
        for key, item in tuple(self._commands.items()):
            if item.status in {"queued", "delivered"} and item.expires_at < now:
                self._commands[key] = item.model_copy(
                    update={"status": "expired", "completed_at": now}
                )
            elif item.user_id == user_id and item.device_id == device_id and item.status == "queued":
                result.append(item)
        return sorted(result, key=lambda item: item.created_at)[:30]

    async def update_command(
        self, command_id: str, status: str, result: dict[str, Any] | None = None
    ) -> LiveCommandRecord | None:
        current = await self.get_command(command_id)
        if not current:
            return None
        allowed = {
            "queued": {"delivered", "rejected", "failed", "expired"},
            "delivered": {"succeeded", "rejected", "failed", "expired"},
        }
        if status != current.status and status not in allowed.get(current.status, set()):
            return current
        now = datetime.now(UTC)
        update = {
            "status": status,
            "result": result or current.result,
            "delivered_at": now if status == "delivered" else current.delivered_at,
            "completed_at": now if status in {"succeeded", "rejected", "failed", "expired"} else current.completed_at,
        }
        if isinstance(self.repo, PostgresRepository):
            row = await self.repo._fetchrow(
                """
                update public.live_commands set status=$2,result=$3::jsonb,
                  delivered_at=$4,completed_at=$5 where command_id=$1 returning *
                """,
                command_id,
                update["status"],
                _json(update["result"]),
                update["delivered_at"],
                update["completed_at"],
            )
            return _command(row)
        if isinstance(self.repo, SupabaseRestRepository):
            response = await self.repo.client.patch(
                f"{self.repo.url}/live_commands",
                headers={**self.repo.headers, "Prefer": "return=representation"},
                params={"command_id": f"eq.{command_id}"},
                json={
                    key: value.isoformat() if isinstance(value, datetime) else value
                    for key, value in update.items()
                },
            )
            response.raise_for_status()
            rows = response.json()
            return LiveCommandRecord(**rows[0]) if rows else current
        updated = current.model_copy(update=update)
        self._commands[command_id] = updated
        return updated


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _dict(row: Any) -> dict[str, Any] | None:
    return dict(row) if row else None


def _device(row: Any) -> CompanionDeviceRecord | None:
    data = _dict(row)
    return CompanionDeviceRecord(**data) if data else None


def _snapshot(row: Any) -> LiveSnapshot | None:
    data = _dict(row)
    return LiveSnapshot(**data) if data else None


def _command(row: Any) -> LiveCommandRecord | None:
    data = _dict(row)
    return LiveCommandRecord(**data) if data else None


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


LIVE_SCHEMA_SQL = """
create table if not exists public.companion_pair_codes (
  code_hash text primary key,
  user_id text not null,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists companion_pair_codes_expires_idx
  on public.companion_pair_codes(expires_at);

create table if not exists public.companion_devices (
  device_id text primary key,
  user_id text not null,
  device_name text not null,
  app_version text not null,
  protocol_version integer not null default 1,
  secret_hash text not null,
  active boolean not null default true,
  revoked_at timestamptz,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists companion_devices_user_active_idx
  on public.companion_devices(user_id, active);
create unique index if not exists companion_devices_one_active_idx
  on public.companion_devices(user_id) where active and revoked_at is null;

create table if not exists public.live_snapshots (
  user_id text primary key,
  device_id text not null,
  revision bigint not null default 0,
  phase text not null,
  state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.live_commands (
  command_id text primary key,
  user_id text not null,
  device_id text not null,
  command text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  delivered_at timestamptz,
  completed_at timestamptz
);
create index if not exists live_commands_delivery_idx
  on public.live_commands(user_id, device_id, status, expires_at);
alter table public.companion_pair_codes enable row level security;
alter table public.companion_devices enable row level security;
alter table public.live_snapshots enable row level security;
alter table public.live_commands enable row level security;
"""
