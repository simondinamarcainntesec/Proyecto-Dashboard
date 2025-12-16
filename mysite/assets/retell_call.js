// assets/retell_call.js
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
    ).toString().trim();
  }

  try {
    return JSON.stringify(update).slice(0, 500);
  } catch {
    return "";
  }
}

function positionPanelNearAnchor(panel, anchorEl, prefer = "bottom") {
  if (!panel || !anchorEl) return;

  // medir aunque esté hidden
  const wasHidden = panel.classList.contains("hidden");
  if (wasHidden) {
    panel.classList.remove("hidden");
    panel.style.visibility = "hidden";
  }

  const anchorRect = anchorEl.getBoundingClientRect();
  const panelRect = panel.getBoundingClientRect();

  const margin = 10;
  const pad = 8;

  // --- CLAVE: anclar por RIGHT (no por LEFT) ---
  // Queremos que el borde derecho del panel quede alineado con el borde derecho del botón.
  let right = window.innerWidth - anchorRect.right;
  right = Math.max(pad, Math.min(right, window.innerWidth - panelRect.width - pad));

  // Top: preferentemente debajo del botón; si no cabe, arriba.
  const belowTop = anchorRect.bottom + margin;
  const aboveTop = anchorRect.top - panelRect.height - margin;

  let top;
  if (prefer === "top") {
    top = aboveTop >= pad ? aboveTop : belowTop;
  } else {
    top = (belowTop + panelRect.height <= window.innerHeight - pad) ? belowTop : aboveTop;
  }
  top = Math.max(pad, Math.min(top, window.innerHeight - panelRect.height - pad));

  panel.style.position = "fixed";
  panel.style.left = "auto";
  panel.style.bottom = "auto";
  panel.style.right = `${right}px`;
  panel.style.top = `${top}px`;

  if (wasHidden) {
    panel.classList.add("hidden");
    panel.style.visibility = "";
  }
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
}) {
  const toggleBtn = document.getElementById(toggleBtnId);
  const statusEl = document.getElementById(statusId);

  const panel = document.getElementById(panelId);
  const panelBody = document.getElementById(panelBodyId);
  const panelCloseBtn = document.getElementById(panelCloseBtnId);
  const panelClearBtn = document.getElementById(panelClearBtnId);

  const setStatus = (t) => {
    const txt = (t || "").toString();
    if (statusEl) {
      statusEl.textContent = txt;
      statusEl.title = txt;
    }
  };

  const reposition = () => {
    if (!panel || panel.classList.contains("hidden")) return;
    if (!toggleBtn) return;
    positionPanelNearAnchor(panel, toggleBtn, "bottom");
  };

  const openPanel = () => {
    if (!panel) return;
    panel.classList.remove("hidden");
    panel.setAttribute("aria-hidden", "false");
    requestAnimationFrame(reposition);
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

  window.addEventListener("resize", () => requestAnimationFrame(reposition));
  window.addEventListener("scroll", () => requestAnimationFrame(reposition), true);

  // ---- Render: UNA sola caja viva (no spam de líneas) ----
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

    // Heurística anti-repetición:
    // - Si llega exactamente lo mismo, no hacemos nada.
    // - Si llega un texto más corto (a veces resets), lo aceptamos igual.
    if (t === lastLiveText) return;

    const box = ensureLiveEl();
    if (!box) return;

    const txtEl = box.querySelector(".txt");
    if (txtEl) txtEl.textContent = t;

    lastLiveText = t;

    panelBody.scrollTop = panelBody.scrollHeight;
    reposition();
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
    reposition();
  }

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
      throw new Error(data?.detail || data?.error || `Error creando llamada (${resp.status})`);
    }

    return data; // { ok, access_token, call_id }
  }

  async function fetchCallSummary() {
    if (!getCallUrlTemplate || !lastCallId) return null;
    const url = getCallUrlTemplate.replace("{call_id}", encodeURIComponent(lastCallId));
    const resp = await fetch(url, { credentials: "same-origin" });
    const data = await resp.json().catch(() => ({}));
    if (!data?.ok) return null;
    return data.call || null;
  }

  async function startCall() {
    if (isActive) return;

    setStatus("Retell: creando llamada…");

    const { access_token, call_id } = await createWebCallOnServer();
    lastCallId = call_id || null;

    // Reset UI live
    lastLiveText = "";
    clearPanel();

    setStatus("Retell: conectando…");
    await retellWebClient.startCall({ accessToken: access_token });
  }

  function stopCall() {
    try { retellWebClient.stopCall(); } catch (_) {}
  }

  // ---- Eventos SDK ----
  retellWebClient.on("call_started", () => {
    isActive = true;
    paintToggle();
    setStatus("Retell: llamada iniciada");
    openPanel();
  });

  retellWebClient.on("agent_start_talking", () => {
    setStatus("Retell: IA hablando…");
  });

  retellWebClient.on("agent_stop_talking", () => {
    setStatus("Retell: escuchando…");
  });

  // IMPORTANT: update incremental => reemplazamos texto, NO agregamos líneas
  retellWebClient.on("update", (update) => {
    const text = extractTranscriptText(update);
    if (text) {
      openPanel();
      setLiveText(text);
    }
  });

  retellWebClient.on("call_ended", async () => {
    isActive = false;
    paintToggle();
    setStatus("Retell: llamada finalizada");

    // Mostrar SOLO el transcript final (si backend lo entrega)
    try {
      const call = await fetchCallSummary();
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
    setStatus("Retell: error en la llamada");
    openPanel();
    showFinalTranscript(`Error: ${error?.message || "revisa consola"}`);
    try { retellWebClient.stopCall(); } catch (_) {}
  });

  if (toggleBtn) {
    toggleBtn.addEventListener("click", async (e) => {
      e.preventDefault();

      if (isActive) {
        setStatus("Retell: colgando…");
        stopCall();
        return;
      }

      try {
        await startCall();
      } catch (err) {
        openPanel();

        if (String(err?.message || err) === "NO_PHONE") {
          setStatus("Retell: no tienes número registrado");
          showFinalTranscript(
            "No tienes un número de teléfono registrado. Actualízalo en tu perfil o solicita al administrador que lo ingrese."
          );
        } else {
          setStatus("Retell: no se pudo iniciar");
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
