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
    ssid: str = Field(default="", max_length=4096)
    cookies: dict[str, str] = Field(default_factory=dict)
    client_version: str = Field(default="", max_length=120)


class LinkCompleteResponse(BaseModel):
    linked: bool
    riot_account: RiotAccount


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
