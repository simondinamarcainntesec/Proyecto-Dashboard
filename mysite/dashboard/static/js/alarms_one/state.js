// state.js
const state = {
  severityFilter: "",
  deviceFilter: "",
  actionFilter: "",      // normalizado
  hourFilter: "",        // "00".."23"
  msgSeverityFilter: "", // tal cual BD
};

const listeners = new Set();
export function getState() { return { ...state }; }
export function setState(patch) { Object.assign(state, patch); listeners.forEach(l => l(getState())); }
export function onStateChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }

export const actions = {
  toggleSeverity(sev) {
    const s = (state.severityFilter || "").toLowerCase() === String(sev).toLowerCase() ? "" : sev;
    setState({ severityFilter: s, deviceFilter:"", actionFilter:"", hourFilter:"", msgSeverityFilter:"" });
  },
  setDevice(dev) {
    const s = state.deviceFilter === dev ? "" : dev;
    setState({ deviceFilter: s, severityFilter:"", actionFilter:"", hourFilter:"", msgSeverityFilter:"" });
  },
  toggleAction(key) {
    const s = state.actionFilter === key ? "" : key;
    setState({ actionFilter: s, severityFilter:"", deviceFilter:"", hourFilter:"", msgSeverityFilter:"" });
  },
  toggleHour(h) {
    const s = state.hourFilter === h ? "" : h;
    setState({ hourFilter: s, severityFilter:"", deviceFilter:"", actionFilter:"", msgSeverityFilter:"" });
  },
  toggleMsgSeverity(k) {
    const s = state.msgSeverityFilter === k ? "" : k;
    setState({ msgSeverityFilter: s, severityFilter:"", deviceFilter:"", actionFilter:"", hourFilter:"" });
  },
};
