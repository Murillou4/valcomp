from __future__ import annotations

from typing import Annotated

import httpx
import jwt
from fastapi import Depends, Header

from .errors import AuthProviderError, UnauthorizedError
from .schemas import AuthSession, AuthSessionResponse, AuthUser
from .settings import BackendSettings, get_settings


class SupabaseAuth:
    def __init__(self, settings: BackendSettings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.http_timeout_seconds, trust_env=False)

    def verify_authorization(self, authorization: str | None) -> AuthUser:
        token = self._bearer_token(authorization)
        if self.settings.allow_dev_auth and token.startswith("dev:"):
            user_id = token.removeprefix("dev:").strip() or "dev-user"
            return AuthUser(id=user_id, email=f"{user_id}@dev.local", claims={"dev": True})
        return self.verify_jwt(token)

    async def verify_authorization_async(self, authorization: str | None) -> AuthUser:
        token = self._bearer_token(authorization)
        if self.settings.allow_dev_auth and token.startswith("dev:"):
            user_id = token.removeprefix("dev:").strip() or "dev-user"
            return AuthUser(id=user_id, email=f"{user_id}@dev.local", claims={"dev": True})
        if self.settings.supabase_jwt_secret:
            return self.verify_jwt(token)
        return await self.verify_with_supabase_auth(token)

    @staticmethod
    def _bearer_token(authorization: str | None) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise UnauthorizedError("Missing Bearer token.")
        return authorization.split(" ", 1)[1].strip()

    def verify_jwt(self, token: str) -> AuthUser:
        if not self.settings.supabase_jwt_secret:
            raise UnauthorizedError("Supabase JWT secret is not configured.")
        try:
            claims = jwt.decode(
                token,
                self.settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": False},
            )
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid Supabase JWT.") from exc
        subject = str(claims.get("sub") or "")
        if not subject:
            raise UnauthorizedError("JWT subject is missing.")
        email = claims.get("email")
        return AuthUser(id=subject, email=email if isinstance(email, str) else None, claims=claims)

    async def verify_with_supabase_auth(self, token: str) -> AuthUser:
        if not self.settings.supabase_url or not self.settings.supabase_anon_key:
            raise UnauthorizedError("Supabase URL and publishable key are not configured.")
        response = await self.client.get(
            f"{self.settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": self.settings.supabase_anon_key,
                "Authorization": f"Bearer {token}",
            },
        )
        if response.status_code in {401, 403}:
            raise UnauthorizedError("Invalid Supabase JWT.")
        response.raise_for_status()
        data = response.json()
        user_id = str(data.get("id") or "")
        if not user_id:
            raise UnauthorizedError("Supabase user id is missing.")
        return AuthUser(
            id=user_id,
            email=data.get("email") if isinstance(data.get("email"), str) else None,
            claims=data if isinstance(data, dict) else {},
        )

    async def sign_up_with_password(
        self, email: str, password: str, display_name: str = ""
    ) -> AuthSessionResponse:
        email = self._normalize_email(email)
        if not self.settings.supabase_url or not self.settings.supabase_anon_key:
            return self._dev_password_response(email, display_name)
        response = await self.client.post(
            f"{self.settings.supabase_url.rstrip('/')}/auth/v1/signup",
            headers=self._supabase_auth_headers(),
            json={
                "email": email,
                "password": password,
                "data": {"display_name": display_name},
            },
        )
        data = self._decode_auth_response(response, fallback_code="signup_failed")
        return self._normalize_password_auth_response(
            data,
            message=(
                "Conta criada. Confirme seu email e depois entre no app."
                if not self._extract_session(data)
                else "Conta criada e login realizado."
            ),
        )

    async def sign_in_with_password(self, email: str, password: str) -> AuthSessionResponse:
        email = self._normalize_email(email)
        if not self.settings.supabase_url or not self.settings.supabase_anon_key:
            return self._dev_password_response(email)
        response = await self.client.post(
            f"{self.settings.supabase_url.rstrip('/')}/auth/v1/token",
            headers=self._supabase_auth_headers(),
            params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
        data = self._decode_auth_response(
            response,
            fallback_code="invalid_credentials",
            fallback_message="Email ou senha invalidos.",
        )
        return self._normalize_password_auth_response(data, message="Login realizado.")

    async def refresh_password_session(self, refresh_token: str) -> AuthSessionResponse:
        if not self.settings.supabase_url or not self.settings.supabase_anon_key:
            raise UnauthorizedError("Refresh is not available in local dev auth.")
        response = await self.client.post(
            f"{self.settings.supabase_url.rstrip('/')}/auth/v1/token",
            headers=self._supabase_auth_headers(),
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
        )
        data = self._decode_auth_response(
            response,
            fallback_code="refresh_failed",
            fallback_message="Sessao expirada. Entre novamente.",
        )
        return self._normalize_password_auth_response(data, message="Sessao renovada.")

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    def _supabase_auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self.settings.supabase_anon_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _decode_auth_response(
        response: httpx.Response,
        *,
        fallback_code: str,
        fallback_message: str = "Nao foi possivel autenticar.",
    ) -> dict:
        payload = response.json() if response.content else {}
        if not response.is_success:
            message = fallback_message
            code = fallback_code
            if isinstance(payload, dict):
                message = str(
                    payload.get("msg")
                    or payload.get("message")
                    or payload.get("error_description")
                    or fallback_message
                )
                code = str(payload.get("error_code") or payload.get("code") or fallback_code)
            raise AuthProviderError(
                message,
                code=code,
                status_code=401 if response.status_code in {400, 401, 403} else response.status_code,
            )
        return payload if isinstance(payload, dict) else {}

    def _normalize_password_auth_response(
        self, data: dict, *, message: str = ""
    ) -> AuthSessionResponse:
        session = self._extract_session(data)
        user_payload = data.get("user") if isinstance(data.get("user"), dict) else data
        user = self._user_from_auth_payload(user_payload)
        return AuthSessionResponse(
            user=user,
            session=session,
            email_confirmation_required=session is None,
            message=message,
        )

    @staticmethod
    def _extract_session(data: dict) -> AuthSession | None:
        session_payload = data.get("session") if isinstance(data.get("session"), dict) else data
        access_token = session_payload.get("access_token") if isinstance(session_payload, dict) else None
        if not isinstance(access_token, str) or not access_token:
            return None
        return AuthSession(
            access_token=access_token,
            refresh_token=str(session_payload.get("refresh_token") or ""),
            token_type=str(session_payload.get("token_type") or "bearer"),
            expires_in=(
                int(session_payload["expires_in"])
                if session_payload.get("expires_in") is not None
                else None
            ),
            expires_at=(
                int(session_payload["expires_at"])
                if session_payload.get("expires_at") is not None
                else None
            ),
        )

    @staticmethod
    def _user_from_auth_payload(payload: dict) -> AuthUser:
        user_id = str(payload.get("id") or payload.get("sub") or "")
        if not user_id:
            raise AuthProviderError("Supabase nao retornou o usuario.", code="user_missing")
        email = payload.get("email")
        return AuthUser(
            id=user_id,
            email=email if isinstance(email, str) else None,
            claims=payload if isinstance(payload, dict) else {},
        )

    def _dev_password_response(self, email: str, display_name: str = "") -> AuthSessionResponse:
        if not self.settings.allow_dev_auth:
            raise AuthProviderError(
                "Supabase Auth nao esta configurado.",
                code="auth_not_configured",
                status_code=500,
            )
        local = email.split("@", 1)[0].strip() or "mobile-user"
        user_id = "dev-" + "".join(ch for ch in local.lower() if ch.isalnum() or ch == "-")[:40]
        token = f"dev:{user_id}"
        return AuthSessionResponse(
            user=AuthUser(
                id=user_id,
                email=email,
                claims={"dev": True, "display_name": display_name},
            ),
            session=AuthSession(access_token=token, refresh_token=token, token_type="bearer"),
            message="Login dev local realizado.",
        )


def get_auth(settings: Annotated[BackendSettings, Depends(get_settings)]) -> SupabaseAuth:
    return SupabaseAuth(settings)


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    auth: Annotated[SupabaseAuth, Depends(get_auth)] = None,
) -> AuthUser:
    assert auth is not None
    return auth.verify_authorization(authorization)
