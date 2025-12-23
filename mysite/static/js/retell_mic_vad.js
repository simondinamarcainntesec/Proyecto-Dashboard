(() => {
  const wrap = document.getElementById("callMicWrap");
  const micBtn = document.getElementById("callMicBtn");

  // Botón principal Retell (para bloquear doble click en "Llamar")
  const retellToggleBtn = document.getElementById("retellToggleBtn");
  const retellStatus = document.getElementById("retellStatus");

  if (!wrap || !micBtn) return;

  // ===== Ajustes =====
  const SMOOTHING = 0.85;
  const SPEECH_THRESHOLD = 0.02; // RMS (ajusta según ambiente)
  const MAX_SCALE = 1.25;
  const MAX_GLOW = 1.0;

  // Autoinicio por defecto
  const AUTO_START_VAD = true;

  let audioCtx = null;
  let analyser = null;
  let mediaStream = null;
  let rafId = null;

  let smoothedLevel = 0;
  let vadRunning = false;
  let autoStartAttempted = false;

  // ===== UI: mic siempre visible =====
  function showAlways() {
    wrap.classList.remove("hidden");
    wrap.setAttribute("aria-hidden", "false");
    wrap.style.display = "inline-flex";
    wrap.style.alignItems = "center";

    micBtn.classList.remove("hidden");
    micBtn.style.display = "inline-grid";
    micBtn.style.visibility = "visible";
    micBtn.style.opacity = "1";
  }

  function setMicUIOn(on) {
    micBtn.classList.toggle("is-on", on);
    micBtn.setAttribute("aria-pressed", String(on));
  }

  // ===== VAD =====
  function computeRms(data) {
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / data.length);
  }

  function tick() {
    if (!analyser) return;

    const buffer = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(buffer);

    const level = computeRms(buffer);
    smoothedLevel = SMOOTHING * smoothedLevel + (1 - SMOOTHING) * level;

    const speaking = smoothedLevel > SPEECH_THRESHOLD;
    micBtn.dataset.speaking = speaking ? "1" : "0";

    const normalized = Math.min(1, smoothedLevel / 0.12);
    const scale = 1 + normalized * (MAX_SCALE - 1);
    const glow = normalized * MAX_GLOW;
    const haloScale = 1 + normalized * 0.35;

    micBtn.style.setProperty("--mic-scale", scale.toFixed(3));
    micBtn.style.setProperty("--mic-glow", glow.toFixed(3));
    micBtn.style.setProperty("--mic-halo-scale", haloScale.toFixed(3));

    rafId = requestAnimationFrame(tick);
  }

  async function startVAD() {
    if (vadRunning) return;
    vadRunning = true;

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });

      audioCtx = new (window.AudioContext || window.webkitAudioContext)();

      // En algunos navegadores el AudioContext puede quedar "suspended" sin gesto.
      // Igual dejamos creado; el usuario puede clickear y se reintenta/resume.
      if (audioCtx.state === "suspended") {
        try { await audioCtx.resume(); } catch (_) {}
      }

      const source = audioCtx.createMediaStreamSource(mediaStream);

      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.0;

      source.connect(analyser);

      setMicUIOn(true);
      tick();
    } catch (e) {
      // Si falla por permisos o política del navegador, dejamos el botón listo para reintento con click.
      console.warn("[retell_mic_vad] getUserMedia falló:", e);
      await stopVAD();
      micBtn.title = "Click para activar micrófono (permisos requeridos)";
    }
  }

  async function stopVAD() {
    vadRunning = false;

    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;

    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.stop());
      mediaStream = null;
    }

    if (audioCtx) {
      try { await audioCtx.close(); } catch (_) {}
      audioCtx = null;
    }

    analyser = null;
    smoothedLevel = 0;

    micBtn.style.setProperty("--mic-scale", 1);
    micBtn.style.setProperty("--mic-glow", 0);
    micBtn.style.setProperty("--mic-halo-scale", 1);
    setMicUIOn(false);
  }

  // Click: toggle VAD (permiso por gesto del usuario)
  micBtn.addEventListener("click", async () => {
    micBtn.title = "";
    if (vadRunning && analyser) await stopVAD();
    else await startVAD();
  });

  window.addEventListener("pagehide", () => { stopVAD(); });
  window.addEventListener("beforeunload", () => { stopVAD(); });

  // Inicialización: SIEMPRE visible
  showAlways();

  // Autostart (por defecto)
  if (AUTO_START_VAD && !autoStartAttempted) {
    autoStartAttempted = true;
    // micro delay para evitar carreras con render/layout
    setTimeout(() => { startVAD(); }, 50);
  }

  // =========================================================
  // BLOQUEO: evitar doble click en "Llamar" hasta que diga "Colgar"
  // =========================================================
  if (retellToggleBtn) {
    let lock = false;
    let lockTimeoutId = null;

    const isHangupState = () => {
      const t = (retellToggleBtn.textContent || "").toLowerCase();
      return t.includes("colgar") || t.includes("finalizar") || t.includes("hang");
    };

    const unlock = () => {
      lock = false;
      retellToggleBtn.disabled = false;
      retellToggleBtn.classList.remove("is-loading");
      retellToggleBtn.removeAttribute("aria-busy");
      if (lockTimeoutId) clearTimeout(lockTimeoutId);
      lockTimeoutId = null;
    };

    const lockCall = () => {
      lock = true;
      retellToggleBtn.disabled = true;
      retellToggleBtn.classList.add("is-loading");
      retellToggleBtn.setAttribute("aria-busy", "true");

      // fallback: si nunca cambia a "Colgar", desbloquear igual
      lockTimeoutId = setTimeout(() => {
        if (!isHangupState()) unlock();
      }, 8000);
    };

    // Captura el click antes que otros handlers para bloquear de inmediato
    retellToggleBtn.addEventListener("click", (ev) => {
      if (lock) {
        ev.preventDefault();
        ev.stopPropagation();
        return;
      }

      // Si ya está en "Colgar", no bloquees (deja colgar)
      if (isHangupState()) return;

      // Bloquea al intentar llamar
      lockCall();
    }, true);

    // Observa cambios del texto para desbloquear cuando aparezca "Colgar"
    const mo = new MutationObserver(() => {
      if (lock && isHangupState()) unlock();
    });

    mo.observe(retellToggleBtn, { childList: true, subtree: true, characterData: true, attributes: true });

    if (retellStatus) {
      mo.observe(retellStatus, { childList: true, subtree: true, characterData: true });
    }

    // Seguridad: si hay error, desbloquear
    const safetyPoll = setInterval(() => {
      if (!lock) return;

      if (isHangupState()) {
        unlock();
        return;
      }

      const st = (retellStatus?.textContent || "").toLowerCase();
      if (st.includes("error") || st.includes("no disponible") || st.includes("fall")) {
        unlock();
      }
    }, 500);

    window.addEventListener("pagehide", () => clearInterval(safetyPoll));
  }
})();
