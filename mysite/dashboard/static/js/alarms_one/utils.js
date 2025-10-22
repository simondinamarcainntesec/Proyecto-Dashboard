// utils.js (ESM: sin globals, todo por export)
export const $ = (sel) => document.querySelector(sel);

export function readJSON(id) {
  const el = document.getElementById(id);
  try {
    return el ? JSON.parse(el.textContent) : null;
  } catch (e) {
    console.error("JSON inválido en", id, e);
    return null;
  }
}

export const norm = (s) => String(s ?? "N/A").trim().toLowerCase();

export const safeLabel = (s) => {
  const t = (s ?? "").toString().trim();
  return t ? t : "N/A";
};

export function normalizeCountsLabels(counts) {
  const out = {};
  Object.entries(counts || {}).forEach(([k, v]) => {
    const kk = safeLabel(k);
    out[kk] = (out[kk] || 0) + Number(v || 0);
  });
  return out;
}

export function findKeyCI(obj, target) {
  if (!obj) return null;
  const t = String(target ?? "").trim().toLowerCase();
  if (!t) return null;
  for (const k of Object.keys(obj)) {
    if (String(k).trim().toLowerCase() === t) return k;
  }
  return null;
}

export function normalizeMapValues(obj) {
  const map = {};
  if (obj && typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) map[norm(k)] = Number(v || 0);
  }
  return map;
}

// === Acción -> etiqueta bonita (con alias) ===
export const ACTION_ALIASES = {
  "0": "Open",
  "1": "Blocked",
  "false": "Open",
  "true": "Blocked",
  "allow": "Open",
  "allowed": "Open",
  "deny": "Blocked",
  "denied": "Blocked",
  "block": "Blocked",
  "blocked": "Blocked",
  "resolved": "Resolved",
  "closed": "Resolved",
  "2": "Resolved",
};

export const prettyActionLabel = (value) => {
  const k = norm(value);
  if (ACTION_ALIASES[k]) return ACTION_ALIASES[k];
  const raw = String(value ?? "").trim();
  return raw ? raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase() : "N/A";
};
