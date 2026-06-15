from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


class EndpointCatalog:
    def __init__(self) -> None:
        catalog_path = files("ares_console").joinpath("resources/endpoints.json")
        with catalog_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        self.metadata: dict[str, Any] = payload["metadata"]
        self.endpoints: list[dict[str, Any]] = payload["endpoints"]
        self.by_id = {endpoint["id"]: endpoint for endpoint in self.endpoints}

    @property
    def categories(self) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for endpoint in self.endpoints:
            category = endpoint["category"]
            counts[category] = counts.get(category, 0) + 1
        return [
            {"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda item: item[0])
        ]

    def filtered(self, search: str = "", category: str = "") -> list[dict[str, Any]]:
        needle = search.casefold().strip()
        results = []
        for endpoint in self.endpoints:
            if category and endpoint["category"] != category:
                continue
            haystack = " ".join(
                (
                    endpoint["name"],
                    endpoint.get("query_name", ""),
                    endpoint["method"],
                    endpoint["category"],
                    endpoint["url_template"],
                )
            ).casefold()
            if needle and needle not in haystack:
                continue
            results.append(endpoint)
        return results
