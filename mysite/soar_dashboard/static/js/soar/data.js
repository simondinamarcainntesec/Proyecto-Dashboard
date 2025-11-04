// Fuente única de datos embebidos desde el template (#soar-events)
let EVENTS = [];

/**
 * Carga y normaliza (mínimo) los eventos desde el <script id="soar-events"> embebido.
 */
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
      date:            safeStr(r.date),
      time:            safeStr(r.time),
      // NUEVOS:
      aotag:           safeStr(r.aotag),
      srcip:           safeStr(r.srcip),
      dstip:           safeStr(r.dstip),
      // application/displayname podrían añadirse si luego los serializas
      application:     safeStr(r.application),
      displayname:     safeStr(r.displayname),
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
