from ares_backend.player import normalize_match_details, normalize_player_summary


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


def test_normalizes_match_scoreboard_and_rounds() -> None:
    result = normalize_match_details(
        {
            "matchInfo": {
                "matchId": "match-1",
                "mapId": "/Game/Maps/Ascent/Ascent",
                "gameStartMillis": 1_700_000_000_000,
                "gameLengthMillis": 1_800_000,
                "queueID": "competitive",
                "isRanked": True,
                "isCompleted": True,
                "completionState": "Completed",
            },
            "players": [
                {
                    "subject": "self-player",
                    "gameName": "Player",
                    "tagLine": "BR1",
                    "teamId": "Blue",
                    "characterId": "agent-1",
                    "competitiveTier": 18,
                    "stats": {
                        "score": 4000,
                        "roundsPlayed": 20,
                        "kills": 20,
                        "deaths": 10,
                        "assists": 5,
                    },
                    "roundDamage": [{"damage": 300}],
                }
            ],
            "teams": [{"teamId": "Blue", "won": True, "roundsWon": 13}],
            "roundResults": [
                {
                    "roundNum": 0,
                    "winningTeam": "Blue",
                    "roundResult": "Eliminated",
                    "playerStats": [
                        {
                            "subject": "self-player",
                            "damage": [
                                {"headshots": 2, "bodyshots": 3, "legshots": 0}
                            ],
                        }
                    ],
                }
            ],
        },
        player_puuid="self-player",
        agents=[
            {
                "uuid": "agent-1",
                "displayName": "Jett",
                "displayIcon": "agent.png",
            }
        ],
        maps=[
            {
                "mapUrl": "/Game/Maps/Ascent/Ascent",
                "displayName": "Ascent",
                "splash": "ascent.png",
            }
        ],
    )

    assert result["match"]["map_name"] == "Ascent"
    assert result["self"]["is_self"] is True
    assert result["self"]["agent_name"] == "Jett"
    assert result["self"]["stats"]["acs"] == 200
    assert result["self"]["stats"]["kd"] == 2
    assert result["self"]["stats"]["headshot_percent"] == 40
    assert result["rounds"][0]["round"] == 1
