from __future__ import annotations

from typing import Any

from .schemas import Capability


def classify_endpoint(endpoint: dict[str, Any]) -> tuple[Capability, str]:
    method = endpoint.get("method", "GET")
    category = endpoint.get("category", "")
    endpoint_type = endpoint.get("endpoint_type", "")
    transport = endpoint.get("transport", "http")
    name = endpoint.get("name", "")

    if transport == "websocket":
        return "local_only", "Local websocket exists only on the player's PC."
    if endpoint_type == "local":
        return "local_only", "This route targets 127.0.0.1 on the player's PC."
    if transport == "xmpp":
        return "unsupported_hosted", "Continuous XMPP streaming is not exposed through the hosted API yet."
    if category in {"Current Game Endpoints", "Pre-Game Endpoints"}:
        return "requires_game_state", "Requires an active pre-game/current-game session."
    if category == "Party Endpoints" and name != "Custom Game Configs":
        return "requires_game_state", "Requires live party state from the Riot session."
    if endpoint.get("mutating") or method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "unsafe_mutation", "Mutation is blocked by default on hosted backend."
    return "remote_supported", "Can be executed by the hosted backend with Riot credentials."
