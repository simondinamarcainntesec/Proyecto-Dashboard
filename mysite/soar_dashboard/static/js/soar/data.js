// Fuente única de datos embebidos desde el template (#soar-events)
let EVENTS = [];

/**
 * Carga y normaliza (mínimo) los eventos desde el <script id="soar-events"> embebido.
 * La dejo async para que puedas usar `await preloadEvents()` sin problema.
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
    // Normalización ligera: solo aseguramos strings y trim.
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
