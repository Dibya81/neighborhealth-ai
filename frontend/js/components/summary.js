/**
 * City summary card — top-right HUD.
 * Updates when allRiskScores state changes.
 */
window.summaryComponent = (function() {

  function render(scoresMap) {
    if (!scoresMap) return;

    const wards = Object.values(scoresMap);
    const isSim = !!window.simulationMode;

    const high   = wards.filter(w => isSim ? (w.simulated_score >= 70) : (w.risk_level === 'high')).length;
    const medium = wards.filter(w => isSim ? (w.simulated_score >= 40 && w.simulated_score < 70) : (w.risk_level === 'medium')).length;
    const low    = wards.filter(w => isSim ? (w.simulated_score < 40) : (w.risk_level === 'low')).length;

    // Animate counters
    _countUp('stat-high',   high);
    _countUp('stat-medium', medium);
    _countUp('stat-low',    low);

    // Insight text
    const insight = _buildInsight(high, medium, wards);
    dom.setText(document.getElementById('summary-insight'), insight);

    // Brand status
    dom.setText(document.getElementById('update-time'), `Updated ${_timeNow()}`);
  }

  function _countUp(elId, target) {
    const el = document.getElementById(elId);
    if (!el) return;
    let n = 0;
    const step = Math.max(1, Math.ceil(target / 20));
    const timer = setInterval(() => {
      n = Math.min(n + step, target);
      el.textContent = n;
      if (n >= target) clearInterval(timer);
    }, 30);
  }

  function _buildInsight(high, medium, wards) {
    if (window.simulationMode) {
        return `Simulation Active: ${window.simulationMode.toUpperCase()} impact analysis.`;
    }
    if (high === 0 && medium === 0) return 'All wards at low risk today.';
    if (high > 10) return `${high} wards elevated — monsoon risk active.`;
    if (high > 0)  return `${high} ward${high > 1 ? 's' : ''} at high dengue risk today.`;
    return `${medium} wards at medium risk — monitor conditions.`;
  }

  function _timeNow() {
    return new Date().toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' });
  }

  // Re-render when scores update
  store.on('allRiskScores', render);

  return { render };
})();
