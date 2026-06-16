const { app, BrowserWindow, clipboard, ipcMain, shell } = require("electron");
const fs = require("fs");
const https = require("https");
const path = require("path");
const { randomUUID, createHash } = require("crypto");

const DEFAULT_BACKEND_URL = "https://valcomp-api-cda2.fly.dev";
const REGION_TO_SHARD = {
  na: "na",
  latam: "na",
  br: "na",
  eu: "eu",
  ap: "ap",
  kr: "kr",
};
const MAX_LOG_BYTES = 2 * 1024 * 1024;

let mainWindow = null;
let riotPayload = null;
let logFile = null;

function jwtTiming(token) {
  try {
    const [, payload] = String(token || "").split(".");
    if (!payload) return { secondsLeft: 0, expiresAt: "" };
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = JSON.parse(Buffer.from(normalized, "base64").toString("utf8"));
    const expiresAt = Number(decoded.exp || 0);
    return {
      secondsLeft: Math.floor(expiresAt - Date.now() / 1000),
      expiresAt: expiresAt ? new Date(expiresAt * 1000).toISOString() : "",
    };
  } catch {
    return { secondsLeft: 0, expiresAt: "" };
  }
}

function sanitize(value, key = "", depth = 0) {
  if (depth > 5) return "[MAX_DEPTH]";
  const lowerKey = String(key).toLowerCase();
  if (
    [
      "access_token",
      "authorization",
      "cookie",
      "entitlement",
      "password",
      "puuid",
      "refresh_token",
      "secret",
      "ssid",
      "token",
    ].some((secret) => lowerKey.includes(secret))
  ) {
    return "[REDACTED]";
  }
  if (Array.isArray(value)) {
    return value.slice(0, 80).map((item) => sanitize(item, "", depth + 1));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .slice(0, 80)
        .map(([childKey, childValue]) => [
          childKey,
          sanitize(childValue, childKey, depth + 1),
        ]),
    );
  }
  if (typeof value === "string") {
    return value
      .slice(0, 8000)
      .replace(
        /\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?\b/g,
        "[REDACTED_JWT]",
      )
      .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/gi, "Bearer [REDACTED]")
      .replace(
        /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
        "[REDACTED_EMAIL]",
      )
      .replace(
        /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi,
        "[REDACTED_ID]",
      );
  }
  return value;
}

function initializeLogging() {
  const directory = app.getPath("logs");
  fs.mkdirSync(directory, { recursive: true });
  logFile = path.join(directory, "valcomp-companion.jsonl");
  rotateLog();
}

function rotateLog() {
  if (!logFile || !fs.existsSync(logFile)) return;
  if (fs.statSync(logFile).size <= MAX_LOG_BYTES) return;
  const backup = `${logFile}.1`;
  if (fs.existsSync(backup)) fs.unlinkSync(backup);
  fs.renameSync(logFile, backup);
}

function logEvent(level, event, context = {}) {
  try {
    rotateLog();
    const record = sanitize({
      timestamp: new Date().toISOString(),
      source: "desktop",
      level,
      event,
      app_version: app.getVersion(),
      context,
    });
    fs.appendFileSync(logFile, `${JSON.stringify(record)}\n`, "utf8");
  } catch {
    // Diagnostics must never interrupt the linking flow.
  }
}

function readLockfile() {
  const lockfilePath = path.join(
    process.env.LOCALAPPDATA || "",
    "Riot Games",
    "Riot Client",
    "Config",
    "lockfile",
  );
  if (!fs.existsSync(lockfilePath)) {
    throw new Error(
      "Não encontrei o Riot Client aberto. Abra o Riot Client ou VALORANT e tente novamente.",
    );
  }
  const parts = fs.readFileSync(lockfilePath, "utf8").trim().split(":");
  if (parts.length < 5) throw new Error("O arquivo de sessão do Riot Client está inválido.");
  return {
    name: parts[0],
    pid: Number(parts[1]),
    port: Number(parts[2]),
    password: parts[3],
    protocol: parts[4],
  };
}

function localGet(lockfile, endpoint) {
  return new Promise((resolve, reject) => {
    const authorization = Buffer.from(`riot:${lockfile.password}`).toString("base64");
    const request = https.request(
      {
        hostname: "127.0.0.1",
        port: lockfile.port,
        path: `/${endpoint.replace(/^\/+/, "")}`,
        method: "GET",
        rejectUnauthorized: false,
        timeout: 6000,
        headers: {
          Authorization: `Basic ${authorization}`,
          "User-Agent": "",
          Accept: "application/json",
        },
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const body = Buffer.concat(chunks).toString("utf8");
          if ((response.statusCode || 500) >= 400) {
            reject(new Error(`A API local da Riot respondeu HTTP ${response.statusCode}.`));
            return;
          }
          try {
            resolve(body ? JSON.parse(body) : {});
          } catch {
            reject(new Error("A Riot devolveu uma resposta local inválida."));
          }
        });
      },
    );
    request.on("timeout", () => request.destroy(new Error("A Riot demorou para responder.")));
    request.on("error", reject);
    request.end();
  });
}

function parseSessions(data) {
  if (!data || typeof data !== "object") return {};
  const session = Object.values(data).find(
    (value) => value && typeof value === "object" && value.productId === "valorant",
  );
  if (!session) return {};
  const result = {};
  const args = session.launchConfiguration?.arguments || [];
  for (const argument of args) {
    if (typeof argument !== "string" || !argument.includes("=")) continue;
    const [rawKey, ...rest] = argument.split("=");
    const key = rawKey.replace(/^-+/, "").toLowerCase();
    const value = rest.join("=");
    if (key === "ares-deployment") result.region = value;
    if (key === "ares-shard" || key === "ares-platform") result.shard = value;
  }
  if (typeof session.version === "string") result.clientVersion = session.version;
  return result;
}

function parseShooterLog() {
  const logPath = path.join(
    process.env.LOCALAPPDATA || "",
    "VALORANT",
    "Saved",
    "Logs",
    "ShooterGame.log",
  );
  if (!fs.existsSync(logPath)) return {};
  try {
    const stats = fs.statSync(logPath);
    const bytes = Math.min(stats.size, 12 * 1024 * 1024);
    const fd = fs.openSync(logPath, "r");
    const buffer = Buffer.alloc(bytes);
    fs.readSync(fd, buffer, 0, bytes, stats.size - bytes);
    fs.closeSync(fd);
    const text = buffer.toString("utf8");
    const regionMatches = [
      ...text.matchAll(/https:\/\/glz-(.+?)-1\.(.+?)\.a\.pvp\.net/gi),
    ];
    const versionMatches = [...text.matchAll(/CI server version: ([^\r\n]+)/g)];
    const result = {};
    if (regionMatches.length) {
      const latest = regionMatches.at(-1);
      result.region = latest[1];
      result.shard = latest[2];
    }
    if (versionMatches.length) {
      result.clientVersion = versionMatches
        .at(-1)[1]
        .trim()
        .replace(/^(release-\d+\.\d+-)/, "$1shipping-");
    }
    return result;
  } catch {
    return {};
  }
}

function readSsid() {
  const settingsPath = path.join(
    process.env.LOCALAPPDATA || "",
    "Riot Games",
    "Riot Client",
    "Data",
    "RiotGamesPrivateSettings.yaml",
  );
  if (!fs.existsSync(settingsPath)) return "";
  const text = fs.readFileSync(settingsPath, "utf8");
  const match = text.match(
    /name:\s*["']?ssid["']?.{0,800}?value:\s*["']([^"']+)["']/is,
  );
  return match ? match[1].trim() : "";
}

async function publicClientVersion() {
  try {
    const response = await fetch("https://valorant-api.com/v1/version", {
      headers: { "User-Agent": "" },
      signal: AbortSignal.timeout(6000),
    });
    if (!response.ok) return "";
    const payload = await response.json();
    return String(payload?.data?.riotClientVersion || "");
  } catch {
    return "";
  }
}

async function detectRiotSession() {
  logEvent("info", "riot_detection_started");
  const lockfile = readLockfile();
  const [entitlements, regionLocale, sessions] = await Promise.all([
    localGet(lockfile, "entitlements/v1/token"),
    localGet(lockfile, "riotclient/region-locale"),
    localGet(lockfile, "product-session/v1/external-sessions"),
  ]);
  const session = parseSessions(sessions);
  const shooterLog = parseShooterLog();
  const region = String(
    session.region || shooterLog.region || regionLocale.region || "",
  ).toLowerCase();
  const shard = String(
    session.shard || shooterLog.shard || REGION_TO_SHARD[region] || "",
  ).toLowerCase();
  const clientVersion =
    shooterLog.clientVersion ||
    session.clientVersion ||
    (await publicClientVersion());
  const ssid = readSsid();
  const accessToken = String(entitlements.accessToken || "");
  const entitlementToken = String(entitlements.token || "");
  const puuid = String(entitlements.subject || "");
  if (!accessToken || !entitlementToken || !puuid) {
    throw new Error(
      "A sessão local ainda não está pronta. Abra o VALORANT, aguarde a tela inicial e tente novamente.",
    );
  }
  if (!region || !shard) {
    throw new Error("Não foi possível identificar a região da sua conta Riot.");
  }
  const timing = jwtTiming(accessToken);
  const refreshOnServer = timing.secondsLeft < 300 && Boolean(ssid);
  if (timing.secondsLeft < 300 && !ssid) {
    logEvent("warning", "riot_detection_expired_token", {
      seconds_left: timing.secondsLeft,
      expires_at: timing.expiresAt,
    });
    throw new Error(
      "A sessão local da Riot está expirada. Feche e abra o Riot Client ou entre na tela inicial do VALORANT, depois clique em Detectar novamente.",
    );
  }
  riotPayload = {
    ssid,
    cookies: ssid ? { ssid } : {},
    access_token: refreshOnServer ? "" : accessToken,
    entitlement_token: refreshOnServer ? "" : entitlementToken,
    puuid,
    region,
    shard,
    client_version: clientVersion,
  };
  const accountReference = createHash("sha256").update(puuid).digest("hex").slice(0, 10);
  logEvent("info", "riot_detection_succeeded", {
    account_reference: accountReference,
    region,
    shard,
    has_ssid: Boolean(ssid),
    has_client_version: Boolean(clientVersion),
  });
  return {
    detected: true,
    accountReference,
    region: region.toUpperCase(),
    shard: shard.toUpperCase(),
    hasSsid: Boolean(ssid),
    secondsLeft: timing.secondsLeft,
    refreshOnServer,
  };
}

function validateBackendUrl(value) {
  const parsed = new URL(value || DEFAULT_BACKEND_URL);
  const isLocal = ["127.0.0.1", "localhost"].includes(parsed.hostname);
  if (parsed.protocol !== "https:" && !isLocal) {
    throw new Error("O servidor do Valcomp precisa usar uma conexão HTTPS segura.");
  }
  return parsed.origin;
}

async function submitLink({ code, backendUrl }) {
  if (!/^\d{6}$/.test(String(code || ""))) {
    throw new Error("Digite o código de 6 números mostrado no celular.");
  }
  await detectRiotSession();
  if (!riotPayload) {
    throw new Error("Detecte sua conta Riot antes de vincular.");
  }
  const baseUrl = validateBackendUrl(backendUrl);
  const requestId = `desk-${randomUUID()}`;
  logEvent("info", "link_started", { request_id: requestId, backend: baseUrl });
  let response;
  try {
    response = await fetch(`${baseUrl}/riot/link/complete`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "User-Agent": `Valcomp-Companion/${app.getVersion()}`,
        "X-Valcomp-Client": `desktop/${app.getVersion()}`,
        "X-Request-ID": requestId,
      },
      body: JSON.stringify({ link_code: code, riot: riotPayload }),
      signal: AbortSignal.timeout(30000),
    });
  } catch (error) {
    logEvent("error", "link_network_failed", {
      request_id: requestId,
      error: String(error),
    });
    throw new Error(
      `Não foi possível falar com o Valcomp. Confira sua internet e tente novamente.\nReferência: ${requestId}`,
    );
  }
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    const error = payload?.error || payload?.detail || {};
    const message =
      error.message ||
      payload.message ||
      `O servidor respondeu HTTP ${response.status}.`;
    const serverRequestId =
      error.request_id || response.headers.get("x-request-id") || requestId;
    logEvent("error", "link_rejected", {
      request_id: serverRequestId,
      status: response.status,
      code: error.code || "link_failed",
      message,
    });
    throw new Error(`${message}\nReferência: ${serverRequestId}`);
  }
  const account = payload.riot_account || {};
  logEvent("info", "link_succeeded", {
    request_id: response.headers.get("x-request-id") || requestId,
    region: account.region || "",
    shard: account.shard || "",
  });
  riotPayload = null;
  return {
    linked: true,
    riotId: account.tag_line
      ? `${account.game_name || "Conta Riot"}#${account.tag_line}`
      : account.game_name || "Conta Riot",
  };
}

function diagnosticsText() {
  const lines =
    logFile && fs.existsSync(logFile) ? fs.readFileSync(logFile, "utf8").trim().split(/\r?\n/) : [];
  const selected = lines.slice(-300);
  return [
    "VALCOMP COMPANION DIAGNOSTICS",
    `App: ${app.getVersion()}`,
    `Windows: ${process.getSystemVersion()}`,
    `Arquivo local: ${logFile || "indisponível"}`,
    `Eventos: ${selected.length}`,
    "",
    ...selected,
  ].join("\n");
}

function registerIpc() {
  ipcMain.handle("app:version", () => app.getVersion());
  ipcMain.handle("riot:detect", async () => {
    try {
      return { ok: true, data: await detectRiotSession() };
    } catch (error) {
      riotPayload = null;
      logEvent("error", "riot_detection_failed", { error: String(error) });
      return { ok: false, error: String(error.message || error) };
    }
  });
  ipcMain.handle("riot:link", async (_, input) => {
    try {
      return { ok: true, data: await submitLink(input || {}) };
    } catch (error) {
      return { ok: false, error: String(error.message || error) };
    }
  });
  ipcMain.handle("diagnostics:copy", () => {
    clipboard.writeText(diagnosticsText());
    return { ok: true, path: logFile };
  });
  ipcMain.handle("diagnostics:open-folder", async () => {
    await shell.openPath(path.dirname(logFile));
    return { ok: true };
  });
  ipcMain.handle("clipboard:write", (_, text) => {
    clipboard.writeText(String(text || ""));
    return { ok: true };
  });
  ipcMain.on("diagnostics:renderer", (_, payload) => {
    logEvent("info", payload?.event || "renderer_event", payload?.context || {});
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 780,
    height: 720,
    minWidth: 700,
    minHeight: 680,
    show: false,
    autoHideMenuBar: true,
    backgroundColor: "#090E15",
    icon: path.join(__dirname, "..", "assets", "app-icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      devTools: !app.isPackaged,
    },
  });
  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event) => event.preventDefault());
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    const screenshotPath = process.env.VALCOMP_SCREENSHOT_PATH;
    if (screenshotPath) {
      setTimeout(async () => {
        const image = await mainWindow.webContents.capturePage();
        fs.writeFileSync(screenshotPath, image.toPNG());
        app.quit();
      }, 1800);
    }
  });
}

process.on("uncaughtException", (error) => {
  logEvent("critical", "uncaught_exception", {
    error: String(error),
    stack: error.stack || "",
  });
});
process.on("unhandledRejection", (error) => {
  logEvent("critical", "unhandled_rejection", { error: String(error) });
});

app.whenReady().then(() => {
  app.setAppUserModelId("com.cda2.valcomp.companion");
  initializeLogging();
  logEvent("info", "app_started", { packaged: app.isPackaged });
  registerIpc();
  createWindow();
});

app.on("window-all-closed", () => {
  riotPayload = null;
  app.quit();
});
