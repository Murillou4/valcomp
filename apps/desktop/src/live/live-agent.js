const EventEmitter = require("events");
const os = require("os");

const { BackendConnection } = require("./backend-connection");
const { RiotLiveBridge } = require("./riot-live-bridge");

class LiveAgent extends EventEmitter {
  constructor({ app, secureStore, log }) {
    super();
    this.app = app;
    this.secureStore = secureStore;
    this.log = log;
    this.device = secureStore.loadDevice();
    this.connection = this.createConnection();
    this.bridge = new RiotLiveBridge({ log });
    this.pollTimer = null;
    this.riotSessionTimer = null;
    this.riotSessionRetryTimer = null;
    this.polling = false;
    this.syncingRiotSession = false;
    this.running = false;
    this.lastSnapshot = {
      revision: 0,
      phase: "offline",
      state: { reason: this.device ? "riot_client_unavailable" : "companion_not_paired" },
    };
    this.bridge.on("changed", () => this.scheduleImmediatePoll());
    this.bridge.on("credentials-changed", () => this.syncRiotSession());
  }

  createConnection() {
    const connection = new BackendConnection({ appVersion: this.app.getVersion(), log: this.log });
    connection.on("status", (status) => this.emitStatus({ backend: status }));
    connection.on("ready", (message) => {
      this.bridge.setRevisionFloor(Number(message.next_revision || 1) - 1);
      this.pollNow();
      this.syncRiotSession();
    });
    connection.on("riot-session-result", (message) => {
      if (message.status === "succeeded") {
        this.log("info", "riot_session_refreshed", { expires_at: message.expires_at || "" });
      } else if (message.status === "rejected") {
        this.log("warning", "riot_session_refresh_rejected");
      } else if (message.status === "rate_limited" && !this.riotSessionRetryTimer) {
        this.riotSessionRetryTimer = setTimeout(() => {
          this.riotSessionRetryTimer = null;
          this.syncRiotSession();
        }, 65000);
      }
    });
    connection.on("command", (command) => this.handleCommand(command));
    connection.on("revoked", () => {
      this.secureStore.clearDevice();
      this.device = null;
      this.emitStatus({ backend: { status: "error", message: "Este Companion foi revogado no celular." } });
    });
    return connection;
  }

  status() {
    return {
      paired: Boolean(this.device),
      device: this.device
        ? { deviceId: this.device.deviceId, deviceName: this.device.deviceName }
        : null,
      snapshot: this.lastSnapshot,
      preferences: this.secureStore.loadPreferences(),
      appVersion: this.app.getVersion(),
    };
  }

  start() {
    if (this.running) return;
    this.running = true;
    if (this.device) {
      this.connection.configure(this.device);
      this.connection.connect();
    }
    this.pollNow();
    this.pollTimer = setInterval(() => this.pollNow(), 5000);
    this.riotSessionTimer = setInterval(() => this.syncRiotSession(), 5 * 60 * 1000);
  }

  async pair({ pairCode, backendUrl }) {
    const deviceName = os.hostname().slice(0, 80) || "PC Windows";
    const device = await this.connection.pair({ pairCode, backendUrl, deviceName });
    this.secureStore.saveDevice(device);
    this.device = device;
    this.connection.configure(device);
    this.connection.connect();
    this.emitStatus({ paired: true });
    return { deviceId: device.deviceId, deviceName: device.deviceName };
  }

  async unpair() {
    this.connection.close();
    this.secureStore.clearDevice();
    this.device = null;
    this.connection = this.createConnection();
    this.lastSnapshot = {
      revision: this.lastSnapshot.revision + 1,
      phase: "offline",
      state: { reason: "companion_not_paired" },
    };
    this.emitStatus({ paired: false });
  }

  async pollNow() {
    if (this.polling) return;
    this.polling = true;
    try {
      this.lastSnapshot = await this.bridge.poll();
      if (this.device) this.connection.sendState(this.lastSnapshot);
      this.emit("snapshot", this.lastSnapshot);
    } catch (error) {
      this.log("error", "live_poll_failed", { error: String(error) });
    } finally {
      this.polling = false;
    }
  }

  scheduleImmediatePoll() {
    setTimeout(() => this.pollNow(), 180);
  }

  async syncRiotSession() {
    if (!this.device || this.syncingRiotSession) return;
    this.syncingRiotSession = true;
    try {
      const riot = await this.bridge.credentialSnapshot();
      this.connection.sendRiotSession(riot);
    } catch (error) {
      this.log("debug", "riot_session_refresh_waiting_for_client", {
        error: String(error?.message || error),
      });
    } finally {
      this.syncingRiotSession = false;
    }
  }

  async handleCommand(command) {
    if (!command?.command_id) return;
    const expiresAt = Date.parse(command.expires_at || "");
    if (!Number.isFinite(expiresAt) || expiresAt < Date.now()) {
      this.connection.sendCommandResult(command.command_id, "expired", {
        code: "command_expired",
        message: "A ação chegou depois do limite de segurança.",
      });
      return;
    }
    this.emit("command", { ...command, status: "running" });
    const outcome = await this.bridge.execute(command);
    this.connection.sendCommandResult(command.command_id, outcome.status, outcome.result);
    this.emit("command", { ...command, ...outcome });
    await this.pollNow();
  }

  setAutoLaunch(enabled) {
    const preferences = { ...this.secureStore.loadPreferences(), autoLaunch: Boolean(enabled), consented: true };
    this.secureStore.savePreferences(preferences);
    this.app.setLoginItemSettings({ openAtLogin: preferences.autoLaunch, openAsHidden: true });
    this.emitStatus({ preferences });
    return preferences;
  }

  emitStatus(partial = {}) {
    this.emit("status", { ...this.status(), ...partial });
  }

  close() {
    this.running = false;
    if (this.pollTimer) clearInterval(this.pollTimer);
    if (this.riotSessionTimer) clearInterval(this.riotSessionTimer);
    if (this.riotSessionRetryTimer) clearTimeout(this.riotSessionRetryTimer);
    this.pollTimer = null;
    this.riotSessionTimer = null;
    this.riotSessionRetryTimer = null;
    this.connection.close();
    this.bridge.close();
  }
}

module.exports = { LiveAgent };
