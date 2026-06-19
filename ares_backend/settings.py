from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Ares Valorant API"
    environment: str = "development"
    api_base_url: str = "http://127.0.0.1:8000"
    allow_dev_auth: bool = True
    backend_auth_enabled: bool = True
    access_token_ttl_seconds: int = 0
    refresh_token_ttl_seconds: int = 0

    app_secret_key: str = Field(
        default="dev-secret-change-me",
        description="Secret used to encrypt Riot credential material.",
    )
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = ""
    database_ssl: bool = True

    riot_client_platform: str = (
        "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjog"
        "IldpbmRvd3MiLA0KCSJwbGF0Zm9TVmVyc2lvbiI6ICIxMC4wLjE5"
        "MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVu"
        "a25vd24iDQp9"
    )
    default_client_version: str = ""

    link_code_ttl_seconds: int = 600
    companion_pair_code_ttl_seconds: int = 600
    live_command_ttl_seconds: int = 8
    live_offline_after_seconds: int = 25
    live_protocol_version: int = 1
    live_feature_enabled: bool = True
    live_party_commands_enabled: bool = True
    live_agent_commands_enabled: bool = True
    live_chat_commands_enabled: bool = True
    live_leave_commands_enabled: bool = True
    live_match_accept_enabled: bool = False
    http_timeout_seconds: float = 18.0
    store_snapshot_ttl_seconds: int = 300
    riot_session_monitor_interval_seconds: int = 300
    riot_token_proactive_refresh_seconds: int = 900
    riot_relink_notification_grace_seconds: int = 86400
    riot_companion_refresh_grace_seconds: int = 900
    companion_riot_session_sync_min_seconds: int = 60
    allow_unsafe_mutations: bool = False
    job_secret_token: str = ""
    valorant_assets_language: str = "pt-BR"
    firebase_project_id: str = ""
    firebase_service_account_json: str = ""


@lru_cache
def get_settings() -> BackendSettings:
    return BackendSettings()
