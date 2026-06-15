from ares_console.models import RiotContext, normalize_variable_name
from ares_console.session import REGION_TO_SHARD, RiotSessionDiscovery


def test_parse_valorant_session_arguments() -> None:
    payload = {
        "session": {
            "productId": "valorant",
            "version": "release-15.01-shipping-1-1234567",
            "launchConfiguration": {
                "arguments": [
                    "-ares-deployment=br",
                    "-ares-shard=na",
                    "-some-other-flag=true",
                ]
            },
        }
    }

    parsed = RiotSessionDiscovery._parse_sessions(payload)

    assert parsed["region"] == "br"
    assert parsed["shard"] == "na"
    assert parsed["client_version"].startswith("release-15.01")


def test_common_variable_defaults_are_normalized() -> None:
    context = RiotContext(
        region="br",
        shard="na",
        puuid="player-id",
        party_id="party-id",
    )

    assert normalize_variable_name("{PARTY_ID}") == "party id"
    assert context.default_for("{party id}") == "party-id"
    assert context.default_for("PUUID") == "player-id"
    assert REGION_TO_SHARD["br"] == "na"
