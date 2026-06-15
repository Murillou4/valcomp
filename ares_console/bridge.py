from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtCore import QUrl

from .catalog import EndpointCatalog
from .executor import EndpointExecutor
from .models import RiotContext
from .session import RiotSessionDiscovery
from .streams import StreamManager


class AppBridge(QObject):
    sessionChanged = Signal()
    requestChanged = Signal()
    streamStateChanged = Signal()
    streamMessage = Signal(str)
    _sessionFinished = Signal(object)
    _requestFinished = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.catalog = EndpointCatalog()
        self.discovery = RiotSessionDiscovery()
        self.executor = EndpointExecutor()
        self.context = RiotContext()
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ares")
        self._session_loading = False
        self._request_running = False
        self._response: dict[str, Any] = {}
        self._stream_state = {
            "state": "disconnected",
            "detail": "Nenhuma conexão ativa",
        }
        self.streams = StreamManager(self._emit_stream_message, self._set_stream_state)
        self._sessionFinished.connect(self._apply_session)
        self._requestFinished.connect(self._apply_response)

    @Property("QVariantMap", notify=sessionChanged)
    def session(self) -> dict[str, Any]:
        data = self.context.summary()
        data["loading"] = self._session_loading
        return data

    @Property(bool, notify=requestChanged)
    def requestRunning(self) -> bool:
        return self._request_running

    @Property("QVariantMap", notify=requestChanged)
    def response(self) -> dict[str, Any]:
        return self._response

    @Property("QVariantMap", notify=streamStateChanged)
    def streamState(self) -> dict[str, str]:
        return self._stream_state

    @Property("QVariantMap", constant=True)
    def catalogMetadata(self) -> dict[str, Any]:
        return self.catalog.metadata

    @Slot(str, str, result="QVariantList")
    def filteredEndpoints(self, search: str, category: str) -> list[dict[str, Any]]:
        return self.catalog.filtered(search, category)

    @Slot(result="QVariantList")
    def categories(self) -> list[dict[str, Any]]:
        return self.catalog.categories

    @Slot(str, result="QVariantMap")
    def endpointById(self, endpoint_id: str) -> dict[str, Any]:
        return self.catalog.by_id.get(endpoint_id, {})

    @Slot(str, result=str)
    def defaultValue(self, variable_name: str) -> str:
        return self.context.default_for(variable_name)

    @Slot()
    def refreshSession(self) -> None:
        if self._session_loading:
            return
        self._session_loading = True
        self.sessionChanged.emit()
        future = self.pool.submit(self.discovery.discover)
        future.add_done_callback(
            lambda completed: self._sessionFinished.emit(completed.result())
        )

    @Slot(str, str, str, result="QVariantMap")
    def previewRequest(
        self, endpoint_id: str, variables_json: str, query_json: str
    ) -> dict[str, Any]:
        endpoint = self.catalog.by_id.get(endpoint_id)
        if not endpoint:
            return {"url": "", "missing": [], "error": "Rota não encontrada."}
        return self.executor.preview(
            endpoint,
            self.context,
            self._json_object(variables_json),
            self._json_object(query_json),
        )

    @Slot(str, str, str, str, str)
    def executeEndpoint(
        self,
        endpoint_id: str,
        variables_json: str,
        query_json: str,
        body_text: str,
        headers_json: str,
    ) -> None:
        if self._request_running:
            return
        endpoint = self.catalog.by_id.get(endpoint_id)
        if not endpoint:
            self._response = {"error": "Rota não encontrada.", "status": 0}
            self.requestChanged.emit()
            return
        self._request_running = True
        self._response = {}
        self.requestChanged.emit()
        future = self.pool.submit(
            self.executor.execute,
            endpoint,
            self.context,
            self._json_object(variables_json),
            self._json_object(query_json),
            body_text,
            self._json_object(headers_json),
        )
        future.add_done_callback(
            lambda completed: self._requestFinished.emit(completed.result())
        )

    @Slot(str)
    def connectStream(self, endpoint_id: str) -> None:
        endpoint = self.catalog.by_id.get(endpoint_id)
        if not endpoint:
            self._set_stream_state("error", "Rota não encontrada.")
            return
        try:
            self.streams.connect(endpoint["transport"], self.context)
        except Exception as exc:
            self._set_stream_state("error", str(exc))

    @Slot(str)
    def sendStream(self, message: str) -> None:
        try:
            self.streams.send(message)
        except Exception as exc:
            self._set_stream_state("error", str(exc))

    @Slot()
    def disconnectStream(self) -> None:
        self.streams.disconnect()
        self._set_stream_state("disconnected", "Nenhuma conexão ativa")

    @Slot(str)
    def copyText(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)

    @Slot(str)
    def openUrl(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def shutdown(self) -> None:
        self.streams.disconnect()
        self.executor.close()
        self.pool.shutdown(wait=False, cancel_futures=True)

    @Slot(object)
    def _apply_session(self, context: RiotContext) -> None:
        self.context = context
        self._session_loading = False
        self.sessionChanged.emit()

    @Slot(object)
    def _apply_response(self, response: dict[str, Any]) -> None:
        self._response = response
        self._request_running = False
        self.requestChanged.emit()

    def _emit_stream_message(self, message: str) -> None:
        self.streamMessage.emit(message)

    def _set_stream_state(self, state: str, detail: str) -> None:
        self._stream_state = {"state": state, "detail": detail}
        self.streamStateChanged.emit()

    @staticmethod
    def _json_object(raw: str) -> dict[str, Any]:
        if not raw.strip():
            return {}
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
