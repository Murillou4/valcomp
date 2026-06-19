const byId = (id) => document.getElementById(id);

const elements = {
  code: byId("link-code"),
  pairCode: byId("pair-code"),
  detect: byId("detect-button"),
  link: byId("link-button"),
  pair: byId("pair-button"),
  backend: byId("backend-url"),
  riotStatus: byId("riot-status"),
  riotTitle: byId("riot-status-title"),
  riotMessage: byId("riot-status-message"),
  riotBadge: byId("riot-badge"),
  pairBadge: byId("pair-badge"),
  pairForm: byId("pair-form"),
  pairedDevice: byId("paired-device"),
  autoLaunch: byId("auto-launch"),
  copyError: byId("copy-error"),
  globalConnection: byId("global-connection"),
};

let riotDetected = false;
let busy = false;
let lastError = "";
let currentLiveStatus = null;
let currentSnapshot = null;

function setRiotStatus(type, title, message) {
  elements.riotStatus.className = `inline-status ${type}`;
  elements.riotTitle.textContent = title;
  elements.riotMessage.textContent = message;
  elements.riotBadge.className = `status-badge ${type}`;
  elements.riotBadge.textContent =
    type === "success" ? "Detectada" : type === "error" ? "Erro" : type === "warning" ? "Atenção" : "Verificando";
}

function syncControls() {
  elements.code.value = elements.code.value.replace(/\D/g, "").slice(0, 6);
  elements.pairCode.value = elements.pairCode.value.replace(/\D/g, "").slice(0, 6);
  elements.link.disabled = busy || !riotDetected || !/^\d{6}$/.test(elements.code.value);
  elements.pair.disabled = busy || !/^\d{6}$/.test(elements.pairCode.value);
  elements.detect.disabled = busy;
  elements.code.disabled = busy;
  elements.pairCode.disabled = busy;
}

async function detectRiot() {
  busy = true;
  riotDetected = false;
  lastError = "";
  elements.copyError.hidden = true;
  setRiotStatus("neutral", "Procurando o Riot Client", "Aguardando a sessão local.");
  syncControls();
  try {
    const result = await window.valcomp.detectRiot();
    if (!result.ok) throw new Error(result.error);
    riotDetected = true;
    const data = result.data;
    setRiotStatus(
      data.hasSsid ? "success" : "warning",
      `Conta detectada em ${data.region}/${data.shard}`,
      data.refreshOnServer
        ? "A sessão será renovada com segurança durante o vínculo."
        : "Sessão local pronta para vínculo e estado ao vivo.",
    );
  } catch (error) {
    lastError = String(error?.message || error);
    elements.copyError.hidden = false;
    setRiotStatus("error", "Riot Client indisponível", lastError);
  } finally {
    busy = false;
    syncControls();
  }
}

async function linkRiot() {
  if (elements.link.disabled) return;
  busy = true;
  syncControls();
  setRiotStatus("neutral", "Vinculando conta Riot", "Aguardando o Valcomp confirmar a sessão.");
  try {
    const result = await window.valcomp.linkAccount({
      code: elements.code.value,
      backendUrl: elements.backend.value.trim(),
    });
    if (!result.ok) throw new Error(result.error);
    elements.code.value = "";
    setRiotStatus("success", "Conta Riot vinculada", result.data.riotId);
  } catch (error) {
    lastError = String(error?.message || error);
    elements.copyError.hidden = false;
    setRiotStatus("error", "Falha no vínculo Riot", lastError);
  } finally {
    busy = false;
    syncControls();
  }
}

async function pairCompanion() {
  if (elements.pair.disabled) return;
  busy = true;
  elements.pair.textContent = "Pareando...";
  syncControls();
  try {
    const result = await window.valcomp.pairCompanion({
      code: elements.pairCode.value,
      backendUrl: elements.backend.value.trim(),
    });
    if (!result.ok) throw new Error(result.error);
    elements.pairCode.value = "";
    await loadLiveStatus();
  } catch (error) {
    lastError = String(error?.message || error);
    elements.copyError.hidden = false;
    elements.pairBadge.className = "status-badge error";
    elements.pairBadge.textContent = "Falha ao parear";
  } finally {
    busy = false;
    elements.pair.textContent = "Parear celular";
    syncControls();
  }
}

async function unpairCompanion() {
  if (!window.confirm("Remover este Companion do celular?")) return;
  await window.valcomp.unpairCompanion();
  await loadLiveStatus();
}

async function loadLiveStatus() {
  const status = await window.valcomp.liveStatus();
  if (!status) return;
  applyLiveStatus(status);
}

function applyLiveStatus(status) {
  currentLiveStatus = { ...(currentLiveStatus || {}), ...status };
  const paired = Boolean(currentLiveStatus.paired);
  elements.pairForm.hidden = paired;
  elements.pairedDevice.hidden = !paired;
  elements.pairBadge.className = `status-badge ${paired ? "success" : "neutral"}`;
  elements.pairBadge.textContent = paired ? "Pareado" : "Não pareado";
  if (paired) {
    byId("paired-device-name").textContent = currentLiveStatus.device?.deviceName || "Este PC";
    byId("paired-device-id").textContent = `Dispositivo ${String(currentLiveStatus.device?.deviceId || "").slice(0, 8)}`;
  }
  if (currentLiveStatus.preferences) {
    elements.autoLaunch.checked = Boolean(currentLiveStatus.preferences.autoLaunch);
  }
  const backend = status.backend;
  if (backend) {
    const connected = backend.status === "connected";
    elements.globalConnection.className = `connection-pill ${connected ? "online" : backend.status === "error" ? "error" : ""}`;
    elements.globalConnection.querySelector("b").textContent = connected ? "Celular conectado" : backend.message;
    byId("mobile-live-state").textContent = connected ? "Conectado" : paired ? "Reconectando" : "Não pareado";
  } else {
    byId("mobile-live-state").textContent = paired ? "Pareado" : "Não pareado";
  }
  if (currentLiveStatus.snapshot) applySnapshot(currentLiveStatus.snapshot);
}

function applySnapshot(snapshot) {
  currentSnapshot = snapshot;
  const phase = snapshot.phase || "offline";
  const state = snapshot.state || {};
  const phaseInfo = phasePresentation(phase);
  byId("live-title").textContent = phaseInfo.title;
  byId("live-subtitle").textContent = phaseInfo.subtitle;
  byId("live-phase").textContent = phaseInfo.label;
  byId("live-region").textContent = state.region || "--";
  byId("riot-live-state").textContent = phase === "offline" ? "Offline" : "Conectado";
  byId("live-tab-dot").classList.toggle("online", phase !== "offline" && phase !== "error");

  const map = state.match?.map || state.map;
  const hasMap = Boolean(map?.name || map?.id);
  byId("match-visual").hidden = !hasMap;
  if (hasMap) {
    byId("match-map-name").textContent = map.name || "Mapa indisponível";
    byId("match-mode").textContent = state.match?.mode?.name || state.mode?.name || phaseInfo.label;
    const image = byId("match-map-image");
    image.hidden = !map.icon;
    if (map.icon) image.src = map.icon;
  }

  const queue = state.queue;
  byId("queue-section").hidden = !queue || phase === "in_game";
  if (queue) byId("queue-mode").textContent = queue.id || "Indisponível";

  const agents = Array.isArray(state.agents) ? state.agents : [];
  byId("agents-section").hidden = agents.length === 0 || phase === "in_game";
  renderAgents(byId("agent-strip"), agents);
  const team = Array.isArray(state.match?.team) ? state.match.team : [];
  byId("team-section").hidden = phase !== "in_game" || team.length === 0;
  renderAgents(byId("team-strip"), team);

  const hasData = hasMap || Boolean(queue) || agents.length > 0 || team.length > 0;
  byId("live-empty").hidden = hasData;
  byId("live-empty-message").textContent = state.message || phaseInfo.subtitle;
  renderCapabilities(state.capabilities || {});
  updateQueueClock();
}

function renderAgents(container, agents) {
  container.replaceChildren();
  agents.forEach((entry) => {
    const item = document.createElement("div");
    item.className = `agent-item${entry.is_self ? " self" : ""}${entry.locked ? " locked" : ""}`;
    if (entry.agent?.icon) {
      const image = document.createElement("img");
      image.src = entry.agent.icon;
      image.alt = entry.agent.name || "Agente";
      item.appendChild(image);
    } else {
      const placeholder = document.createElement("span");
      placeholder.className = "agent-placeholder";
      item.appendChild(placeholder);
    }
    const name = document.createElement("strong");
    name.textContent = entry.agent?.name || "Não escolhido";
    item.appendChild(name);
    container.appendChild(item);
  });
}

function renderCapabilities(capabilities) {
  const target = byId("capabilities");
  target.replaceChildren();
  const labels = {
    party: "Party e fila",
    agent: "Seleção manual",
    chat: "Chat manual",
    leave: "Saída confirmada",
    match_accept: "Aceite de partida",
  };
  Object.entries(labels).forEach(([key, label]) => {
    const row = document.createElement("div");
    const text = document.createElement("span");
    const status = document.createElement("strong");
    text.textContent = label;
    status.textContent = capabilities[key] ? "Disponível" : "Indisponível";
    status.className = capabilities[key] ? "available" : "unavailable";
    row.append(text, status);
    target.appendChild(row);
  });
}

function phasePresentation(phase) {
  return {
    offline: { title: "Companion offline", subtitle: "Abra o Riot Client e o VALORANT.", label: "Offline" },
    client: { title: "Cliente conectado", subtitle: "Aguardando o lobby do VALORANT.", label: "Cliente" },
    lobby: { title: "No lobby", subtitle: "Party pronta para entrar na fila.", label: "Lobby" },
    queue: { title: "Buscando partida", subtitle: "O celular será avisado quando a partida aparecer.", label: "Fila" },
    match_found: { title: "Partida encontrada", subtitle: "Confirme a partida no cliente quando necessário.", label: "Encontrada" },
    pregame: { title: "Seleção de agente", subtitle: "Escolhas manuais disponíveis no celular.", label: "Pre-game" },
    in_game: { title: "Partida em andamento", subtitle: "Somente dados reais visíveis no cliente.", label: "Em partida" },
    postgame: { title: "Partida encerrada", subtitle: "Aguardando os dados finais da Riot.", label: "Pós-partida" },
    error: { title: "Estado indisponível", subtitle: "Consulte o diagnóstico da conexão.", label: "Erro" },
  }[phase] || { title: "Estado desconhecido", subtitle: "Aguardando atualização.", label: phase };
}

function updateQueueClock() {
  const queue = currentSnapshot?.state?.queue;
  if (!queue) return;
  let elapsed = Number(queue.elapsed_seconds);
  if (queue.entered_at) elapsed = Math.max(0, Math.floor((Date.now() - Date.parse(queue.entered_at)) / 1000));
  if (!Number.isFinite(elapsed)) {
    byId("queue-time").textContent = "--:--";
    return;
  }
  byId("queue-time").textContent = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
    document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.id === `page-${tab.dataset.tab}`));
  });
});

elements.code.addEventListener("input", syncControls);
elements.pairCode.addEventListener("input", syncControls);
elements.detect.addEventListener("click", detectRiot);
elements.link.addEventListener("click", linkRiot);
elements.pair.addEventListener("click", pairCompanion);
byId("unpair-button").addEventListener("click", unpairCompanion);
elements.autoLaunch.addEventListener("change", () => window.valcomp.setAutoLaunch(elements.autoLaunch.checked));
byId("refresh-live").addEventListener("click", () => window.valcomp.refreshLive().then(applyLiveStatus));
byId("copy-diagnostics").addEventListener("click", async () => {
  await window.valcomp.copyDiagnostics();
  byId("copy-diagnostics").textContent = "Copiado";
  setTimeout(() => (byId("copy-diagnostics").textContent = "Copiar diagnóstico"), 1600);
});
byId("open-logs").addEventListener("click", () => window.valcomp.openLogsFolder());
elements.copyError.addEventListener("click", () => window.valcomp.copyText(lastError));
byId("download-update").addEventListener("click", () => window.valcomp.downloadUpdate());

window.valcomp.onLiveSnapshot(applySnapshot);
window.valcomp.onLiveStatus(applyLiveStatus);
window.valcomp.onLiveCommand((command) => {
  const label = String(command.command || "Ação ao vivo").replaceAll("_", " ");
  byId("command-activity").textContent = command.status === "running" ? `${label}: executando` : `${label}: ${command.status}`;
});
window.valcomp.checkUpdate().then((update) => {
  if (!update?.available) return;
  byId("update-message").textContent = `Instalado ${update.currentVersion}; disponível ${update.latestVersion}.`;
  byId("update-banner").hidden = false;
});

setInterval(updateQueueClock, 1000);
syncControls();
loadLiveStatus();
detectRiot();
