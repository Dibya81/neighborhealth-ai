/**
 * Global state store — single source of truth.
 * All state mutations go through store.set().
 * Components subscribe via store.on().
 */
(function() {
  const _state = {
    // Data
    allRiskScores: null,      // { ward_id: {risk_score, risk_level, ...} }
    wardList: [],             // [{id, name, constituency}]
    currentDisease: 'dengue', // Default to dengue
    selectedWardId: null,
    selectedWardDetail: null, // full detail from GET /risk/{ward_id}
    wardHistory: [],          // [{date, risk_score}]
    wardReports: [],
    // User
    currentUser: null,        // { id, name, email, phone, ... }
    userLocation: null,       // { lat, lng, ward_id }

    // UI
    panelOpen: false,
    reportMode: false,
    reportPinLat: null,
    reportPinLng: null,
    reportPinWardId: null,
    alertModalOpen: false,
    aiChatOpen: false,
    aiCurrentWardId: null,
    loading: true,
    error: null,
  };

  const _listeners = {};

  window.store = {
    get(key) {
      return _state[key];
    },

    set(key, value) {
      const prev = _state[key];
      _state[key] = value;
      if (_listeners[key]) {
        _listeners[key].forEach(fn => fn(value, prev));
      }
      if (_listeners['*']) {
        _listeners['*'].forEach(fn => fn(key, value, prev));
      }
    },

    on(key, fn) {
      if (!_listeners[key]) _listeners[key] = [];
      _listeners[key].push(fn);
    },

    off(key, fn) {
      if (!_listeners[key]) return;
      _listeners[key] = _listeners[key].filter(f => f !== fn);
    },

    getAll() { return { ..._state }; },
  };
})();
