from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Lockfile:
    name: str
    pid: int
    port: int
    password: str
    protocol: str


@dataclass(slots=True)
class RiotContext:
    online: bool = False
    status: str = "offline"
    error: str = ""
    lockfile: Lockfile | None = None
    token: str = ""
    entitlement: str = ""
    puuid: str = ""
    region: str = ""
    shard: str = ""
    client_version: str = ""
    client_platform: str = (
        "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjog"
        "IldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5"
        "MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVu"
        "a25vd24iDQp9"
    )
    party_id: str = ""
    pregame_match_id: str = ""
    current_game_match_id: str = ""
    extras: dict[str, str] = field(default_factory=dict)

    def default_for(self, name: str) -> str:
        normalized = normalize_variable_name(name)
        values = {
            "port": str(self.lockfile.port) if self.lockfile else "",
            "puuid": self.puuid,
            "region": self.region,
            "shard": self.shard,
            "client version": self.client_version,
            "client platform": self.client_platform,
            "party id": self.party_id,
            "pre-game match id": self.pregame_match_id,
            "pregame match id": self.pregame_match_id,
            "current game match id": self.current_game_match_id,
            "coregame match id": self.current_game_match_id,
        }
        return values.get(normalized, self.extras.get(normalized, ""))

    def summary(self) -> dict[str, Any]:
        masked_puuid = ""
        if self.puuid:
            masked_puuid = f"{self.puuid[:6]}...{self.puuid[-4:]}"
        return {
            "online": self.online,
            "status": self.status,
            "error": self.error,
            "region": self.region.upper(),
            "shard": self.shard.upper(),
            "puuid": masked_puuid,
            "clientVersion": self.client_version,
            "port": self.lockfile.port if self.lockfile else 0,
            "hasToken": bool(self.token),
            "hasEntitlement": bool(self.entitlement),
            "partyId": bool(self.party_id),
            "pregameId": bool(self.pregame_match_id),
            "currentGameId": bool(self.current_game_match_id),
        }


def normalize_variable_name(name: str) -> str:
    return name.strip().strip("{}").strip().lower().replace("_", " ")
