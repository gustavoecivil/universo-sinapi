import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

type EnvStatus = {
  ok: boolean;
  projectRoot: string;
  pythonPath: string;
  message: string;
};

type EtlFinished = {
  code: number;
  success: boolean;
};

const logEl = () => document.querySelector<HTMLPreElement>("#log");
const envStatusEl = () => document.querySelector<HTMLElement>("#env-status");
const runStateEl = () => document.querySelector<HTMLElement>("#run-state");
const runBtn = () => document.querySelector<HTMLButtonElement>("#run-btn");

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function appendLog(line: string) {
  const el = logEl();
  if (!el) return;
  el.textContent += `${line}\n`;
  el.scrollTop = el.scrollHeight;
}

function setRunning(running: boolean) {
  const btn = runBtn();
  const state = runStateEl();
  if (btn) btn.disabled = running;
  if (state) {
    state.textContent = running ? "Executando…" : "Idle";
    state.classList.toggle("running", running);
  }
}

function selectedMode(): string {
  const checked = document.querySelector<HTMLInputElement>('input[name="mode"]:checked');
  return checked?.value ?? "current";
}

function selectedFormats(): string[] {
  return Array.from(
    document.querySelectorAll<HTMLInputElement>('input[name="format"]:checked'),
  ).map((el) => el.value);
}

function syncSpecificFields() {
  const specific = document.querySelector<HTMLElement>("#specific-fields");
  if (specific) {
    specific.hidden = selectedMode() !== "specific";
  }
}

async function refreshEnv() {
  const status = envStatusEl();
  try {
    const env = await invoke<EnvStatus>("check_env");
    if (!status) return;
    status.textContent = env.message;
    status.className = `status ${env.ok ? "status-ok" : "status-error"}`;
    status.title = `${env.projectRoot}\n${env.pythonPath}`;
    const btn = runBtn();
    if (btn) btn.disabled = !env.ok;
  } catch (error) {
    if (!status) return;
    status.textContent = String(error);
    status.className = "status status-error";
  }
}

async function runEtl(event: Event) {
  event.preventDefault();

  const formats = selectedFormats();
  if (formats.length === 0) {
    appendLog("Selecione ao menos um formato de saída.");
    return;
  }

  const mode = selectedMode();
  const yearValue = document.querySelector<HTMLInputElement>("#year")?.value;
  const monthValue = document.querySelector<HTMLInputElement>("#month")?.value;
  const supabase =
    document.querySelector<HTMLInputElement>("#supabase")?.checked ?? false;

  const options = {
    mode,
    year: yearValue ? Number(yearValue) : null,
    month: monthValue ? Number(monthValue) : null,
    formats,
    supabase,
  };

  const log = logEl();
  if (log) log.textContent = "";
  setRunning(true);
  appendLog("Iniciando ETL…");

  try {
    // Retorna na hora; o progresso chega via eventos etl-log / etl-finished.
    await invoke("run_etl", { options });
  } catch (error) {
    appendLog(`Erro: ${error}`);
    setRunning(false);
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  document
    .querySelectorAll<HTMLInputElement>('input[name="mode"]')
    .forEach((input) => input.addEventListener("change", syncSpecificFields));

  document.querySelector("#etl-form")?.addEventListener("submit", runEtl);
  document.querySelector("#clear-btn")?.addEventListener("click", () => {
    const log = logEl();
    if (log) log.textContent = "";
  });

  syncSpecificFields();

  if (!isTauriRuntime()) {
    const status = envStatusEl();
    if (status) {
      status.textContent =
        "Abra com yarn tauri dev — o Vite no browser não tem a API Tauri.";
      status.className = "status status-error";
    }
    const btn = runBtn();
    if (btn) btn.disabled = true;
    return;
  }

  await refreshEnv();

  await listen<string>("etl-log", (event) => {
    appendLog(event.payload);
  });

  await listen<EtlFinished>("etl-finished", (event) => {
    appendLog(
      event.payload.success
        ? `Processo finalizado (código ${event.payload.code}).`
        : `Processo terminou com falha (código ${event.payload.code}).`,
    );
    setRunning(false);
  });
});
