from ares_backend.player import normalize_player_summary


def test_normalizes_competitive_summary_and_recent_matches() -> None:
    result = normalize_player_summary(
        {
            "QueueSkills": {
                "competitive": {
                    "SeasonalInfoBySeasonID": {
                        "season-current": {
                            "CompetitiveTier": 18,
                            "RankedRating": 62,
                            "LeaderboardRank": 0,
                            "NumberOfWins": 14,
                            "NumberOfGames": 26,
                        }
                    }
                }
            },
            "LatestCompetitiveUpdate": {
                "SeasonID": "season-current",
                "MatchID": "match-current",
                "MatchStartTime": 1_700_000_000_000,
                "TierAfterUpdate": 18,
                "RankedRatingAfterUpdate": 62,
                "RankedRatingEarned": 17,
            },
        },
        {
            "Total": 1,
            "History": [
                {
                    "MatchID": "match-current",
                    "QueueID": "competitive",
                    "GameStartTime": 1_700_000_000_000,
                }
            ],
        },
    )

    assert result["available"] is True
    assert result["competitive"]["tier_name"] == "Diamante 1"
    assert result["competitive"]["ranked_rating"] == 62
    assert result["competitive"]["wins"] == 14
    assert result["recent_matches"][0]["queue_id"] == "competitive"
