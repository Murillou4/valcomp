from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .catalog import EndpointCatalog
from .executor import EndpointExecutor
from .models import Lockfile, RiotContext, normalize_variable_name
from .session import RiotSessionDiscovery


SAMPLE_UUID = "00000000-0000-0000-0000-000000000000"
AGENT_JETT_UUID = "add6443a-41bd-e414-f6ad-e58d267f4e95"
OWNED_ITEMS_AGENT_TYPE_UUID = "01bb38e1-da47-4e6a-9b3d-945fe4655707"


class RouteDiagnosticsRunner:
    def __init__(self, catalog: EndpointCatalog | None = None) -> None:
        self.catalog = catalog or EndpointCatalog()
        self.executor = EndpointExecutor()

    def close(self) -> None:
        self.executor.close()

    def run(
        self,
        *,
        live: bool = False,
        execute_mutating: bool = False,
        include_streams: bool = False,
    ) -> dict[str, Any]:
        discovered_context = RiotSessionDiscovery().discover() if live else None
        context = (
            discovered_context
            if discovered_context and discovered_context.online
            else self._fake_context()
        )
        results = []

        for endpoint in self.catalog.endpoints:
            variables = self._variables_for(endpoint, context)
            query = self._query_for(endpoint)
            body = endpoint.get("body_example") or ""
            item = {
                "id": endpoint["id"],
                "name": endpoint["name"],
                "method": endpoint["method"],
                "transport": endpoint["transport"],
                "category": endpoint["category"],
                "risk": self._risk(endpoint),
                "status": "pending",
                "detail": "",
                "url": "",
                "http_status": None,
                "used_sample_values": self._uses_sample_values(endpoint, context, variables),
            }

            try:
                built = self.executor.build_request(
                    endpoint, context, variables, query, body, {}
                )
                item["url"] = self._redact_url(built["url"], context)
            except Exception as exc:
                item["status"] = "failed_build"
                item["detail"] = str(exc)
                results.append(item)
                continue

            should_execute = self._should_execute(
                endpoint,
                live=live,
                context_online=bool(discovered_context and discovered_context.online),
                execute_mutating=execute_mutating,
                include_streams=include_streams,
            )
            if should_execute is not True:
                item["status"] = should_execute
                item["detail"] = self._skip_reason(
                    should_execute,
                    live=live,
                    context=discovered_context,
                )
                results.append(item)
                continue

            response = self.executor.execute(endpoint, context, variables, query, body, {})
            item["http_status"] = response.get("status")
            item["url"] = self._redact_url(response.get("url") or item["url"], context)
            if response.get("error"):
                item["status"] = "failed_execute"
                item["detail"] = response["error"]
            else:
                item["status"] = "executed"
                item["detail"] = response.get("reason", "")
            results.append(item)

        summary = Counter(item["status"] for item in results)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "catalog": self.catalog.metadata,
            "live_requested": live,
            "execute_mutating": execute_mutating,
            "include_streams": include_streams,
            "session": (discovered_context or context).summary(),
            "summary": dict(sorted(summary.items())),
            "total": len(results),
            "results": results,
        }

    @staticmethod
    def _fake_context() -> RiotContext:
        return RiotContext(
            online=True,
            status="synthetic",
            lockfile=Lockfile("Riot Client", 1, 54321, "local-password", "https"),
            token="test-auth-token",
            entitlement="test-entitlement-token",
            puuid=SAMPLE_UUID,
            region="br",
            shard="na",
            client_version="release-test-shipping-0-000000",
            party_id=SAMPLE_UUID,
            pregame_match_id=SAMPLE_UUID,
            current_game_match_id=SAMPLE_UUID,
        )

    def _variables_for(
        self, endpoint: dict[str, Any], context: RiotContext
    ) -> dict[str, str]:
        variables: dict[str, str] = {}
        for variable in endpoint.get("variables", []):
            name = variable["name"]
            normalized = normalize_variable_name(name)
            default = context.default_for(normalized)
            if default:
                variables[name] = default
                continue
            if variable.get("optional"):
                continue
            variables[name] = self._sample_variable_value(normalized)
        return variables

    @staticmethod
    def _query_for(endpoint: dict[str, Any]) -> dict[str, str]:
        query: dict[str, str] = {}
        for item in endpoint.get("query", []):
            if item.get("optional"):
                continue
            name = item["name"]
            if "season" in normalize_variable_name(name):
                query[name] = SAMPLE_UUID
            elif item.get("type") == "number":
                query[name] = "0" if "start" in name.lower() else "20"
            else:
                query[name] = "test"
        return query

    @staticmethod
    def _sample_variable_value(name: str) -> str:
        if name in {"agent id", "character id"}:
            return AGENT_JETT_UUID
        if name in {"itemtypeid", "item type id"}:
            return OWNED_ITEMS_AGENT_TYPE_UUID
        if "name" in name and "match" not in name:
            return "Teste"
        if "tag" in name:
            return "BR1"
        if "code" in name:
            return "TESTCODE"
        if name in {"cid", "conversation id"}:
            return "ares-diagnostics"
        return SAMPLE_UUID

    @staticmethod
    def _risk(endpoint: dict[str, Any]) -> str:
        if endpoint["transport"] != "http":
            return "stream"
        if endpoint.get("mutating"):
            return "mutating"
        return "read"

    @staticmethod
    def _should_execute(
        endpoint: dict[str, Any],
        *,
        live: bool,
        context_online: bool,
        execute_mutating: bool,
        include_streams: bool,
    ) -> bool | str:
        if endpoint["transport"] != "http":
            return "skipped_stream" if not include_streams else "skipped_stream_manual"
        if not live:
            return "validated_build_only"
        if not context_online:
            return "skipped_no_live_session"
        if endpoint.get("mutating") and not execute_mutating:
            return "skipped_unsafe_mutation"
        return True

    @staticmethod
    def _skip_reason(
        status: str,
        *,
        live: bool,
        context: RiotContext | None,
    ) -> str:
        reasons = {
            "validated_build_only": "URL, headers, query e corpo foram montados sem executar rede.",
            "skipped_stream": "Stream validado por build; execução exige conexão contínua.",
            "skipped_stream_manual": "Execução de stream deve ser feita pela interface para observar mensagens.",
            "skipped_unsafe_mutation": "Rota mutável pulada para não alterar conta, party, fila, chat ou loadout.",
            "skipped_no_live_session": (
                context.error if context else "Sessão local indisponível para execução live."
            ),
        }
        return reasons.get(status, "Rota não executada.")

    @staticmethod
    def _uses_sample_values(
        endpoint: dict[str, Any],
        context: RiotContext,
        variables: dict[str, str],
    ) -> bool:
        for variable in endpoint.get("variables", []):
            name = variable["name"]
            value = variables.get(name, "")
            if not value:
                continue
            if value != context.default_for(name):
                return True
        return False

    @staticmethod
    def _redact_url(url: str, context: RiotContext) -> str:
        redacted = url
        for value, label in (
            (context.puuid, "[puuid]"),
            (context.party_id, "[party_id]"),
            (context.pregame_match_id, "[pregame_match_id]"),
            (context.current_game_match_id, "[current_game_match_id]"),
        ):
            if value:
                redacted = redacted.replace(value, label)
        return redacted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Ares Console route coverage.")
    parser.add_argument("--live", action="store_true", help="Execute safe HTTP routes with the local Riot session.")
    parser.add_argument(
        "--execute-mutating",
        action="store_true",
        help="Dangerous: execute POST/PUT/DELETE routes too.",
    )
    parser.add_argument(
        "--include-streams",
        action="store_true",
        help="Mark streams as manually verified instead of simple build validation.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write the JSON report.",
    )
    args = parser.parse_args(argv)

    runner = RouteDiagnosticsRunner()
    try:
        report = runner.run(
            live=args.live,
            execute_mutating=args.execute_mutating,
            include_streams=args.include_streams,
        )
    finally:
        runner.close()

    output = args.output or Path("response-exports") / (
        "route-diagnostics-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total", "summary", "session")}, ensure_ascii=False, indent=2))
    print(f"Report: {output}")
    return 0 if not any(item["status"].startswith("failed") for item in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
