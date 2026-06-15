from ares_backend.capabilities import classify_endpoint
from ares_console.catalog import EndpointCatalog


def test_all_catalog_routes_are_classified() -> None:
    catalog = EndpointCatalog()
    classified = [classify_endpoint(endpoint)[0] for endpoint in catalog.endpoints]

    assert len(classified) == 82
    assert set(classified) <= {
        "remote_supported",
        "local_only",
        "requires_game_state",
        "unsafe_mutation",
        "unsupported_hosted",
    }


def test_hosted_capabilities_match_route_constraints() -> None:
    catalog = EndpointCatalog()

    assert classify_endpoint(catalog.by_id["walletEndpoint"])[0] == "remote_supported"
    assert classify_endpoint(catalog.by_id["storefrontEndpoint"])[0] == "remote_supported"
    assert classify_endpoint(catalog.by_id["sendChatEndpoint"])[0] == "local_only"
    assert classify_endpoint(catalog.by_id["localWebSocketEndpoint"])[0] == "local_only"
    assert classify_endpoint(catalog.by_id["currentGamePlayerEndpoint"])[0] == "requires_game_state"
    assert classify_endpoint(catalog.by_id["partyEndpoint"])[0] == "requires_game_state"
    assert classify_endpoint(catalog.by_id["activateContractEndpoint"])[0] == "unsafe_mutation"
    assert classify_endpoint(catalog.by_id["xmppEndpoint"])[0] == "unsupported_hosted"

