from __future__ import annotations

import asyncio
import hmac
import json
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ares_console.catalog import EndpointCatalog
from ares_console.executor import EndpointExecutor

from .assets import (
    ASSET_ENDPOINTS,
    ValorantAssetsClient,
    search_key,
    skin_catalog_filters,
)
from .auth import SupabaseAuth
from .capabilities import classify_endpoint
from .diagnostics import (
    diagnostic_record,
    emit_log,
    redact_text,
    sanitize_context,
    user_fingerprint,
)
from .errors import BackendError, RelinkRequiredError, RiotRequestError, UnauthorizedError
from .live import (
    LiveHub,
    command_public,
    hash_companion_secret,
    new_companion_secret,
    public_companion_device,
    sanitize_live_state,
    snapshot_public,
    verify_companion_secret,
)
from .live_store import LiveStore
from .notifications import PushClient, StoreAlertService
from .player import normalize_match_details, normalize_player_summary
from .repository import Repository, build_repository
from .riot import (
    REGION_TO_SHARD,
    RiotAuthService,
    RiotRemoteClient,
    RiotSession,
    access_token_expiration,
    access_token_needs_refresh,
)
from .schemas import (
    AuthSessionResponse,
    AuthUser,
    DiagnosticEventCreate,
    GenericRouteRequest,
    GenericRouteResponse,
    LinkCompleteRequest,
    LinkCompleteResponse,
    LinkStartResponse,
    CompanionDeviceRecord,
    CompanionRiotSessionPayload,
    CompanionPairCompleteRequest,
    CompanionPairCompleteResponse,
    CompanionPairStartResponse,
    JobRunResponse,
    PasswordAuthRequest,
    Profile,
    ProfilePatch,
    PushDeviceRegisterRequest,
    RefreshTokenRequest,
    RiotMobileLoginCompleteRequest,
    RiotAccount,
    RiotCredentialPayload,
    RiotCredentialRecord,
    RouteInfo,
    SkinWatchCreateRequest,
    LiveCommandCreate,
    LiveCommandRecord,
    LiveSnapshot,
)
from .security import CryptoService
from .settings import BackendSettings, get_settings
from .store import StoreService


@dataclass(slots=True)
class AppServices:
    settings: BackendSettings
    repo: Repository
    crypto: CryptoService
    auth: SupabaseAuth
    riot_auth: RiotAuthService
    riot_client: RiotRemoteClient
    assets: ValorantAssetsClient
    store: StoreService
    alerts: StoreAlertService
    catalog: EndpointCatalog
    executor: EndpointExecutor
    live_store: LiveStore
    live_hub: LiveHub


async def run_riot_account_monitor(svc: AppServices) -> JobRunResponse:
    user_ids = await svc.repo.list_users_with_riot_accounts()
    checked = 0
    relink_required = 0
    sent = 0
    errors: list[str] = []
    for user_id in user_ids:
        try:
            session = await svc.riot_auth.session_for_user(user_id, svc.repo)
            daily = await svc.store.daily_store(user_id, session)
            result = await svc.alerts.check_daily_store(user_id, daily)
            checked += 1
            sent += result.sent_count
            errors.extend(f"{user_id}: {error}" for error in result.errors)
        except RelinkRequiredError:
            relink_required += 1
            try:
                if await should_notify_riot_relink(user_id, svc):
                    sent += await svc.alerts.notify_riot_relink_required(user_id)
            except Exception as exc:
                errors.append(f"{user_id}: relink notification failed: {type(exc).__name__}")
        except Exception as exc:
            errors.append(f"{user_id}: {exc}")
    return JobRunResponse(
        checked_users=checked,
        relink_required=relink_required,
        sent_count=sent,
        errors=errors[:50],
    )


async def riot_account_monitor_loop(svc: AppServices) -> None:
    await asyncio.sleep(30)
    while True:
        result = await run_riot_account_monitor(svc)
        emit_log(
            "riot_account_monitor",
            checked_users=result.checked_users,
            relink_required=result.relink_required,
            sent_count=result.sent_count,
            errors=len(result.errors),
        )
        await asyncio.sleep(max(60, svc.settings.riot_session_monitor_interval_seconds))


def create_app(
    *,
    settings: BackendSettings | None = None,
    repository: Repository | None = None,
    riot_auth: RiotAuthService | None = None,
    riot_client: RiotRemoteClient | None = None,
    assets: ValorantAssetsClient | None = None,
    push_client: PushClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    crypto = CryptoService(settings.app_secret_key)
    repo = repository or build_repository(settings)
    riot_client = riot_client or RiotRemoteClient(settings)
    assets = assets or ValorantAssetsClient(settings)
    live_store = LiveStore(repo)
    services = AppServices(
        settings=settings,
        repo=repo,
        crypto=crypto,
        auth=SupabaseAuth(settings),
        riot_auth=riot_auth or RiotAuthService(settings, crypto),
        riot_client=riot_client,
        assets=assets,
        store=StoreService(riot_client, assets, repo),
        alerts=StoreAlertService(settings, repo, assets, push_client),
        catalog=EndpointCatalog(),
        executor=EndpointExecutor(),
        live_store=live_store,
        live_hub=LiveHub(),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ensure_schema = getattr(services.repo, "ensure_schema", None)
        if ensure_schema:
            await ensure_schema()
        await services.live_store.ensure_schema()
        monitor_task: asyncio.Task[None] | None = None
        if services.settings.environment == "production":
            monitor_task = asyncio.create_task(riot_account_monitor_loop(services))
        try:
            yield
        finally:
            if monitor_task is not None:
                monitor_task.cancel()
                with suppress(asyncio.CancelledError):
                    await monitor_task

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Backend hosted for a Valorant mobile app. Uses Supabase auth and "
            "unofficial Riot client endpoints without a Riot Developer API key."
        ),
        lifespan=lifespan,
    )
    app.state.services = services

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_diagnostics(request: Request, call_next: Any) -> JSONResponse:
        supplied_request_id = request.headers.get("X-Request-ID", "").strip()
        request_id = (
            supplied_request_id[:120]
            if 8 <= len(supplied_request_id) <= 120
            else str(uuid4())
        )
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        emit_log(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=elapsed_ms,
            user=user_fingerprint(getattr(request.state, "user_id", None)),
            client=request.headers.get("X-Valcomp-Client", "")[:80],
        )
        return response

    @app.exception_handler(BackendError)
    async def backend_error_handler(request: Request, exc: BackendError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        message = redact_text(str(exc), max_length=4000)
        payload: dict[str, Any] = {
            "error": {
                "code": exc.code,
                "message": message,
                "request_id": request_id,
            }
        }
        if isinstance(exc, RiotRequestError) and exc.riot_status is not None:
            payload["error"]["riot_status"] = exc.riot_status
        await persist_backend_error(request, exc.code, message, exc.status_code)
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = str(detail.get("code") or "http_error")
        message = redact_text(
            str(detail.get("message") or exc.detail or "Não foi possível concluir esta ação."),
            max_length=4000,
        )
        await persist_backend_error(request, code, message, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id,
                }
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        await persist_backend_error(
            request,
            "internal_error",
            f"{type(exc).__name__}: {exc}",
            500,
            stack_trace=repr(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Algo deu errado no servidor. Tente novamente em instantes.",
                    "request_id": request_id,
                }
            },
        )

    async def persist_backend_error(
        request: Request,
        code: str,
        message: str,
        status_code: int,
        *,
        stack_trace: str = "",
    ) -> None:
        request_id = getattr(request.state, "request_id", "")
        user_id = getattr(request.state, "user_id", None)
        emit_log(
            "request_error",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            status=status_code,
            code=code,
            message=message,
            user=user_fingerprint(user_id),
        )
        try:
            record = diagnostic_record(
                DiagnosticEventCreate(
                    source="backend",
                    level="error" if status_code < 500 else "critical",
                    category=code,
                    message=message,
                    context={
                        "path": request.url.path,
                        "method": request.method,
                        "status_code": status_code,
                    },
                    stack_trace=stack_trace,
                    request_id=request_id,
                    app_version=app.version,
                ),
                user_id=user_id,
                fallback_request_id=request_id,
            )
            await services.repo.add_diagnostic_event(record)
        except Exception as persist_error:
            emit_log(
                "diagnostic_persist_failed",
                request_id=request_id,
                error=type(persist_error).__name__,
            )
        if code == "relink_required" and user_id:
            try:
                if await should_notify_riot_relink(user_id, services):
                    await services.alerts.notify_riot_relink_required(user_id)
            except Exception as notification_error:
                emit_log(
                    "relink_notification_failed",
                    request_id=request_id,
                    user=user_fingerprint(user_id),
                    error=type(notification_error).__name__,
                )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "environment": settings.environment,
            "supabase": bool(settings.supabase_url),
            "catalog_routes": len(services.catalog.endpoints),
        }

    @app.post("/auth/signup", response_model=AuthSessionResponse)
    async def auth_signup(
        payload: PasswordAuthRequest,
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> AuthSessionResponse:
        result = await svc.auth.sign_up_with_password(
            payload.email, payload.password, payload.display_name, svc.repo
        )
        result.profile = await ensure_profile(result.user, svc.repo, payload.display_name)
        return result

    @app.post("/auth/login", response_model=AuthSessionResponse)
    async def auth_login(
        payload: PasswordAuthRequest,
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> AuthSessionResponse:
        result = await svc.auth.sign_in_with_password(payload.email, payload.password, svc.repo)
        result.profile = await ensure_profile(result.user, svc.repo)
        return result

    @app.post("/auth/refresh", response_model=AuthSessionResponse)
    async def auth_refresh(
        payload: RefreshTokenRequest,
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> AuthSessionResponse:
        result = await svc.auth.refresh_password_session(payload.refresh_token, svc.repo)
        result.profile = await ensure_profile(result.user, svc.repo)
        return result

    @app.post("/auth/session/verify")
    async def verify_session(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        profile = await ensure_profile(user, svc.repo)
        return {"valid": True, "user": user.model_dump(), "profile": profile.model_dump()}

    @app.post("/diagnostics/events")
    async def create_diagnostic_event(
        payload: DiagnosticEventCreate,
        user: Annotated[AuthUser, Depends(current_user)],
        request: Request,
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        record = diagnostic_record(
            payload,
            user_id=user.id,
            fallback_request_id=getattr(request.state, "request_id", ""),
        )
        saved = await svc.repo.add_diagnostic_event(record)
        emit_log(
            "client_diagnostic",
            event_id=saved.event_id,
            source=saved.source,
            level=saved.level,
            category=saved.category,
            request_id=saved.request_id,
            user=user_fingerprint(user.id),
        )
        return {
            "accepted": True,
            "event_id": saved.event_id,
            "request_id": saved.request_id,
        }

    @app.get("/diagnostics/events")
    async def list_diagnostic_events(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> dict[str, Any]:
        rows = await svc.repo.list_diagnostic_events(user.id, limit)
        return {
            "events": [
                row.model_dump(mode="json", exclude={"user_id"}) for row in rows
            ]
        }

    @app.get("/jobs/diagnostics/export")
    async def export_diagnostic_events(
        svc: Annotated[AppServices, Depends(get_services)],
        x_job_token: Annotated[str | None, Header(alias="X-Job-Token")] = None,
        limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    ) -> dict[str, Any]:
        require_job_token(svc.settings, x_job_token)
        rows = await svc.repo.list_all_diagnostic_events(limit)
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "environment": svc.settings.environment,
            "events": [
                {
                    **row.model_dump(mode="json", exclude={"user_id"}),
                    "user": user_fingerprint(row.user_id),
                }
                for row in rows
            ],
        }

    @app.post("/riot/link/start", response_model=LinkStartResponse)
    async def link_start(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> LinkStartResponse:
        await ensure_profile(user, svc.repo)
        code, expires_at = await svc.repo.create_link_code(
            user.id, svc.settings.link_code_ttl_seconds
        )
        created_at = expires_at - timedelta(seconds=svc.settings.link_code_ttl_seconds)
        return LinkStartResponse(
            link_code=code,
            created_at=created_at,
            expires_at=expires_at,
        )

    @app.post("/riot/link/complete", response_model=LinkCompleteResponse)
    async def link_complete(
        payload: LinkCompleteRequest,
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> LinkCompleteResponse:
        code = payload.link_code.strip()
        if not await svc.repo.get_link_code_user(code):
            raise HTTPException(
                status_code=404,
                detail={"code": "link_code_invalid", "message": "Link code is invalid or expired."},
            )
        riot_payload = await normalize_link_payload(payload.riot, svc)
        user_id = await svc.repo.consume_link_code(code)
        if not user_id:
            raise HTTPException(
                status_code=404,
                detail={"code": "link_code_invalid", "message": "Link code is invalid or expired."},
            )
        account = await persist_riot_link(user_id, riot_payload, svc)
        return LinkCompleteResponse(linked=True, riot_account=account)

    @app.post("/riot/mobile-login/complete", response_model=LinkCompleteResponse)
    async def riot_mobile_login_complete(
        payload: RiotMobileLoginCompleteRequest,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> LinkCompleteResponse:
        await ensure_profile(user, svc.repo)
        riot_payload = await svc.riot_auth.payload_from_web_login(
            access_token=payload.access_token,
            id_token=payload.id_token,
            entitlement_token=payload.entitlement_token,
            puuid=payload.puuid,
            region=payload.region,
            shard=payload.shard,
            game_name=payload.game_name,
            tag_line=payload.tag_line,
            ssid=payload.ssid,
            cookies=payload.cookies,
            client_version=payload.client_version,
        )
        riot_payload = await normalize_link_payload(riot_payload, svc)
        account = await persist_riot_link(user.id, riot_payload, svc)
        return LinkCompleteResponse(linked=True, riot_account=account)

    @app.get("/riot/session/status")
    async def riot_session_status(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, bool]:
        session = await riot_session_for_user(user, svc)
        await svc.riot_client.mmr(session)
        return {"valid": True}

    @app.get("/me")
    async def get_me(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        profile = await ensure_profile(user, svc.repo)
        account = await svc.repo.get_riot_account(user.id)
        return {
            "user": user.model_dump(),
            "profile": profile.model_dump(),
            "riot_account": account.model_dump() if account else None,
        }

    @app.patch("/me")
    async def patch_me(
        patch: ProfilePatch,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        current = await ensure_profile(user, svc.repo)
        updated = current.model_copy(
            update={
                key: value
                for key, value in patch.model_dump().items()
                if value is not None
            }
        )
        updated = await svc.repo.upsert_profile(updated)
        return {"profile": updated.model_dump()}

    @app.post("/notifications/devices")
    async def register_push_device(
        payload: PushDeviceRegisterRequest,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        device = await svc.alerts.register_device(user.id, payload)
        return {"device": public_device(device)}

    @app.get("/notifications/devices")
    async def list_push_devices(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        devices = await svc.repo.list_push_devices(user.id)
        return {"devices": [public_device(device) for device in devices]}

    @app.post("/notifications/test")
    async def send_test_notification(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        return await svc.alerts.send_test_notification(user.id)

    @app.delete("/notifications/devices/{device_id}")
    async def disable_push_device(
        device_id: str,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        return {"disabled": await svc.repo.disable_push_device(user.id, device_id)}

    @app.get("/notifications/deliveries")
    async def list_notification_deliveries(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> dict[str, Any]:
        deliveries = await svc.repo.list_notification_deliveries(user.id, limit)
        return {"deliveries": [delivery.model_dump(mode="json") for delivery in deliveries]}

    @app.post("/companion/pair/start", response_model=CompanionPairStartResponse)
    async def companion_pair_start(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> CompanionPairStartResponse:
        if not svc.settings.live_feature_enabled:
            raise HTTPException(503, detail={"code": "live_disabled", "message": "O Companion ao vivo está temporariamente desativado."})
        created_at = datetime.now(UTC)
        expires_at = created_at + timedelta(
            seconds=svc.settings.companion_pair_code_ttl_seconds
        )
        code = await svc.live_store.create_pair_code(
            user.id,
            lambda value: hash_companion_secret(value, svc.settings.app_secret_key),
            expires_at,
        )
        return CompanionPairStartResponse(
            pair_code=code, created_at=created_at, expires_at=expires_at
        )

    @app.post("/companion/pair/complete", response_model=CompanionPairCompleteResponse)
    async def companion_pair_complete(
        payload: CompanionPairCompleteRequest,
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> CompanionPairCompleteResponse:
        if payload.protocol_version != svc.settings.live_protocol_version:
            raise HTTPException(
                409,
                detail={
                    "code": "protocol_upgrade_required",
                    "message": "Atualize o Valcomp Companion antes de parear.",
                },
            )
        code_hash = hash_companion_secret(payload.pair_code, svc.settings.app_secret_key)
        user_id = await svc.live_store.consume_pair_code(code_hash)
        if not user_id:
            raise HTTPException(
                410,
                detail={
                    "code": "pair_code_invalid",
                    "message": "O código expirou ou já foi utilizado.",
                },
            )
        now = datetime.now(UTC)
        secret = new_companion_secret()
        device = await svc.live_store.pair_device(
            CompanionDeviceRecord(
                device_id=str(uuid4()),
                user_id=user_id,
                device_name=payload.device_name.strip(),
                app_version=payload.app_version.strip(),
                protocol_version=payload.protocol_version,
                secret_hash=hash_companion_secret(secret, svc.settings.app_secret_key),
                active=True,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        websocket_url = svc.settings.api_base_url.rstrip("/")
        websocket_url = websocket_url.replace("https://", "wss://").replace("http://", "ws://")
        return CompanionPairCompleteResponse(
            device=device,
            device_secret=secret,
            websocket_url=f"{websocket_url}/ws/companion",
        )

    @app.get("/companion/devices")
    async def companion_devices(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        devices = await svc.live_store.list_devices(user.id)
        return {"devices": [public_companion_device(device) for device in devices]}

    @app.post("/companion/devices/{device_id}/activate")
    async def companion_device_activate(
        device_id: str,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        device = await svc.live_store.activate_device(user.id, device_id)
        if not device:
            raise HTTPException(404, detail={"code": "device_not_found", "message": "Companion não encontrado."})
        return {"device": public_companion_device(device)}

    @app.delete("/companion/devices/{device_id}")
    async def companion_device_delete(
        device_id: str,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        revoked = await svc.live_store.revoke_device(user.id, device_id)
        return {"revoked": revoked}

    @app.get("/live/state")
    async def live_state(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        snapshot = await svc.live_store.get_snapshot(user.id)
        return snapshot_public(
            snapshot, offline_after=svc.settings.live_offline_after_seconds
        )

    @app.post("/live/commands")
    async def live_command(
        payload: LiveCommandCreate,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        existing = await svc.live_store.get_command(payload.command_id)
        if existing:
            if existing.user_id != user.id:
                raise HTTPException(
                    409,
                    detail={
                        "code": "command_id_conflict",
                        "message": "Este identificador de comando já foi utilizado.",
                    },
                )
            return {"command": command_public(existing)}
        command_group = payload.command.split(".", 1)[0]
        enabled = {
            "party": svc.settings.live_party_commands_enabled,
            "pregame": svc.settings.live_agent_commands_enabled,
            "chat": svc.settings.live_chat_commands_enabled,
            "current_game": svc.settings.live_leave_commands_enabled,
            "match": svc.settings.live_match_accept_enabled,
        }.get(command_group, False)
        if not svc.settings.live_feature_enabled or not enabled:
            raise HTTPException(
                403,
                detail={
                    "code": "command_disabled",
                    "message": "Esta ação ao vivo está desativada no momento.",
                },
            )
        devices = await svc.live_store.list_devices(user.id)
        device = next(
            (item for item in devices if item.active and item.revoked_at is None), None
        )
        if not device:
            raise HTTPException(
                409,
                detail={
                    "code": "companion_offline",
                    "message": "Pareie e abra o Companion antes de enviar ações.",
                },
            )
        snapshot = await svc.live_store.get_snapshot(user.id)
        if payload.command == "match.accept" and not bool(
            snapshot and snapshot.state.get("capabilities", {}).get("match_accept")
        ):
            raise HTTPException(
                409,
                detail={
                    "code": "capability_unavailable",
                    "message": "O cliente Riot instalado não confirmou suporte ao aceite remoto.",
                },
            )
        now = datetime.now(UTC)
        command = await svc.live_store.create_command(
            LiveCommandRecord(
                **payload.model_dump(),
                user_id=user.id,
                device_id=device.device_id,
                status="queued",
                created_at=now,
                expires_at=now + timedelta(seconds=svc.settings.live_command_ttl_seconds),
            )
        )
        delivered = await svc.live_hub.send_to_companion(
            user.id, {"type": "command", "command": command_public(command)}
        )
        if delivered and command.status == "queued":
            command = (
                await svc.live_store.update_command(command.command_id, "delivered")
            ) or command
        await svc.live_hub.publish_mobile(
            user.id, {"type": "command_result", "command": command_public(command)}
        )
        return {"command": command_public(command)}

    @app.websocket("/ws/companion")
    async def companion_websocket(socket: WebSocket) -> None:
        svc: AppServices = socket.app.state.services
        device_id = socket.headers.get("x-companion-id") or socket.query_params.get("device_id", "")
        secret = socket.headers.get("x-companion-secret") or socket.query_params.get("secret", "")
        device = await svc.live_store.get_device(device_id)
        if (
            not device
            or not device.active
            or device.revoked_at is not None
            or not verify_companion_secret(secret, device.secret_hash, svc.settings.app_secret_key)
        ):
            await socket.close(code=4401, reason="Companion não autorizado.")
            return
        if device.protocol_version != svc.settings.live_protocol_version:
            await socket.close(code=4409, reason="Atualização obrigatória.")
            return
        await socket.accept()
        await svc.live_hub.attach_companion(device.user_id, socket)
        await svc.live_store.touch_device(device.device_id, device.app_version)
        current_snapshot = await svc.live_store.get_snapshot(device.user_id)
        await socket.send_json(
            {
                "type": "ready",
                "protocol_version": svc.settings.live_protocol_version,
                "heartbeat_seconds": 10,
                "next_revision": (current_snapshot.revision + 1) if current_snapshot else 1,
                "feature_flags": live_feature_flags(svc.settings),
            }
        )
        for pending in await svc.live_store.pending_commands(device.user_id, device.device_id):
            await socket.send_json({"type": "command", "command": command_public(pending)})
            await svc.live_store.update_command(pending.command_id, "delivered")
        last_riot_session_sync = 0.0
        try:
            while True:
                message = await socket.receive_json()
                message_type = str(message.get("type") or "") if isinstance(message, dict) else ""
                if message_type == "heartbeat":
                    await svc.live_store.touch_device(
                        device.device_id, str(message.get("app_version") or "")[:40]
                    )
                    await socket.send_json({"type": "heartbeat_ack", "at": datetime.now(UTC).isoformat()})
                elif message_type == "riot_session_refresh":
                    now_monotonic = time.monotonic()
                    if (
                        now_monotonic - last_riot_session_sync
                        < svc.settings.companion_riot_session_sync_min_seconds
                    ):
                        await socket.send_json(
                            {
                                "type": "riot_session_refresh_result",
                                "status": "rate_limited",
                            }
                        )
                        continue
                    last_riot_session_sync = now_monotonic
                    try:
                        payload = CompanionRiotSessionPayload.model_validate(
                            message.get("riot") or {}
                        )
                        expires_at = await sync_companion_riot_session(
                            device.user_id, payload, svc
                        )
                        await svc.live_store.touch_device(device.device_id)
                        result = {
                            "type": "riot_session_refresh_result",
                            "status": "succeeded",
                            "expires_at": expires_at.isoformat() if expires_at else None,
                        }
                        await socket.send_json(result)
                        await svc.live_hub.publish_mobile(
                            device.user_id,
                            {
                                "type": "riot_session",
                                "valid": True,
                                "refreshed_at": datetime.now(UTC).isoformat(),
                            },
                        )
                    except Exception as exc:
                        emit_log(
                            "companion_riot_session_refresh_failed",
                            user=user_fingerprint(device.user_id),
                            error=type(exc).__name__,
                        )
                        await socket.send_json(
                            {
                                "type": "riot_session_refresh_result",
                                "status": "rejected",
                                "message": "A sessão local não corresponde à conta vinculada.",
                            }
                        )
                elif message_type == "state":
                    phase = str(message.get("phase") or "error")
                    revision = int(message.get("revision") or 0)
                    state = sanitize_live_state(message.get("state"))
                    previous = await svc.live_store.get_snapshot(device.user_id)
                    saved = await svc.live_store.save_snapshot(
                        LiveSnapshot(
                            user_id=device.user_id,
                            device_id=device.device_id,
                            revision=revision,
                            phase=phase,
                            state=state,
                            updated_at=datetime.now(UTC),
                        )
                    )
                    await svc.live_store.touch_device(device.device_id)
                    public = snapshot_public(
                        saved, offline_after=svc.settings.live_offline_after_seconds
                    )
                    await svc.live_hub.publish_mobile(device.user_id, public)
                    if saved.phase == "match_found" and (
                        previous is None
                        or previous.state.get("pregame_id") != saved.state.get("pregame_id")
                    ):
                        await svc.alerts.notify_match_found(
                            device.user_id,
                            str(saved.state.get("pregame_id") or ""),
                            str(saved.state.get("map", {}).get("name") or ""),
                        )
                elif message_type == "command_result":
                    command_id = str(message.get("command_id") or "")
                    status = str(message.get("status") or "")
                    current = await svc.live_store.get_command(command_id)
                    if not current or current.device_id != device.device_id:
                        continue
                    if status not in {"succeeded", "rejected", "failed", "expired"}:
                        continue
                    result = sanitize_live_state(message.get("result") or {})
                    updated = await svc.live_store.update_command(command_id, status, result)
                    if updated:
                        await svc.live_hub.publish_mobile(
                            device.user_id,
                            {"type": "command_result", "command": command_public(updated)},
                        )
        except WebSocketDisconnect:
            pass
        finally:
            svc.live_hub.detach_companion(device.user_id, socket)

    @app.websocket("/ws/live")
    async def mobile_live_websocket(socket: WebSocket) -> None:
        svc: AppServices = socket.app.state.services
        authorization = socket.headers.get("authorization")
        token = socket.query_params.get("access_token", "")
        if not authorization and not token:
            await socket.close(code=4401, reason="Sessão inválida.")
            return
        try:
            user = await svc.auth.verify_authorization_async(
                authorization or f"Bearer {token}"
            )
        except UnauthorizedError:
            await socket.close(code=4401, reason="Sessão inválida.")
            return
        await socket.accept()
        svc.live_hub.attach_mobile(user.id, socket)
        snapshot = await svc.live_store.get_snapshot(user.id)
        await socket.send_json(
            snapshot_public(snapshot, offline_after=svc.settings.live_offline_after_seconds)
        )
        try:
            while True:
                message = await socket.receive_json()
                if isinstance(message, dict) and message.get("type") == "ping":
                    await socket.send_json({"type": "pong", "at": datetime.now(UTC).isoformat()})
        except WebSocketDisconnect:
            pass
        finally:
            svc.live_hub.detach_mobile(user.id, socket)

    @app.get("/valorant/routes")
    async def valorant_routes(
        _: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        routes = [route_info(endpoint) for endpoint in svc.catalog.endpoints]
        counts: dict[str, int] = {}
        for route in routes:
            counts[route.capability] = counts.get(route.capability, 0) + 1
        return {
            "total": len(routes),
            "counts": counts,
            "routes": [route.model_dump() for route in routes],
        }

    @app.post("/valorant/routes/{route_id}", response_model=GenericRouteResponse)
    async def execute_valorant_route(
        route_id: str,
        request_payload: GenericRouteRequest,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> GenericRouteResponse:
        endpoint = svc.catalog.by_id.get(route_id)
        if not endpoint:
            raise HTTPException(
                status_code=404,
                detail={"code": "route_not_found", "message": f"Unknown route: {route_id}"},
            )
        capability, reason = classify_endpoint(endpoint)
        if capability == "unsafe_mutation":
            if not (svc.settings.allow_unsafe_mutations and request_payload.confirm_mutation):
                return unavailable_route_response(route_id, capability, "unsafe_mutation_blocked", reason)
        elif capability != "remote_supported":
            return unavailable_route_response(route_id, capability, "requires_live_client", reason)

        session = await riot_session_for_user(user, svc)
        body_text = json.dumps(request_payload.body) if request_payload.body is not None else ""
        result = await run_in_threadpool(
            svc.executor.execute,
            endpoint,
            session.to_console_context(),
            request_payload.variables,
            request_payload.query,
            body_text,
            {},
        )
        status = int(result.get("status") or 0) or None
        data = decode_executor_body(str(result.get("body") or ""))
        error = None
        if result.get("error"):
            error = {"code": "execution_failed", "message": result["error"]}
        elif status in {401, 403}:
            error = {"code": "relink_required", "message": "Riot rejected the stored session."}
        elif result.get("ok") is False:
            error = {
                "code": "riot_request_failed",
                "message": str(result.get("reason") or "Riot request failed."),
            }
        return GenericRouteResponse(
            route_id=route_id,
            capability=capability,
            executed=True,
            status_code=status,
            data=data,
            error=error,
        )

    @app.get("/valorant/store/daily")
    async def store_daily(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        session = await riot_session_for_user(user, svc)
        daily = await svc.store.daily_store(user.id, session)
        alerts = await svc.alerts.check_daily_store(user.id, daily)
        return {**daily.model_dump(mode="json"), "alerts": alerts.model_dump(mode="json")}

    @app.get("/valorant/store/wallet")
    async def store_wallet(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.wallet(await riot_session_for_user(user, svc))

    @app.get("/valorant/store/inventory")
    async def store_inventory(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
        item_type_id: str = "",
    ) -> Any:
        session = await riot_session_for_user(user, svc)
        return await svc.riot_client.inventory(session, item_type_id=item_type_id)

    @app.get("/valorant/store/offers")
    @app.get("/valorant/store/prices")
    async def store_offers(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.offers(await riot_session_for_user(user, svc))

    @app.get("/valorant/store/night-market")
    async def store_night_market(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        session = await riot_session_for_user(user, svc)
        result = await svc.store.night_market(user.id, session)
        return result.model_dump(mode="json")

    @app.get("/valorant/store/bundles")
    async def store_bundles(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        raw = await svc.riot_client.storefront(await riot_session_for_user(user, svc))
        return {
            "featured_bundle": raw.get("FeaturedBundle") if isinstance(raw, dict) else None,
            "bundles": collect_store_bundles(raw),
            "raw": raw,
        }

    @app.get("/valorant/items/{category}")
    async def valorant_items(
        category: str,
        _: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
        q: str = "",
        limit: Annotated[int, Query(ge=1, le=5000)] = 5000,
        offset: Annotated[int, Query(ge=0, le=50000)] = 0,
    ) -> dict[str, Any]:
        if category not in ASSET_ENDPOINTS:
            raise HTTPException(
                status_code=404,
                detail={"code": "item_category_not_found", "message": f"Unknown category: {category}"},
            )
        items = await svc.assets.list_items(category, svc.repo)
        query = q.strip().lower()
        if query:
            items = [
                item
                for item in items
                if query in str(item.get("displayName") or "").lower()
            ]
        return {
            "category": category,
            "total": len(items),
            "items": items[offset : offset + limit],
        }

    @app.get("/valorant/items/{item_id}/status")
    async def valorant_item_status(
        item_id: str,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        session = await riot_session_for_user(user, svc)
        return (await svc.store.item_status(user.id, session, item_id)).model_dump(mode="json")

    @app.get("/valorant/skins/catalog")
    async def skin_catalog(
        _: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
        q: str = "",
        category: str = "",
        weapon: str = "",
        tier: str = "",
        sort: str = "name_asc",
        limit: Annotated[int, Query(ge=1, le=200)] = 80,
        offset: Annotated[int, Query(ge=0, le=5000)] = 0,
    ) -> dict[str, Any]:
        all_items = await svc.assets.skin_catalog(svc.repo)
        items = all_items
        query = search_key(q.strip())
        if query:
            items = [
                item
                for item in items
                if query
                in search_key(
                    f"{item.get('name', '')} {item.get('weapon_name', '')}"
                )
            ]
        if category:
            items = [
                item for item in items if str(item.get("category") or "") == category
            ]
        if weapon:
            items = [
                item for item in items if str(item.get("weapon_id") or "") == weapon
            ]
        if tier:
            items = [item for item in items if str(item.get("tier") or "") == tier]
        if sort == "name_desc":
            items = sorted(items, key=lambda item: search_key(str(item["name"])), reverse=True)
        elif sort == "weapon":
            items = sorted(
                items,
                key=lambda item: (
                    search_key(str(item["weapon_name"])),
                    search_key(str(item["name"])),
                ),
            )
        else:
            items = sorted(items, key=lambda item: search_key(str(item["name"])))
        return {
            "total": len(items),
            "offset": offset,
            "limit": limit,
            "filters": skin_catalog_filters(all_items),
            "items": items[offset : offset + limit],
        }

    @app.get("/valorant/skins/watchlist")
    async def list_skin_watchlist(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        watches = await svc.repo.list_skin_watches(user.id)
        return {"items": [watch.model_dump(mode="json") for watch in watches]}

    @app.post("/valorant/skins/watchlist")
    async def add_skin_watchlist_item(
        payload: SkinWatchCreateRequest,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        try:
            watch = await svc.alerts.add_skin_watch(
                user.id, payload.item_id, enabled=payload.notify_enabled
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "skin_not_found", "message": str(exc)},
            ) from exc
        return {"item": watch.model_dump(mode="json")}

    @app.delete("/valorant/skins/watchlist/{item_id}")
    async def delete_skin_watchlist_item(
        item_id: str,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        return {"deleted": await svc.repo.delete_skin_watch(user.id, item_id)}

    @app.post("/valorant/skins/watchlist/check")
    async def check_skin_watchlist(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        session = await riot_session_for_user(user, svc)
        daily = await svc.store.daily_store(user.id, session)
        result = await svc.alerts.check_daily_store(user.id, daily)
        return result.model_dump(mode="json")

    @app.get("/valorant/player/profile")
    async def player_profile(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        session = await riot_session_for_user(user, svc)
        account = await svc.repo.get_riot_account(user.id)
        xp = await svc.riot_client.account_xp(session)
        return {
            "riot_account": account.model_dump() if account else None,
            "xp": xp,
        }

    @app.get("/valorant/player/mmr")
    async def player_mmr(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.mmr(await riot_session_for_user(user, svc))

    @app.get("/valorant/player/summary")
    async def player_summary(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        session = await riot_session_for_user(user, svc)
        mmr = await svc.riot_client.mmr(session)
        matches = await svc.riot_client.match_history(
            session, start_index=0, end_index=10
        )
        return normalize_player_summary(mmr, matches)

    @app.get("/valorant/player/matches")
    async def player_matches(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
        start_index: Annotated[int, Query(ge=0, le=500)] = 0,
        end_index: Annotated[int, Query(ge=1, le=500)] = 20,
    ) -> Any:
        session = await riot_session_for_user(user, svc)
        return await svc.riot_client.match_history(
            session, start_index=start_index, end_index=end_index
        )

    @app.get("/valorant/player/matches/{match_id}")
    async def player_match_details(
        match_id: str,
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> dict[str, Any]:
        if len(match_id) < 8 or len(match_id) > 100:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_match_id",
                    "message": "O identificador da partida é inválido.",
                },
            )
        session = await riot_session_for_user(user, svc)
        raw = await svc.riot_client.match_details(session, match_id)
        agents, maps = await asyncio.gather(
            svc.assets.list_items("agents", svc.repo),
            svc.assets.list_items("maps", svc.repo),
        )
        return normalize_match_details(
            raw,
            player_puuid=session.puuid,
            agents=agents,
            maps=maps,
        )

    @app.get("/valorant/player/loadout")
    async def player_loadout(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.loadout(await riot_session_for_user(user, svc))

    @app.get("/valorant/player/xp")
    async def player_xp(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.account_xp(await riot_session_for_user(user, svc))

    @app.get("/valorant/player/contracts")
    async def player_contracts(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.contracts(await riot_session_for_user(user, svc))

    @app.get("/valorant/player/item-upgrades")
    async def player_item_upgrades(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.item_upgrades(await riot_session_for_user(user, svc))

    @app.get("/valorant/player/content")
    async def player_content(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> Any:
        return await svc.riot_client.content(await riot_session_for_user(user, svc))

    @app.post("/jobs/store-alerts/run", response_model=JobRunResponse)
    async def run_store_alert_job(
        svc: Annotated[AppServices, Depends(get_services)],
        x_job_token: Annotated[str | None, Header(alias="X-Job-Token")] = None,
    ) -> JobRunResponse:
        require_job_token(svc.settings, x_job_token)
        return await run_riot_account_monitor(svc)

    return app


def get_services(request: Request) -> AppServices:
    return request.app.state.services


async def current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser:
    try:
        user = await request.app.state.services.auth.verify_authorization_async(authorization)
        request.state.user_id = user.id
        return user
    except UnauthorizedError:
        raise


def public_device(device: Any) -> dict[str, Any]:
    return device.model_dump(mode="json", exclude={"push_token"})


def require_job_token(settings: BackendSettings, supplied: str | None) -> None:
    if settings.job_secret_token and supplied == settings.job_secret_token:
        return
    if settings.environment == "development" and not settings.job_secret_token:
        return
    raise UnauthorizedError("Invalid or missing job token.")


def live_feature_flags(settings: BackendSettings) -> dict[str, bool]:
    return {
        "party": settings.live_feature_enabled and settings.live_party_commands_enabled,
        "agent": settings.live_feature_enabled and settings.live_agent_commands_enabled,
        "chat": settings.live_feature_enabled and settings.live_chat_commands_enabled,
        "leave": settings.live_feature_enabled and settings.live_leave_commands_enabled,
        "match_accept": settings.live_feature_enabled and settings.live_match_accept_enabled,
    }


async def should_notify_riot_relink(user_id: str, svc: AppServices) -> bool:
    now = datetime.now(UTC)

    def age_seconds(value: datetime) -> float:
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return (now - aware).total_seconds()

    credentials = await svc.repo.get_riot_credentials(user_id)
    if credentials and svc.settings.riot_relink_notification_grace_seconds > 0:
        age = age_seconds(credentials.updated_at)
        if age < svc.settings.riot_relink_notification_grace_seconds:
            return False
    if svc.settings.riot_companion_refresh_grace_seconds > 0:
        devices = await svc.live_store.list_devices(user_id)
        for device in devices:
            if not device.active or device.revoked_at is not None or device.last_seen_at is None:
                continue
            age = age_seconds(device.last_seen_at)
            if age < svc.settings.riot_companion_refresh_grace_seconds:
                return False
    return True


async def ensure_profile(user: AuthUser, repo: Repository, display_name: str = "") -> Profile:
    profile = await repo.get_profile(user.id)
    if profile:
        return profile
    display_name = display_name.strip() or (user.email.split("@", 1)[0] if user.email else "")
    return await repo.upsert_profile(Profile(user_id=user.id, display_name=display_name))


async def riot_session_for_user(user: AuthUser, svc: AppServices) -> RiotSession:
    return await svc.riot_auth.session_for_user(user.id, svc.repo)


async def normalize_link_payload(
    payload: RiotCredentialPayload, svc: AppServices
) -> RiotCredentialPayload:
    payload = payload.model_copy(
        update={
            "region": payload.region.lower(),
            "shard": (payload.shard or REGION_TO_SHARD.get(payload.region.lower(), "")).lower(),
            "client_version": payload.client_version or svc.settings.default_client_version,
        }
    )
    has_reauth_cookie = bool(payload.ssid or payload.cookies.get("ssid"))
    token_needs_refresh = bool(
        payload.access_token
        and access_token_needs_refresh(payload.access_token, leeway_seconds=300)
    )
    needs_refresh = (
        token_needs_refresh
        or not (payload.access_token and payload.entitlement_token and payload.puuid)
    )
    if needs_refresh and has_reauth_cookie:
        payload = await svc.riot_auth.refresh_payload(payload)
    elif token_needs_refresh:
        raise RelinkRequiredError(
            "A sessão local da Riot expirou. Detecte a Riot novamente no Companion."
        )
    if not payload.puuid or not payload.region or not payload.shard:
        raise RelinkRequiredError("Companion did not send PUUID, region and shard.")
    if payload.access_token and access_token_needs_refresh(payload.access_token, leeway_seconds=300):
        raise RelinkRequiredError(
            "A sessão Riot renovada ainda veio expirada. Abra o VALORANT e detecte novamente."
        )
    return payload


async def persist_riot_link(
    user_id: str, riot_payload: RiotCredentialPayload, svc: AppServices
) -> RiotAccount:
    now = datetime.now(UTC)
    account = RiotAccount(
        user_id=user_id,
        puuid=riot_payload.puuid,
        game_name=riot_payload.game_name,
        tag_line=riot_payload.tag_line,
        region=riot_payload.region.lower(),
        shard=riot_payload.shard.lower(),
        client_version=riot_payload.client_version,
        linked_at=now,
    )
    await svc.repo.upsert_riot_account(account)
    await svc.repo.upsert_riot_credentials(
        RiotCredentialRecord(
            user_id=user_id,
            encrypted_payload=svc.crypto.encrypt_json(riot_payload.model_dump()),
            last_refresh_at=now if riot_payload.access_token else None,
            expires_hint=access_token_expiration(riot_payload.access_token),
            updated_at=now,
        )
    )
    return account


async def sync_companion_riot_session(
    user_id: str,
    fresh: CompanionRiotSessionPayload,
    svc: AppServices,
) -> datetime | None:
    account = await svc.repo.get_riot_account(user_id)
    if account is None or not hmac.compare_digest(account.puuid, fresh.puuid):
        raise RelinkRequiredError("A sessão local não corresponde à conta Riot vinculada.")

    region = fresh.region.strip().lower()
    shard = fresh.shard.strip().lower()
    expected_shard = REGION_TO_SHARD.get(region)
    if not expected_shard or shard != expected_shard:
        raise RelinkRequiredError("A região da sessão local da Riot é inválida.")

    current = RiotCredentialPayload(
        puuid=account.puuid,
        region=account.region,
        shard=account.shard,
        client_version=account.client_version,
        game_name=account.game_name,
        tag_line=account.tag_line,
    )
    record = await svc.repo.get_riot_credentials(user_id)
    if record:
        try:
            current = RiotCredentialPayload(
                **svc.crypto.decrypt_json(record.encrypted_payload)
            )
        except Exception:
            pass
    if current.puuid and not hmac.compare_digest(current.puuid, fresh.puuid):
        raise RelinkRequiredError("A credencial salva pertence a outra conta Riot.")

    merged = current.model_copy(
        update={
            "access_token": fresh.access_token,
            "entitlement_token": fresh.entitlement_token,
            "puuid": fresh.puuid,
            "region": region,
            "shard": shard,
            "client_version": fresh.client_version or account.client_version,
            "game_name": current.game_name or account.game_name,
            "tag_line": current.tag_line or account.tag_line,
        }
    )
    merged = await normalize_link_payload(merged, svc)
    now = datetime.now(UTC)
    expires_at = access_token_expiration(merged.access_token)
    await svc.repo.upsert_riot_credentials(
        RiotCredentialRecord(
            user_id=user_id,
            encrypted_payload=svc.crypto.encrypt_json(merged.model_dump()),
            last_refresh_at=now,
            expires_hint=expires_at,
            updated_at=now,
        )
    )
    if merged.client_version != account.client_version:
        await svc.repo.upsert_riot_account(
            account.model_copy(update={"client_version": merged.client_version})
        )
    return expires_at


def route_info(endpoint: dict[str, Any]) -> RouteInfo:
    capability, reason = classify_endpoint(endpoint)
    return RouteInfo(
        id=endpoint["id"],
        name=endpoint["name"],
        query_name=endpoint.get("query_name", ""),
        method=endpoint.get("method", "GET"),
        category=endpoint.get("category", ""),
        capability=capability,
        reason=reason,
        docs_url=endpoint.get("docs_url", ""),
        description=endpoint.get("description", ""),
    )


def unavailable_route_response(
    route_id: str,
    capability: str,
    code: str,
    message: str,
) -> GenericRouteResponse:
    if capability == "unsupported_hosted":
        code = "unsupported_hosted"
    return GenericRouteResponse(
        route_id=route_id,
        capability=capability,  # type: ignore[arg-type]
        executed=False,
        error={"code": code, "message": message},
    )


def decode_executor_body(body: str) -> Any:
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def collect_store_bundles(raw: Any) -> list[Any]:
    bundles: list[Any] = []
    if not isinstance(raw, dict):
        return bundles
    for key in ("FeaturedBundles", "Bundles"):
        value = raw.get(key)
        if isinstance(value, list):
            bundles.extend(value)
    featured = raw.get("FeaturedBundle")
    if featured:
        bundles.append(featured)
    return bundles


def main() -> int:
    settings = get_settings()
    uvicorn.run(
        "ares_backend.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        log_config=None,
    )
    return 0
