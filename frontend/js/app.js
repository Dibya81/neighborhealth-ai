/**
 * App entry point.
 * Bootstraps all components, loads initial data, wires global events.
 */
// ── CONSTANTS ─────────────────────────────────────────
const DISEASES = [
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

window.openTravelModal = () => document.getElementById('travel-modal-overlay')?.classList.remove('hidden');

(async function () {
  // ── MANDATORY AUTH GUARD (Disabled for testing) ──────────────────────
  const savedUserRaw = localStorage.getItem('neighborhealth_user');
  if (!savedUserRaw && !window.location.pathname.includes('login.html')) {
    window.NH_LOG.ui("No session found, bypassing redirect for testing.");
    // window.location.href = 'Dashboard.html';
    // return;
  }
  // ──────────────────────────────────────────────────────

  const hideSplash = () => {
    const loading = document.getElementById('loading-screen');
    if (loading) loading.classList.add('hidden');
    store.set('loading', false);
  };

  try {
    // ── 0. Init User Session ───────────────────────────────────────
    try {
      const savedUser = JSON.parse(localStorage.getItem('neighborhealth_user') || 'null');
      if (savedUser) {
        store.set('currentUser', savedUser);
        const btnSignIn = document.getElementById('btn-signin');
        const profileBtn = document.getElementById('profile-btn');
        const userDisplayName = document.getElementById('user-display-name');

        if (btnSignIn && profileBtn && userDisplayName) {
          btnSignIn.classList.add('hidden');
          profileBtn.classList.remove('hidden');
          userDisplayName.textContent = savedUser.name || 'Friend';
        }
      }
    } catch (e) {
      window.NH_LOG.error('Session init failed', e);
    }

    // ── 1. Init map & components ────────────────────────────────────
    if (window.mapComponent) {
      await mapComponent.init();
    }
    if (window.reportComponent) {
      window.reportComponent.init();
    }

    // ── 2. Background Data Fetches ──────────────────────────────────
    api.getWards().then(resp => {
      store.set('wardList', resp.wards || []);
    }).catch(err => window.NH_LOG.error('Wards load failed', err));

    api.getTodayAlerts().then(alertData => {
      if (alertData?.alerts?.length > 0) {
        const activeAlerts = alertData.alerts.filter(a => ['medium', 'high'].includes(a.severity));
        if (activeAlerts.length > 0) {
          toast.show(`Detected ${activeAlerts.length} high-risk zones today`, 'warning', 6000);
        }
      }
    }).catch(err => window.NH_LOG.error('Alerts load failed', err));

    // ── 3. Initial Disease State ─────────────────────────────────────
    store.set('currentDisease', 'dengue');
    _renderGlobalDiseasePills();

    // We await the first disease load, but with a timeout catch
    try {
      await switchDisease('dengue');
    } catch (err) {
      window.NH_LOG.error('Initial data load failed', err);
    }

  } catch (criticalErr) {
    window.NH_LOG.error('Critical boot error', criticalErr);
  } finally {
    hideSplash();
  }

  // ── UI Functions ─────────────────────────────────────────────
  async function switchDisease(diseaseId) {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) loadingOverlay.classList.remove('hidden');

    try {
      store.set('currentDisease', diseaseId);
      _renderGlobalDiseasePills();

      let resp;
      try {
        resp = await api.getAllRiskScores(diseaseId);
      } catch (reqErr) {
        if (reqErr.message.includes('404')) {
          // Graceful handle for empty DB
          store.set('allRiskScores', {});
          mapComponent.refreshColors();
          summaryComponent.render({});
          toast.show(`No live data found for ${diseaseId} today.`, 'info');
          return;
        }
        throw reqErr;
      }

      if (!resp || !resp.wards || resp.wards.length === 0) {
        throw new Error(`Invalid response for ${diseaseId}`);
      }

      const scoresMap = {};
      resp.wards.forEach(w => {
        scoresMap[w.ward_id] = w;
      });

      store.set('allRiskScores', scoresMap);
      mapComponent.refreshColors();
      summaryComponent.render(scoresMap);

      const selWardId = store.get('selectedWardId');
      if (selWardId) panelComponent.open(selWardId);

      const dName = DISEASES.find(d => d.id === diseaseId)?.label || diseaseId;
      toast.show(`Switched to ${dName}`);
      window.NH_LOG.ui(`Disease context changed to: ${dName}`);
    } catch (err) {
      window.NH_LOG.error('Failed to switch disease', err);
      toast.show(err.message || 'Failed to load risk data', 'error', 5000);
    } finally {
      if (loadingOverlay) loadingOverlay.classList.add('hidden');
    }
  }

  function _renderGlobalDiseasePills() {
    const container = document.getElementById('global-disease-pills');
    if (!container) return;

    const current = store.get('currentDisease') || 'dengue';
    container.innerHTML = '';

    DISEASES.forEach(d => {
      const pill = document.createElement('button');
      pill.className = `btn-pill ${current === d.id ? 'active' : ''}`;
      pill.textContent = d.label;
      pill.addEventListener('click', () => switchDisease(d.id));
      container.appendChild(pill);
    });
  }

  // ── 6. Search visibility logic ───────────────────────────────────
  const searchInput = document.getElementById('search-input');
  const metaTable = document.getElementById('hud-meta-table');
  if (searchInput && metaTable) {
    searchInput.addEventListener('input', () => {
      if (searchInput.value.trim().length > 0) {
        metaTable.classList.add('hidden');
      } else {
        metaTable.classList.remove('hidden');
      }
    });
  }

  // ── 7. Keyboard shortcuts ────────────────────────────────────────
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (store.get('panelOpen')) panelComponent.close();
      if (store.get('alertModalOpen')) alertModal.close();
      if (store.get('reportMode')) reportComponent.close();
      if (store.get('aiChatOpen')) aiAssistant.close();
    }
    if (e.key === '/' && !e.target.matches('input, textarea')) {
      e.preventDefault();
      document.getElementById('search-input').focus();
    }
  });

  // ── 7. Geolocation ─────────────────────────────────────────────
  async function requestUserLocation() {
    if (!navigator.geolocation) return;

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords;
        store.set('userLocation', { lat, lng });
        const found = mapComponent.findWardAt(lat, lng);
        if (found) {
          mapComponent.selectWard(found.id, found.name);
          mapComponent.flyToWard(found.id);
          toast.show(`Detected location: ${found.name}`, 'info');
        } else {
          mapComponent.panTo(lat, lng, 14);
        }
      },
      (err) => {
        window.NH_LOG.error('Geolocation denied or failed', err);
      }
    );
  }

  requestUserLocation();

  // ── SIMULATION MODE ────────────────────────────────────────────────────────
  window.simulationMode = null;

  // Per-ward deterministic factors (never changes for same wardId)
  function _wardFactors(wardId) {
    const id = parseInt(wardId, 10);
    return {
      nearWater: (id % 7 === 0 || id % 11 === 0),   // ~24% of wards
      poorDrainage: (id % 5 === 0 || id % 13 === 0),   // ~27% of wards
      highDensity: (id % 3 === 0),                     // ~33% of wards
      industrialZone: (id % 17 === 0),                    // ~6%  of wards
      lowElevation: (id % 4 === 0),                     // ~25% of wards
      openBurnArea: (id % 9 === 0),                     // ~11% of wards
      crowdedMarket: (id % 6 === 0),                     // ~17% of wards
      noisePct: ((id * 6271) % 100) / 100,          // 0.0–1.0, unique per ward
    };
  }

  function _simulatedScore(wardId, mode, baseDensity, maxDensity) {
    const f = _wardFactors(wardId);
    const densityRatio = Math.min(1, (baseDensity || 10000) / maxDensity);
    let score = 0;

    if (mode === 'monsoon') {
      // Base: rainfall effect everywhere
      score = 30 + (f.noisePct * 12);
      // Water proximity drives the biggest spikes
      if (f.nearWater) score += 35;
      if (f.poorDrainage) score += 28;
      if (f.lowElevation) score += 18;
      if (f.highDensity) score += densityRatio * 15;
      if (f.crowdedMarket) score += 10;

    } else if (mode === 'pollution') {
      // Base: density-driven everywhere
      score = 20 + (densityRatio * 30) + (f.noisePct * 10);
      if (f.industrialZone) score += 38;
      if (f.openBurnArea) score += 25;
      if (f.highDensity) score += densityRatio * 20;
      if (f.crowdedMarket) score += 15;
      if (f.nearWater) score += 8; // water bodies trap smog

    } else if (mode === 'cold') {
      // Base: moderate, density spreads respiratory risk
      score = 18 + (f.noisePct * 14);
      if (f.highDensity) score += densityRatio * 28;
      if (f.crowdedMarket) score += 22;
      if (f.poorDrainage) score += 12; // damp cold worsens conditions
      if (f.industrialZone) score += 10;
    }

    return Math.round(Math.min(100, score) * 10) / 10;
  }

  function _simulatedReasons(wardId, mode, score) {
    const f = _wardFactors(wardId);
    const reasons = [];
    const level = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';

    if (mode === 'monsoon') {
      if (f.nearWater) reasons.push('Proximity to water bodies — stagnant water risk elevated');
      if (f.poorDrainage) reasons.push('Poor drainage infrastructure — flooding likely after rainfall');
      if (f.lowElevation) reasons.push('Low elevation zone — water accumulation confirmed');
      if (f.highDensity) reasons.push('High population density — vector breeding accelerated');
      if (f.crowdedMarket) reasons.push('Crowded market area — sanitation pressure increases');
      if (reasons.length === 0) {
        if (level === 'low') reasons.push('Good drainage and elevation — monsoon impact contained');
        else reasons.push('General seasonal rainfall risk for this area');
      }

    } else if (mode === 'pollution') {
      if (f.industrialZone) reasons.push('Active industrial zone — PM2.5 and NO₂ levels critical');
      if (f.openBurnArea) reasons.push('Open burning detected nearby — AQI severely impacted');
      if (f.highDensity) reasons.push('Dense urban area — pollutant dispersion is limited');
      if (f.crowdedMarket) reasons.push('High vehicle and foot traffic — localized pollution spike');
      if (f.nearWater) reasons.push('Water body traps ground-level smog in this zone');
      if (reasons.length === 0) {
        if (level === 'low') reasons.push('Low density and no industrial activity — cleaner air quality');
        else reasons.push('Urban pollution accumulation in this sector');
      }

    } else if (mode === 'cold') {
      if (f.highDensity) reasons.push('Dense housing — rapid respiratory disease transmission likely');
      if (f.crowdedMarket) reasons.push('Crowded market — high person-to-person contact in cold weather');
      if (f.poorDrainage) reasons.push('Damp conditions from drainage — worsens respiratory symptoms');
      if (f.industrialZone) reasons.push('Industrial dust and cold air mix — bronchitis risk elevated');
      if (reasons.length === 0) {
        if (level === 'low') reasons.push('Lower density and open spaces — cold-weather spread is limited');
        else reasons.push('Cold weather risk for this ward — keep warm and avoid crowds');
      }
    }

    // Always append scenario context
    const ctx = {
      monsoon: 'Scenario: 2025 Bengaluru monsoon simulation (Oct conditions)',
      pollution: 'Scenario: 2025 post-Diwali pollution simulation (Nov conditions)',
      cold: 'Scenario: 2025 Bengaluru winter simulation (Dec–Jan conditions)',
    };
    reasons.push(ctx[mode]);

    return reasons;
  }

  function applySimulation(mode) {
    const scores = store.get('allRiskScores');
    if (!scores) return;

    window.simulationMode = mode;

    if (!mode) {
      Object.values(scores).forEach(w => {
        delete w.simulated_score;
        delete w.simulated_reasons;
      });
      store.set('allRiskScores', scores);
      mapComponent.refreshColors();
      const badge = document.getElementById('sim-badge');
      if (badge) badge.classList.add('hidden');
      return;
    }

    // Build density lookup from wardList
    const wardList = store.get('wardList') || [];
    const popLookup = {};
    wardList.forEach(w => { popLookup[w.id] = w.population_density || 10000; });
    const allDensities = Object.values(popLookup);
    const maxDensity = allDensities.length ? Math.max(...allDensities) : 22000;

    Object.entries(scores).forEach(([wardId, ward]) => {
      const density = popLookup[wardId] || 10000;
      const sim = _simulatedScore(wardId, mode, density, maxDensity);
      ward.simulated_score = sim;
      ward.simulated_reasons = _simulatedReasons(wardId, mode, sim);
    });

    store.set('allRiskScores', scores);
    mapComponent.refreshColors();

    const badge = document.getElementById('sim-badge');
    const labels = {
      monsoon: '🌧 Monsoon 2025',
      pollution: '🌫 Pollution 2025',
      cold: '❄ Cold 2025',
    };
    if (badge) {
      badge.textContent = labels[mode];
      badge.classList.remove('hidden');
    }
  }

  function setSimulation(mode) {
    const panel = document.getElementById('sim-panel');
    if (panel) panel.classList.add('hidden');
    applySimulation(mode || null);

    // If a ward panel is open, reload it with simulation data
    const openWardId = store.get('selectedWardId');
    if (openWardId) panelComponent.open(openWardId);

    window.NH_LOG.ui(`Simulation mode set to: ${mode || 'None'}`);
  }

  // Wire Simulate button
  const simBtn = document.getElementById('btn-simulate');
  const simPanel = document.getElementById('sim-panel');
  if (simBtn && simPanel) {
    simBtn.addEventListener('click', e => {
      e.stopPropagation();
      simPanel.classList.toggle('hidden');
    });
    document.addEventListener('click', e => {
      if (!simPanel.contains(e.target) && e.target !== simBtn) {
        simPanel.classList.add('hidden');
      }
    });
  }
  document.querySelectorAll('[data-sim]').forEach(el => {
    el.addEventListener('click', () => setSimulation(el.dataset.sim || null));
  });
  // ── SMART SUMMARY ─────────────────────────────────────────────────────────
  (function () {
    const summaryBtn = document.getElementById('btn-summary');
    const summaryPanel = document.getElementById('summary-panel');
    const summaryOverlay = document.getElementById('summary-modal-overlay');
    const summaryClose = document.getElementById('summary-modal-close');
    const summaryTitle = document.getElementById('summary-modal-title');
    const summarySub = document.getElementById('summary-modal-subtitle');
    const summaryBody = document.getElementById('summary-modal-body');
    const summaryMeta = document.getElementById('summary-modal-meta');
    const summaryDot = document.getElementById('summary-loading-dot');
    const summaryTyping = document.getElementById('summary-typing');

    if (!summaryBtn) return;

    // Toggle dropdown
    summaryBtn.addEventListener('click', e => {
      e.stopPropagation();
      summaryPanel.classList.toggle('hidden');
    });
    document.addEventListener('click', e => {
      if (summaryPanel && !summaryPanel.contains(e.target) && e.target !== summaryBtn) {
        summaryPanel.classList.add('hidden');
      }
    });

    // Option click
    document.querySelectorAll('[data-summary]').forEach(el => {
      el.addEventListener('click', () => {
        summaryPanel.classList.add('hidden');
        _openSummary(el.dataset.summary);
      });
    });

    summaryClose.addEventListener('click', () => {
      summaryOverlay.classList.add('hidden');
    });
    summaryOverlay.addEventListener('click', e => {
      if (e.target === summaryOverlay) summaryOverlay.classList.add('hidden');
    });

    async function _openSummary(range) {
      const labels = {
        past: 'Past 10 Days — Weather & Health',
        today: 'Today — Current Risk Status',
        forecast: 'Next 10 Days — Health Forecast',
      };
      const wardId = store.get('selectedWardId') || null;
      const wardName = wardId
        ? (store.get('wardList') || []).find(w => w.id === wardId)?.name || `Ward ${wardId}`
        : 'All of Bengaluru';

      summaryTitle.textContent = labels[range] || 'Summary';
      summarySub.textContent = wardName;
      summaryBody.innerHTML = '';
      summaryMeta.textContent = '';
      summaryTyping.textContent = 'Generating summary...';
      summaryBody.appendChild(summaryTyping);
      summaryDot.style.display = 'block';
      summaryOverlay.classList.remove('hidden');

      // Build context from store
      const scores = store.get('allRiskScores') || {};
      const wardScores = Object.values(scores);
      const high = wardScores.filter(w => (window.simulationMode ? w.simulated_score >= 70 : w.risk_level === 'high')).length;
      const medium = wardScores.filter(w => (window.simulationMode ? (w.simulated_score >= 40 && w.simulated_score < 70) : w.risk_level === 'medium')).length;
      const low = wardScores.filter(w => (window.simulationMode ? w.simulated_score < 40 : w.risk_level === 'low')).length;
      const disease = store.get('currentDisease') || 'dengue';

      // Get focused ward detail if one is selected
      let wardDetail = null;
      if (wardId) wardDetail = store.get('selectedWardDetail');

      const wardContext = wardDetail
        ? `Selected ward: ${wardName}, risk score ${Math.round(wardDetail.risk_score)}/100 (${wardDetail.risk_level}), signals: rainfall ${wardDetail.signals?.rainfall_7d ?? '?'}mm, cases ${wardDetail.signals?.dengue_cases ?? '?'}, reports ${wardDetail.signals?.report_count ?? '?'}.`
        : `City-wide: ${high} high-risk wards, ${medium} medium, ${low} low, out of 198 total BBMP wards.`;

      const rangePrompts = {
        past: `Summarize the health and weather conditions in Bengaluru over the past 10 days. Focus on disease: ${disease}. ${wardContext} Use your knowledge of Bengaluru's recent weather patterns to enrich this. Keep it to 4–5 sentences.`,

        today: `Provide a concise health status summary for today in Bengaluru. Focus on disease: ${disease}. ${wardContext} Mention what residents should do today. Keep it to 3–4 sentences.`,

        forecast: `Forecast the health and disease risk in Bengaluru for the next 10 days. Focus on disease: ${disease}. ${wardContext} Mention expected weather trends and their impact on outbreak risk. Keep it to 4–5 sentences.`,
      };

      const message = rangePrompts[range] || rangePrompts.today;
      const targetWardId = wardId || 'city'; // Default to city-wide if no ward selected

      try {
        const resp = await api.sendChat(targetWardId, message, 'en');
        const text = resp?.response || 'No summary available.';

        // Stream text into modal
        summaryBody.innerHTML = '';
        const p = document.createElement('p');
        p.style.cssText = 'margin:0;white-space:pre-wrap;';
        summaryBody.appendChild(p);

        let i = 0;
        const interval = setInterval(() => {
          p.textContent = text.slice(0, i + 1);
          i++;
          if (i >= text.length) {
            clearInterval(interval);
            // Apply formatting if helper exists
            if (window.aiAssistant && window.aiAssistant.formatMarkdown) {
              p.innerHTML = window.aiAssistant.formatMarkdown(text);
            }
          }
        }, 10);

        summaryMeta.textContent = `${labels[range]} · ${disease.charAt(0).toUpperCase() + disease.slice(1)} · ${wardName} · ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`;

      } catch (err) {
        summaryBody.innerHTML = `<p style="color:#c94b2c;font-size:13px;">Could not generate summary: ${err.message}</p>`;
      } finally {
        summaryDot.style.display = 'none';
      }
    }
  })();

  window.NH_LOG.ui('Application Fully Booted');
})();

// ── ML INTEGRATION MODAL ────────────────────────────────────────────────────
(function () {
  const btn = document.getElementById('btn-ml');
  const overlay = document.getElementById('ml-modal-overlay');
  const closeBtn = document.getElementById('ml-modal-close');
  if (!btn || !overlay) return;

  let _loaded = false;

  btn.addEventListener('click', () => {
    overlay.classList.remove('hidden');
    overlay.scrollTop = 0; // Reset scroll position
    document.body.style.overflow = 'hidden'; // Lock scroll
    if (!_loaded) { _loadMLInfo(); _loaded = true; }
    // Trigger staggered reveal
    setTimeout(() => {
      overlay.querySelectorAll('.dashboard-section').forEach(s => s.classList.add('reveal'));
    }, 50);
  });
  closeBtn.addEventListener('click', () => {
    overlay.classList.add('hidden');
    document.body.style.overflow = ''; // Unlock scroll
    overlay.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('reveal'));
  });
  overlay.addEventListener('click', e => {
    if (e.target === overlay) {
      overlay.classList.add('hidden');
      document.body.style.overflow = ''; // Unlock scroll
      overlay.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('reveal'));
    }
  });

  async function _loadMLInfo() {
    try {
      const data = await apiClient.get('/api/v1/ml/info');
      _renderModelCards(data.model);
      _renderPipeline(data.pipeline_stages);
      _renderFeatureImportance(data.features, data.feature_importances);
      _renderLivePrediction(data.live_prediction);
      _renderDataTable(data.sample_data, data.features);

      const sub = document.getElementById('ml-model-subtitle');
      if (sub) sub.textContent = `${data.model.type} · Hyper-tuned Hybrid Architecture · Pipeline Active`;

    } catch (err) {
      const sub = document.getElementById('ml-model-subtitle');
      if (sub) sub.textContent = 'Intelligence Offline: ' + err.message;
    }
  }

  function _renderModelCards(model) {
    const container = document.getElementById('ml-model-cards');
    if (!container) return;
    const cards = [
      { label: 'Architecture', value: model.type, icon: '🧠' },
      { label: 'ROC-AUC Score', value: model.roc_auc, icon: '⚡' },
      { label: 'Training Size', value: model.n_samples, icon: '📚' },
      { label: 'Vector Size', value: model.n_features, icon: '📐' },
    ];
    container.innerHTML = cards.map(c => `
      <div class="ml-card">
        <div class="ml-card-icon">${c.icon}</div>
        <div class="ml-card-val">${c.value}</div>
        <div class="ml-card-lab">${c.label}</div>
      </div>`).join('');
  }

  function _renderPipeline(stages) {
    const container = document.getElementById('ml-pipeline');
    if (!container || !stages) return;
    container.innerHTML = stages.map((s, i) => `
      <div class="ml-pipeline-step">
        <div class="ml-step-box">
          <div class="ml-step-icon">${s.icon}</div>
          <div class="ml-step-name">${s.name}</div>
          <div class="ml-step-desc">${s.desc}</div>
        </div>
        ${i < stages.length - 1 ? '<div class="ml-step-arrow">→</div>' : ''}
      </div>`).join('');
  }

  function _renderFeatureImportance(features, importances) {
    const container = document.getElementById('ml-features');
    if (!container || !importances) return;
    const sorted = Object.entries(importances).sort((a, b) => b[1] - a[1]);
    const max = sorted[0]?.[1] || 1;
    container.innerHTML = sorted.map(([feat, imp]) => {
      const pct = Math.round((imp / max) * 100);
      const color = pct > 60 ? '#1db97a' : pct > 35 ? '#2d8ef0' : '#c4870a';
      return `
        <div class="ml-feature-row">
          <div class="ml-feature-name">${feat.replace(/_/g, ' ')}</div>
          <div class="ml-feature-bar-bg">
            <div class="ml-feature-bar-val" style="width:0; background:${color};" data-width="${pct}%"></div>
          </div>
          <div class="ml-feature-pct">${(imp * 100).toFixed(1)}%</div>
        </div>`;
    }).join('');

    // Animate bars
    setTimeout(() => {
      container.querySelectorAll('.ml-feature-bar-val').forEach(bar => {
        bar.style.width = bar.getAttribute('data-width');
      });
    }, 400);
  }

  function _renderLivePrediction(lp) {
    const container = document.getElementById('ml-live-prediction');
    if (!container || !lp) return;
    const riskColor = lp.predicted_output.risk_level === 'high' ? '#c94b2c' :
      lp.predicted_output.risk_level === 'medium' ? '#c4870a' : '#1db97a';
    const features = lp.input_features;
    container.innerHTML = `
      <div style="display:flex; flex-direction:column; justify-content:space-between; height:100%; padding:20px; background:rgba(255,255,255,0.02); border:1px solid var(--border); border-radius:16px;">
        <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:12px;">
          ${Object.entries(features).map(([k, v]) => `
            <div style="border-left:2px solid rgba(255,255,255,0.05); padding-left:10px;">
              <div style="font-size:9px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.05em;">${k.replace(/_/g, ' ')}</div>
              <div style="font-size:14px; font-weight:600; color:var(--text-primary);">${typeof v === 'number' ? v.toFixed(1) : v}</div>
            </div>`).join('')}
        </div>
        <div style="margin-top:24px; display:flex; align-items:center; gap:20px; padding-top:20px; border-top:1px solid rgba(255,255,255,0.05);">
          <div style="text-align:center;">
             <div style="font-size:42px; font-weight:800; color:${riskColor}; line-height:1;">${Math.round(lp.predicted_output.risk_score)}</div>
             <div style="font-size:10px; color:${riskColor}; font-weight:600; text-transform:uppercase; margin-top:4px;">${lp.predicted_output.risk_level}</div>
          </div>
          <div>
            <div style="font-size:13px; font-weight:600; color:var(--text-primary);">Neural Inference</div>
            <div style="font-size:11px; color:var(--text-muted);">Instance: Ward ${lp.ward_id} · ${lp.model_version}</div>
          </div>
        </div>
      </div>`;
  }

  function _renderDataTable(rows, features) {
    const table = document.getElementById('ml-data-table');
    if (!table || !rows || rows.length === 0) return;

    const cols = ['rainfall_7d', 'temp_avg', 'humidity_avg', 'population_density', 'dengue_cases_30d', 'month', 'label'];
    const colLabels = {
      rainfall_7d: 'Rain 7d (mm)', temp_avg: 'Temp (°C)', humidity_avg: 'Humidity (%)',
      population_density: 'Pop Density', dengue_cases_30d: 'Cases 30d',
      month: 'Month', label: 'Outbreak',
    };

    const thead = `<thead><tr>${cols.map(c =>
      `<th style="padding:8px 12px;text-align:left;font-size:11px;color:rgba(255,255,255,0.4);font-weight:500;border-bottom:1px solid rgba(255,255,255,0.06);white-space:nowrap;">${colLabels[c] || c}</th>`
    ).join('')}</tr></thead>`;

    const tbody = `<tbody>${rows.slice(0, 10).map((row, i) => {
      const bg = i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent';
      return `<tr style="background:${bg};">${cols.map(c => {
        let val = row[c];
        let color = '#f0eff8';
        if (c === 'label') { color = val === 1 ? '#c94b2c' : '#1db97a'; val = val === 1 ? '🔴 Yes' : '🟢 No'; }
        if (c === 'rainfall_7d' && val > 40) color = '#2d8ef0';
        return `<td style="padding:7px 12px;font-size:12px;color:${color};border-bottom:1px solid rgba(255,255,255,0.04);">${typeof val === 'number' ? (Number.isInteger(val) ? val : val.toFixed(1)) : val}</td>`;
      }).join('')}</tr>`;
    }).join('')}</tbody>`;

    table.innerHTML = thead + tbody;
  }

  // ── TRAVEL MODE ──────────────────────────────────────────────────────────
  (function () {
    const overlay = document.getElementById('travel-modal-overlay');
    const checkBtn = document.getElementById('travel-check-btn');
    const resultDiv = document.getElementById('travel-result');

    if (!overlay) return;

    // Ward search autocomplete for both inputs
    function _wireSearch(inputId, hiddenId, dropdownId) {
      const input = document.getElementById(inputId);
      const hidden = document.getElementById(hiddenId);
      const dropdown = document.getElementById(dropdownId);
      if (!input) return;

      input.addEventListener('input', helpers.debounce(() => {
        const wards = store.get('wardList') || [];
        const q = input.value.toLowerCase();
        const results = q ? wards.filter(w => w.name.toLowerCase().includes(q) || w.id.includes(q)).slice(0, 6) : [];
        dropdown.innerHTML = '';
        if (results.length === 0) { dropdown.classList.add('hidden'); return; }
        results.forEach(w => {
          const item = dom.create('div', ['search-item']);
          item.textContent = w.name;
          item.addEventListener('click', () => {
            input.value = w.name;
            hidden.value = w.id;
            dropdown.classList.add('hidden');
          });
          dropdown.appendChild(item);
        });
        dropdown.classList.remove('hidden');
      }, 200));
    }

    _wireSearch('travel-from-input', 'travel-from-id', 'travel-from-results');
    _wireSearch('travel-to-input', 'travel-to-id', 'travel-to-results');

    checkBtn?.addEventListener('click', async () => {
      let fromId = document.getElementById('travel-from-id').value;
      let toId = document.getElementById('travel-to-id').value;
      const fromName = document.getElementById('travel-from-input').value;
      const toName = document.getElementById('travel-to-input').value;

      // Fallback: Try to find ID by name if not selected from dropdown
      const wards = store.get('wardList') || [];
      if (!fromId && fromName) {
        const match = wards.find(w => w.name.toLowerCase() === fromName.toLowerCase());
        if (match) fromId = match.id;
      }
      if (!toId && toName) {
        const match = wards.find(w => w.name.toLowerCase() === toName.toLowerCase());
        if (match) toId = match.id;
      }

      if (!fromId || !toId) {
        toast.show('Please select valid Bengaluru wards from the suggestions', 'warning');
        return;
      }

      dom.setText(checkBtn, 'Analyzing...');
      checkBtn.disabled = true;

      try {
        const disease = store.get('currentDisease') || 'dengue';
        const data = await api.getTravelRisk(fromId, toId, disease);

        // Render from/to cards
        const colorMap = { high: '#c94b2c', medium: '#c4870a', low: '#1db97a' };
        const _card = (info, score) => {
          const lvl = score?.risk_level || 'unknown';
          return `<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">${info.name}</div>
                  <div style="font-size:26px;font-weight:700;color:${colorMap[lvl] || '#aaa'}">${score ? Math.round(score.risk_score) : '—'}</div>
                  <div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:${colorMap[lvl] || '#aaa'}">${lvl}</div>`;
        };
        document.getElementById('travel-from-card').innerHTML = _card(data.from, data.from.score);
        document.getElementById('travel-to-card').innerHTML = _card(data.to, data.to.score);
        document.getElementById('travel-advisory').textContent = data.advisory;
        resultDiv.style.display = 'block';

      } catch (err) {
        toast.show('Travel risk check failed: ' + err.message, 'error');
      } finally {
        dom.setText(checkBtn, 'Check Travel Risk');
        checkBtn.disabled = false;
      }
    })();
  })();
})();
