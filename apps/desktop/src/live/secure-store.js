const fs = require("fs");
const path = require("path");

class SecureStore {
  constructor({ app, safeStorage }) {
    this.app = app;
    this.safeStorage = safeStorage;
    this.file = path.join(app.getPath("userData"), "companion-device.json");
    this.preferencesFile = path.join(app.getPath("userData"), "preferences.json");
  }

  loadDevice() {
    if (!fs.existsSync(this.file) || !this.safeStorage.isEncryptionAvailable()) return null;
    try {
      const record = JSON.parse(fs.readFileSync(this.file, "utf8"));
      const secret = this.safeStorage.decryptString(Buffer.from(record.encryptedSecret, "base64"));
      if (!record.deviceId || !secret || !record.backendUrl) return null;
      return {
        deviceId: String(record.deviceId),
        secret,
        backendUrl: String(record.backendUrl),
        websocketUrl: String(record.websocketUrl || ""),
        deviceName: String(record.deviceName || "Este PC"),
      };
    } catch {
      return null;
    }
  }

  saveDevice(device) {
    if (!this.safeStorage.isEncryptionAvailable()) {
      throw new Error("A proteção de credenciais do Windows não está disponível.");
    }
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    const encryptedSecret = this.safeStorage
      .encryptString(String(device.secret || ""))
      .toString("base64");
    fs.writeFileSync(
      this.file,
      JSON.stringify({
        deviceId: device.deviceId,
        backendUrl: device.backendUrl,
        websocketUrl: device.websocketUrl,
        deviceName: device.deviceName,
        encryptedSecret,
      }),
      { encoding: "utf8", mode: 0o600 },
    );
  }

  clearDevice() {
    if (fs.existsSync(this.file)) fs.unlinkSync(this.file);
  }

  loadPreferences() {
    try {
      return JSON.parse(fs.readFileSync(this.preferencesFile, "utf8"));
    } catch {
      return { autoLaunch: false, consented: false };
    }
  }

  savePreferences(preferences) {
    fs.mkdirSync(path.dirname(this.preferencesFile), { recursive: true });
    fs.writeFileSync(this.preferencesFile, JSON.stringify(preferences), "utf8");
  }
}

module.exports = { SecureStore };
