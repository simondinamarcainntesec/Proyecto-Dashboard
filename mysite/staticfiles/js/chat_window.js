(function(){
  const log = document.getElementById("chatLog");
  const input = document.getElementById("chatInput");
  const btn = document.getElementById("sendBtn");
  const status = document.getElementById("status");

  if (!log || !input || !btn || !status) return;

  const csrf = window.CHAT_CSRF_TOKEN || "";
  const apiUrl = window.CHAT_API_URL || "";

  // Persistencia simple (por ventana)
  const STORAGE_KEY = "portal_chat_history_v1";

  function loadHistory(){
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
    catch { return []; }
  }
  function saveHistory(items){
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(-200)));
  }

  function appendBubble(text, who){
    const wrap = document.createElement("div");
    wrap.className = "msg " + (who === "me" ? "me" : "ai");
    wrap.textContent = text;

    log.appendChild(wrap);
    log.scrollTop = log.scrollHeight;
  }

  // ===== "Analizando..." (nuevo) =====
  let analyzingEl = null;

  function showAnalyzing(){
    if (analyzingEl) return;

    analyzingEl = document.createElement("div");
    analyzingEl.className = "typing";
    analyzingEl.innerHTML = `
      <span>Analizando</span>
      <span class="dots" aria-hidden="true">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </span>
    `;
    log.appendChild(analyzingEl);
    log.scrollTop = log.scrollHeight;
  }

  function hideAnalyzing(){
    if (!analyzingEl) return;
    analyzingEl.remove();
    analyzingEl = null;
  }

  // Render historial
  const hist = loadHistory();
  for (const it of hist) appendBubble(it.text, it.who);

  function setBusy(isBusy){
    btn.disabled = isBusy;
    // Si quieres permitir escribir mientras analiza, comenta la siguiente línea:
    input.disabled = isBusy;

    status.textContent = isBusy ? "Analizando..." : "Listo";

    if (isBusy) showAnalyzing();
    else hideAnalyzing();
  }

  async function send(){
    const msg = (input.value || "").trim();
    if (!msg || !apiUrl) return;

    input.value = "";
    appendBubble(msg, "me");

    const newHist = loadHistory();
    newHist.push({ who:"me", text: msg, ts: Date.now() });
    saveHistory(newHist);

    setBusy(true);
    try{
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ message: msg }),
        credentials: "same-origin",
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok){
        const err = data.error || ("Error HTTP " + res.status);
        appendBubble("Error: " + err, "ai");

        const h2 = loadHistory();
        h2.push({ who:"ai", text: "Error: " + err, ts: Date.now() });
        saveHistory(h2);
        return;
      }

      // Soporta 1 o múltiples respuestas (replies[] o reply)
      const replies = Array.isArray(data.replies)
        ? data.replies
        : (data.reply ? [data.reply] : []);

      for (const r of replies) {
        if (!r) continue;
        appendBubble(r, "ai");

        const h3 = loadHistory();
        h3.push({ who:"ai", text: r, ts: Date.now() });
        saveHistory(h3);
      }

    } finally {
      setBusy(false);
    }
  }

  btn.addEventListener("click", send);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey){
      e.preventDefault();
      send();
    }
  });

  // Opcional: canal para “reusar” el popup y permitir que otras páginas le pidan foco
  const bc = ("BroadcastChannel" in window) ? new BroadcastChannel("portal_chat_channel_v1") : null;
  bc?.addEventListener("message", (ev) => {
    if (ev?.data?.type === "focus") window.focus();

    // Si estás usando el reset al reabrir:
    if (ev?.data?.type === "reset") {
      try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
      log.innerHTML = "";
      hideAnalyzing();
      status.textContent = "Listo";
      input.disabled = false;
      btn.disabled = false;
      window.focus();
    }
  });
})();
