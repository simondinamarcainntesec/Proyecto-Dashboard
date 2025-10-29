const state = {
  severityFilter: "",
  countryFilter: "",
  actionFilter: "",
  deviceFilter: "",
  serviceFilter: "",
  protoFilter: "",
};

const listeners = new Set();
export function getState(){ return { ...state }; }
export function setState(patch){ Object.assign(state, patch); listeners.forEach(l=>l(getState())); }
export function onStateChange(fn){ listeners.add(fn); return () => listeners.delete(fn); }

// un solo filtro activo a la vez
function only(patch){
  setState({
    severityFilter:"", countryFilter:"", actionFilter:"",
    deviceFilter:"", serviceFilter:"", protoFilter:"",
    ...patch
  });
}

export const actions = {
  toggleSeverity(sev){
    const s = String(sev ?? "").trim();
    only({ severityFilter: (state.severityFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleCountry(cty){
    const s = String(cty ?? "").trim();
    only({ countryFilter: (state.countryFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleAction(act){
    const s = String(act ?? "").trim();
    only({ actionFilter: (state.actionFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  // NUEVOS
  toggleDevice(dev){
    const s = String(dev ?? "").trim();
    only({ deviceFilter: (state.deviceFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleService(svc){
    const s = String(svc ?? "").trim();
    only({ serviceFilter: (state.serviceFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleProto(proto){
    const s = String(proto ?? "").trim();
    only({ protoFilter: (state.protoFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
};
