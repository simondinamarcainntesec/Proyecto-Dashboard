// static/js/soar/utils.js

export const norm = (s) => String(s ?? "").trim().toLowerCase();
export const safe = (s) => (String(s ?? "").trim() || "N/A");

// Alias para acciones (normaliza 0/1, booleanos y textos comunes)
export const ACTION_ALIASES = {
  "0": "Open",
  "1": "Blocked",
  "false": "Open",
  "true": "Blocked",
  "allow": "Open",
  "allowed": "Open",
  "pass": "Open",
  "open": "Open",

  "deny": "Blocked",
  "denied": "Blocked",
  "block": "Blocked",
  "blocked": "Blocked",
  "drop": "Blocked",
  "dropped": "Blocked",

  "reset": "Reset",
  "client-rst": "Reset",
  "server-rst": "Reset",
  "timeout": "Timeout",
  "monitor": "Monitor",
  "alert": "Alert",
};

export function prettyActionLabel(value) {
  const k = norm(value);
  if (k in ACTION_ALIASES) return ACTION_ALIASES[k];
  const raw = String(value ?? "").trim();
  return raw ? raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase() : "N/A";
}
