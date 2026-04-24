/**
 * Report submission flow.
 * Steps: tap FAB → pin mode → drop pin → fill details → submit → confirm.
 */
window.reportComponent = (function() {
  const overlay  = document.getElementById('report-overlay');
  const stepPin  = document.getElementById('report-step-pin');
  const stepDets = document.getElementById('report-step-details');
  const stepConf = document.getElementById('report-step-confirm');
  const sheetTitle = document.getElementById('report-sheet-title');
  const sheetSub   = document.getElementById('report-sheet-sub');

  function open() {
    dom.removeClass(overlay, 'hidden');
    showPinStep();
    mapComponent.enterReportMode();

    // Close panel if open so map is accessible
    if (store.get('panelOpen')) panelComponent.close();
  }

  function close() {
    dom.addClass(overlay, 'hidden');
    mapComponent.exitReportMode();
    // Reset to pin step for next time
    setTimeout(() => { showPinStep(); }, 400);
  }

  function showPinStep() {
    dom.setText(sheetTitle, 'Pin the location');
    dom.setText(sheetSub, 'Tap on the map to mark the stagnant water location');
    dom.removeClass(stepPin,  'hidden');
    dom.addClass(stepDets, 'hidden');
    dom.addClass(stepConf, 'hidden');
    document.getElementById('report-description').value = '';
    document.getElementById('photo-input').value = '';
  }

  function showDetailsStep() {
    dom.setText(sheetTitle, 'Describe the spot');
    dom.setText(sheetSub, '');
    dom.addClass(stepPin,  'hidden');
    dom.removeClass(stepDets, 'hidden');
    dom.addClass(stepConf, 'hidden');
  }

  async function submit() {
    const lat    = store.get('reportPinLat');
    const lng    = store.get('reportPinLng');
    const wardId = store.get('reportPinWardId') || (store.get('selectedWardId'));
    const desc   = document.getElementById('report-description').value.trim();

    if (!lat || !lng) {
      toast.show('Please tap on the map to place a pin first.', 'warning');
      return;
    }

    const submitBtn = document.getElementById('btn-report-submit');
    if (submitBtn) {
      submitBtn.disabled = true;
      dom.setText(submitBtn, 'Submitting...');
    }

    try {
      await api.submitReport({
        ward_id:     wardId || '1',
        lat,
        lng,
        description: desc || null,
        photo_url:   null,
      });

      // Show confirmation
      dom.addClass(stepDets, 'hidden');
      dom.removeClass(stepConf, 'hidden');
      dom.setText(sheetTitle, '');
      dom.setText(sheetSub, '');

      // Show ripple on map
      mapComponent.removeReportPin();
      mapComponent.showConfirmedPin(lat, lng);

      // Auto-close after 2s
      setTimeout(close, 2200);

    } catch (err) {
      toast.show(`Report failed: ${err.message}`, 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        dom.setText(submitBtn, 'Submit report');
      }
    }
  }

  function init() {
    const fab = document.getElementById('fab-report');
    if (fab) fab.addEventListener('click', open);
    
    const cancel = document.getElementById('btn-report-cancel');
    if (cancel) cancel.addEventListener('click', close);
    
    const sub = document.getElementById('btn-report-submit');
    if (sub) sub.addEventListener('click', submit);

    // Close on overlay backdrop click
    if (overlay) {
      overlay.addEventListener('click', e => {
        if (e.target === overlay) close();
      });
    }
  }

  return { init, open, close, showDetailsStep };
})();
