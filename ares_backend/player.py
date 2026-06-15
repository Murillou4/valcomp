from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


COMPETITIVE_TIER_ASSET = "03621f52-342b-cf4e-4f86-9350a49c6d04"
TIER_NAMES = {
    0: "Sem ranque",
    3: "Ferro 1",
    4: "Ferro 2",
    5: "Ferro 3",
    6: "Bronze 1",
    7: "Bronze 2",
    8: "Bronze 3",
    9: "Prata 1",
    10: "Prata 2",
    11: "Prata 3",
    12: "Ouro 1",
    13: "Ouro 2",
    14: "Ouro 3",
    15: "Platina 1",
    16: "Platina 2",
    17: "Platina 3",
    18: "Diamante 1",
    19: "Diamante 2",
    20: "Diamante 3",
    21: "Ascendente 1",
    22: "Ascendente 2",
    23: "Ascendente 3",
    24: "Imortal 1",
    25: "Imortal 2",
    26: "Imortal 3",
    27: "Radiante",
}


def normalize_player_summary(
    mmr: dict[str, Any] | None,
    matches: dict[str, Any] | None,
) -> dict[str, Any]:
    mmr = mmr if isinstance(mmr, dict) else {}
    matches = matches if isinstance(matches, dict) else {}
    latest = mmr.get("LatestCompetitiveUpdate")
    latest = latest if isinstance(latest, dict) else {}

    competitive = (mmr.get("QueueSkills") or {}).get("competitive", {})
    competitive = competitive if isinstance(competitive, dict) else {}
    seasons = competitive.get("SeasonalInfoBySeasonID", {})
    seasons = seasons if isinstance(seasons, dict) else {}
    season_id = str(latest.get("SeasonID") or "")
    season = seasons.get(season_id, {}) if season_id else {}
    season = season if isinstance(season, dict) else {}

    tier = _integer(latest.get("TierAfterUpdate"))
    if tier <= 0:
        tier = _integer(season.get("CompetitiveTier"))
    ranked_rating = _integer(latest.get("RankedRatingAfterUpdate"))
    if not latest:
        ranked_rating = _integer(season.get("RankedRating"))

    history = matches.get("History", [])
    recent_matches = []
    for item in history if isinstance(history, list) else []:
        if not isinstance(item, dict):
            continue
        recent_matches.append(
            {
                "match_id": str(item.get("MatchID") or ""),
                "queue_id": str(item.get("QueueID") or ""),
                "started_at": _millis_to_iso(item.get("GameStartTime")),
            }
        )

    return {
        "available": bool(tier > 0 or season or latest),
        "competitive": {
            "tier": tier,
            "tier_name": TIER_NAMES.get(tier, "Sem ranque"),
            "tier_icon": tier_icon(tier),
            "ranked_rating": ranked_rating,
            "rr_earned": _integer(latest.get("RankedRatingEarned")),
            "leaderboard_rank": _integer(season.get("LeaderboardRank")),
            "wins": _integer(season.get("NumberOfWins")),
            "games": _integer(season.get("NumberOfGames")),
            "season_id": season_id,
            "last_match_id": str(latest.get("MatchID") or ""),
            "last_match_at": _millis_to_iso(latest.get("MatchStartTime")),
        },
        "recent_matches": recent_matches,
        "total_matches": _integer(matches.get("Total")),
    }


def normalize_match_details(
    raw: dict[str, Any] | None,
    *,
    player_puuid: str,
    agents: list[dict[str, Any]] | None = None,
    maps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    match_info = raw.get("matchInfo")
    match_info = match_info if isinstance(match_info, dict) else {}
    agent_index = {
        str(agent.get("uuid") or "").lower(): agent
        for agent in agents or []
        if isinstance(agent, dict)
    }
    map_asset = _find_map_asset(match_info.get("mapId"), maps or [])
    shot_totals = _shot_totals(raw.get("roundResults"))
    players: list[dict[str, Any]] = []
    for player in raw.get("players", []) if isinstance(raw.get("players"), list) else []:
        if not isinstance(player, dict) or player.get("isObserver") is True:
            continue
        stats = player.get("stats")
        stats = stats if isinstance(stats, dict) else {}
        subject = str(player.get("subject") or "")
        agent_id = str(player.get("characterId") or "")
        agent = agent_index.get(agent_id.lower(), {})
        rounds = _integer(stats.get("roundsPlayed"))
        score = _integer(stats.get("score"))
        shots = shot_totals.get(subject.lower(), {})
        headshots = _integer(shots.get("headshots"))
        bodyshots = _integer(shots.get("bodyshots"))
        legshots = _integer(shots.get("legshots"))
        total_shots = headshots + bodyshots + legshots
        damage = sum(
            _integer(entry.get("damage"))
            for entry in player.get("roundDamage", [])
            if isinstance(entry, dict)
        )
        kills = _integer(stats.get("kills"))
        deaths = _integer(stats.get("deaths"))
        players.append(
            {
                "subject": subject,
                "game_name": str(player.get("gameName") or "Jogador"),
                "tag_line": str(player.get("tagLine") or ""),
                "team_id": str(player.get("teamId") or ""),
                "agent_id": agent_id,
                "agent_name": str(agent.get("displayName") or "Agente"),
                "agent_icon": str(agent.get("displayIcon") or ""),
                "competitive_tier": _integer(player.get("competitiveTier")),
                "competitive_tier_name": TIER_NAMES.get(
                    _integer(player.get("competitiveTier")), "Sem ranque"
                ),
                "competitive_tier_icon": tier_icon(
                    _integer(player.get("competitiveTier"))
                ),
                "account_level": _integer(player.get("accountLevel")),
                "is_self": subject.lower() == player_puuid.lower(),
                "stats": {
                    "score": score,
                    "rounds_played": rounds,
                    "kills": kills,
                    "deaths": deaths,
                    "assists": _integer(stats.get("assists")),
                    "acs": round(score / rounds, 1) if rounds > 0 else 0,
                    "kd": round(kills / deaths, 2) if deaths > 0 else float(kills),
                    "damage": damage,
                    "average_damage_per_round": (
                        round(damage / rounds, 1) if rounds > 0 else 0
                    ),
                    "headshots": headshots,
                    "bodyshots": bodyshots,
                    "legshots": legshots,
                    "headshot_percent": (
                        round(headshots / total_shots * 100, 1)
                        if total_shots > 0
                        else 0
                    ),
                },
            }
        )
    players.sort(
        key=lambda player: (
            str(player["team_id"]),
            -_integer(player["stats"]["score"]),
        )
    )
    teams = []
    for team in raw.get("teams", []) if isinstance(raw.get("teams"), list) else []:
        if not isinstance(team, dict):
            continue
        teams.append(
            {
                "team_id": str(team.get("teamId") or ""),
                "won": team.get("won") is True,
                "rounds_played": _integer(team.get("roundsPlayed")),
                "rounds_won": _integer(team.get("roundsWon")),
                "num_points": _integer(team.get("numPoints")),
            }
        )
    rounds = []
    for round_result in (
        raw.get("roundResults", [])
        if isinstance(raw.get("roundResults"), list)
        else []
    ):
        if not isinstance(round_result, dict):
            continue
        rounds.append(
            {
                "round": _integer(round_result.get("roundNum")) + 1,
                "winning_team": str(round_result.get("winningTeam") or ""),
                "result": str(round_result.get("roundResult") or ""),
                "ceremony": str(round_result.get("roundCeremony") or ""),
                "plant_site": str(round_result.get("plantSite") or ""),
            }
        )
    self_player = next(
        (player for player in players if player["is_self"]),
        None,
    )
    winner = next((team for team in teams if team["won"]), None)
    return {
        "match": {
            "match_id": str(match_info.get("matchId") or ""),
            "map_id": str(match_info.get("mapId") or ""),
            "map_name": str(map_asset.get("displayName") or "Mapa"),
            "map_icon": str(map_asset.get("listViewIcon") or ""),
            "map_splash": str(
                map_asset.get("splash")
                or map_asset.get("stylizedBackgroundImage")
                or ""
            ),
            "queue_id": str(match_info.get("queueID") or ""),
            "game_mode": str(match_info.get("gameMode") or ""),
            "is_ranked": match_info.get("isRanked") is True,
            "is_completed": match_info.get("isCompleted") is True,
            "completion_state": str(match_info.get("completionState") or ""),
            "started_at": _millis_to_iso(match_info.get("gameStartMillis")),
            "duration_seconds": (
                round(_integer(match_info.get("gameLengthMillis")) / 1000)
                if _integer(match_info.get("gameLengthMillis")) > 0
                else 0
            ),
            "winning_team": winner["team_id"] if winner else "",
        },
        "teams": teams,
        "players": players,
        "rounds": rounds,
        "self": self_player,
    }


def tier_icon(tier: int) -> str:
    if tier < 0 or tier > 27:
        tier = 0
    return (
        "https://media.valorant-api.com/competitivetiers/"
        f"{COMPETITIVE_TIER_ASSET}/{tier}/largeicon.png"
    )


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _millis_to_iso(value: Any) -> str | None:
    millis = _integer(value)
    if millis <= 0:
        return None
    return datetime.fromtimestamp(millis / 1000, tz=UTC).isoformat()


def _find_map_asset(value: Any, maps: list[dict[str, Any]]) -> dict[str, Any]:
    needle = str(value or "").lower()
    for item in maps:
        if not isinstance(item, dict):
            continue
        candidates = {
            str(item.get("uuid") or "").lower(),
            str(item.get("mapUrl") or "").lower(),
        }
        if needle in candidates:
            return item
    return {}


def _shot_totals(value: Any) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for round_result in value if isinstance(value, list) else []:
        if not isinstance(round_result, dict):
            continue
        for player_stats in (
            round_result.get("playerStats", [])
            if isinstance(round_result.get("playerStats"), list)
            else []
        ):
            if not isinstance(player_stats, dict):
                continue
            subject = str(player_stats.get("subject") or "").lower()
            if not subject:
                continue
            current = totals.setdefault(
                subject,
                {"headshots": 0, "bodyshots": 0, "legshots": 0},
            )
            for damage in (
                player_stats.get("damage", [])
                if isinstance(player_stats.get("damage"), list)
                else []
            ):
                if not isinstance(damage, dict):
                    continue
                current["headshots"] += _integer(damage.get("headshots"))
                current["bodyshots"] += _integer(damage.get("bodyshots"))
                current["legshots"] += _integer(damage.get("legshots"))
    return totals
