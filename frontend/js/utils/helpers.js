/**
 * Pure utility functions — no DOM, no state.
 */
window.helpers = {

  /** Format ISO date string to "Oct 15" */
  formatDate(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
  },

  /** "2025-10-15T06:00:00Z" → "6:02 AM" */
  formatTime(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' });
  },

  /** 0–39 = low, 40–69 = medium, 70–100 = high */
  scoreToLevel(score) {
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  },

  /** Returns CSS colour var string for a risk level */
  levelToColor(level) {
    const map = { high: '#C94B2C', medium: '#C4870A', low: '#1D9E75' };
    return map[level] || '#4A4A4A';
  },

  /** Gauge circumference = 2πr = 2 × 3.14159 × 50 ≈ 314 */
  scoreToDashOffset(score) {
    const circ = 314;
    const pct = Math.min(100, Math.max(0, score)) / 100;
    return circ - circ * pct;
  },

  /** Debounce a fn call */
  debounce(fn, delay) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), delay);
    };
  },

  /** Build trend direction string from score array */
  trendDirection(scores) {
    if (!scores || scores.length < 3) return 'stable';
    const recent = scores.slice(-2).reduce((a,b) => a+b, 0) / 2;
    const earlier = scores.slice(0, 2).reduce((a,b) => a+b, 0) / 2;
    const diff = recent - earlier;
    if (diff > 5) return 'rising';
    if (diff < -5) return 'falling';
    return 'stable';
  },

  /** Round to N decimal places */
  round(n, decimals = 1) {
    return Math.round(n * 10**decimals) / 10**decimals;
  },

  /** Get ward ID from Leaflet feature properties */
  wardIdFromFeature(feature) {
    return feature?.properties?.KGISWardNo
        || feature?.properties?.ward_no
        || feature?.properties?.id
        || feature?.properties?.ward_id
        || null;
  },

  /** Get ward name from Leaflet feature properties */
  wardNameFromFeature(feature) {
    return feature?.properties?.KGISWardName
        || feature?.properties?.ward_name
        || feature?.properties?.name
        || 'Unknown ward';
  },

  /** Standard ray-casting point-in-polygon check */
  isPointInPolygon(point, polygon) {
    // point: [lat, lng], polygon: array of [lat, lng]
    const x = point[0], y = point[1];
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i][0], yi = polygon[i][1];
        const xj = polygon[j][0], yj = polygon[j][1];
        const intersect = ((yi > y) !== (yj > y))
            && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
  }
};

/**
 * PRODUCTION LOGGING SYSTEM
 * Standardised format: [TAG] message
 */
window.NH_LOG = {
  _time() {
    return new Date().toLocaleTimeString('en-IN', { hour12: false });
  },

  ui(msg) {
    console.log(`%c[${this._time()}] [UI] ${msg}`, "color: #1DB97A; font-weight: bold;");
  },

  api(method, url, status, time) {
    const color = status >= 400 ? "#E53E3E" : "#2D8EF0";
    console.groupCollapsed(`%c[${this._time()}] [API] ${method} ${url} (${status}) - ${time}ms`, `color: ${color}; font-weight: bold;`);
    console.trace("Stack Trace:");
    console.groupEnd();
  },

  ai(msg) {
    console.log(`%c[${this._time()}] [AI] ${msg}`, "color: #A855F7; font-weight: bold;");
  },

  error(msg, err) {
    console.error(`[${this._time()}] [ERROR] ${msg}`, err || "");
  }
};
