/**
 * Alert subscription modal.
 */
window.alertModal = (function() {
  const overlay  = document.getElementById('alert-modal-overlay');
  const wardName = document.getElementById('modal-ward-name');
  const badge    = document.getElementById('modal-risk-badge');
  const nameInput = document.getElementById('alert-name');
  const input    = document.getElementById('alert-contact');
  const errorEl  = document.getElementById('alert-error');
  const submitBtn = document.getElementById('btn-alert-submit');
  const btnText  = document.getElementById('alert-btn-text');
  const spinner  = document.getElementById('alert-btn-spinner');
  const success  = document.getElementById('alert-success');

  let _wardDetail = null;
  let _contactType = 'sms';

  function open(wardDetail) {
    _wardDetail = wardDetail;
    _contactType = 'sms';

    // Reset state
    nameInput.value = '';
    input.value = '';
    dom.removeClass(errorEl, 'hidden');
    dom.addClass(errorEl, 'hidden');
    dom.addClass(success, 'hidden');
    dom.removeClass(submitBtn, 'hidden');
    dom.setText(btnText, 'Set alert');
    dom.addClass(spinner, 'hidden');

    // Populate
    dom.setText(wardName, wardDetail.ward_name || `Ward ${wardDetail.ward_id}`);
    badge.className = `modal-risk-badge ${wardDetail.risk_level}`;
    dom.setText(badge, wardDetail.risk_level?.toUpperCase() + ` · ${Math.round(wardDetail.risk_score)}/100`);

    // Reset type buttons
    $$('.type-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.type === 'sms');
    });

    dom.removeClass(overlay, 'hidden');
    setTimeout(() => input.focus(), 300);
  }

  function close() { dom.addClass(overlay, 'hidden'); }

  function _validate(contact, type) {
    if (type === 'sms') {
      return /^[+]?[\d\s\-]{8,15}$/.test(contact.replace(/\s/g, ''));
    }
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact);
  }

  async function submit() {
    const contact = input.value.trim();

    if (!_validate(contact, _contactType)) {
      dom.removeClass(errorEl, 'hidden');
      dom.setText(errorEl, _contactType === 'sms'
        ? 'Please enter a valid phone number'
        : 'Please enter a valid email address');
      return;
    }
    dom.addClass(errorEl, 'hidden');

    // Loading state
    dom.setText(btnText, 'Setting alert...');
    dom.removeClass(spinner, 'hidden');
    submitBtn.disabled = true;

    try {
      // 1. Upsert User
      const userPayload = {
        name: nameInput.value.trim() || 'Anonymous',
        email: _contactType === 'email' ? contact : null,
        phone: _contactType === 'sms' ? contact : null,
        ward_id: _wardDetail.ward_id,
        lat: store.get('userLocation')?.lat,
        lng: store.get('userLocation')?.lng
      };

      const userResp = await api.upsertUser(userPayload);
      const userId = userResp.id;
      
      // Store user in state
      store.set('currentUser', userResp);

      // 2. Create Subscription linked to User
      await api.createSubscription({
        ward_id:      _wardDetail.ward_id,
        contact,
        contact_type: _contactType,
        threshold:    70,
        user_id:      userId,
        name:         userPayload.name,
        email:        userPayload.email,
        notify_diseases: [store.get('currentDisease') || 'dengue']
      });

      // Success
      dom.addClass(submitBtn, 'hidden');
      dom.removeClass(success, 'hidden');
      toast.show(`Alert set for ${_wardDetail.ward_name || 'ward'}`, 'success');

      // Auto-close
      setTimeout(close, 2000);

    } catch (err) {
      dom.setText(errorEl, `Failed: ${err.message}`);
      dom.removeClass(errorEl, 'hidden');
    } finally {
      dom.setText(btnText, 'Set alert');
      dom.addClass(spinner, 'hidden');
      submitBtn.disabled = false;
    }
  }

  // Wiring
  document.getElementById('alert-modal-close').addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  submitBtn.addEventListener('click', submit);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });

  $$('.type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _contactType = btn.dataset.type;
      $$('.type-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      input.placeholder = _contactType === 'sms' ? '+91 98765 43210' : 'you@example.com';
      input.type = _contactType === 'sms' ? 'tel' : 'email';
    });
  });

  return { open, close };
})();
