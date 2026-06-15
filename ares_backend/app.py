from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
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
from .errors import BackendError, RelinkRequiredError, RiotRequestError, UnauthorizedError
from .notifications import PushClient, StoreAlertService
from .player import normalize_player_summary
from .repository import Repository, build_repository
from .riot import REGION_TO_SHARD, RiotAuthService, RiotRemoteClient, RiotSession
from .schemas import (
    AuthSessionResponse,
    AuthUser,
    GenericRouteRequest,
    GenericRouteResponse,
    LinkCompleteRequest,
    LinkCompleteResponse,
    LinkStartResponse,
    JobRunResponse,
    PasswordAuthRequest,
    Profile,
    ProfilePatch,
    PushDeviceRegisterRequest,
    RefreshTokenRequest,
    RiotAccount,
    RiotCredentialPayload,
    RiotCredentialRecord,
    RouteInfo,
    SkinWatchCreateRequest,
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
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ensure_schema = getattr(services.repo, "ensure_schema", None)
        if ensure_schema:
            await ensure_schema()
        yield

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

    @app.exception_handler(BackendError)
    async def backend_error_handler(_: Request, exc: BackendError) -> JSONResponse:
        payload: dict[str, Any] = {"error": {"code": exc.code, "message": str(exc)}}
        if isinstance(exc, RiotRequestError) and exc.riot_status is not None:
            payload["error"]["riot_status"] = exc.riot_status
        return JSONResponse(status_code=exc.status_code, content=payload)

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

    @app.post("/riot/link/start", response_model=LinkStartResponse)
    async def link_start(
        user: Annotated[AuthUser, Depends(current_user)],
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> LinkStartResponse:
        await ensure_profile(user, svc.repo)
        code, expires_at = await svc.repo.create_link_code(
            user.id, svc.settings.link_code_ttl_seconds
        )
        return LinkStartResponse(link_code=code, expires_at=expires_at)

    @app.post("/riot/link/complete", response_model=LinkCompleteResponse)
    async def link_complete(
        payload: LinkCompleteRequest,
        svc: Annotated[AppServices, Depends(get_services)],
    ) -> LinkCompleteResponse:
        user_id = await svc.repo.consume_link_code(payload.link_code.strip())
        if not user_id:
            raise HTTPException(
                status_code=404,
                detail={"code": "link_code_invalid", "message": "Link code is invalid or expired."},
            )
        riot_payload = await normalize_link_payload(payload.riot, svc)
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
                expires_hint=None,
                updated_at=now,
            )
        )
        return LinkCompleteResponse(linked=True, riot_account=account)

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
        daily = await svc.store.daily_store(user.id, session)
        return {
            "expires_at": daily.expires_at,
            "items": [item.model_dump() for item in daily.night_market],
            "active": bool(daily.night_market),
        }

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
        user_ids = await svc.repo.list_users_with_skin_watches()
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
            except Exception as exc:
                errors.append(f"{user_id}: {exc}")
        return JobRunResponse(
            checked_users=checked,
            relink_required=relink_required,
            sent_count=sent,
            errors=errors[:50],
        )

    return app


def get_services(request: Request) -> AppServices:
    return request.app.state.services


async def current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser:
    try:
        return await request.app.state.services.auth.verify_authorization_async(authorization)
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
    needs_refresh = not (payload.access_token and payload.entitlement_token and payload.puuid)
    if needs_refresh and (payload.ssid or payload.cookies.get("ssid")):
        payload = await svc.riot_auth.refresh_payload(payload)
    if not payload.puuid or not payload.region or not payload.shard:
        raise RelinkRequiredError("Companion did not send PUUID, region and shard.")
    return payload


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
