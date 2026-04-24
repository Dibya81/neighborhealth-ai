/**
 * Logic for standalone login page.
 */
(function() {
  const form = document.getElementById('login-form');
  const nameInput = document.getElementById('user-name');
  const contactInput = document.getElementById('user-contact');
  const btn = document.getElementById('btn-login');
  const btnText = btn.querySelector('.btn-text');
  const spinner = document.getElementById('login-spinner');
  const errorEl = document.getElementById('login-error');

  // Pre-fill if already known
  const savedUser = JSON.parse(localStorage.getItem('neighborhealth_user') || 'null');
  if (savedUser) {
    nameInput.value = savedUser.name || '';
    contactInput.value = savedUser.email || savedUser.phone || '';
  }

  function _validate(contact) {
    const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact);
    const isPhone = /^[+]?[\d\s\-]{8,15}$/.test(contact.replace(/\s/g, ''));
    return { isEmail, isPhone, isValid: isEmail || isPhone };
  }

  function _showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove('hidden');
    btn.disabled = false;
    btnText.textContent = 'Unlock Dashboard';
    spinner.classList.add('hidden');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const contact = contactInput.value.trim();
    const name = nameInput.value.trim() || 'Anonymous';

    const validation = _validate(contact);
    if (!validation.isValid) {
      errorEl.textContent = 'Please enter a valid email or phone number';
      errorEl.classList.remove('hidden');
      return;
    }
    errorEl.classList.add('hidden');

    // Loading state
    btn.disabled = true;
    btnText.textContent = 'Signing in...';
    spinner.classList.remove('hidden');

    try {
      const payload = {
        name,
        email: validation.isEmail ? contact : null,
        phone: validation.isPhone ? contact : null
      };

      let user;
      try {
        user = await api.upsertUser(payload);
      } catch (apiErr) {
        // Backend may be offline — create a local session so the app still works
        console.warn('Backend unavailable, using local session:', apiErr.message);
        user = {
          id: 'local_' + Date.now(),
          name,
          email: validation.isEmail ? contact : null,
          phone: validation.isPhone ? contact : null,
          offline: true
        };
      }

      localStorage.setItem('neighborhealth_user', JSON.stringify(user));
      if (window.store) store.set('currentUser', user);

      // Smooth transition
      btnText.textContent = 'Verified ✓';
      spinner.classList.add('hidden');

      setTimeout(() => {
        window.location.href = 'index.html';
      }, 600);

    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.classList.remove('hidden');

      btn.disabled = false;
      btnText.textContent = 'Unlock Dashboard';
      spinner.classList.add('hidden');
    }
  });
})();
