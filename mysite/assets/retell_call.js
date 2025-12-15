import { RetellWebClient } from "retell-client-js-sdk";

const retellWebClient = new RetellWebClient();

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

async function postJSON(url) {
  const csrftoken = getCookie("csrftoken");
  const r = await fetch(url, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrftoken,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });
  const data = await r.json();
  if (!r.ok || !data.ok) {
    throw new Error(data?.error || `HTTP ${r.status}`);
  }
  return data;
}

export function wireRetellButtons({ createUrl, startBtnId, stopBtnId, statusId }) {
  const startBtn = document.getElementById(startBtnId);
  const stopBtn = document.getElementById(stopBtnId);
  const statusEl = statusId ? document.getElementById(statusId) : null;

  function setStatus(t) { if (statusEl) statusEl.textContent = t; }

  // Eventos útiles :contentReference[oaicite:4]{index=4}
  retellWebClient.on("call_started", () => setStatus("Llamada iniciada"));
  retellWebClient.on("call_ended", () => setStatus("Llamada finalizada"));

  startBtn?.addEventListener("click", async () => {
    try {
      setStatus("Creando llamada...");
      const createResp = await postJSON(createUrl);

      setStatus("Conectando...");
      await retellWebClient.startCall({
        accessToken: createResp.access_token,
      }); // startCall con accessToken :contentReference[oaicite:5]{index=5}
    } catch (e) {
      console.error(e);
      setStatus(`Error: ${e.message || e}`);
    }
  });

  stopBtn?.addEventListener("click", () => {
    retellWebClient.stopCall(); // stopCall :contentReference[oaicite:6]{index=6}
  });
}
