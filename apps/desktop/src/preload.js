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
});
