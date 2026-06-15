import json
import re

from ares_console.catalog import EndpointCatalog


def test_catalog_contains_all_documented_transports() -> None:
    catalog = EndpointCatalog()

    assert catalog.metadata["endpoint_count"] == 82
    assert len(catalog.endpoints) == 82
    assert {endpoint["transport"] for endpoint in catalog.endpoints} == {
        "http",
        "websocket",
        "xmpp",
    }


def test_endpoint_ids_are_unique_and_templates_are_complete() -> None:
    catalog = EndpointCatalog()
    ids = [endpoint["id"] for endpoint in catalog.endpoints]

    assert len(ids) == len(set(ids))
    assert all(endpoint["name"] for endpoint in catalog.endpoints)
    assert all(endpoint["url_template"] for endpoint in catalog.endpoints)
    for endpoint in catalog.endpoints:
        placeholders = {
            match.lower()
            for match in re.findall(r"\{([^{}]+)\}", endpoint["url_template"])
        }
        variables = {item["name"].lower() for item in endpoint["variables"]}
        assert placeholders == variables
        if endpoint["body_example"] and endpoint["transport"] != "xmpp":
            json.loads(endpoint["body_example"])


def test_filter_matches_internal_names_and_categories() -> None:
    catalog = EndpointCatalog()

    match_history = catalog.filtered("MatchHistory_FetchMatchHistory")
    assert [endpoint["name"] for endpoint in match_history] == ["Match History"]

    local = catalog.filtered(category="Local Endpoints")
    assert local
    assert all(endpoint["category"] == "Local Endpoints" for endpoint in local)
