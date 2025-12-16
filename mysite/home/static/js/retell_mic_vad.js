(() => {
  const wrap = document.getElementById("callMicWrap");
  const micBtn = document.getElementById("callMicBtn");
  const retellBtn = document.getElementById("retellToggleBtn");
  const retellStatus = document.getElementById("retellStatus");

  if (!wrap || !micBtn) return;

  // ===== Ajustes =====
  const SMOOTHING = 0.85;         // 0..1 (más alto = más suave)
  const SPEECH_THRESHOLD = 0.02;  // RMS (ajústalo según ambiente)
  const MAX_SCALE = 1.25;
  const MAX_GLOW = 1.0;

  let audioCtx = null;
  let analyser = null;
  let mediaStream = null;
  let rafId = null;

  let smoothedLevel = 0;
  let callActive = false;
  let vadRunning = false;

  // Si aplicas el hook 100% (ver abajo), este flag queda actualizado por Retell.
  // El mic lo lee como estado inicial.
  const getStickyCallState = () => Boolean(window.__retellCallActive);

  const setVisible = (on) => {
    wrap.classList.toggle("hidden", !on);
    wrap.setAttribute("aria-hidden", String(!on));
  };

  const setMicUIOn = (on) => {
    micBtn.classList.toggle("is-on", on);
    micBtn.setAttribute("aria-pressed", String(on));
  };

  function computeRms(data) {
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128; // -1..1
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

    const isUserSpeaking = smoothedLevel > SPEECH_THRESHOLD;
    micBtn.dataset.speaking = isUserSpeaking ? "1" : "0";

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
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(mediaStream);

      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.0;

      source.connect(analyser);

      setMicUIOn(true);
      tick();
    } catch (e) {
      console.warn("[retell_mic_vad] No se pudo iniciar el mic:", e);
      await stopVAD();
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

  function updateCallState(on) {
    const next = Boolean(on);
    if (next === callActive) return;

    callActive = next;
    setVisible(callActive);

    if (callActive) {
      // Intento autoiniciar VAD; si el navegador lo bloquea, el usuario puede clickear el mic.
      startVAD();
    } else {
      stopVAD();
    }
  }

  // ===== API “infalible” (Retell debe llamar esto) =====
  // Recomendado: desde el bundle, al conectar/cortar -> window.setRetellCallActive(true/false)
  window.setRetellCallActive = (on) => {
    window.__retellCallActive = Boolean(on); // sticky
    updateCallState(Boolean(on));
  };

  // ===== Evento “infalible” (Retell debe emitirlo) =====
  // Recomendado: window.dispatchEvent(new CustomEvent("retell:call-active",{detail:{active:true}}))
  window.addEventListener("retell:call-active", (ev) => {
    const active = Boolean(ev?.detail?.active);
    window.__retellCallActive = active; // sticky
    updateCallState(active);
  });

  // Click manual del mic: solo durante llamada
  micBtn.addEventListener("click", async () => {
    if (!callActive) return;
    if (vadRunning && analyser) await stopVAD();
    else await startVAD();
  });

  // ===== Fallback (mientras no apliques hook 100%) =====
  function inferCallActiveFallback() {
    if (!retellBtn) return false;

    const pressed = (retellBtn.getAttribute("aria-pressed") || "").toLowerCase();
    if (pressed === "true") return true;

    const btnText = (retellBtn.textContent || "").toLowerCase();
    if (btnText.includes("colgar") || btnText.includes("finalizar") || btnText.includes("hang")) return true;

    const st = (retellStatus?.textContent || "").toLowerCase();
    if (st.includes("en llamada") || st.includes("connected") || st.includes("conect") || st.includes("llamada")) return true;

    return false;
  }

  function inferCallEndedFallback() {
    if (!retellBtn) return true;

    const pressed = (retellBtn.getAttribute("aria-pressed") || "").toLowerCase();
    if (pressed === "false") return true;

    const btnText = (retellBtn.textContent || "").toLowerCase();
    if (btnText.includes("llamar") || btnText.includes("call")) return true;

    const st = (retellStatus?.textContent || "").toLowerCase();
    if (
      st.includes("finalizada") ||
      st.includes("colgada") ||
      st.includes("ended") ||
      st.includes("disconnected") ||
      st.includes("error") ||
      st.includes("sin llamada")
    ) return true;

    return false;
  }

  // Observa cambios de UI para ocultar al colgar (fallback)
  if (retellBtn) {
    const mo = new MutationObserver(() => {
      if (inferCallEndedFallback()) updateCallState(false);
      else updateCallState(inferCallActiveFallback());
    });

    mo.observe(retellBtn, { attributes: true, childList: true, subtree: true, characterData: true });
    if (retellStatus) mo.observe(retellStatus, { childList: true, subtree: true, characterData: true });

    // Fallback extra tras click (por delays del bundle)
    retellBtn.addEventListener("click", () => {
      setTimeout(() => {
        if (inferCallEndedFallback()) updateCallState(false);
        else updateCallState(inferCallActiveFallback());
      }, 150);

      setTimeout(() => {
        if (inferCallEndedFallback()) updateCallState(false);
        else updateCallState(inferCallActiveFallback());
      }, 900);

      setTimeout(() => {
        if (inferCallEndedFallback()) updateCallState(false);
        else updateCallState(inferCallActiveFallback());
      }, 1800);
    });
  }

  // Limpieza al salir
  window.addEventListener("pagehide", () => { stopVAD(); });
  window.addEventListener("beforeunload", () => { stopVAD(); });

  // Estado inicial: usa sticky si existe, si no, fallback
  setVisible(false);
  updateCallState(getStickyCallState() || inferCallActiveFallback());
})();
