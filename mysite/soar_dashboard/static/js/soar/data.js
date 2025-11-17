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

    // Instrumentación previa
    console.log("[data] rows crudos recibidos:", Array.isArray(raw) ? raw.length : 0);
    const sampleRaw = (raw || []).slice(0, 3);
    console.log("[data] sample raw[0..2]:", sampleRaw);

    EVENTS = raw.map((r) => ({
      alarm_id:        safeStr(r.alarm_id),     // ← clave para el modal
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

    // Instrumentación post-map
    const total = EVENTS.length;
    const withAlarm = EVENTS.filter(e => e.alarm_id).length;
    const withoutAlarm = total - withAlarm;
    console.log(`[data] eventos mapeados: total=${total} | con alarm_id=${withAlarm} | sin alarm_id=${withoutAlarm}`);
    console.log("[data] sample EVENTS[0..2]:", EVENTS.slice(0, 3));
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
