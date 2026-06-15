from __future__ import annotations

import json
import re
import threading
import time
from typing import Any
from urllib.parse import quote

import httpx

from .models import RiotContext, normalize_variable_name
from .session import RiotSessionDiscovery


class RequestBuildError(ValueError):
    pass


class EndpointExecutor:
    MAX_DISPLAY_BYTES = 1_500_000

    def __init__(self) -> None:
        self._remote_client = httpx.Client(
            timeout=25.0,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": ""},
        )
        self._client_lock = threading.Lock()

    def close(self) -> None:
        self._remote_client.close()

    def preview(
        self,
        endpoint: dict[str, Any],
        context: RiotContext,
        variables: dict[str, Any],
        query: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            built = self.build_request(endpoint, context, variables, query, "")
            return {"url": built["url"], "missing": [], "error": ""}
        except RequestBuildError as exc:
            missing = re.findall(r"Variável obrigatória sem valor: (.+)", str(exc))
            return {
                "url": self._best_effort_url(endpoint, context, variables),
                "missing": missing,
                "error": str(exc),
            }

    def execute(
        self,
        endpoint: dict[str, Any],
        context: RiotContext,
        variables: dict[str, Any],
        query: dict[str, Any],
        body_text: str,
        extra_headers: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            request = self.build_request(
                endpoint, context, variables, query, body_text, extra_headers
            )
            if endpoint["transport"] != "http":
                raise RequestBuildError(
                    "Use o controle de conexão para rotas WebSocket ou XMPP."
                )

            with self._client_lock:
                if request["local"]:
                    with httpx.Client(
                        verify=False,
                        timeout=25.0,
                        follow_redirects=False,
                        trust_env=False,
                        headers={"User-Agent": ""},
                    ) as client:
                        response = client.request(
                            request["method"],
                            request["url"],
                            headers=request["headers"],
                            params=request["query"],
                            json=request["json"],
                        )
                else:
                    response = self._remote_client.request(
                        request["method"],
                        request["url"],
                        headers=request["headers"],
                        params=request["query"],
                        json=request["json"],
                    )

            elapsed_ms = round((time.perf_counter() - started) * 1000)
            content = response.content
            truncated = len(content) > self.MAX_DISPLAY_BYTES
            display_content = content[: self.MAX_DISPLAY_BYTES]
            body = self._format_body(display_content, response)
            if truncated:
                body += (
                    "\n\n[Resposta truncada na interface: "
                    f"{len(content):,} bytes recebidos.]"
                )
            return {
                "ok": response.is_success,
                "status": response.status_code,
                "reason": response.reason_phrase,
                "elapsedMs": elapsed_ms,
                "url": str(response.request.url),
                "method": request["method"],
                "body": body,
                "headers": self._safe_response_headers(response.headers),
                "requestHeaders": self._redact_headers(request["headers"]),
                "error": "",
                "truncated": truncated,
                "size": len(content),
            }
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            return {
                "ok": False,
                "status": 0,
                "reason": "Request failed",
                "elapsedMs": elapsed_ms,
                "url": self._best_effort_url(endpoint, context, variables),
                "method": endpoint["method"],
                "body": "",
                "headers": {},
                "requestHeaders": {},
                "error": str(exc),
                "truncated": False,
                "size": 0,
            }

    def build_request(
        self,
        endpoint: dict[str, Any],
        context: RiotContext,
        variables: dict[str, Any],
        query: dict[str, Any],
        body_text: str,
        extra_headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = {
            normalize_variable_name(key): str(value)
            for key, value in variables.items()
            if value is not None and str(value) != ""
        }
        optional_url_variables = {
            normalize_variable_name(variable["name"])
            for variable in endpoint.get("variables", [])
            if variable.get("optional")
        }
        url = endpoint["url_template"]
        for match in list(re.finditer(r"\{([^{}]+)\}", url)):
            raw_name = match.group(1)
            normalized = normalize_variable_name(raw_name)
            value = values.get(normalized) or context.default_for(normalized)
            if not value:
                if normalized in optional_url_variables:
                    url = url.replace("/" + match.group(0), "")
                    url = url.replace(match.group(0), "")
                    continue
                raise RequestBuildError(f"Variável obrigatória sem valor: {raw_name}")
            url = url.replace(match.group(0), quote(str(value), safe=""))

        requirements = endpoint.get("requirements", {})
        headers = {str(key): str(value) for key, value in endpoint.get("headers", {}).items()}
        headers.update(self._requirement_headers(requirements, context))
        if extra_headers:
            headers.update(
                {
                    str(key): str(value)
                    for key, value in extra_headers.items()
                    if str(key).strip()
                }
            )

        body = None
        if body_text.strip():
            try:
                body = json.loads(body_text)
            except json.JSONDecodeError as exc:
                raise RequestBuildError(
                    f"JSON do corpo inválido na linha {exc.lineno}, coluna {exc.colno}."
                ) from exc

        query_values = {
            str(key): value
            for key, value in query.items()
            if value is not None and str(value) != ""
        }
        return {
            "method": endpoint["method"],
            "url": url,
            "headers": headers,
            "query": query_values,
            "json": body,
            "local": endpoint.get("endpoint_type") == "local",
        }

    @staticmethod
    def _requirement_headers(
        requirements: dict[str, Any], context: RiotContext
    ) -> dict[str, str]:
        headers: dict[str, str] = {}
        missing: list[str] = []
        if requirements.get("token"):
            if context.token:
                headers["Authorization"] = f"Bearer {context.token}"
            else:
                missing.append("auth token")
        if requirements.get("entitlement"):
            if context.entitlement:
                headers["X-Riot-Entitlements-JWT"] = context.entitlement
            else:
                missing.append("entitlement token")
        if requirements.get("client_version"):
            if context.client_version:
                headers["X-Riot-ClientVersion"] = context.client_version
            else:
                missing.append("client version")
        if requirements.get("client_platform"):
            headers["X-Riot-ClientPlatform"] = context.client_platform
        if requirements.get("local_auth"):
            if context.lockfile:
                headers["Authorization"] = RiotSessionDiscovery.local_authorization(
                    context.lockfile
                )
            else:
                missing.append("lockfile")
        if missing:
            raise RequestBuildError(
                "Contexto ausente para a rota: " + ", ".join(missing) + "."
            )
        return headers

    @staticmethod
    def _format_body(content: bytes, response: httpx.Response) -> str:
        if not content:
            return ""
        text = content.decode(response.encoding or "utf-8", errors="replace")
        try:
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            return text

    @staticmethod
    def _safe_response_headers(headers: httpx.Headers) -> dict[str, str]:
        result = dict(headers)
        if "set-cookie" in result:
            result["set-cookie"] = "[oculto]"
        return result

    @staticmethod
    def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
        sensitive = {
            "authorization",
            "x-riot-entitlements-jwt",
            "x-riot-pas-jwt",
            "cookie",
            "set-cookie",
        }
        return {
            key: ("[oculto]" if key.lower() in sensitive else value)
            for key, value in headers.items()
        }

    @staticmethod
    def _best_effort_url(
        endpoint: dict[str, Any],
        context: RiotContext,
        variables: dict[str, Any],
    ) -> str:
        url = endpoint["url_template"]
        values = {
            normalize_variable_name(key): str(value)
            for key, value in variables.items()
            if value is not None
        }
        for match in list(re.finditer(r"\{([^{}]+)\}", url)):
            normalized = normalize_variable_name(match.group(1))
            value = values.get(normalized) or context.default_for(normalized)
            if value:
                url = url.replace(match.group(0), quote(str(value), safe=""))
        return url
