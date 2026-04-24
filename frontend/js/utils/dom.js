/**
 * DOM helpers — thin wrappers to avoid repetition.
 */
window.$ = (sel, ctx = document) => ctx.querySelector(sel);
window.$$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

window.dom = {
  show(el) { el?.classList.remove('hidden'); },
  hide(el) { el?.classList.add('hidden'); },
  toggle(el, force) { el?.classList.toggle('hidden', force === undefined ? undefined : !force); },

  setText(el, text) { if (el) el.textContent = text; },
  setHTML(el, html) { if (el) el.innerHTML = html; },

  addClass(el, ...cls)    { el?.classList.add(...cls); },
  removeClass(el, ...cls) { el?.classList.remove(...cls); },
  hasClass(el, cls)       { return el?.classList.contains(cls); },

  /** Remove all children */
  empty(el) { if (el) el.innerHTML = ''; },

  /** Create element with optional classes and text */
  create(tag, classes = [], text = '') {
    const el = document.createElement(tag);
    if (classes.length) el.className = classes.join(' ');
    if (text) el.textContent = text;
    return el;
  },

  /** Set multiple attributes */
  setAttrs(el, attrs = {}) {
    Object.entries(attrs).forEach(([k, v]) => el?.setAttribute(k, v));
  },
};
