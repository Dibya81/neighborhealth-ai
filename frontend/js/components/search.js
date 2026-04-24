/**
 * Ward search bar — autocomplete from wardList state.
 */
window.searchComponent = (function() {
  const input   = document.getElementById('search-input');
  const dropdown = document.getElementById('search-results');

  function _filter(query) {
    const wards = store.get('wardList') || [];
    if (!query) return [];
    const q = query.toLowerCase();
    return wards
      .filter(w => w.name.toLowerCase().includes(q) || w.id.includes(q))
      .slice(0, 8);
  }

  function _renderDropdown(results) {
    dom.empty(dropdown);
    if (results.length === 0) {
      dom.addClass(dropdown, 'hidden');
      return;
    }

    results.forEach(ward => {
      const item = dom.create('div', ['search-item']);
      item.innerHTML = `${ward.name}<span class="ward-id-badge">#${ward.id}</span>`;
      item.addEventListener('click', () => {
        input.value = ward.name;
        dom.addClass(dropdown, 'hidden');
        mapComponent.flyToWard(ward.id);
        panelComponent.open(ward.id, ward.name);
      });
      dropdown.appendChild(item);
    });

    dom.removeClass(dropdown, 'hidden');
  }

  const _onInput = helpers.debounce(e => {
    const results = _filter(e.target.value.trim());
    _renderDropdown(results);
  }, 200);

  input.addEventListener('input', _onInput);
  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      dom.addClass(dropdown, 'hidden');
      input.blur();
    }
  });

  // Close when clicking outside
  document.addEventListener('click', e => {
    if (!e.target.closest('#hud-search')) {
      dom.addClass(dropdown, 'hidden');
    }
  });

  return {};
})();
