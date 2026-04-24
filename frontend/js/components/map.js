/**
 * Map component — Leaflet + ward choropleth.
 * Handles: init, risk colouring, hover, click, report-pin mode.
 */
window.mapComponent = (function() {
  let _map = null;
  let _geoLayer = null;
  let _activeTileLayer = null;
  let _currentStyle = 'dark';
  let _reportPin = null;
  let _trendChart = null;

  const C = window.NH_CONFIG;

  /** Colour a feature based on current risk scores */
  function _wardStyle(feature) {
    const wardId = helpers.wardIdFromFeature(feature);
    const scores = store.get('allRiskScores');
    const ward = scores?.[wardId];
    const activeScore = (window.simulationMode && ward?.simulated_score != null)
      ? ward.simulated_score : ward?.risk_score;
    const level = activeScore != null
      ? (activeScore >= 70 ? 'high' : activeScore >= 40 ? 'medium' : 'low')
      : (ward?.risk_level || 'unknown');
    const cfg = C.RISK_COLORS[level];
    return {
      fillColor:   cfg.fill,
      fillOpacity: cfg.opacity,
      color:       'rgba(255,255,255,0.18)',
      weight:      1,
      opacity:     1,
    };
  }

  function _onEachFeature(feature, layer) {
    const wardId = helpers.wardIdFromFeature(feature);
    const wardName = helpers.wardNameFromFeature(feature);

    layer.on({
      mouseover(e) {
        const scores = store.get('allRiskScores');
        const ward = scores?.[wardId];
        const score = (window.simulationMode && ward?.simulated_score != null)
          ? ward.simulated_score : (ward?.risk_score ?? '—');
        const level = typeof score === 'number'
          ? (score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low')
          : (ward?.risk_level ?? 'unknown');

        e.target.setStyle({
          fillOpacity: C.RISK_HOVER_OPACITY,
          weight: 2,
          color: 'rgba(255,255,255,0.5)',
        });

        const label = `
          <span>${wardName}</span>
          <span class="tooltip-score ${level}">${typeof score === 'number' ? Math.round(score) : score}</span>
        `;
        layer.bindTooltip(label, {
          className: 'ward-tooltip',
          sticky: true,
          offset: [10, 0],
        }).openTooltip();
      },

      mouseout(e) {
        if (store.get('selectedWardId') === wardId) return;
        _geoLayer.resetStyle(e.target);
        layer.closeTooltip();
      },

      click() {
        if (store.get('reportMode')) return;
        _selectWard(wardId, wardName);
      },
    });
  }

  function _selectWard(wardId, wardName) {
    const prev = store.get('selectedWardId');

    // Reset previous selection style
    if (prev && _geoLayer) {
      _geoLayer.eachLayer(l => {
        if (helpers.wardIdFromFeature(l.feature) === prev) {
          _geoLayer.resetStyle(l);
        }
      });
    }

    // Highlight selected ward
    if (_geoLayer) {
      _geoLayer.eachLayer(l => {
        if (helpers.wardIdFromFeature(l.feature) === wardId) {
          l.setStyle({ weight: 2.5, color: '#FFFFFF', fillOpacity: 0.9 });
          l.bringToFront();
        }
      });
    }

    store.set('selectedWardId', wardId);
    panelComponent.open(wardId, wardName);
  }

  /** Re-colour all wards after risk data loads */
  function refreshColors() {
    if (!_geoLayer) return;
    _geoLayer.eachLayer(layer => {
      if (layer.feature) {
        _geoLayer.resetStyle(layer);
      }
    });
  }

  /** Fly map to a ward centroid */
  function flyToWard(wardId) {
    if (!_geoLayer || !_map) return;
    _geoLayer.eachLayer(l => {
      if (helpers.wardIdFromFeature(l.feature) === wardId) {
        const bounds = l.getBounds();
        _map.flyToBounds(bounds, { padding: [60, 60], duration: 0.6 });
      }
    });
  }

  /** Enter report-pin-drop mode */
  function enterReportMode() {
    if (!_map) return;
    store.set('reportMode', true);
    _map.getContainer().style.cursor = 'crosshair';
  }

  /** Exit report-pin-drop mode */
  function exitReportMode() {
    store.set('reportMode', false);
    if (_map) _map.getContainer().style.cursor = '';
    if (_reportPin) {
      _map.removeLayer(_reportPin);
      _reportPin = null;
    }
  }

  /** Drop a pin at lat/lng during report mode */
  function dropReportPin(lat, lng) {
    if (_reportPin) _map.removeLayer(_reportPin);
    const icon = L.divIcon({ className: 'report-pin-marker', iconSize: [16, 16] });
    _reportPin = L.marker([lat, lng], { icon }).addTo(_map);
  }

  /** Remove the report pin (after submission) */
  function removeReportPin() {
    if (_reportPin) {
      _map.removeLayer(_reportPin);
      _reportPin = null;
    }
  }

  /** Show confirmed-report ripple at lat/lng */
  function showConfirmedPin(lat, lng) {
    const icon = L.divIcon({ className: 'confirmed-pin', iconSize: [14, 14] });
    const pin = L.marker([lat, lng], { icon }).addTo(_map);
    setTimeout(() => _map.removeLayer(pin), 4000);
  }

  async function init() {
    // Init Leaflet
    _map = L.map('map', {
      center: C.BENGALURU_CENTER,
      zoom:   C.BENGALURU_ZOOM,
      minZoom: C.BENGALURU_MIN_ZOOM,
      maxZoom: C.BENGALURU_MAX_ZOOM,
      zoomControl: false,
    });

    _activeTileLayer = L.tileLayer(C.MAP_DARK_URL, {
      attribution: C.MAP_ATTRIBUTION,
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(_map);

    // Map click for report mode
    _map.on('click', e => {
      if (!store.get('reportMode')) return;
      const { lat, lng } = e.latlng;
      store.set('reportPinLat', lat);
      store.set('reportPinLng', lng);
      dropReportPin(lat, lng);

      // Find ward for this lat/lng
      let foundWardId = null;
      if (_geoLayer) {
        _geoLayer.eachLayer(l => {
          if (foundWardId) return;
          if (l.feature && l.getBounds().contains(e.latlng)) {
            foundWardId = helpers.wardIdFromFeature(l.feature);
          }
        });
      }
      store.set('reportPinWardId', foundWardId);
      reportComponent.showDetailsStep();
    });

    // Load GeoJSON — try local file first, fallback to simple city outline
    try {
      const resp = await fetch('assets/bengaluru-wards.geojson');
      if (resp.ok) {
        const geojson = await resp.json();
        _geoLayer = L.geoJSON(geojson, {
          style: _wardStyle,
          onEachFeature: _onEachFeature,
        }).addTo(_map);
      } else {
        _loadFallbackOutline();
      }
    } catch (_) {
      _loadFallbackOutline();
    }

    // Wire up Layers button
    const layerBtn = document.getElementById('fab-layers');
    if (layerBtn) {
      layerBtn.addEventListener('click', toggleMapStyle);
    }

    return _map;
  }

  function toggleMapStyle() {
    if (!_map || !_activeTileLayer) return;

    _currentStyle = (_currentStyle === 'dark') ? 'satellite' : 'dark';
    const newUrl = (_currentStyle === 'dark') ? C.MAP_DARK_URL : C.MAP_SATELLITE_URL;

    _map.removeLayer(_activeTileLayer);
    _activeTileLayer = L.tileLayer(newUrl, {
      attribution: C.MAP_ATTRIBUTION,
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(_map);

    // Keep Ward layer on top
    if (_geoLayer) _geoLayer.bringToFront();
    
    toast.show(`Switched to ${_currentStyle} view`, 'info');
  }

  /** Find ward containing a given lat/lng */
  function findWardAt(lat, lng) {
    if (!_geoLayer) return null;
    let found = null;
    const point = [lat, lng];

    // Note: Leaflet stores coordinates as [lng, lat] in GeoJSON, 
    // but helpers.isPointInPolygon expects [lat, lng] as first arg and 
    // polygon points as [lat, lng] too. Leaflet GeoJSON layer is already [lat, lng].
    // Actually, GeoJSON standard is [lng, lat]. Let's be careful.
    
    _geoLayer.eachLayer(l => {
      if (found) return;
      if (!l.feature) return;

      // Leaflet GeoJSON layers are actually Polygons with [lat, lng] order in _latlngs
      const poly = l;
      if (poly.getBounds().contains([lat, lng])) {
        // Double check with actual PIP algorithm for precision
        // Leaflet polygon .getLatLngs() returns nested arrays of L.LatLng
        const latLngs = poly.getLatLngs()[0]; 
        // Normalize to [[lat, lng], ...]
        const coords = (Array.isArray(latLngs[0]) ? latLngs[0] : latLngs).map(ll => [ll.lat, ll.lng]);
        
        if (helpers.isPointInPolygon([lat, lng], coords)) {
          found = { 
            id: helpers.wardIdFromFeature(l.feature), 
            name: helpers.wardNameFromFeature(l.feature) 
          };
        }
      }
    });

    return found;
  }

  function _loadFallbackOutline() {
    // Minimal fallback: just show the base map without ward polygons
    window.NH_LOG.error('Ward GeoJSON not found. Make sure assets/bengaluru-wards.geojson exists.');
    toast.show('Ward boundaries not loaded. Add bengaluru-wards.geojson to assets/', 'warning', 5000);
  }

  /** Pan/Fly to specific coordinates */
  function panTo(lat, lng, zoom = 14) {
    if (!_map) return;
    _map.flyTo([lat, lng], zoom, { duration: 0.8 });
  }

  return { 
    init, 
    refreshColors, 
    flyToWard, 
    panTo,
    enterReportMode, 
    exitReportMode, 
    dropReportPin, 
    removeReportPin, 
    showConfirmedPin,
    findWardAt,
    selectWard: _selectWard,
    toggleMapStyle
  };
})();
