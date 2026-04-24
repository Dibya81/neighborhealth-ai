/**
 * Ward Detail Panel — slide-in right panel.
 * Renders risk gauge, signal tiles, trend chart, action buttons.
 */
window.panelComponent = (function() {
  let _trendChart = null;
  let _currentDisease = store.get('currentDisease') || 'dengue';

  const diseases = [
    { id: 'dengue', label: 'Dengue' },
    { id: 'malaria', label: 'Malaria' },
    { id: 'heatstroke', label: 'Heatstroke' },
    { id: 'heat_exhaustion', label: 'Heat Exhaustion' },
    { id: 'dehydration', label: 'Dehydration' },
    { id: 'cholera', label: 'Cholera' },
    { id: 'typhoid', label: 'Typhoid' },
    { id: 'hepatitis_a', label: 'Hepatitis A' },
    { id: 'common_cold', label: 'Common Cold' },
    { id: 'bronchitis', label: 'Bronchitis' },
    { id: 'allergic_rhinitis', label: 'Allergic Rhinitis' },
    { id: 'copd', label: 'COPD' }
  ];

  function open(wardId, wardNameHint) {
    _currentDisease = store.get('currentDisease') || 'dengue';
    const panel = document.getElementById('ward-panel');
    const inner = document.querySelector('.panel-inner');

    // Show loading state immediately
    dom.addClass(inner, 'refreshing');
    panel.setAttribute('aria-hidden', 'false');
    dom.addClass(panel, 'open');
    store.set('panelOpen', true);
    document.getElementById('app').classList.add('panel-open');

    // Set ward name from hint immediately (full name loads shortly)
    dom.setText(document.getElementById('panel-ward-name'), wardNameHint || '...');
    dom.setText(document.getElementById('panel-ward-id'), `Ward ${wardId}`);
    store.set('aiCurrentWardId', wardId);

    _renderDiseaseLabel();

    // Load data
    _loadWardData(wardId);
  }

  function _renderDiseaseLabel() {
    let label = document.getElementById('panel-disease-label');
    if (!label) {
      label = document.createElement('div');
      label.id = 'panel-disease-label';
      label.className = 'panel-disease-label';
      const header = document.querySelector('.panel-header-top');
      if (header) {
        header.appendChild(label);
      } else {
        document.querySelector('.panel-header').appendChild(label);
      }
    }
    const currentDiseaseId = store.get('currentDisease') || 'dengue';
    const d = diseases.find(idx => idx.id === currentDiseaseId) || diseases[0];
    label.textContent = `${d.label} Profile`;
  }

  function close() {
    const panel = document.getElementById('ward-panel');
    dom.removeClass(panel, 'open');
    panel.setAttribute('aria-hidden', 'true');
    store.set('panelOpen', false);
    store.set('selectedWardId', null);
    document.getElementById('app').classList.remove('panel-open');

    // Reset selected style on map
    mapComponent.refreshColors();

    if (_trendChart) { _trendChart.destroy(); _trendChart = null; }
  }

  async function _loadWardData(wardId) {
    try {
      const inner = document.querySelector('.panel-inner');
      dom.addClass(inner, 'refreshing');
      
      // ── SIMULATION OVERRIDE ──────────────────────────────
      if (window.simulationMode) {
        const scores = store.get('allRiskScores');
        const ward = scores?.[wardId];
        if (ward && ward.simulated_score != null) {
          // Construct mock detail object matching the expected schema
          const wardList = store.get('wardList') || [];
          const wardMeta = wardList.find(w => w.id === wardId);
          const simulatedDetail = {
            ward_id:    wardId,
            ward_name:  wardMeta ? wardMeta.name : `Ward ${wardId}`,
            risk_score: ward.simulated_score,
            risk_level: (ward.simulated_score >= 70 ? 'high' : ward.simulated_score >= 40 ? 'medium' : 'low'),
            reasons:    ward.simulated_reasons || [],
            signals: {
                rainfall_7d:  _simSignal(wardId, 'rain'),
                temp_avg:     _simSignal(wardId, 'temp'),
                humidity_avg: _simSignal(wardId, 'hum'),
                dengue_cases: 'Simulated',
                report_count: _simSignal(wardId, 'reports'),
            },
            trend: [40, 45, 50, 60, ward.simulated_score], // Mock trend
            trend_direction: 'rising'
          };
          
          store.set('selectedWardDetail', simulatedDetail);
          store.set('wardHistory', []); // No history for sim yet
          _render(simulatedDetail, []);
          return;
        }
      }
      // ──────────────────────────────────────────────────────

      const [detail, historyData] = await Promise.all([
        api.getWardRisk(wardId, _currentDisease),
        api.getWardHistory(wardId, 30, _currentDisease),
      ]);

      store.set('selectedWardDetail', detail);
      store.set('wardHistory', historyData?.history || []);

      _render(detail, historyData?.history || []);
    } catch (err) {
      toast.show(`Could not load ward data: ${err.message}`, 'error');
      dom.setText(document.getElementById('panel-ward-name'), wardId);
    } finally {
      dom.removeClass(document.querySelector('.panel-inner'), 'refreshing');
    }
  }

  function _render(detail, history) {
    // Ward name + meta
    dom.setText(document.getElementById('panel-ward-name'), detail.ward_name || `Ward ${detail.ward_id}`);
    dom.setText(document.getElementById('panel-ward-id'), `Ward ${detail.ward_id}`);

    // Simulation overrides
    const scores = store.get('allRiskScores');
    const simWard = scores ? scores[detail.ward_id] : null;
    const isSimulated = window.simulationMode && simWard && simWard.simulated_score != null;

    let activeScore = isSimulated ? simWard.simulated_score : detail.risk_score;
    let activeLevel = isSimulated 
      ? (activeScore >= 70 ? 'high' : (activeScore >= 40 ? 'medium' : 'low'))
      : detail.risk_level;

    // Gauge
    _animateGauge(activeScore, activeLevel);

    // Trend badge
    const historyScores = history.map(h => h.risk_score);
    const direction = helpers.trendDirection(historyScores);
    const badge = document.getElementById('trend-badge');
    const arrows = { rising: '↑ Rising', falling: '↓ Falling', stable: '→ Stable' };
    dom.setText(document.getElementById('trend-direction'), arrows[direction] || '→ Stable');
    badge.className = `trend-badge ${direction}`;

    // Updated time
    dom.setText(document.getElementById('panel-updated'),
      detail.score_date ? `Updated ${helpers.formatDate(detail.score_date)}` : '');

    // Signal tiles
    const sig = detail.signals || {};
    const diseaseCfg = diseases.find(d => d.id === _currentDisease) || diseases[0];
    
    // Update labels based on disease
    const labels = {
      rainfall_7d: 'Rainfall 7d',
      temp_avg: 'Avg Temp',
      humidity_avg: 'Humidity',
      dengue_cases: 'Dengue Cases',
      report_count: 'Public Reports'
    };

    dom.setText(document.getElementById('sig-rain-val'),
      sig.rainfall_7d !== null ? `${helpers.round(sig.rainfall_7d)}mm` : '—');
    dom.setText(document.querySelector('#sig-rain .sig-name'), labels.rainfall_7d);

    dom.setText(document.getElementById('sig-cases-val'),
      sig.dengue_cases !== null ? sig.dengue_cases : (sig.cases_30d !== null ? sig.cases_30d : '—'));
    dom.setText(document.querySelector('#sig-cases .sig-name'), _currentDisease === 'dengue' ? 'Dengue Cases' : 'Reported Cases');

    dom.setText(document.getElementById('sig-reports-val'),
      sig.report_count !== null ? sig.report_count : '—');

    // AI Reasons
    const reasonsContainer = document.getElementById('panel-reasons');
    if (reasonsContainer) {
      reasonsContainer.innerHTML = '';

      // Prefer simulated reasons when simulation is active
      const scores = store.get('allRiskScores');
      const simWard = scores?.[detail.ward_id];
      const activeReasons = (window.simulationMode && simWard?.simulated_reasons?.length)
        ? simWard.simulated_reasons
        : (detail.reasons || []);

      // Show simulated score in gauge if simulation active
      if (window.simulationMode && simWard?.simulated_score != null) {
        const simLevel = simWard.simulated_score >= 70 ? 'high'
          : simWard.simulated_score >= 40 ? 'medium' : 'low';
        _animateGauge(simWard.simulated_score, simLevel);
      }

      if (activeReasons.length > 0) {
        // Section label changes when simulated
        const sectionLabel = document.querySelector('#reasons-section .section-label');
        if (sectionLabel) {
          sectionLabel.textContent = window.simulationMode
            ? `AI Insights — ${_simLabel(window.simulationMode)}`
            : 'AI Insights';
        }

        activeReasons.forEach((r, idx) => {
          const li = document.createElement('li');
          // Last item is the scenario context line — style differently
          const isContext = idx === activeReasons.length - 1 && window.simulationMode;
          li.className = isContext ? 'reason-item reason-context' : 'reason-item';
          li.textContent = r;
          reasonsContainer.appendChild(li);
        });
      } else {
        const li = document.createElement('li');
        li.className = 'reason-item empty';
        li.textContent = 'No specific alerts for this area.';
        reasonsContainer.appendChild(li);
      }
    }

    // Trend chart
    _renderTrendChart(history);

    // Subscribe button colour
    const subBtn = document.getElementById('btn-subscribe');
    const level = detail.risk_level;
    subBtn.className = `btn-primary ${level === 'high' ? 'high-cta' : level === 'low' ? 'low-cta' : ''}`;
  }

  function _animateGauge(score, level) {
    const fill = document.getElementById('gauge-fill');
    const scoreEl = document.getElementById('gauge-score');
    const levelEl = document.getElementById('gauge-level');

    fill.className = `gauge-fill ${level}`;

    // Animate score counter
    let current = 0;
    const target = Math.round(score);
    const step = Math.ceil(target / 30);
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      dom.setText(scoreEl, current);
      if (current >= target) clearInterval(timer);
    }, 20);

    // Animate ring
    setTimeout(() => {
      fill.style.strokeDashoffset = helpers.scoreToDashOffset(score);
    }, 50);

    dom.setText(levelEl, level?.toUpperCase() || '');
  }

  function _renderTrendChart(history) {
    const canvas = document.getElementById('trend-chart');
    if (!canvas) return;
    if (_trendChart) { _trendChart.destroy(); _trendChart = null; }

    if (!history || history.length === 0) return;

    const labels = history.map(h => helpers.formatDate(h.date));
    const data   = history.map(h => Math.round(h.risk_score));

    // Determine line colour from latest score
    const latest = data[data.length - 1] || 50;
    const level  = helpers.scoreToLevel(latest);
    const colour = helpers.levelToColor(level);

    _trendChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data,
          borderColor: colour,
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 3,
          fill: true,
          backgroundColor: colour + '18',
          tension: 0.4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 600, easing: 'easeOutQuart' },
        plugins: { legend: { display: false }, tooltip: {
          callbacks: { label: ctx => `Risk: ${ctx.raw}` },
          displayColors: false,
          backgroundColor: '#0E0E10',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          titleFont: { size: 11 },
          bodyFont: { size: 11 },
        }},
        scales: {
          x: { display: false },
          y: {
            display: false,
            min: 0,
            max: 100,
          },
        },
      },
    });
  }

  // Button wiring
  document.getElementById('panel-close').addEventListener('click', close);

  document.getElementById('btn-subscribe').addEventListener('click', () => {
    const detail = store.get('selectedWardDetail');
    if (detail) alertModal.open(detail);
  });

  document.getElementById('btn-ask-ai').addEventListener('click', () => {
    const detail = store.get('selectedWardDetail');
    if (detail) aiAssistant.openWithContext(detail);
  });

  function _simLabel(mode) {
    return { monsoon: 'Monsoon 2025', pollution: 'Pollution 2025', cold: 'Cold 2025' }[mode] || mode;
  }


  function _simSignal(wardId, type) {
    const id = parseInt(wardId, 10) || 1;
    const seed = (id * 6271 + {'rain':1,'temp':2,'hum':3,'reports':4}[type]) % 100;
    if (type === 'rain')    return +(8 + seed * 0.3).toFixed(1);
    if (type === 'temp')    return +(22 + (seed % 10)).toFixed(1);
    if (type === 'hum')     return +(60 + (seed % 25)).toFixed(1);
    if (type === 'reports') return Math.floor(seed % 6);
    return 0;
  }

  return { open, close };
})();
