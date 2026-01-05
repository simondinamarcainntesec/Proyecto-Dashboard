let EVENTS = [];

export async function preloadEvents() {
  const el = document.getElementById("soar-events");
  if (!el) {
    EVENTS = [];
    return;
  }
  try {
    const raw = JSON.parse(el.textContent || "[]") || [];

    // Instrumentación previa
   
    const sampleRaw = (raw || []).slice(0, 3);
   

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

  } catch (e) {
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
