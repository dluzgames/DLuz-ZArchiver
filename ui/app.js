// Audio Context for subtle SFX feedback
let audioCtx = null;
function playSound(type = "click") {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    const now = audioCtx.currentTime;
    if (type === "click") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(800, now);
      osc.frequency.exponentialRampToValueAtTime(400, now + 0.05);
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.linearRampToValueAtTime(0.001, now + 0.05);
      osc.start(now);
      osc.stop(now + 0.05);
    } else if (type === "success") {
      // Pleasant victory chord
      [523.25, 659.25, 783.99, 1046.50].forEach((freq, i) => {
        const o = audioCtx.createOscillator();
        const g = audioCtx.createGain();
        o.type = "triangle";
        o.frequency.setValueAtTime(freq, now + i * 0.08);
        g.gain.setValueAtTime(0.09, now + i * 0.08);
        g.gain.exponentialRampToValueAtTime(0.001, now + i * 0.08 + 0.35);
        o.connect(g);
        g.connect(audioCtx.destination);
        o.start(now + i * 0.08);
        o.stop(now + i * 0.08 + 0.4);
      });
    } else if (type === "error") {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.linearRampToValueAtTime(110, now + 0.2);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.linearRampToValueAtTime(0.001, now + 0.2);
      osc.start(now);
      osc.stop(now + 0.2);
    }
  } catch (e) {
    // Audio context not available or blocked
  }
}

// Elements
const deviceSelect = document.getElementById("device-select");
const btnRefreshDevices = document.getElementById("btn-refresh-devices");
const refreshIcon = document.getElementById("refresh-icon");
const devicePulse = document.getElementById("device-pulse");
const deviceDot = document.getElementById("device-dot");
const adbEngineLabel = document.getElementById("adb-engine-label");

const ffCard = document.getElementById("ff-card");
const ffPathLabel = document.getElementById("ff-path-label");
const ffSizeLabel = document.getElementById("ff-size-label");
const btnInstallFF = document.getElementById("btn-install-ff");

const dropZone = document.getElementById("drop-zone");
const btnBrowseFile = document.getElementById("btn-browse-file");
const selectedFilePanel = document.getElementById("selected-file-panel");
const selectedFileName = document.getElementById("selected-file-name");
const selectedFileMeta = document.getElementById("selected-file-meta");
const btnCancelFile = document.getElementById("btn-cancel-file");
const btnInstallSelected = document.getElementById("btn-install-selected");

const optReplace = document.getElementById("opt-replace");
const optDowngrade = document.getElementById("opt-downgrade");
const optPerms = document.getElementById("opt-perms");
const optLaunch = document.getElementById("opt-launch");

const logStatusBadge = document.getElementById("log-status-badge");
const btnClearLog = document.getElementById("btn-clear-log");
const progressMessage = document.getElementById("progress-message");
const progressPercent = document.getElementById("progress-percent");
const progressBar = document.getElementById("progress-bar");
const terminalLogs = document.getElementById("terminal-logs");

let currentSelectedFile = null;
let isInstalling = false;
let presetFFPath = "C:\\Users\\dluzgg\\Desktop\\free fire v7a\\FF V7A\\Free Fire V7A att via zarchiver.apks";

// Logging helper
function appendLog(text, type = "info") {
  const time = new Date().toLocaleTimeString();
  const line = document.createElement("div");

  let tag = `<span class="text-slate-500">[${time}]</span>`;
  let color = "text-slate-300";

  if (type === "success") {
    tag += ` <span class="text-emerald-400 font-bold">[SUCESSO]</span>`;
    color = "text-emerald-300";
  } else if (type === "error") {
    tag += ` <span class="text-red-400 font-bold">[ERRO]</span>`;
    color = "text-red-300";
  } else if (type === "extract") {
    tag += ` <span class="text-amber-400 font-bold">[EXTRAÇÃO]</span>`;
    color = "text-amber-200";
  } else if (type === "adb") {
    tag += ` <span class="text-cyan-400 font-bold">[ADB]</span>`;
    color = "text-cyan-200";
  } else if (type === "obb") {
    tag += ` <span class="text-purple-400 font-bold">[OBB]</span>`;
    color = "text-purple-200";
  } else if (type === "warning") {
    tag += ` <span class="text-yellow-400 font-bold">[AVISO]</span>`;
    color = "text-yellow-200";
  } else {
    tag += ` <span class="text-blue-400 font-bold">[INFO]</span>`;
  }

  line.innerHTML = `${tag} <span class="${color}">${text}</span>`;
  terminalLogs.appendChild(line);
  terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

// Global Callback invoked from Python
window.onInstallProgress = function(percent, message, stage) {
  progressBar.style.width = percent + "%";
  progressPercent.textContent = percent + "%";
  progressMessage.textContent = message;

  if (stage === "success" || stage === "done") {
    logStatusBadge.textContent = "CONCLUÍDO";
    logStatusBadge.className = "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    appendLog(message, "success");
    playSound("success");
    setBusy(false);
  } else if (stage === "error") {
    logStatusBadge.textContent = "FALHOU";
    logStatusBadge.className = "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30";
    appendLog(message, "error");
    playSound("error");
    setBusy(false);
  } else {
    logStatusBadge.textContent = stage.toUpperCase();
    logStatusBadge.className = "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30";
    appendLog(message, stage);
  }
};

function setBusy(busy) {
  isInstalling = busy;
  btnInstallFF.disabled = busy;
  btnInstallSelected.disabled = busy;
  btnRefreshDevices.disabled = busy;
  btnBrowseFile.disabled = busy;

  if (busy) {
    btnInstallFF.classList.add("opacity-50", "cursor-not-allowed");
    btnInstallSelected.classList.add("opacity-50", "cursor-not-allowed");
  } else {
    btnInstallFF.classList.remove("opacity-50", "cursor-not-allowed");
    btnInstallSelected.classList.remove("opacity-50", "cursor-not-allowed");
  }
}

// Device population
function populateDevices(devices) {
  deviceSelect.innerHTML = "";
  if (!devices || devices.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Nenhum emulador detectado";
    deviceSelect.appendChild(opt);

    devicePulse.classList.add("hidden");
    deviceDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500";
    return;
  }

  devicePulse.classList.remove("hidden");
  deviceDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500";

  devices.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = `${d.name} [${d.id}]`;
    deviceSelect.appendChild(opt);
  });
}

// Initial Data Load
async function initApp() {
  appendLog("Iniciando conexão com a API interna do DLuz ZArchiver...", "info");
  if (window.pywebview && window.pywebview.api) {
    try {
      const data = await window.pywebview.api.get_initial_data();
      populateDevices(data.devices);
      if (data.adb_path) {
        adbEngineLabel.textContent = `ADB: ${data.adb_path.split('\\').pop()}`;
      }
      if (data.preset_ff && data.preset_ff.exists) {
        presetFFPath = data.preset_ff.path;
        ffPathLabel.textContent = data.preset_ff.path;
        ffSizeLabel.textContent = data.preset_ff.size;
        ffCard.classList.remove("hidden");
        appendLog(`Free Fire V7A detectado: ${data.preset_ff.size}`, "info");
      } else {
        ffCard.classList.add("hidden");
      }
      appendLog("Pronto para uso! Selecione o arquivo ou clique em Instalar.", "success");
    } catch (e) {
      appendLog("Erro ao carregar dados iniciais: " + e, "error");
    }
  } else {
    setTimeout(initApp, 300);
  }
}

// Event Listeners
btnRefreshDevices.addEventListener("click", async () => {
  playSound("click");
  refreshIcon.classList.add("spinning");
  appendLog("Buscando e reconectando emuladores...", "info");
  try {
    const devices = await window.pywebview.api.refresh_devices();
    populateDevices(devices);
    appendLog(`Busca concluída: ${devices.length} dispositivo(s) encontrado(s).`, "info");
  } catch (e) {
    appendLog("Erro ao atualizar dispositivos: " + e, "error");
  } finally {
    refreshIcon.classList.remove("spinning");
  }
});

// Copy to clipboard helper
window.copyToClipboard = function(text, btn) {
  playSound("click");
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      updateBtnState(btn);
    }).catch(() => fallbackCopy(text, btn));
  } else {
    fallbackCopy(text, btn);
  }
};

function fallbackCopy(text, btn) {
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  updateBtnState(btn);
}

function updateBtnState(btn) {
  const originalText = btn.textContent;
  btn.textContent = "Copiado!";
  btn.classList.add("text-emerald-400", "border-emerald-400/40");
  setTimeout(() => {
    btn.textContent = originalText;
    btn.classList.remove("text-emerald-400", "border-emerald-400/40");
  }, 1500);
}

// Device profile application handler
const btnApplyProfile = document.getElementById("btn-apply-profile");
if (btnApplyProfile) {
  btnApplyProfile.addEventListener("click", async () => {
    playSound("click");
    const serial = deviceSelect.value || null;
    appendLog("Aplicando perfil Infinix X6891 para destravar 120 e 144 FPS...", "info");
    try {
      const res = await window.pywebview.api.apply_device_profile(serial);
      if (res && res.success) {
        playSound("success");
        appendLog(`Perfil Infinix X6891 aplicado! (Configurações: ${res.conf_updated}, ADB: ${res.adb_updated ? 'OK' : 'Pendente'})`, "success");
        appendLog("⚠️ AVISO OBRIGATÓRIO: Reinicie seu emulador antes de instalar o Free Fire!", "warning");
        alert("✅ Perfil Infinix X6891 aplicado com sucesso!\n\n⚠️ ATENÇÃO OBRIGATÓRIA: REINICIE O SEU EMULADOR antes de instalar o Free Fire para que a taxa de 120 e 144 FPS seja reconhecida!");
      } else {
        appendLog("Falha ao aplicar perfil: " + (res ? res.message : "Erro desconhecido"), "error");
      }
    } catch (e) {
      appendLog("Erro ao aplicar perfil: " + e, "error");
    }
  });
}

btnInstallFF.addEventListener("click", () => {
  if (isInstalling) return;
  playSound("click");
  startInstallation(presetFFPath);
});

btnBrowseFile.addEventListener("click", async (e) => {
  e.stopPropagation();
  playSound("click");
  try {
    const file = await window.pywebview.api.browse_file();
    if (file) {
      handleFileSelected(file);
    }
  } catch (e) {
    appendLog("Erro ao selecionar arquivo: " + e, "error");
  }
});

dropZone.addEventListener("click", () => {
  btnBrowseFile.click();
});

btnCancelFile.addEventListener("click", () => {
  playSound("click");
  currentSelectedFile = null;
  selectedFilePanel.classList.add("hidden");
  dropZone.classList.remove("hidden");
});

btnInstallSelected.addEventListener("click", () => {
  if (isInstalling || !currentSelectedFile) return;
  playSound("click");
  startInstallation(currentSelectedFile.path);
});

btnClearLog.addEventListener("click", () => {
  playSound("click");
  terminalLogs.innerHTML = `<div class="text-slate-500">[LOG LIMPO] Terminal reiniciado.</div>`;
});

function handleFileSelected(fileInfo) {
  currentSelectedFile = fileInfo;
  selectedFileName.textContent = fileInfo.name;
  selectedFileMeta.textContent = `Tamanho: ${fileInfo.size} • Formato: ${fileInfo.ext.toUpperCase()}`;
  selectedFilePanel.classList.remove("hidden");
  dropZone.classList.add("hidden");
  appendLog(`Arquivo selecionado: ${fileInfo.name} (${fileInfo.size})`, "info");
}

function startInstallation(filePath) {
  const serial = deviceSelect.value;
  if (!serial) {
    alert("Nenhum emulador selecionado ou online! Verifique se seu BlueStacks/emulador está aberto.");
    appendLog("Instalação cancelada: nenhum dispositivo selecionado.", "error");
    playSound("error");
    return;
  }

  setBusy(true);
  progressBar.style.width = "0%";
  progressPercent.textContent = "0%";
  progressMessage.textContent = "Iniciando processo...";

  const options = {
    replace: optReplace.checked,
    downgrade: optDowngrade.checked,
    grant_perms: optPerms.checked,
    launch_after: optLaunch.checked
  };

  appendLog(`Disparando instalação para ${serial}...`, "info");
  window.pywebview.api.install(serial, filePath, options);
}

// Drag and drop prevent defaults
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
  }, false);
});

dropZone.addEventListener('dragover', () => {
  dropZone.classList.add('border-cyan-400', 'bg-[#1a2942]/90');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('border-cyan-400', 'bg-[#1a2942]/90');
});

dropZone.addEventListener('drop', (e) => {
  dropZone.classList.remove('border-cyan-400', 'bg-[#1a2942]/90');
  // Em navegadores / pywebview arquivos locais podem ser disparados pelo browse_file
  btnBrowseFile.click();
});

// Wait for pywebview initialization
window.addEventListener("pywebviewready", () => {
  initApp();
});

// Fallback if pywebviewready already fired
setTimeout(() => {
  if (window.pywebview && window.pywebview.api) {
    initApp();
  }
}, 500);
