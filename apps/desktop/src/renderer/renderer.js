const statusBox = document.querySelector("#status");
const statusIcon = document.querySelector("#status-icon");
const statusTitle = document.querySelector("#status-title");
const statusMessage = document.querySelector("#status-message");
const codeInput = document.querySelector("#link-code");
const codeReady = document.querySelector("#code-ready");
const detectButton = document.querySelector("#detect-button");
const linkButton = document.querySelector("#link-button");
const backendInput = document.querySelector("#backend-url");
const advanced = document.querySelector("#advanced");
const advancedToggle = document.querySelector("#advanced-toggle");
const copyDiagnostics = document.querySelector("#copy-diagnostics");
const openLogs = document.querySelector("#open-logs");
const copyError = document.querySelector("#copy-error");
const steps = [
  document.querySelector("#step-detect"),
  document.querySelector("#step-code"),
  document.querySelector("#step-done"),
];

let detected = false;
let busy = false;
let lastError = "";

function setStatus(type, title, message, icon = "") {
  statusBox.className = `status ${type}`;
  statusTitle.textContent = title;
  statusMessage.textContent = message;
  statusIcon.innerHTML =
    icon || (type === "neutral" ? '<span class="spinner"></span>' : "✓");
}

function setStep(index) {
  steps.forEach((step, current) => {
    step.classList.toggle("active", current === index);
    step.classList.toggle("done", current < index);
  });
}

function syncControls() {
  const ready = /^\d{6}$/.test(codeInput.value) && detected && !busy;
  linkButton.disabled = !ready;
  detectButton.disabled = busy;
  codeInput.disabled = busy;
  codeReady.classList.toggle("ready", /^\d{6}$/.test(codeInput.value));
  codeReady.textContent = /^\d{6}$/.test(codeInput.value)
    ? "Código pronto"
    : "6 dígitos";
  if (detected && codeInput.value.length > 0) setStep(1);
}

async function detect() {
  busy = true;
  detected = false;
  lastError = "";
  copyError.hidden = true;
  setStep(0);
  setStatus(
    "neutral",
    "Procurando sua conta Riot",
    "Deixe o Riot Client ou VALORANT aberto e logado.",
  );
  syncControls();
  const result = await window.valcomp.detectRiot();
  busy = false;
  if (result.ok) {
    detected = true;
    const data = result.data;
    const refreshHint = data.hasSsid
      ? "A sessão está pronta para continuar."
      : "A conta foi encontrada, mas talvez seja preciso vincular novamente no futuro.";
    setStatus(
      data.hasSsid ? "success" : "warning",
      `Conta Riot encontrada • ${data.region}/${data.shard}`,
      refreshHint,
      data.hasSsid ? "✓" : "!",
    );
    setStep(codeInput.value.length === 6 ? 1 : 0);
    codeInput.focus();
    window.valcomp.log("renderer_detection_success");
  } else {
    lastError = result.error;
    copyError.hidden = false;
    setStatus(
      "warning",
      "Não encontrei uma sessão Riot ativa",
      result.error,
      "!",
    );
    window.valcomp.log("renderer_detection_failed");
  }
  syncControls();
}

async function link() {
  if (linkButton.disabled) return;
  busy = true;
  lastError = "";
  copyError.hidden = true;
  setStep(1);
  setStatus(
    "neutral",
    "Conectando sua conta",
    "Enviando a sessão com segurança para o Valcomp.",
  );
  syncControls();
  const result = await window.valcomp.linkAccount({
    code: codeInput.value,
    backendUrl: backendInput.value.trim(),
  });
  busy = false;
  if (result.ok) {
    detected = false;
    codeInput.value = "";
    setStep(2);
    setStatus(
      "success",
      "Conta vinculada com sucesso",
      `${result.data.riotId}. Você já pode fechar esta janela e voltar ao celular.`,
      "✓",
    );
    linkButton.textContent = "Vínculo concluído";
    window.valcomp.log("renderer_link_success");
  } else {
    lastError = result.error;
    copyError.hidden = false;
    setStatus(
      "error",
      "Não foi possível concluir o vínculo",
      result.error,
      "×",
    );
    window.valcomp.log("renderer_link_failed");
  }
  syncControls();
}

codeInput.addEventListener("input", () => {
  codeInput.value = codeInput.value.replace(/\D/g, "").slice(0, 6);
  syncControls();
});
codeInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") link();
});
detectButton.addEventListener("click", detect);
linkButton.addEventListener("click", link);
advancedToggle.addEventListener("click", () => {
  advanced.hidden = !advanced.hidden;
  advancedToggle.querySelector("span").textContent = advanced.hidden ? "⌄" : "⌃";
});
copyDiagnostics.addEventListener("click", async () => {
  await window.valcomp.copyDiagnostics();
  copyDiagnostics.textContent = "Diagnóstico copiado";
  setTimeout(() => (copyDiagnostics.textContent = "Copiar diagnóstico"), 1800);
});
openLogs.addEventListener("click", () => window.valcomp.openLogsFolder());
copyError.addEventListener("click", async () => {
  await window.valcomp.copyText(lastError);
  copyError.textContent = "Erro copiado";
  setTimeout(() => (copyError.textContent = "Copiar erro"), 1800);
});

window.addEventListener("error", (event) => {
  window.valcomp.log("renderer_error", {
    message: event.message,
    source: event.filename,
    line: event.lineno,
  });
});
window.addEventListener("unhandledrejection", (event) => {
  window.valcomp.log("renderer_unhandled_rejection", {
    message: String(event.reason),
  });
});

window.valcomp.version().then((version) => {
  document.title = `Valcomp Companion ${version}`;
});
detect();
