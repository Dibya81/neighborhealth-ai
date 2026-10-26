window.apiClient = (function() {
  function getBaseUrl() {
    return (window.NH_CONFIG && window.NH_CONFIG.API_BASE_URL) || '';
  }

  function getAuthToken() {
    try {
      const explicitToken = localStorage.getItem('neighborhealth_token');
      if (explicitToken) return explicitToken;
      const user = JSON.parse(localStorage.getItem('neighborhealth_user') || 'null');
      return user?.token || null;
    } catch (_) {
      return null;
    }
  }

  async function request(method, path, body = null, opts = {}) {
    const base = getBaseUrl();
    const url = `${base}${path}`;
    const isFormData = body instanceof FormData;
    const headers = isFormData ? { ...opts.headers } : { 'Content-Type': 'application/json', ...opts.headers };

    // Inject Bearer token if available and not explicitly provided
    const token = getAuthToken();
    if (token && !headers['Authorization'] && !headers['authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timeoutId  = setTimeout(() => controller.abort(), 15000);
    const config     = { method, headers, signal: controller.signal };

    if (body) config.body = isFormData ? body : JSON.stringify(body);

    let response;
    try {
      response = await fetch(url, config);
      clearTimeout(timeoutId);
    } catch (networkErr) {
      clearTimeout(timeoutId);
      if (networkErr.name === 'AbortError') throw new Error('Request timed out after 15s');
      throw networkErr;
    }

    if (window.NH_LOG) {
      const dur = Math.round(performance.now() - (window._reqStart || 0));
      window.NH_LOG.api(method, path, response.status, dur);
    }

    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try { const b = await response.json(); detail = b.detail || detail; } catch (_) {}
      
      // Handle session expiration
      if (response.status === 401 && token) {
        console.warn('Session expired or invalid, clearing local session.');
        localStorage.removeItem('neighborhealth_token');
        const user = JSON.parse(localStorage.getItem('neighborhealth_user') || 'null');
        if (user && user.token) {
          delete user.token;
          localStorage.setItem('neighborhealth_user', JSON.stringify(user));
        }
      }
      throw new Error(detail);
    }

    return response.json();
  }

  return {
    get:    (path, opts)  => request('GET',    path, null, opts),
    post:   (path, body, opts)  => request('POST',   path, body, opts),
    put:    (path, body, opts)  => request('PUT',     path, body, opts),
    delete: (path, opts)        => request('DELETE',  path, null, opts),
  };
})();

