// static/js/retell_mic.js
export function createMicController(opts) {
  const {
    buttonId,
    meterFillId,
    // callbacks
    onStart,
    onStop,
  } = opts || {};

  const btn = document.getElementById(buttonId);
  const meterFill = document.getElementById(meterFillId);

  let stream = null;
  let ctx = null;
  let analyser = null;
  let raf = null;
  let enabled = false; // mic "unmuted"

  const setMeter = (pct) => {
    if (!meterFill) return;
    const v = Math.max(0, Math.min(100, pct));
    meterFill.style.width = v + "%";
  };

  const setActiveUi = (isActive) => {
    if (!btn) return;
    btn.classList.toggle("is-active", !!isActive);
  };

  const stopLoop = () => {
    if (raf) cancelAnimationFrame(raf);
    raf = null;
    setActiveUi(false);
    setMeter(0);
  };

  const loop = () => {
    if (!analyser) return;
    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);

    // RMS simple
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const x = (data[i] - 128) / 128;
      sum += x * x;
    }
    const rms = Math.sqrt(sum / data.length);

    // map a %
    const pct = Math.min(100, Math.max(0, (rms * 220)));
    setMeter(pct);

    // “hablando” cuando pasa umbral
    setActiveUi(enabled && pct > 8);

    raf = requestAnimationFrame(loop);
  };

  async function ensureAudio() {
    if (stream && ctx && analyser) return;

    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      }
    });

    ctx = new (window.AudioContext || window.webkitAudioContext)();
    const source = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 512;

    source.connect(analyser);
  }

  function setTracksEnabled(on) {
    if (!stream) return;
    stream.getAudioTracks().forEach(t => { t.enabled = !!on; });
  }

  async function start() {
    if (!btn) return;

    btn.setAttribute("aria-disabled", "true");
    try {
      await ensureAudio();
      enabled = true;
      setTracksEnabled(true);

      // some browsers need this after a gesture
      try { await ctx.resume(); } catch (_) {}

      stopLoop();
      loop();

      if (typeof onStart === "function") onStart({ stream });
    } finally {
      btn.setAttribute("aria-disabled", "false");
    }
  }

  function mute() {
    enabled = false;
    setTracksEnabled(false);
    setActiveUi(false);
    setMeter(0);
  }

  function unmute() {
    enabled = true;
    setTracksEnabled(true);
  }

  function stop() {
    enabled = false;
    stopLoop();

    try { if (ctx) ctx.close(); } catch (_) {}
    ctx = null;
    analyser = null;

    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }

    if (typeof onStop === "function") onStop();
  }

  function toggleMute() {
    if (!stream) {
      // primer click pide permisos y arranca
      start();
      return;
    }
    if (enabled) mute();
    else unmute();
  }

  if (btn) {
    btn.addEventListener("click", () => toggleMute());
  }

  return {
    start,
    stop,
    mute,
    unmute,
    isEnabled: () => enabled,
    getStream: () => stream,
  };
}
