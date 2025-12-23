// static/js/retell_call_window.js

function nowTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function norm(s) {
  return String(s || "").trim();
}

function normalizeRole(raw) {
  const s = String(raw || "").toLowerCase();
  if (!s) return "MIX";

  if (s === "agent" || s.includes("agent") || s.includes("assistant") || s.includes("ai") || s.includes("bot")) return "AI";
  if (s === "user" || s.includes("user") || s.includes("customer") || s.includes("human") || s.includes("client")) return "USER";

  return "MIX";
}

/**
 * Retell SDK a veces manda la info de rol en campos distintos.
 * Aquí buscamos “profundo” sin asumir una forma única.
 */
function roleFromRawUpdate(raw) {
  if (!raw || typeof raw !== "object") return "MIX";

  const candidates = [
    raw.role,
    raw.speaker,
    raw.from,
    raw.participant,
    raw.type,
    raw.source,

    raw?.data?.role,
    raw?.data?.speaker,
    raw?.data?.from,
    raw?.data?.participant,

    raw?.speaker?.role,
    raw?.speaker?.type,
    raw?.participant?.role,
    raw?.participant?.type,
  ];

  for (const c of candidates) {
    const r = normalizeRole(c);
    if (r !== "MIX") return r;
  }
  return "MIX";
}

/**
 * Parser robusto para strings con prefijos:
 *   Agent: ...
 *   User: ...
 *   Usuario: ...
 *   IA: ...
 * Devuelve lista [{role:"AI"|"USER"|"MIX", text:"..."}]
 */
function parseLabeledTranscript(text) {
  const t = String(text || "").replace(/\r\n/g, "\n").trim();
  if (!t) return [];

  // Si viene en varias líneas, primero intentamos por líneas.
  const lines = t.split("\n").map((x) => x.trim()).filter(Boolean);
  const out = [];

  const rxLine = /^([^:]{1,30}):\s*(.*)$/;

  for (const line of lines) {
    const m = line.match(rxLine);
    if (m) {
      const label = String(m[1] || "").toLowerCase();
      const content = String(m[2] || "").trim();
      if (!content) continue;

      const role =
        label.includes("agent") || label.includes("assistant") || label.includes("ia") || label.includes("ai") || label.includes("bot")
          ? "AI"
          : label.includes("user") || label.includes("usuario") || label.includes("customer") || label.includes("humano") || label.includes("client")
          ? "USER"
          : "MIX";

      out.push({ role, text: content });
    } else {
      out.push({ role: "MIX", text: line });
    }
  }

  // Caso especial: todo viene en UNA línea con “Agent: … User: … Agent: …”
  // (sin saltos). Intentamos extraer segmentos por prefijos.
  if (out.length === 1 && out[0].role === "MIX") {
    const one = out[0].text;
    const rx = /(agent|assistant|ia|ai|bot|user|usuario|customer|humano|client)\s*:\s*/gi;

    const parts = [];
    let match;
    let lastIdx = 0;
    let lastLabel = null;

    while ((match = rx.exec(one)) !== null) {
      const idx = match.index;
      if (lastLabel !== null) {
        const seg = one.slice(lastIdx, idx).trim();
        if (seg) parts.push({ label: lastLabel, text: seg });
      }
      lastLabel = match[1];
      lastIdx = rx.lastIndex;
    }
    if (lastLabel !== null) {
      const seg = one.slice(lastIdx).trim();
      if (seg) parts.push({ label: lastLabel, text: seg });
    }

    if (parts.length) {
      return parts.map((p) => ({
        role: normalizeRole(p.label),
        text: p.text,
      }));
    }
  }

  return out;
}

/**
 * Merge incremental: si llega una versión más larga del mismo rol, reemplaza.
 */
function mergeTurns(turns) {
  const merged = [];
  for (const t of turns) {
    const role = t?.role || "MIX";
    const text = norm(t?.text);
    if (!text) continue;

    const prev = merged.length ? merged[merged.length - 1] : null;
    if (!prev || prev.role !== role) {
      merged.push({ role, text });
      continue;
    }

    const a = prev.text;
    const b = text;

    // incremental típico (b extiende a)
    if (b.startsWith(a)) prev.text = b;
    else if (a.startsWith(b)) prev.text = a;
    else prev.text = (a + " " + b).trim();
  }
  return merged;
}

function buildFinalTranscript(mergedTurns) {
  if (!mergedTurns || !mergedTurns.length) return "Sin transcripción final disponible.";
  return mergedTurns
    .map((t) => {
      const label = t.role === "AI" ? "IA" : t.role === "USER" ? "Usuario" : "Transcripción";
      return `[${label}] ${t.text}`;
    })
    .join("\n\n");
}

(async function main() {
  const statusEl = document.getElementById("retellStatus");
  const liveEl = document.getElementById("retellLive");
  const finalWrap = document.getElementById("retellFinalWrap");
  const finalText = document.getElementById("retellFinalText");

  const btnClear = document.getElementById("retellClearBtn");
  const btnCopyFinal = document.getElementById("retellCopyFinalBtn");
  const btnClose = document.getElementById("retellCloseBtn");

  // NUEVO: botón mic del template
  const micBtn = document.getElementById("retellMicBtn");

const setStatus = (t) => { if (statusEl) statusEl.textContent = t || ""; };

  // ===== LIVE UI: 2 cajas =====
  let liveUserBox = null;
  let liveAiBox = null;

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

  function setLiveBox(which, text) {
    ensureLiveBoxes();
    const box = which === "USER" ? liveUserBox : liveAiBox;
    if (!box) return;

    box.querySelector(".time").textContent = nowTime();
    box.querySelector(".body").textContent = text || "";
  }

  function resetAll() {
    if (liveEl) liveEl.innerHTML = "";
    liveUserBox = null;
    liveAiBox = null;

    if (finalWrap) finalWrap.classList.add("hidden");
    if (finalText) finalText.textContent = "";

    // NUEVO: reset animación mic
    stopUserMicViz();
    stopUserMicPulse();
    micBtn?.classList.remove("is-speaking", "is-call-active");
  }

  btnClear?.addEventListener("click", () => resetAll());
  btnClose?.addEventListener("click", () => window.close());

  btnCopyFinal?.addEventListener("click", async () => {
    const txt = (finalText?.textContent || "").trim();
    if (!txt) {
      setStatus("No hay transcripción final para copiar");
      setTimeout(() => setStatus(""), 1600);
      return;
    }
    try {
      await navigator.clipboard.writeText(txt);
      setStatus("Transcripción final copiada");
      setTimeout(() => setStatus(""), 1600);
    } catch (_) {
      setStatus("No se pudo copiar (permiso navegador)");
      setTimeout(() => setStatus(""), 2200);
    }
  });

  const createUrl = window.__RETELL_CREATE_URL;
  const getCallUrlTemplate = window.__RETELL_GETCALL_TEMPLATE;
  const bundleUrl = window.__RETELL_BUNDLE_URL;

  if (!createUrl || !getCallUrlTemplate || !bundleUrl) {
    setStatus("Retell: faltan URLs del backend/bundle");
    return;
  }

  let wireRetellButtons = null;
  try {
    const mod = await import(bundleUrl);
    wireRetellButtons = mod?.wireRetellButtons;
  } catch (e) {
    console.error(e);
    setStatus("Retell: no se pudo cargar el bundle");
    return;
  }

  if (typeof wireRetellButtons !== "function") {
    setStatus("Retell: wireRetellButtons no disponible");
    return;
  }

  // ===== Estado live (anti incremental spam) =====
  let lastAI = "";
  let lastUSER = "";

  function applyLive(role, text) {
    const r = role === "USER" ? "USER" : role === "AI" ? "AI" : "MIX";
    const t = norm(text);
    if (!t) return;

    if (r === "AI") {
      if (t === lastAI) return;
      lastAI = t;
      setLiveBox("AI", t);
      return;
    }

    if (r === "USER") {
      if (t === lastUSER) return;
      lastUSER = t;
      setLiveBox("USER", t);
      return;
    }

    // MIX: intentamos parsear si viene etiquetado dentro del texto
    const labeled = parseLabeledTranscript(t);
    if (labeled.length) {
      // tomamos el último texto por rol
      let lastAiSeg = "";
      let lastUserSeg = "";

      for (const seg of labeled) {
        if (seg.role === "AI") lastAiSeg = seg.text;
        if (seg.role === "USER") lastUserSeg = seg.text;
      }

      if (lastUserSeg) applyLive("USER", lastUserSeg);
      if (lastAiSeg) applyLive("AI", lastAiSeg);

      // si no había roles claros, cae a IA
      if (!lastUserSeg && !lastAiSeg) {
        if (t !== lastAI) {
          lastAI = t;
          setLiveBox("AI", t);
        }
      }
      return;
    }

    // fallback
    if (t !== lastAI) {
      lastAI = t;
      setLiveBox("AI", t);
    }
  }

  function showFinalFromCall(call) {
    if (!finalWrap || !finalText) return;

    const tObj = call?.transcript_object;

    // 1) transcript_object SOLO si realmente tiene USER
    if (Array.isArray(tObj) && tObj.length) {
      const turns = [];
      let hasUser = false;

      for (const it of tObj) {
        const role = normalizeRole(it?.role);
        const text = norm(it?.content);
        if (!text) continue;

        if (role === "USER") hasUser = true;
        turns.push({ role, text });
      }

      if (hasUser) {
        const merged = mergeTurns(turns);
        finalText.textContent = buildFinalTranscript(merged);
        finalWrap.classList.remove("hidden");
        return;
      }
      // si NO hay user en transcript_object, seguimos al transcript string
    }

    // 2) fallback: transcript string (Agent:/User:)
    const parsed = parseLabeledTranscript(call?.transcript || "");
    const merged = mergeTurns(parsed);
    finalText.textContent = buildFinalTranscript(merged);
    finalWrap.classList.remove("hidden");
  }

  // ============================================================
  // NUEVO: Animación mic cuando habla el usuario (Web Audio API)
  // ============================================================
  let _micPulseTimer = null;

  function startUserMicPulse(ms = 650) {
    if (!micBtn) return;
    micBtn.classList.add("is-speaking");
    if (_micPulseTimer) window.clearTimeout(_micPulseTimer);
    _micPulseTimer = window.setTimeout(() => {
      micBtn.classList.remove("is-speaking");
      _micPulseTimer = null;
    }, Math.max(250, ms));
  }

  function stopUserMicPulse() {
    if (_micPulseTimer) {
      window.clearTimeout(_micPulseTimer);
      _micPulseTimer = null;
    }
    micBtn?.classList.remove("is-speaking");
  }

  // Visualizador “real” por nivel de micrófono
  const micViz = {
    active: false,
    stream: null,
    ctx: null,
    source: null,
    analyser: null,
    raf: 0,
    lastLoudAt: 0,
    denied: false,
  };

  function computeRmsFromTimeDomain(u8) {
    // u8: 0..255, centro ~128
    let sum = 0;
    for (let i = 0; i < u8.length; i++) {
      const v = (u8[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / u8.length);
  }

  async function startUserMicViz() {
    if (!micBtn) return;
    if (micViz.active || micViz.denied) return;

    // Marcamos que hay llamada activa (útil si quieres mostrar/ocultar/estilizar)
    micBtn.classList.add("is-call-active");

    try {
      // Pedimos un stream SOLO para visualización (no altera el flujo del SDK).
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();

      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.75;

      source.connect(analyser);

      micViz.active = true;
      micViz.stream = stream;
      micViz.ctx = ctx;
      micViz.source = source;
      micViz.analyser = analyser;
      micViz.lastLoudAt = 0;

      const buf = new Uint8Array(analyser.fftSize);

      const THRESH = 0.02;          // sensibilidad base (ajustable)
      const HOLD_MS = 220;          // mantiene “hablando” un poco para evitar parpadeo
      const MIN_ACTIVE_MS = 450;    // evita pulsos demasiado cortos

      let speakOnAt = 0;

      const tick = () => {
        if (!micViz.active || !micViz.analyser) return;

        micViz.analyser.getByteTimeDomainData(buf);
        const rms = computeRmsFromTimeDomain(buf);

        const now = Date.now();
        const loud = rms >= THRESH;

        if (loud) {
          micViz.lastLoudAt = now;
          if (!micBtn.classList.contains("is-speaking")) {
            micBtn.classList.add("is-speaking");
            speakOnAt = now;
          }
        } else {
          const sinceLoud = now - micViz.lastLoudAt;
          const sinceOn = speakOnAt ? (now - speakOnAt) : 999999;
          if (micBtn.classList.contains("is-speaking") && sinceLoud > HOLD_MS && sinceOn > MIN_ACTIVE_MS) {
            micBtn.classList.remove("is-speaking");
            speakOnAt = 0;
          }
        }

        micViz.raf = window.requestAnimationFrame(tick);
      };

      micViz.raf = window.requestAnimationFrame(tick);
    } catch (e) {
      // Si el navegador niega permiso, quedamos con el fallback (pulsos por update USER)
      micViz.denied = true;
      console.warn("[retell] mic viz denied/unavailable:", e);
    }
  }

  function stopUserMicViz() {
    if (!micViz.active) return;

    micViz.active = false;
    if (micViz.raf) {
      window.cancelAnimationFrame(micViz.raf);
      micViz.raf = 0;
    }

    try {
      micViz.source && micViz.source.disconnect();
    } catch (_) {}

    try {
      micViz.stream?.getTracks?.().forEach((t) => t.stop());
    } catch (_) {}

    try {
      micViz.ctx?.close?.();
    } catch (_) {}

    micViz.stream = null;
    micViz.ctx = null;
    micViz.source = null;
    micViz.analyser = null;

    micBtn?.classList.remove("is-speaking");
    micBtn?.classList.remove("is-call-active");
  }

  // ===== Wire principal =====
  wireRetellButtons({
    createUrl,
    getCallUrlTemplate,

    toggleBtnId: "retellToggleBtn",
    statusId: "retellStatus",

    // Popup pinta por su cuenta
    panelId: null,
    panelBodyId: null,
    panelCloseBtnId: null,
    panelClearBtnId: null,

    pollIntervalMs: 700,

    onEvent: (ev) => {
      // PostMessage al opener (si existe)
      try {
        if (window.opener && !window.opener.closed) {
          window.opener.postMessage({ source: "retell", ...ev }, window.location.origin);
        }
      } catch (_) {}

      if (ev.type === "call_started") {
        setStatus("Llamada activa");
        // NUEVO: inicia visualización de mic
        startUserMicViz();
      }
      if (ev.type === "call_ended") {
        setStatus("Llamada finalizada");
        // NUEVO: detiene visualización de mic
        stopUserMicViz();
        stopUserMicPulse();
      }
      if (ev.type === "call_error") {
        setStatus("Error en la llamada");
        stopUserMicViz();
        stopUserMicPulse();
      }
    },

    // EN VIVO: SDK update
    onUpdate: ({ role, text, raw }) => {
      const r = roleFromRawUpdate(raw);
      const finalRole = (r !== "MIX" ? r : (role || "MIX"));

      applyLive(finalRole, text);

      // NUEVO: fallback de animación si no pudimos usar WebAudio (o si quieres refuerzo visual)
      // Solo cuando el rol detectado sea USER.
      if (finalRole === "USER" && (!micViz.active)) {
        startUserMicPulse(700);
      }
    },

    // FINAL: backend get-call
    onPollData: (json) => {
      const call = json?.call || json;
      if (!call) return;

      const st = String(call?.call_status || "").toLowerCase();
      if (st === "ended") {
        showFinalFromCall(call);
      }
    },
  });

  setStatus("");
})();
