from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


Capability = Literal[
    "remote_supported",
    "local_only",
    "requires_game_state",
    "unsafe_mutation",
    "unsupported_hosted",
]


class AuthUser(BaseModel):
    id: str
    email: str | None = None
    claims: dict[str, Any] = Field(default_factory=dict)


class PasswordAuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=80)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=4096)


class AuthSession(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int | None = None
    expires_at: int | None = None


class AuthSessionResponse(BaseModel):
    user: AuthUser
    session: AuthSession | None = None
    profile: "Profile | None" = None
    email_confirmation_required: bool = False
    message: str = ""


class Profile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    display_name: str = ""
    avatar_url: str = ""
    preferences: dict[str, Any] = Field(default_factory=dict)


class ProfilePatch(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    preferences: dict[str, Any] | None = None


class RiotAccount(BaseModel):
    user_id: str
    puuid: str
    game_name: str = ""
    tag_line: str = ""
    region: str
    shard: str
    client_version: str = ""
    linked_at: datetime


class RiotCredentialRecord(BaseModel):
    user_id: str
    encrypted_payload: str
    last_refresh_at: datetime | None = None
    expires_hint: datetime | None = None
    updated_at: datetime


class RiotCredentialPayload(BaseModel):
    ssid: str = ""
    cookies: dict[str, str] = Field(default_factory=dict)
    access_token: str = ""
    id_token: str = ""
    entitlement_token: str = ""
    puuid: str = ""
    region: str = ""
    shard: str = ""
    client_version: str = ""
    game_name: str = ""
    tag_line: str = ""


class CompanionRiotSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(min_length=20, max_length=8192)
    entitlement_token: str = Field(min_length=20, max_length=8192)
    puuid: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=1, max_length=20)
    shard: str = Field(min_length=1, max_length=20)
    client_version: str = Field(default="", max_length=160)


class LinkStartResponse(BaseModel):
    link_code: str
    created_at: datetime
    expires_at: datetime


class LinkCompleteRequest(BaseModel):
    link_code: str
    riot: RiotCredentialPayload


class RiotMobileLoginCompleteRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=8192)
    id_token: str = Field(default="", max_length=8192)
    entitlement_token: str = Field(default="", max_length=8192)
    puuid: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=20)
    shard: str = Field(default="", max_length=20)
    game_name: str = Field(default="", max_length=80)
    tag_line: str = Field(default="", max_length=20)
    ssid: str = Field(default="", max_length=4096)
    cookies: dict[str, str] = Field(default_factory=dict)
    client_version: str = Field(default="", max_length=120)


class LinkCompleteResponse(BaseModel):
    linked: bool
    riot_account: RiotAccount


LivePhase = Literal[
    "offline",
    "client",
    "lobby",
    "queue",
    "match_found",
    "pregame",
    "in_game",
    "postgame",
    "error",
]
LiveCommandStatus = Literal[
    "queued", "delivered", "succeeded", "rejected", "failed", "expired"
]


class CompanionPairStartResponse(BaseModel):
    pair_code: str
    created_at: datetime
    expires_at: datetime


class CompanionPairCompleteRequest(BaseModel):
    pair_code: str = Field(pattern=r"^\d{6}$")
    device_name: str = Field(min_length=1, max_length=80)
    app_version: str = Field(min_length=1, max_length=40)
    protocol_version: int = Field(ge=1, le=20)


class CompanionDevice(BaseModel):
    device_id: str
    device_name: str
    app_version: str
    protocol_version: int = 1
    active: bool = True
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CompanionDeviceRecord(CompanionDevice):
    user_id: str
    secret_hash: str


class CompanionPairCompleteResponse(BaseModel):
    device: CompanionDevice
    device_secret: str
    websocket_url: str


class LiveSnapshot(BaseModel):
    user_id: str
    device_id: str
    revision: int = Field(ge=0)
    phase: LivePhase = "offline"
    state: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


LIVE_COMMAND_FIELDS: dict[str, set[str]] = {
    "party.change_queue": {"queue_id"},
    "party.join_queue": set(),
    "party.leave_queue": set(),
    "party.set_ready": {"ready"},
    "party.invite": {"game_name", "tag_line"},
    "party.remove_member": {"puuid"},
    "party.set_accessibility": {"accessibility"},
    "party.generate_code": set(),
    "pregame.select_agent": {"agent_id"},
    "pregame.lock_agent": {"agent_id"},
    "chat.send": {"cid", "message", "chat_type"},
    "current_game.leave": {"confirmed"},
    "match.accept": set(),
}


class LiveCommandCreate(BaseModel):
    command_id: str = Field(default_factory=lambda: str(uuid4()), min_length=8, max_length=80)
    command: str = Field(min_length=3, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_typed_command(self) -> "LiveCommandCreate":
        expected = LIVE_COMMAND_FIELDS.get(self.command)
        if expected is None:
            raise ValueError("Comando ao vivo não permitido.")
        supplied = set(self.payload)
        if supplied != expected:
            raise ValueError("Payload do comando não corresponde ao contrato permitido.")
        if self.command == "party.change_queue":
            _require_text(self.payload, "queue_id", 40)
        elif self.command == "party.set_ready" and not isinstance(self.payload.get("ready"), bool):
            raise ValueError("ready deve ser booleano.")
        elif self.command == "party.invite":
            _require_text(self.payload, "game_name", 80)
            _require_text(self.payload, "tag_line", 20)
        elif self.command == "party.remove_member":
            _require_text(self.payload, "puuid", 120)
        elif self.command == "party.set_accessibility":
            if self.payload.get("accessibility") not in {"OPEN", "CLOSED"}:
                raise ValueError("A privacidade deve ser OPEN ou CLOSED.")
        elif self.command in {"pregame.select_agent", "pregame.lock_agent"}:
            _require_text(self.payload, "agent_id", 80)
        elif self.command == "chat.send":
            _require_text(self.payload, "cid", 180)
            _require_text(self.payload, "message", 280)
            if self.payload.get("chat_type") not in {"chat", "groupchat"}:
                raise ValueError("Tipo de chat não permitido.")
        elif self.command == "current_game.leave" and self.payload.get("confirmed") is not True:
            raise ValueError("A saída exige confirmação explícita.")
        return self


class LiveCommandRecord(LiveCommandCreate):
    user_id: str
    device_id: str
    status: LiveCommandStatus = "queued"
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    expires_at: datetime
    delivered_at: datetime | None = None
    completed_at: datetime | None = None


def _require_text(payload: dict[str, Any], key: str, maximum: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{key} é inválido.")
    return value.strip()


class RouteInfo(BaseModel):
    id: str
    name: str
    query_name: str = ""
    method: str
    category: str
    capability: Capability
    reason: str = ""
    docs_url: str = ""
    description: str = ""


class GenericRouteRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    query: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] | list[Any] | None = None
    confirm_mutation: bool = False


class GenericRouteResponse(BaseModel):
    route_id: str
    capability: Capability
    executed: bool
    status_code: int | None = None
    data: Any = None
    error: dict[str, Any] | None = None


class StoreItem(BaseModel):
    item_id: str
    item_type_id: str = ""
    name: str = ""
    display_icon: str = ""
    full_render: str = ""
    tier: str = ""
    price: int | None = None
    original_price: int | None = None
    discount_percent: int | None = None
    is_seen: bool | None = None
    bonus_offer_id: str = ""
    currency_id: str = ""
    source: str


class StoreDailyResponse(BaseModel):
    expires_at: datetime | None = None
    seconds_remaining: int | None = None
    items: list[StoreItem]
    night_market: list[StoreItem] = Field(default_factory=list)
    night_market_expires_at: datetime | None = None
    night_market_seconds_remaining: int | None = None
    night_market_active: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class NightMarketResponse(BaseModel):
    active: bool
    expires_at: datetime | None = None
    seconds_remaining: int | None = None
    items: list[StoreItem] = Field(default_factory=list)


class ItemStatusResponse(BaseModel):
    item_id: str
    owned: bool
    in_daily_store: bool
    in_night_market: bool
    price: int | None = None
    expires_at: datetime | None = None
    source: str = "none"
    item: dict[str, Any] | None = None


Platform = Literal["ios", "android", "web", "unknown"]
PushProvider = Literal["fcm", "expo"]


class PushDeviceRegisterRequest(BaseModel):
    push_token: str = Field(default="", max_length=4096)
    expo_push_token: str = Field(default="", max_length=4096)
    provider: PushProvider = "fcm"
    platform: Platform = "unknown"
    device_name: str = Field(default="", max_length=120)
    app_version: str = Field(default="", max_length=40)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_token(self) -> "PushDeviceRegisterRequest":
        legacy_token = self.expo_push_token.strip()
        modern_token = self.push_token.strip()
        token = modern_token or legacy_token
        if len(token) < 20:
            raise ValueError("Push token must contain at least 20 characters.")
        self.push_token = token
        if legacy_token and not modern_token:
            self.provider = "expo"
        return self


class PushDevice(BaseModel):
    device_id: str
    user_id: str
    push_token: str = ""
    provider: PushProvider = "fcm"
    masked_token: str = ""
    platform: Platform = "unknown"
    device_name: str = ""
    app_version: str = ""
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class SkinWatchCreateRequest(BaseModel):
    item_id: str = Field(min_length=8, max_length=80)
    notify_enabled: bool = True


class SkinWatch(BaseModel):
    user_id: str
    item_id: str
    item_name: str = ""
    display_icon: str = ""
    tier: str = ""
    notify_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class NotificationDelivery(BaseModel):
    delivery_key: str
    user_id: str
    item_id: str
    item_name: str = ""
    source: str = "daily_store"
    store_expires_at: datetime | None = None
    status: str = "pending"
    ticket_ids: list[str] = Field(default_factory=list)
    error: str = ""
    sent_at: datetime


class AlertMatch(BaseModel):
    item_id: str
    item_name: str = ""
    source: str
    price: int | None = None
    expires_at: datetime | None = None
    already_notified: bool = False
    sent_count: int = 0


class AlertCheckResponse(BaseModel):
    user_id: str
    checked: bool
    matched: list[AlertMatch] = Field(default_factory=list)
    sent_count: int = 0
    device_count: int = 0
    errors: list[str] = Field(default_factory=list)


class JobRunResponse(BaseModel):
    checked_users: int
    relink_required: int
    sent_count: int
    errors: list[str] = Field(default_factory=list)


DiagnosticSource = Literal["mobile", "desktop", "backend"]
DiagnosticLevel = Literal["debug", "info", "warning", "error", "critical"]


class DiagnosticEventCreate(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()), max_length=80)
    source: DiagnosticSource
    level: DiagnosticLevel = "error"
    category: str = Field(default="general", max_length=120)
    message: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)
    stack_trace: str = Field(default="", max_length=16000)
    request_id: str = Field(default="", max_length=120)
    app_version: str = Field(default="", max_length=80)
    device_id: str = Field(default="", max_length=240)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiagnosticEventRecord(DiagnosticEventCreate):
    user_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
