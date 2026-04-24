/**
 * AI Assistant — floating pill → expandable chat.
 * Calls POST /api/v1/chat and streams text character-by-character.
 */
window.aiAssistant = (function() {
  const pill      = document.getElementById('ai-pill');
  const chat      = document.getElementById('ai-chat');
  const messages  = document.getElementById('ai-messages');
  const input     = document.getElementById('ai-input');
  const sendBtn   = document.getElementById('ai-send');
  const closeBtn  = document.getElementById('ai-chat-close');

  let _isOpen   = false;
  let _sending  = false;

  const SUGGESTIONS = [
    "How can I stay safe?",
    "What are common symptoms?",
    "Show me prevention tips",
    "Explain this risk level"
  ];

  function openWithContext(wardDetail) {
    _open();
    store.set('aiCurrentWardId', wardDetail.ward_id);
    window.NH_LOG.ai(`Opening context chat for ward: ${wardDetail.ward_name}`);

    // Clear and add context badge
    dom.empty(messages);
    const badge = dom.create('div', ['ai-context-badge']);
    dom.setText(badge,
      `${wardDetail.ward_name || 'Ward ' + wardDetail.ward_id} · Risk ${Math.round(wardDetail.risk_score)}/100 ${wardDetail.risk_level?.toUpperCase()}`);
    messages.appendChild(badge);

    // Seed opening message
    _addAIMessage(`I'm looking at ${wardDetail.ward_name || 'this ward'} — it currently has a ${wardDetail.risk_level} dengue risk (${Math.round(wardDetail.risk_score)}/100). What would you like to know?`);
    
    _renderSuggestions();
    input.focus();
  }

  function _renderSuggestions() {
    const container = document.getElementById('ai-suggestions');
    if (!container) return;
    dom.empty(container);

    SUGGESTIONS.forEach(text => {
      const chip = dom.create('button', ['ai-suggestion-chip']);
      chip.textContent = text;
      chip.addEventListener('click', () => {
        input.value = text;
        send();
      });
      container.appendChild(chip);
    });
  }

  function _open() {
    if (_isOpen) return;
    _isOpen = true;
    store.set('aiChatOpen', true);
    dom.addClass(pill, 'hidden');
    dom.removeClass(chat, 'hidden');
    _renderSuggestions();
    input.focus();
  }

  function _close() {
    _isOpen = false;
    store.set('aiChatOpen', false);
    dom.addClass(chat, 'hidden');
    dom.removeClass(pill, 'hidden');
  }

  function _addUserMessage(text) {
    const msg = dom.create('div', ['ai-msg', 'user']);
    dom.setText(msg, text);
    messages.appendChild(msg);
    _scrollToBottom();
  }

  function _addTypingIndicator() {
    const msg = dom.create('div', ['ai-msg', 'ai', 'typing']);
    msg.innerHTML = '<div class="ai-dots"><span></span><span></span><span></span></div>';
    msg.id = 'ai-typing';
    messages.appendChild(msg);
    _scrollToBottom();
    return msg;
  }

  function _addAIMessage(text) {
    const existing = document.getElementById('ai-typing');
    if (existing) existing.remove();

    const msg = dom.create('div', ['ai-msg', 'ai']);
    messages.appendChild(msg);

    // Typing effect simplified to plain text for speed/no-tag-break,
    // but at the end we apply full formatting.
    let i = 0;
    const interval = setInterval(() => {
      msg.textContent = text.slice(0, i + 1);
      i++;
      _scrollToBottom();
      if (i >= text.length) {
        clearInterval(interval);
        msg.innerHTML = _formatMarkdown(text);
        _scrollToBottom();
        window.NH_LOG.ai(`AI response streamed (${text.length} chars)`);
      }
    }, 12);
  }

  function _formatMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/### (.*?)\n/g, '<div class="ai-msg-h"> $1</div>')
      .replace(/\*\* (.*?)\*\*/g, '<b>$1</b>')
      .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
      .replace(/^- (.*)/gm, '<div class="ai-msg-li">• $1</div>')
      .replace(/^(\d+)\. (.*)/gm, '<div class="ai-msg-li">$1. $2</div>')
      .replace(/\n/g, '<br>');
  }

  function _scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  async function send() {
    if (_sending) return;
    const text = input.value.trim();
    if (!text) return;

    const wardId = store.get('aiCurrentWardId');
    input.value = '';
    _sending = true;
    sendBtn.disabled = true;

    // Hide suggestions after first message is sent
    const container = document.getElementById('ai-suggestions');
    if (container) dom.addClass(container, 'hidden');

    _addUserMessage(text);
    _addTypingIndicator();
    window.NH_LOG.ai(`User query sent [ward:${wardId || 'city'}]: "${text.substring(0, 30)}..."`);

    try {
      const resp = await api.sendChat(wardId || '1', text, 'en', window.simulationMode);
      _addAIMessage(resp.response || 'No response from server.');
    } catch (err) {
      const existing = document.getElementById('ai-typing');
      if (existing) existing.remove();
      _addAIMessage(`Sorry, I couldn't process that right now. (${err.message})`);
      window.NH_LOG.error("AI Request Failed", err);
    } finally {
      _sending = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  // Wiring
  pill.addEventListener('click', _open);
  closeBtn.addEventListener('click', _close);
  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) send(); });

  return { openWithContext, open: _open, close: _close, formatMarkdown: _formatMarkdown };
})();
