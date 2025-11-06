
let EVENTS = [];

export async function preloadEvents() {
  const el = document.getElementById("soar-events");
  if (!el) {
    console.warn("[data] No se encontró #soar-events en el DOM.");
    EVENTS = [];
    return;
  }
  try {
    const raw = JSON.parse(el.textContent || "[]") || [];
    EVENTS = raw.map((r) => ({
      severity:        safeStr(r.severity),
      srccountry:      safeStr(r.srccountry),
      security_action: safeStr(r.security_action ?? r.action),
      action:          safeStr(r.action),
      device:          safeStr(r.device),
      service:         safeStr(r.service),
      proto:           safeStr(r.proto),
      srcip:           safeStr(r.srcip),
      dstip:           safeStr(r.dstip),
      application:     safeStr(r.Application ?? r.app), 
      date:            safeStr(r.date),
      time:            safeStr(r.time),
    }));
  } catch (e) {
    console.error("[data] JSON inválido en #soar-events:", e);
    EVENTS = [];
  }
}

export function getEvents() {
  return EVENTS;
}

// ---- helpers ----
function safeStr(v) {
  if (v == null) return "";
  const s = String(v);
  return s.trim();
}
