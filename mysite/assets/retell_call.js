// mysite/assets/retell_call.js
import { RetellWebClient } from "retell-client-js-sdk";

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function safeJsonParse(text) {
  try { return JSON.parse(text); } catch { return null; }
}

function extractUpdateText(update) {
  if (!update) return "";

  if (typeof update === "string") return update.trim();
  if (typeof update.transcript === "string") return update.transcript.trim();
  if (typeof update.text === "string") return update.text.trim();
  if (typeof update.content === "string") return update.content.trim();

  const t = update.transcript;
  if (Array.isArray(t)) {
    const parts = t
      .map((x) => {
        if (!x) return "";
        if (typeof x === "string") return x;
        return (x.text || x.content || x.transcript || x.message || x.utterance || "").toString();
      })
      .filter(Boolean);
    return parts.join(" ").trim();
  }

  if (t && typeof t === "object") {
    return (t.text || t.content || t.transcript || t.message || t.utterance || "").toString().trim();
  }

  return "";
}

function extractUpdateRole(update) {
  // Intentamos detectar “user” vs “agent/assistant”
  const raw =
    update?.role ||
    update?.speaker ||
    update?.from ||
    update?.participant ||
    update?.type ||
    "";

  const s = String(raw).toLowerCase();
  if (s.includes("user") || s.includes("customer") || s.includes("human") || s.includes("client")) return "USER";
  if (s.includes("agent") || s.includes("assistant") || s.includes("ai") || s.includes("bot")) return "AI";

  // fallback: la mayoría de updates que viste eran del agente
  return "AI";
}

async function fetchCallSummary(getCallUrlTemplate, callId) {
  if (!getCallUrlTemplate || !callId) return null;
  const url = getCallUrlTemplate.replace("{call_id}", encodeURIComponent(callId));

  const resp = await fetch(url, { credentials: "same-origin" });
  const text = await resp.text();
  const data = safeJsonParse(text);

  if (!resp.ok || !data?.ok) return null;
  return data.call || null;
}

async function createWebCallOnServer(createUrl) {
  const csrftoken = getCookie("csrftoken");

  const resp = await fetch(createUrl, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrftoken,
    },
    body: JSON.stringify({}),
  });

  const dataText = await resp.text();
  const data = safeJsonParse(dataText) || {};

  if (!resp.ok || !data?.ok) {
    if (data?.error === "NO_PHONE") throw new Error("NO_PHONE");
    throw new Error(data?.detail || data?.error || `Error creando llamada (${resp.status})`);
  }

  return data; // { ok, access_token, call_id }
}

/**
 * Popup: transcripción en vivo (SDK update) + final (GET call.transcript)
 * Requisitos HTML IDs:
 * - toggleBtnId, statusId, micBtnId (opcional), liveId, clearBtnId, closeBtnId
 * - finalWrapId, finalTextId, copyFinalBtnId (opcionales)
 */
export function wireRetellPopup({
  createUrl,
  getCallUrlTemplate,

  toggleBtnId,
  statusId,

  micBtnId,
  liveId,

  clearBtnId,
  closeBtnId,

  finalWrapId,
  finalTextId,
  copyFinalBtnId,
}) {
  const toggleBtn = document.getElementById(toggleBtnId);
  const statusEl = document.getElementById(statusId);

  const micBtn = micBtnId ? document.getElementById(micBtnId) : null;
  const liveEl = document.getElementById(liveId);

  const clearBtn = clearBtnId ? document.getElementById(clearBtnId) : null;
  const closeBtn = closeBtnId ? document.getElementById(closeBtnId) : null;

  const finalWrap = finalWrapId ? document.getElementById(finalWrapId) : null;
  const finalText = finalTextId ? document.getElementById(finalTextId) : null;
  const copyFinalBtn = copyFinalBtnId ? document.getElementById(copyFinalBtnId) : null;

  const setStatus = (t) => {
    const txt = (t || "").toString();
    if (statusEl) statusEl.textContent = txt;
  };

  // ---------- UI live: 2 cajas (Usuario / IA) y SOLO se actualiza texto ----------
  let liveUserBox = null;
  let liveAiBox = null;
  let lastLive = { USER: "", AI: "" };

  function ensureLiveBoxes() {
    if (!liveEl) return;

    if (!liveUserBox) {
      liveUserBox = document.createElement("div");
      liveUserBox.className = "feed-line";
      liveUserBox.innerHTML = `
        <div class="meta">
          <span class="badge user">Usuario</span><span class="time"></span>
        </div>
        <div class="body"></div>
      `;
      liveEl.appendChild(liveUserBox);
    }

    if (!liveAiBox) {
      liveAiBox = document.createElement("div");
      liveAiBox.className = "feed-line";
      liveAiBox.innerHTML = `
        <div class="meta">
          <span class="badge ai">IA</span><span class="time"></span>
        </div>
        <div class="body"></div>
      `;
      liveEl.appendChild(liveAiBox);
    }
  }

  function nowTime() {
    const d = new Date();
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function setLive(which, text) {
    if (!liveEl) return;
    const t = String(text || "").trim();
    if (!t) return;

    // anti-spam incremental: solo reemplaza si cambió
    if (t === lastLive[which]) return;
    lastLive[which] = t;

    ensureLiveBoxes();
    const box = which === "USER" ? liveUserBox : liveAiBox;
    if (!box) return;

    box.querySelector(".time").textContent = nowTime();
    box.querySelector(".body").textContent = t;
  }

  function clearUI() {
    lastLive.USER = "";
    lastLive.AI = "";
    if (liveEl) liveEl.innerHTML = "";
    liveUserBox = null;
    liveAiBox = null;

    if (finalWrap) finalWrap.classList.add("hidden");
    if (finalText) finalText.textContent = "";
  }

  // ---------- Mic indicador (solo animación / nivel local) ----------
  // Nota: esto NO mutea la llamada; solo muestra actividad del mic del navegador.
  let micOn = false;
  let micStream = null;
  let micRAF = null;
  let audioCtx = null;
  let analyser = null;
  let dataArr = null;

  async function micStart() {
    if (!micBtn || micOn) return;

    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    dataArr = new Uint8Array(analyser.frequencyBinCount);
    src.connect(analyser);

    micOn = true;
    micBtn.classList.add("is-on");

    const tick = () => {
      if (!micOn || !analyser) return;

      analyser.getByteFrequencyData(dataArr);
      let sum = 0;
      for (let i = 0; i < dataArr.length; i++) sum += dataArr[i];
      const avg = sum / dataArr.length; // 0..255

      // “halo” suave
      const glow = Math.min(1, avg / 90);
      const scale = 1 + Math.min(0.25, avg / 300);

      micBtn.style.setProperty("--mic-glow", String(glow));
      micBtn.style.setProperty("--mic-halo-scale", String(scale));
      micBtn.style.setProperty("--mic-scale", String(1 + glow * 0.12));

      // opcional: mandar al opener para icono del home
      try {
        if (window.opener && !window.opener.closed) {
          window.opener.postMessage(
            { source: "retell", type: "mic_level", level: glow },
            window.location.origin
          );
        }
      } catch (_) {}

      micRAF = requestAnimationFrame(tick);
    };

    micRAF = requestAnimationFrame(tick);
  }

  function micStop() {
    micOn = false;
    if (micRAF) cancelAnimationFrame(micRAF);
    micRAF = null;

    try { analyser?.disconnect(); } catch (_) {}
    analyser = null;
    dataArr = null;

    try { audioCtx?.close(); } catch (_) {}
    audioCtx = null;

    try { micStream?.getTracks()?.forEach((t) => t.stop()); } catch (_) {}
    micStream = null;

    if (micBtn) {
      micBtn.classList.remove("is-on");
      micBtn.style.removeProperty("--mic-glow");
      micBtn.style.removeProperty("--mic-halo-scale");
      micBtn.style.removeProperty("--mic-scale");
    }
  }

  micBtn?.addEventListener("click", async () => {
    try {
      if (!micOn) await micStart();
      else micStop();
    } catch (e) {
      setStatus("No se pudo activar mic (permiso)");
      setTimeout(() => setStatus(""), 1800);
    }
  });

  // ---------- Retell SDK ----------
  const retellWebClient = new RetellWebClient();
  let isActive = false;
  let lastCallId = null;

  const paintToggle = () => {
    if (!toggleBtn) return;
    if (isActive) {
      toggleBtn.textContent = "⛔ Colgar";
      toggleBtn.title = "Colgar (Retell)";
    } else {
      toggleBtn.textContent = "📞 Llamar";
      toggleBtn.title = "Llamar (Retell)";
    }
  };

  async function startCall() {
    if (isActive) return;
    if (!createUrl) throw new Error("createUrl faltante");

    setStatus("Retell: creando llamada…");
    clearUI();

    const { access_token, call_id } = await createWebCallOnServer(createUrl);
    lastCallId = call_id || null;

    setStatus("Retell: conectando…");
    await retellWebClient.startCall({ accessToken: access_token });
  }

  function stopCall() {
    try { retellWebClient.stopCall(); } catch (_) {}
  }

  // SDK events
  retellWebClient.on("call_started", () => {
    isActive = true;
    paintToggle();
    setStatus("Llamada activa");

    // notifica al portal
    try {
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage({ source: "retell", type: "call_started" }, window.location.origin);
      }
    } catch (_) {}
  });

  retellWebClient.on("update", (update) => {
    // En vivo: usar SDK, NO polling
    const text = extractUpdateText(update);
    if (!text) return;

    const role = extractUpdateRole(update); // "AI" | "USER"
    if (role === "USER") setLive("USER", text);
    else setLive("AI", text);
  });

  retellWebClient.on("call_ended", async () => {
    isActive = false;
    paintToggle();
    setStatus("Llamada finalizada");

    // final: usar get-call (call.transcript)
    try {
      const call = await fetchCallSummary(getCallUrlTemplate, lastCallId);
      const transcript = String(call?.transcript || "").trim();

      if (finalWrap && finalText) {
        finalText.textContent = transcript || "Sin transcripción final disponible.";
        finalWrap.classList.remove("hidden");
      }
    } catch (_) {
      if (finalWrap && finalText) {
        finalText.textContent = "Sin transcripción final disponible.";
        finalWrap.classList.remove("hidden");
      }
    }

    // notifica al portal
    try {
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage({ source: "retell", type: "call_ended" }, window.location.origin);
      }
    } catch (_) {}

    // mic UI off (si estaba activo)
    try { micStop(); } catch (_) {}
  });

  retellWebClient.on("error", (error) => {
    isActive = false;
    paintToggle();
    setStatus("Error en la llamada");

    try {
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage(
          { source: "retell", type: "call_error", message: error?.message || "" },
          window.location.origin
        );
      }
    } catch (_) {}

    try { micStop(); } catch (_) {}
  });

  // ---------- Botones ----------
  toggleBtn?.addEventListener("click", async (e) => {
    e.preventDefault();

    if (isActive) {
      setStatus("Colgando…");
      stopCall();
      return;
    }

    try {
      await startCall();
    } catch (err) {
      if (String(err?.message || err) === "NO_PHONE") {
        setStatus("No tienes teléfono registrado");
      } else {
        setStatus(`No se pudo iniciar: ${err?.message || err}`);
      }
      isActive = false;
      paintToggle();
    }
  });

  clearBtn?.addEventListener("click", () => clearUI());

  closeBtn?.addEventListener("click", () => window.close());

  copyFinalBtn?.addEventListener("click", async () => {
    const txt = (finalText?.textContent || "").trim();
    if (!txt) {
      setStatus("No hay transcripción final");
      setTimeout(() => setStatus(""), 1600);
      return;
    }
    try {
      await navigator.clipboard.writeText(txt);
      setStatus("Transcripción copiada");
      setTimeout(() => setStatus(""), 1600);
    } catch (_) {
      setStatus("No se pudo copiar (permiso)");
      setTimeout(() => setStatus(""), 2200);
    }
  });

  // init
  paintToggle();
  setStatus("");
}
