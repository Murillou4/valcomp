const EventEmitter = require("events");
const WebSocket = require("ws");

class BackendConnection extends EventEmitter {
  constructor({ appVersion, log }) {
    super();
    this.appVersion = appVersion;
    this.log = log;
    this.device = null;
    this.socket = null;
    this.closed = false;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.reconnectAttempt = 0;
  }

  configure(device) {
    this.device = device;
  }

  async pair({ pairCode, backendUrl, deviceName }) {
    const response = await fetch(`${backendUrl}/companion/pair/complete`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Valcomp-Client": `desktop/${this.appVersion}`,
      },
      body: JSON.stringify({
        pair_code: pairCode,
        device_name: deviceName,
        app_version: this.appVersion,
        protocol_version: 1,
      }),
      signal: AbortSignal.timeout(15000),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = payload.error || payload.detail || {};
      throw new Error(error.message || `O servidor respondeu HTTP ${response.status}.`);
    }
    return {
      deviceId: payload.device.device_id,
      secret: payload.device_secret,
      deviceName: payload.device.device_name,
      backendUrl,
      websocketUrl: payload.websocket_url,
    };
  }

  connect() {
    if (!this.device || this.closed) return;
    this.disconnectSocket();
    const url = this.device.websocketUrl || `${this.device.backendUrl.replace(/^http/, "ws")}/ws/companion`;
    this.emitStatus("connecting", "Conectando ao Valcomp");
    const socket = new WebSocket(url, {
      headers: {
        "X-Companion-ID": this.device.deviceId,
        "X-Companion-Secret": this.device.secret,
        "X-Valcomp-Client": `desktop/${this.appVersion}`,
      },
      handshakeTimeout: 12000,
    });
    this.socket = socket;
    socket.on("open", () => {
      this.reconnectAttempt = 0;
      this.emitStatus("connected", "Companion conectado ao celular");
      this.startHeartbeat();
    });
    socket.on("message", (buffer) => this.handleMessage(buffer));
    socket.on("close", (code, reason) => {
      this.stopHeartbeat();
      if (this.socket === socket) this.socket = null;
      const message = reason?.toString() || `Conexão encerrada (${code})`;
      this.emitStatus(code === 4401 || code === 4409 ? "error" : "offline", message);
      if (code === 4401) this.emit("revoked");
      if (!this.closed && code !== 4401) this.scheduleReconnect();
    });
    socket.on("error", (error) => {
      this.log("warning", "live_backend_socket_error", { error: String(error) });
    });
  }

  handleMessage(buffer) {
    let message;
    try {
      message = JSON.parse(buffer.toString("utf8"));
    } catch {
      return;
    }
    if (message.type === "ready") {
      this.emit("ready", message);
    } else if (message.type === "command") {
      this.emit("command", message.command);
    } else if (message.type === "riot_session_refresh_result") {
      this.emit("riot-session-result", message);
    }
  }

  sendState(snapshot) {
    return this.send({ type: "state", ...snapshot });
  }

  sendCommandResult(commandId, status, result = {}) {
    return this.send({ type: "command_result", command_id: commandId, status, result });
  }

  sendRiotSession(riot) {
    return this.send({ type: "riot_session_refresh", riot });
  }

  send(payload) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(payload));
    return true;
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: "heartbeat", app_version: this.appVersion, at: new Date().toISOString() });
    }, 10000);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }

  scheduleReconnect() {
    if (this.reconnectTimer || this.closed) return;
    const delay = Math.min(30000, 1000 * 2 ** Math.min(this.reconnectAttempt, 5));
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  emitStatus(status, message) {
    this.emit("status", { status, message });
  }

  disconnectSocket() {
    this.stopHeartbeat();
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.close();
      this.socket = null;
    }
  }

  close() {
    this.closed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.disconnectSocket();
  }
}

module.exports = { BackendConnection };
