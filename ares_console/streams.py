from __future__ import annotations

import base64
import json
import socket
import ssl
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
from websockets.sync.client import connect as websocket_connect

from .models import RiotContext
from .session import RiotSessionDiscovery


MessageCallback = Callable[[str], None]
StateCallback = Callable[[str, str], None]


class StreamManager:
    def __init__(
        self, on_message: MessageCallback, on_state: StateCallback
    ) -> None:
        self._on_message = on_message
        self._on_state = on_state
        self._stream: LocalWebSocketStream | XMPPStream | None = None

    def connect(self, transport: str, context: RiotContext) -> None:
        self.disconnect()
        if transport == "websocket":
            self._stream = LocalWebSocketStream(
                context, self._on_message, self._on_state
            )
        elif transport == "xmpp":
            self._stream = XMPPStream(context, self._on_message, self._on_state)
        else:
            raise ValueError(f"Transporte de stream desconhecido: {transport}")
        self._stream.start()

    def send(self, message: str) -> None:
        if not self._stream:
            raise RuntimeError("Nenhuma conexão em tempo real está ativa.")
        self._stream.send(message)

    def disconnect(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None


class LocalWebSocketStream:
    def __init__(
        self,
        context: RiotContext,
        on_message: MessageCallback,
        on_state: StateCallback,
    ) -> None:
        self.context = context
        self.on_message = on_message
        self.on_state = on_state
        self.socket: Any = None
        self.thread: threading.Thread | None = None
        self.closed = threading.Event()

    def start(self) -> None:
        if not self.context.lockfile:
            raise RuntimeError("O lockfile do Riot Client não está disponível.")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        lockfile = self.context.lockfile
        assert lockfile is not None
        self.on_state("connecting", "Conectando ao WebSocket local")
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            self.socket = websocket_connect(
                f"wss://127.0.0.1:{lockfile.port}",
                ssl=ssl_context,
                additional_headers={
                    "Authorization": RiotSessionDiscovery.local_authorization(lockfile)
                },
                open_timeout=8,
                close_timeout=2,
            )
            self.socket.send(json.dumps([5, "OnJsonApiEvent"]))
            self.on_state("connected", "WebSocket local conectado")
            while not self.closed.is_set():
                message = self.socket.recv()
                if message is None:
                    break
                if isinstance(message, bytes):
                    message = message.decode("utf-8", errors="replace")
                self.on_message(str(message))
        except Exception as exc:
            if not self.closed.is_set():
                self.on_state("error", str(exc))
        finally:
            self.closed.set()
            self.on_state("disconnected", "WebSocket desconectado")

    def send(self, message: str) -> None:
        if not self.socket:
            raise RuntimeError("O WebSocket ainda não está conectado.")
        self.socket.send(message)

    def close(self) -> None:
        self.closed.set()
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass


class XMPPStream:
    def __init__(
        self,
        context: RiotContext,
        on_message: MessageCallback,
        on_state: StateCallback,
    ) -> None:
        self.context = context
        self.on_message = on_message
        self.on_state = on_state
        self.socket: ssl.SSLSocket | None = None
        self.thread: threading.Thread | None = None
        self.closed = threading.Event()
        self.write_lock = threading.Lock()

    def start(self) -> None:
        if not self.context.token or not self.context.entitlement:
            raise RuntimeError("Token e entitlement são necessários para o XMPP.")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        self.on_state("connecting", "Obtendo configuração XMPP")
        try:
            pas_token = self._get_pas_token()
            config = self._get_client_config()
            affinity = self._jwt_payload(pas_token).get("affinity")
            if not affinity:
                raise RuntimeError("O PAS token não contém a afinidade do chat.")

            hosts = config.get("chat.affinities", {})
            domains = config.get("chat.affinity_domains", {})
            host = hosts.get(affinity)
            domain = domains.get(affinity)
            port = int(config.get("chat.port", 5223))
            if not host or not domain:
                raise RuntimeError("Afinidade XMPP ausente na configuração do Riot Client.")

            self.on_state("connecting", f"Conectando a {host}:{port}")
            raw_socket = socket.create_connection((host, port), timeout=10)
            tls_context = ssl.create_default_context()
            self.socket = tls_context.wrap_socket(raw_socket, server_hostname=host)
            self.socket.settimeout(1.0)
            self._authenticate(domain, pas_token)
            self.on_state("connected", "XMPP autenticado")

            last_ping = time.monotonic()
            while not self.closed.is_set():
                if time.monotonic() - last_ping > 150:
                    self._write(" ")
                    last_ping = time.monotonic()
                try:
                    data = self.socket.recv(65536)
                    if not data:
                        break
                    self.on_message(data.decode("utf-8", errors="replace"))
                except TimeoutError:
                    continue
        except Exception as exc:
            if not self.closed.is_set():
                self.on_state("error", str(exc))
        finally:
            self.close()
            self.on_state("disconnected", "XMPP desconectado")

    def _authenticate(self, domain: str, pas_token: str) -> None:
        self._write(
            '<?xml version="1.0"?>'
            f'<stream:stream to="{domain}.pvp.net" version="1.0" '
            'xmlns:stream="http://etherx.jabber.org/streams">'
        )
        self._read_until("X-Riot-RSO-PAS")
        self._write(
            '<auth mechanism="X-Riot-RSO-PAS" '
            'xmlns="urn:ietf:params:xml:ns:xmpp-sasl">'
            f"<rso_token>{self.context.token}</rso_token>"
            f"<pas_token>{pas_token}</pas_token></auth>"
        )
        self._read_once()
        self._write(
            '<?xml version="1.0"?>'
            f'<stream:stream to="{domain}.pvp.net" version="1.0" '
            'xmlns:stream="http://etherx.jabber.org/streams">'
        )
        self._read_until("stream:features")
        self._write(
            '<iq id="_xmpp_bind1" type="set">'
            '<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind"></bind></iq>'
        )
        self._read_once()
        self._write(
            '<iq id="_xmpp_session1" type="set">'
            '<session xmlns="urn:ietf:params:xml:ns:xmpp-session"/></iq>'
        )
        self._read_once()
        self._write(
            '<iq id="xmpp_entitlements_0" type="set">'
            '<entitlements xmlns="urn:riotgames:entitlements">'
            f'<token xmlns="">{self.context.entitlement}</token>'
            "</entitlements></iq>"
        )
        self._read_once()

    def _read_until(self, marker: str, timeout: float = 12.0) -> str:
        deadline = time.monotonic() + timeout
        chunks: list[str] = []
        while time.monotonic() < deadline:
            try:
                chunks.append(self._read_once())
            except TimeoutError:
                continue
            text = "".join(chunks)
            if marker in text:
                return text
        raise TimeoutError(f"Timeout aguardando resposta XMPP: {marker}")

    def _read_once(self) -> str:
        if not self.socket:
            raise RuntimeError("Socket XMPP indisponível.")
        data = self.socket.recv(65536)
        if not data:
            raise ConnectionError("O servidor XMPP encerrou a conexão.")
        return data.decode("utf-8", errors="replace")

    def _write(self, message: str) -> None:
        if not self.socket:
            raise RuntimeError("Socket XMPP indisponível.")
        with self.write_lock:
            self.socket.sendall(message.encode("utf-8"))

    def send(self, message: str) -> None:
        self._write(message)

    def close(self) -> None:
        self.closed.set()
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def _get_pas_token(self) -> str:
        response = httpx.get(
            "https://riot-geo.pas.si.riotgames.com/pas/v1/service/chat",
            headers={"Authorization": f"Bearer {self.context.token}", "User-Agent": ""},
            timeout=10.0,
            trust_env=False,
        )
        response.raise_for_status()
        return response.text

    def _get_client_config(self) -> dict[str, Any]:
        response = httpx.get(
            "https://clientconfig.rpg.riotgames.com/api/v1/config/player?app=Riot%20Client",
            headers={
                "Authorization": f"Bearer {self.context.token}",
                "X-Riot-Entitlements-JWT": self.context.entitlement,
                "User-Agent": "",
            },
            timeout=10.0,
            trust_env=False,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _jwt_payload(token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("PAS token inválido.")
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
