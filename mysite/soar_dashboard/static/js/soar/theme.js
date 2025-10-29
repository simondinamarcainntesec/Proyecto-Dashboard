// static/js/soar/theme.js

export const TXT  = "#E5E7EB";
export const GRID = "rgba(229,231,235,0.14)";
export const AXIS = TXT;
export const EMPH = "#FFFFFF";

export const palette = {
  critical: "#FF6B6B",
  high:     "#F59E0B",
  medium:   "#F0E442",
  low:      "#10B981",
  info:     "#60A5FA",
  warning:  "#CC79A7",
  "n/a":    "#A0A3A8",
  default:  "#8B5CF6",
};

export const colorFor = (sev) =>
  palette[String(sev || "").toLowerCase()] || palette.default;

export function colorForMsgSeverity(label) {
  const k = String(label || "").trim().toLowerCase();
  if (k === "critical") return "#FF6B6B";
  if (k === "high")     return "#F59E0B";
  if (k === "medium")   return "#F0E442";
  if (k === "n/a")      return "#A0A3A8";
  return "#8B5CF6";
}

export function setupChartJSDefaults(Chart) {
  const fontFamily = "'Inter', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";

  Chart.defaults.font.family = fontFamily;
  Chart.defaults.color = TXT;
  Chart.defaults.font.size = 15;
  Chart.defaults.font.weight = "700";

  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyle = "circle";
  Chart.defaults.plugins.legend.labels.font = { size: 15, weight: "700" };
  Chart.defaults.plugins.legend.labels.color = "#FFFFFF";

  Chart.defaults.plugins.tooltip.titleFont = { size: 15, family: fontFamily, weight: "700" };
  Chart.defaults.plugins.tooltip.bodyFont  = { size: 15, family: fontFamily, weight: "700" };
  Chart.defaults.plugins.tooltip.titleColor = EMPH;
  Chart.defaults.plugins.tooltip.bodyColor  = EMPH;

  Chart.defaults.scales = {
    ...Chart.defaults.scales,
    linear:   { ticks: { color: AXIS, font: { size: 14, weight: "700" } }, grid: { color: GRID } },
    category: { ticks: { color: AXIS, font: { size: 14, weight: "700" } }, grid: { color: GRID } },
  };

  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.devicePixelRatio = Math.max(1.5, window.devicePixelRatio || 1);
}

// (opcionales: helpers para “atenuar” barras no activas)
export function dimmedBarFill()   { return "rgba(229,231,235,0.18)"; }
export function dimmedBarBorder() { return "rgba(229,231,235,0.85)"; }

export function computeFocusColors(labels, activeLabel, getActiveColor) {
  const isActive = (lbl) =>
    String(lbl).trim().toLowerCase() === String(activeLabel || "").trim().toLowerCase();

  const backgroundColor = labels.map((lbl) => (isActive(lbl) ? getActiveColor(lbl) : dimmedBarFill()));
  const borderColor     = labels.map((lbl) => (isActive(lbl) ? getActiveColor(lbl) : dimmedBarBorder()));
  return { backgroundColor, borderColor };
}
