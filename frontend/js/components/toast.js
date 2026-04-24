/**
 * Toast notification system.
 */
window.toast = (function() {
  const el = document.getElementById('toast');
  let _timer = null;

  function show(message, type = 'info', duration = 3000) {
    if (_timer) clearTimeout(_timer);

    dom.setText(el, message);
    el.style.borderColor = {
      success: 'rgba(29,158,117,0.4)',
      error:   'rgba(201,75,44,0.4)',
      warning: 'rgba(196,135,10,0.4)',
      info:    'rgba(255,255,255,0.15)',
    }[type] || 'rgba(255,255,255,0.15)';

    dom.removeClass(el, 'hidden');
    // Force reflow before adding class
    el.offsetHeight;
    dom.addClass(el, 'show');

    _timer = setTimeout(() => {
      dom.removeClass(el, 'show');
      setTimeout(() => dom.addClass(el, 'hidden'), 300);
    }, duration);
  }

  return { show };
})();
