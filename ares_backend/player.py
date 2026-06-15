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
