window.apiClient = (function() {
  const BASE = window.NH_CONFIG.API_BASE_URL;

  async function request(method, path, body = null, opts = {}) {
    const url = `${BASE}${path}`;
    const isFormData = body instanceof FormData;
    const headers = isFormData ? {} : { 'Content-Type': 'application/json', ...opts.headers };

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
      throw new Error(detail);
    }

    return response.json();
  }

  return {
    get:    (path, opts)  => request('GET',    path, null, opts),
    post:   (path, body)  => request('POST',   path, body),
    put:    (path, body)  => request('PUT',     path, body),
    delete: (path)        => request('DELETE',  path),
  };
})();
