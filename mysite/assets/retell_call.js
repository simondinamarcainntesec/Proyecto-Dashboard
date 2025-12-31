// mysite/assets/retell_call.js
import { RetellWebClient } from "retell-client-js-sdk";

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function extractTranscriptText(update) {
  if (!update) return "";

  if (typeof update === "string") return update;
  if (typeof update.transcript === "string") return update.transcript;

  const t = update.transcript;

  if (Array.isArray(t)) {
    if (t.every((x) => typeof x === "string")) return t.join(" ");

    const parts = t
      .map((x) => {
        if (!x) return "";
        if (typeof x === "string") return x;
        return (
          x.text ||
          x.content ||
          x.transcript ||
          x.message ||
          x.utterance ||
          ""
        );
      })
      .filter(Boolean);

    return parts.join(" ").trim();
  }

  if (t && typeof t === "object") {
    return (
      t.text ||
      t.content ||
      t.transcript ||
      t.message ||
      t.utterance ||
      ""
    )
      .toString()
      .trim();
  }

  return "";
}

function normalizeRole(raw) {
  const s = String(raw || "").toLowerCase();
  if (!s) return "AI";
  if (s.includes("agent") || s.includes("assistant") || s.includes("ai") || s.includes("bot")) return "AI";
  if (s.includes("user") || s.includes("customer") || s.includes("human") || s.includes("client")) return "USER";
  return "MIX";
}

function extractRole(update) {
  if (!update || typeof update !== "object") return "AI";
  return normalizeRole(
    update.role ||
      update.speaker ||
      update.from ||
      update.participant ||
      update.type ||
      update.source
  );
}

export function wireRetellButtons({
  createUrl,
  getCallUrlTemplate,

  toggleBtnId,
  statusId,

  panelId,
  panelBodyId,
  panelCloseBtnId,
  panelClearBtnId,

  // NUEVO: hooks (opcionales)
  onUpdate,     // ({ role, text, raw }) => void   (SDK "update")
  onPollData,   // (json) => void                  (backend get-call)
  onEvent,      // ({type,...}) => void            (call_started/call_ended/error)

  pollIntervalMs = 700,
}) {
  const toggleBtn = toggleBtnId ? document.getElementById(toggleBtnId) : null;
  const statusEl = statusId ? document.getElementById(statusId) : null;

  const panel = panelId ? document.getElementById(panelId) : null;
  const panelBody = panelBodyId ? document.getElementById(panelBodyId) : null;
  const panelCloseBtn = panelCloseBtnId ? document.getElementById(panelCloseBtnId) : null;
  const panelClearBtn = panelClearBtnId ? document.getElementById(panelClearBtnId) : null;

  const setStatus = (t) => {
    const txt = (t || "").toString();
    if (statusEl) {
      statusEl.textContent = txt;
      statusEl.title = txt;
    }
  };

  const openPanel = () => {
    if (!panel) return;
    panel.classList.remove("hidden");
    panel.setAttribute("aria-hidden", "false");
  };

  const closePanel = () => {
    if (!panel) return;
    panel.classList.add("hidden");
    panel.setAttribute("aria-hidden", "true");
  };

  const clearPanel = () => {
    if (panelBody) panelBody.innerHTML = "";
  };

  if (panelCloseBtn) panelCloseBtn.addEventListener("click", closePanel);
  if (panelClearBtn) panelClearBtn.addEventListener("click", clearPanel);

  // ---- UI live en panel (si existe) ----
  let liveEl = null;
  let lastLiveText = "";

  function ensureLiveEl() {
    if (!panelBody) return null;
    if (liveEl && panelBody.contains(liveEl)) return liveEl;

    panelBody.innerHTML = "";
    liveEl = document.createElement("div");
    liveEl.className = "retell-live";
    liveEl.innerHTML = `<span class="who">IA</span><div class="txt"></div>`;
    panelBody.appendChild(liveEl);
    return liveEl;
  }

  function setLiveText(text) {
    if (!panelBody) return;
    const t = (text || "").trim();
    if (!t) return;
    if (t === lastLiveText) return;

    const box = ensureLiveEl();
    if (!box) return;

    const txtEl = box.querySelector(".txt");
    if (txtEl) txtEl.textContent = t;

    lastLiveText = t;
    panelBody.scrollTop = panelBody.scrollHeight;
  }

  function showFinalTranscript(finalText) {
    if (!panelBody) return;
    const t = (finalText || "").trim();

    panelBody.innerHTML = "";
    liveEl = document.createElement("div");
    liveEl.className = "retell-live";
    liveEl.innerHTML = `<span class="who">IA (final)</span><div class="txt"></div>`;
    panelBody.appendChild(liveEl);

    const txtEl = liveEl.querySelector(".txt");
    if (txtEl) txtEl.textContent = t || "Sin transcripción final disponible.";

    lastLiveText = t || "";
    panelBody.scrollTop = 0;
  }

  const retellWebClient = new RetellWebClient();

  let isActive = false;
  let lastCallId = null;

  let pollTimer = null;

  const emitEvent = (payload) => {
    try { onEvent && onEvent(payload); } catch (_) {}
  };

  const paintToggle = () => {
    if (!toggleBtn) return;
    if (isActive) {
      toggleBtn.textContent = "⛔ Colgar";
      toggleBtn.title = "Colgar (Inntesec Agent)";
    } else {
      toggleBtn.textContent = "📞 Llamar";
      toggleBtn.title = "Llamar (Inntesec Agent)";
    }
  };

  async function createWebCallOnServer() {
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

    const data = await resp.json().catch(() => ({}));

    if (!resp.ok || !data?.ok) {
      if (data?.error === "NO_PHONE") throw new Error("NO_PHONE");
      throw new Error(
        data?.detail || data?.error || `Error creando llamada (${resp.status})`
      );
    }

    return data; // { ok, access_token, call_id }
  }

  async function fetchCallJson() {
    if (!getCallUrlTemplate || !lastCallId) return null;
    const url = getCallUrlTemplate.replace(
      "{call_id}",
      encodeURIComponent(lastCallId)
    );
    const resp = await fetch(url, { credentials: "same-origin" });
    const data = await resp.json().catch(() => ({}));
    return data || null;
  }

  function startPolling() {
    stopPolling();
    if (!getCallUrlTemplate) return;

    pollTimer = window.setInterval(async () => {
      if (!isActive || !lastCallId) return;
      try {
        const json = await fetchCallJson();
        if (!json) return;
        try { onPollData && onPollData(json); } catch (_) {}

        const st = String(json?.call?.call_status || json?.call_status || "").toLowerCase();
        if (st === "ended") {
          stopPolling();
        }
      } catch (_) {
        // silencioso
      }
    }, Math.max(250, Number(pollIntervalMs) || 700));
  }

  function stopPolling() {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function startCall() {
    if (isActive) return;

    setStatus("Inntesec Agent: creando llamada…");

    const { access_token, call_id } = await createWebCallOnServer();
    lastCallId = call_id || null;

    lastLiveText = "";
    clearPanel();

    setStatus("Inntesec Agent: conectando…");
    await retellWebClient.startCall({ accessToken: access_token });
  }

  function stopCall() {
    try { retellWebClient.stopCall(); } catch (_) {}
  }

  // ---- Eventos SDK ----
  retellWebClient.on("call_started", () => {
    isActive = true;
    paintToggle();
    setStatus("Inntesec Agent: llamada iniciada");
    openPanel();
    emitEvent({ type: "call_started", call_id: lastCallId });

    // polling para que el popup pueda obtener "final" y (si existe) transcript_object
    startPolling();
  });

  retellWebClient.on("agent_start_talking", () => {
    setStatus("Inntesec Agent: IA hablando…");
  });

  retellWebClient.on("agent_stop_talking", () => {
    setStatus("Inntesec Agent: escuchando…");
  });

  // update incremental => NO depender del panel: dispara hook
  retellWebClient.on("update", (update) => {
    const text = extractTranscriptText(update);
    if (!text) return;

    const role = extractRole(update);

    // panel opcional
    openPanel();
    setLiveText(text);

    // hook para popup
    try { onUpdate && onUpdate({ role, text, raw: update }); } catch (_) {}
  });

  retellWebClient.on("call_ended", async () => {
    isActive = false;
    paintToggle();
    setStatus("Inntesec Agent: llamada finalizada");
    stopPolling();
    emitEvent({ type: "call_ended", call_id: lastCallId });

    // Intentamos traer resumen final desde backend
    try {
      const json = await fetchCallJson();
      try { onPollData && onPollData(json); } catch (_) {}

      const call = json?.call || null;
      const transcript = (call?.transcript || "").trim();

      openPanel();
      showFinalTranscript(transcript);
    } catch (_) {
      openPanel();
      showFinalTranscript(lastLiveText);
    }
  });

  retellWebClient.on("error", (error) => {
    isActive = false;
    paintToggle();
    setStatus("Inntesec Agent: error en la llamada");
    stopPolling();
    emitEvent({ type: "call_error", call_id: lastCallId, error });

    openPanel();
    showFinalTranscript(`Error: ${error?.message || "revisa consola"}`);
    try { retellWebClient.stopCall(); } catch (_) {}
  });

  if (toggleBtn) {
    toggleBtn.addEventListener("click", async (e) => {
      e.preventDefault();

      if (isActive) {
        setStatus("Inntesec Agent: colgando…");
        stopCall();
        return;
      }

      try {
        await startCall();
      } catch (err) {
        openPanel();

        if (String(err?.message || err) === "NO_PHONE") {
          setStatus("Inntesec Agent: no tienes número registrado");
          showFinalTranscript(
            "No tienes un número de teléfono registrado. Actualízalo en tu perfil o solicita al administrador que lo ingrese."
          );
        } else {
          setStatus("Inntesec Agent: no se pudo iniciar");
          showFinalTranscript(`No se pudo iniciar la llamada. ${err?.message || err}`);
        }

        isActive = false;
        paintToggle();
      }
    });
  }

  paintToggle();
  setStatus("");
}
