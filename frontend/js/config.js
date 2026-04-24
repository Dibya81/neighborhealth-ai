/**
 * Global configuration.
 * Change API_BASE_URL when deploying.
 */
window.NH_CONFIG = {
  API_BASE_URL: 'https://neighborhealth-backend.onrender.com',
  MAP_DARK_URL: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  MAP_SATELLITE_URL: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  MAP_ATTRIBUTION: '© OpenStreetMap contributors, © CARTO / Esri',
  BENGALURU_CENTER: [12.9716, 77.5946],
  BENGALURU_ZOOM: 11,
  BENGALURU_MIN_ZOOM: 10,
  BENGALURU_MAX_ZOOM: 16,
  RISK_COLORS: {
    high: { fill: '#C94B2C', opacity: 0.65 },
    medium: { fill: '#C4870A', opacity: 0.50 },
    low: { fill: '#1D9E75', opacity: 0.40 },
    unknown: { fill: '#4A4A4A', opacity: 0.25 },
  },
  RISK_HOVER_OPACITY: 0.9,
  CACHE_TTL_MS: 3600_000,  // 1 hour
};
