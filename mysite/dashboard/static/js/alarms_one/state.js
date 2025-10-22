// state.js
const state = {
  severityFilter: "",
  deviceFilter: "",
  actionFilter: "",      // normalizado
  hourFilter: "",        // "00".."23"
  msgSeverityFilter: "", // tal cual BD
  // === NUEVOS ===
  levelFilter: "",
  subtypeFilter: "",
  logDescriptionFilter: "",
};

const listeners = new Set();
export function getState() { return { ...state }; }
export function setState(patch) { Object.assign(state, patch); listeners.forEach(l => l(getState())); }
export function onStateChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }

// Helper: deja activo SOLO el filtro indicado y limpia el resto
function only(patch) {
  const empty = {
    severityFilter:"", deviceFilter:"", actionFilter:"", hourFilter:"",
    msgSeverityFilter:"", levelFilter:"", subtypeFilter:"", logDescriptionFilter:""
  };
  setState({ ...empty, ...patch });
}

export const actions = {
  toggleSeverity(sev) {
    const s = (state.severityFilter || "").toLowerCase() === String(sev).toLowerCase() ? "" : sev;
    only({ severityFilter: s });
  },
  setDevice(dev) {
    const s = state.deviceFilter === dev ? "" : dev;
    only({ deviceFilter: s });
  },
  toggleAction(key) {
    const s = state.actionFilter === key ? "" : key;
    only({ actionFilter: s });
  },
  toggleHour(h) {
    const s = state.hourFilter === h ? "" : h;
    only({ hourFilter: s });
  },
  toggleMsgSeverity(k) {
    const s = state.msgSeverityFilter === k ? "" : k;
    only({ msgSeverityFilter: s });
  },
  // === NUEVOS ===
  toggleLevel(k) {
    const s = state.levelFilter === k ? "" : k;
    only({ levelFilter: s });
  },
  toggleSubtype(k) {
    const s = state.subtypeFilter === k ? "" : k;
    only({ subtypeFilter: s });
  },
  toggleLogDescription(k) {
    const s = state.logDescriptionFilter === k ? "" : k;
    only({ logDescriptionFilter: s });
  },
};
