const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("valcomp", {
  detectRiot: () => ipcRenderer.invoke("riot:detect"),
  linkAccount: (input) => ipcRenderer.invoke("riot:link", input),
  copyDiagnostics: () => ipcRenderer.invoke("diagnostics:copy"),
  openLogsFolder: () => ipcRenderer.invoke("diagnostics:open-folder"),
  copyText: (text) => ipcRenderer.invoke("clipboard:write", String(text || "")),
  checkUpdate: () => ipcRenderer.invoke("updates:check"),
  downloadUpdate: () => ipcRenderer.invoke("updates:download"),
  log: (event, context = {}) =>
    ipcRenderer.send("diagnostics:renderer", { event, context }),
  version: () => ipcRenderer.invoke("app:version"),
  liveStatus: () => ipcRenderer.invoke("live:status"),
  pairCompanion: (input) => ipcRenderer.invoke("live:pair", input),
  unpairCompanion: () => ipcRenderer.invoke("live:unpair"),
  setAutoLaunch: (enabled) => ipcRenderer.invoke("live:auto-launch", Boolean(enabled)),
  refreshLive: () => ipcRenderer.invoke("live:refresh"),
  onLiveSnapshot: (callback) => {
    const listener = (_, value) => callback(value);
    ipcRenderer.on("live:snapshot", listener);
    return () => ipcRenderer.removeListener("live:snapshot", listener);
  },
  onLiveStatus: (callback) => {
    const listener = (_, value) => callback(value);
    ipcRenderer.on("live:status-changed", listener);
    return () => ipcRenderer.removeListener("live:status-changed", listener);
  },
  onLiveCommand: (callback) => {
    const listener = (_, value) => callback(value);
    ipcRenderer.on("live:command", listener);
    return () => ipcRenderer.removeListener("live:command", listener);
  },
});
