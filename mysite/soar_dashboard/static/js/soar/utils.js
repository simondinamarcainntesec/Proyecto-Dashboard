export const $ = (sel) => document.querySelector(sel);

export function readJSON(id) {
  const el = document.getElementById(id);
  try { return el ? JSON.parse(el.textContent) : null; }
  catch(e){ console.error("JSON inválido en", id, e); return null; }
}

export const norm = (s) => String(s ?? "N/A").trim().toLowerCase();
export const safeLabel = (s) => {
  const t = (s ?? "").toString().trim();
  return t ? t : "N/A";
};

export const ACTION_ALIASES = {
  "0":"Open","1":"Blocked","false":"Open","true":"Blocked",
  "allow":"Open","allowed":"Open","deny":"Blocked","denied":"Blocked",
  "block":"Blocked","blocked":"Blocked","resolved":"Resolved","closed":"Closed","2":"Resolved",
  "drop":"Blocked","timeout":"Blocked","reset":"Blocked"
};

export const prettyActionLabel = (value) => {
  const k = norm(value);
  if (ACTION_ALIASES[k]) return ACTION_ALIASES[k];
  const raw = String(value ?? "").trim();
  return raw ? raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase() : "N/A";
};
