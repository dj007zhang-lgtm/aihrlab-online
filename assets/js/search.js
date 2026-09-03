(function () {
  'use strict';

  var ARTICLES = [];
  var indexLoaded = false;

  function getBasePath() { return '/'; }

  var overlay = null;
  var dialog = null;
  var input = null;
  var resultsContainer = null;
  var footerEl = null;
  var sendBtn = null;
  var isOpen = false;
  var mode = 'ai';
  var currentIndex = -1;
  var aiAnswerEl = null;
  var aiSourcesEl = null;
  var aiThinkingEl = null;
  var aiBusy = false;
  var aiAnswerRaw = '';

  function init() {
    injectQAStyle();
    createSearchUI();
    bindEvents();
    loadIndex();
  }

  function loadIndex() {
    var base = getBasePath();
    fetch(base + 'assets/js/article-index.json')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        ARTICLES = data || [];
        indexLoaded = true;
      })
      .catch(function () { indexLoaded = true; });
  }

  function injectQAStyle() {
    if (document.getElementById('aihr-qa-style')) return;
    var css = '' +
      /* overlay */
      '.search-overlay{position:fixed;inset:0;background:rgba(26,26,23,.55);backdrop-filter:blur(3px);opacity:0;visibility:hidden;transition:opacity .25s ease,z-index 0s .25s;z-index:1000;}' +
      '.search-overlay.active{opacity:1;visibility:visible;transition:opacity .25s ease;}' +
      ':root[data-theme="dark"] .search-overlay{background:rgba(0,0,0,.65);}' +
      /* dialog shell */
      '.search-dialog{position:fixed;top:50%;left:50%;transform:translate(-50%,-48%);width:min(760px,calc(100vw - 28px));max-height:min(84vh,780px);background:var(--surface,#FDFCF8);border:1px solid var(--line-strong,rgba(0,0,0,.08));border-radius:20px;box-shadow:0 24px 80px rgba(0,0,0,.22);display:flex;flex-direction:column;opacity:0;visibility:hidden;transition:opacity .2s ease,transform .2s ease,z-index 0s .2s;z-index:1001;}' +
      '.search-dialog.active{opacity:1;visibility:visible;transform:translate(-50%,-50%);transition:opacity .2s ease,transform .2s ease;}' +
      ':root[data-theme="dark"] .search-dialog{background:#0F1012;border-color:rgba(255,255,255,.1);box-shadow:0 24px 80px rgba(0,0,0,.7);}' +
      /* segmented tabs */
      '.search-dialog .search-tabs{display:flex;justify-content:center;padding:16px 16px 10px;}' +
      '.search-dialog .search-tab{appearance:none;border:1px solid transparent;background:transparent;font:inherit;font-size:14px;font-weight:500;padding:7px 18px;cursor:pointer;color:#6b7280;line-height:1.4;transition:color .15s ease,background .15s ease,border-color .15s ease;}' +
      '.search-dialog .search-tab:first-child{border-radius:999px 0 0 999px;border-right-color:rgba(0,0,0,.06);}' +
      '.search-dialog .search-tab:last-child{border-radius:0 999px 999px 0;}' +
      ':root[data-theme="dark"] .search-dialog .search-tab{color:#9aa0a6;}' +
      '.search-dialog .search-tab.active{color:#fff;background:#3F6212;border-color:#3F6212;}' +
      ':root[data-theme="dark"] .search-dialog .search-tab.active{color:#0B0C0E;background:#6F9A3C;border-color:#6F9A3C;}' +
      '.search-dialog .search-tab:not(.active):hover{background:rgba(63,98,18,.06);color:#3F6212;}' +
      ':root[data-theme="dark"] .search-dialog .search-tab:not(.active):hover{background:rgba(111,154,60,.1);color:#9CC06A;}' +
      /* input area */
      '.search-dialog .search-input-wrap{display:flex;align-items:center;gap:10px;margin:0 16px 12px;padding:10px 14px;border:1.5px solid var(--border,rgba(0,0,0,.1));border-radius:14px;background:var(--surface,#fff);box-shadow:0 2px 8px rgba(0,0,0,.04);transition:border-color .15s ease,box-shadow .15s ease;}' +
      ':root[data-theme="dark"] .search-dialog .search-input-wrap{background:#141518;border-color:rgba(255,255,255,.1);box-shadow:none;}' +
      '.search-dialog .search-input-wrap:focus-within{border-color:#3F6212;box-shadow:0 2px 12px rgba(63,98,18,.14);}' +
      ':root[data-theme="dark"] .search-dialog .search-input-wrap:focus-within{border-color:#6F9A3C;box-shadow:0 2px 12px rgba(111,154,60,.18);}' +
      '.search-dialog .search-input-wrap svg{color:var(--text-muted);flex:0 0 auto;}' +
      '.search-dialog .search-input{flex:1;border:none;background:transparent;font:inherit;font-size:15px;color:var(--text,#1A1A17);outline:none;line-height:1.5;}' +
      '.search-dialog .search-input::placeholder{color:var(--text-muted);opacity:.85;}' +
      ':root[data-theme="dark"] .search-dialog .search-input{color:#ECEAE4;}' +
      '.search-dialog .search-send-btn{appearance:none;border:none;background:#3F6212;color:#fff;font:inherit;font-size:13px;font-weight:600;padding:7px 14px;border-radius:10px;cursor:pointer;line-height:1.3;transition:transform .08s ease,opacity .15s ease;}' +
      '.search-dialog .search-send-btn:disabled{opacity:.45;cursor:default;}' +
      '.search-dialog .search-send-btn:not(:disabled):active{transform:scale(.96);}' +
      ':root[data-theme="dark"] .search-dialog .search-send-btn{background:#6F9A3C;color:#0B0C0E;}' +
      '.search-dialog .search-close-btn{appearance:none;border:none;background:transparent;font-size:22px;line-height:1;color:var(--text-muted);cursor:pointer;padding:0 4px;border-radius:8px;transition:color .15s ease,background .15s ease;}' +
      '.search-dialog .search-close-btn:hover{color:var(--text);background:var(--bg-subtle);}' +
      /* results area */
      '.search-dialog .search-results{flex:1;overflow-y:auto;padding:10px 18px 18px;min-height:120px;scroll-behavior:smooth;}' +
      '.search-dialog .search-footer{padding:10px 18px;border-top:1px solid var(--border,rgba(0,0,0,.07));font-size:12px;color:var(--text-muted);text-align:center;}' +
      ':root[data-theme="dark"] .search-dialog .search-footer{border-color:rgba(255,255,255,.08);}' +
      '.search-dialog .search-footer kbd{font-family:inherit;font-size:11px;background:var(--bg-subtle);border:1px solid var(--line);border-radius:4px;padding:2px 6px;}' +
      '.search-dialog .search-no-results{font-size:14px;color:var(--text-muted);padding:14px 4px;}' +
      '.search-dialog .search-result-item{display:block;padding:11px 14px;border-radius:12px;text-decoration:none;color:var(--text);transition:background .15s ease,border-color .15s ease;border:1px solid transparent;margin-bottom:4px;}' +
      '.search-dialog .search-result-item:hover{background:rgba(63,98,18,.06);border-color:rgba(63,98,18,.12);}' +
      ':root[data-theme="dark"] .search-dialog .search-result-item:hover{background:rgba(111,154,60,.1);border-color:rgba(111,154,60,.18);}' +
      '.search-dialog .result-title{font-size:15px;font-weight:600;color:var(--text-link,#3F6212);line-height:1.4;}' +
      '.search-dialog .result-category{font-size:12px;color:var(--text-muted);margin-top:5px;}' +
      /* AI conversation */
      '.search-dialog .qa-conv{display:flex;flex-direction:column;gap:20px;padding:4px 0;}' +
      '.search-dialog .qa-turn{display:flex;flex-direction:column;gap:8px;padding:16px 16px 14px;border-radius:14px;background:rgba(63,98,18,.04);border:1px solid rgba(63,98,18,.1);}' +
      ':root[data-theme="dark"] .search-dialog .qa-turn{background:rgba(111,154,60,.09);border-color:rgba(111,154,60,.16);}' +
      '.search-dialog .qa-q{font-size:14px;color:#1A1A17;background:rgba(63,98,18,.12);align-self:flex-end;max-width:82%;padding:9px 15px;border-radius:16px 16px 4px 16px;line-height:1.55;box-shadow:0 1px 3px rgba(0,0,0,.06);}' +
      ':root[data-theme="dark"] .search-dialog .qa-q{color:#ECEAE4;background:rgba(111,154,60,.24);box-shadow:none;}' +
      '.search-dialog .qa-answer{white-space:pre-wrap;line-height:1.8;font-size:14.5px;color:#1A1A17;padding:2px 2px 4px;word-break:break-word;}' +
      ':root[data-theme="dark"] .search-dialog .qa-answer{color:#ECEAE4;}' +
      '.search-dialog .qa-cite{display:inline-block;margin-left:1px;vertical-align:super;}' +
      '.search-dialog .qa-cite-link{font-size:10px;line-height:1;text-decoration:none;color:#3F6212;font-weight:700;}' +
      ':root[data-theme="dark"] .search-dialog .qa-cite-link{color:#9CC06A;}' +
      '.search-dialog .qa-cite-link:hover{text-decoration:underline;}' +
      '.search-dialog .qa-sources{margin-top:12px;padding:10px 14px;border-radius:10px;background:rgba(63,98,18,.07);display:flex;flex-direction:column;gap:6px;}' +
      ':root[data-theme="dark"] .search-dialog .qa-sources{background:rgba(0,0,0,.18);}' +
      '.search-dialog .qa-sources-title{font-size:12px;color:#6b7280;font-weight:600;margin-bottom:2px;}' +
      ':root[data-theme="dark"] .search-dialog .qa-sources-title{color:#9aa0a6;}' +
      '.search-dialog .qa-source-item{display:flex;gap:8px;font-size:13px;color:#3F6212;text-decoration:none;align-items:baseline;line-height:1.45;}' +
      '.search-dialog .qa-source-item:hover{text-decoration:underline;}' +
      ':root[data-theme="dark"] .search-dialog .qa-source-item{color:#9CC06A;}' +
      '.search-dialog .qa-source-idx{color:#9aa0a6;font-variant-numeric:tabular-nums;font-weight:600;}' +
      ':root[data-theme="dark"] .search-dialog .qa-source-idx{color:#6b7280;}' +
      '.search-dialog .qa-thinking,.search-dialog .qa-hint,.search-dialog .qa-error{font-size:13.5px;line-height:1.65;}' +
      '.search-dialog .qa-thinking{color:#6b7280;padding:8px 2px;}' +
      ':root[data-theme="dark"] .search-dialog .qa-thinking{color:#9aa0a6;}' +
      '.search-dialog .qa-error{color:#C44536;padding:8px 2px;}' +
      ':root[data-theme="dark"] .search-dialog .qa-error{color:#e8826f;}' +
      '.search-dialog .qa-hint{font-size:13.5px;color:#6b7280;background:rgba(0,0,0,.03);padding:18px 20px;border-radius:14px;border:1px dashed rgba(0,0,0,.1);}' +
      ':root[data-theme="dark"] .search-dialog .qa-hint{color:#9aa0a6;background:rgba(255,255,255,.04);border-color:rgba(255,255,255,.1);}';
    var s = document.createElement('style');
    s.id = 'aihr-qa-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  function createSearchUI() {
    overlay = document.createElement('div');
    overlay.className = 'search-overlay';
    overlay.addEventListener('click', close);

    dialog = document.createElement('div');
    dialog.className = 'search-dialog';
    dialog.innerHTML = '<div class="search-tabs">' +
      '<button type="button" class="search-tab active" data-mode="ai">问 AI</button>' +
      '<button type="button" class="search-tab" data-mode="article">搜文章</button>' +
      '</div>' +
      '<div class="search-input-wrap">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>' +
      '<input type="text" class="search-input" placeholder="搜索文章..." autocomplete="off" spellcheck="false">' +
      '<button type="button" class="search-send-btn" style="display:none" aria-label="发送">发送</button>' +
      '<button class="search-close-btn" title="关闭 (Esc)">&times;</button>' +
      '</div>' +
      '<div class="search-results"><div class="search-no-results">正在加载文章索引...</div></div>' +
      '<div class="search-footer">按 <kbd>↑</kbd><kbd>↓</kbd> 导航 · <kbd>Enter</kbd> 打开 · <kbd>Esc</kbd> 关闭</div>';

    input = dialog.querySelector('.search-input');
    resultsContainer = dialog.querySelector('.search-results');
    footerEl = dialog.querySelector('.search-footer');
    sendBtn = dialog.querySelector('.search-send-btn');

    dialog.querySelector('.search-close-btn').addEventListener('click', close);

    var tabs = dialog.querySelectorAll('.search-tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener('click', function () {
        switchMode(this.getAttribute('data-mode'));
        if (input) input.focus();
      });
    }

    if (sendBtn) {
      sendBtn.addEventListener('click', function () { askAI(input.value.trim()); });
    }

    document.body.appendChild(overlay);
    document.body.appendChild(dialog);
  }

  function bindEvents() {
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        toggle();
        return;
      }
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        close();
        return;
      }
      if (!isOpen) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter') {
        navigateResults(e);
      }
    });

    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.nav-search-btn, .nav-search-btn-article, [data-open-search], .search-toggle');
      if (btn) {
        e.preventDefault();
        open();
      }
    });

    if (input) {
      input.addEventListener('input', debounce(function () {
        if (mode === 'ai') { updateSendState(); }
        else { search(input.value.trim()); }
      }, 150));
    }
  }

  function switchMode(m) {
    if (m !== 'ai' && m !== 'article') return;
    mode = m;
    var tabs = dialog.querySelectorAll('.search-tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle('active', tabs[i].getAttribute('data-mode') === m);
    }
      if (m === 'ai') {
        input.placeholder = aiConversation.length ? '继续追问…' : '问 AI 任何关于组织、AI、人才战略的问题…';
        if (sendBtn) sendBtn.style.display = '';
        footerEl.innerHTML = '<kbd>Enter</kbd> 发送 · <kbd>Esc</kbd> 关闭';
        if (!input.value.trim()) renderAIHint();
      } else {
      input.placeholder = '搜索文章...';
      if (sendBtn) sendBtn.style.display = 'none';
      footerEl.innerHTML = '按 <kbd>↑</kbd><kbd>↓</kbd> 导航 · <kbd>Enter</kbd> 打开 · <kbd>Esc</kbd> 关闭';
      if (input.value.trim()) search(input.value.trim());
      else search('');
    }
    updateSendState();
  }

  function updateSendState() {
    if (sendBtn) sendBtn.disabled = aiBusy || !input.value.trim();
  }

  function renderAIHint() {
    if (aiConversation.length > 0) {
      // 切回 AI tab 时对话仍在：重建对话流容器并把历史渲染成只读气泡
      resultsContainer.innerHTML = '';
      aiConvEl = null;
      for (var i = 0; i < aiConversation.length; i += 2) {
        var u = aiConversation[i];
        var a = aiConversation[i + 1];
        if (!u) break;
        addHistoryTurn(u.text, a ? a.text : '');
      }
    } else {
      resultsContainer.innerHTML = '<div class="qa-hint">输入你的问题，回车发送。答案只引用站内已发文章并标注出处；未覆盖的问题会明说未收录。</div>';
    }
  }

  // 渲染历史轮（只读）：用户问题 + 已生成的答案
  function addHistoryTurn(userText, aiText) {
    if (!aiConvEl) {
      aiConvEl = document.createElement('div');
      aiConvEl.className = 'qa-conv';
      resultsContainer.appendChild(aiConvEl);
    }
    var turn = document.createElement('div');
    turn.className = 'qa-turn';
    var q = document.createElement('div');
    q.className = 'qa-q';
    q.textContent = userText;
    turn.appendChild(q);
    var a = document.createElement('div');
    a.className = 'qa-answer';
    a.innerHTML = aiText ? renderCitations(aiText) : '（暂无回答）';
    turn.appendChild(a);
    aiConvEl.appendChild(turn);
    scrollToBottom();
  }

  function getQAEndpoint() {
    if (window.AIHR_QA_ENDPOINT) return window.AIHR_QA_ENDPOINT;
    var meta = document.querySelector('meta[name="aihr-qa-endpoint"]');
    return meta ? (meta.getAttribute('content') || '') : '';
  }

  // ---- Copilot 自动重试：429 / 5xx / 服务繁忙时自动重发，最多 3 次 ----
  var aiRetryCount = 0;
  var AI_MAX_RETRY = 3;
  var AI_RETRY_DELAY = 3000;

  // 多轮对话：维护对话历史，供追问时回传 Worker 维持上下文（与元器智能体一致的连续问题体验）
  var aiConversation = [];
  var AI_MAX_HISTORY = 10; // 最近 10 轮
  var aiConvEl = null; // 对话流容器（切 tab 重建时复用）

  function isRetryableMsg(msg) {
    if (!msg) return false;
    return /429|较忙|限流|服务.*忙|AI 服务|稍后|retry|繁忙/i.test(msg);
  }

  function askAI(query) {
    if (!query) return;
    var endpoint = getQAEndpoint();
    if (!endpoint) {
      renderAIUnavailable();
      return;
    }
    if (!aiBusy) {
      aiBusy = true;
      updateSendState();
      aiRetryCount = 0;
    }
    // 新会话（无历史）首次建容器；后续追问追加 turn（连续问题维持上下文）
    if (aiConversation.length === 0 && !aiConvEl) renderAIContainer();
    if (input) input.value = '';
    startTurn(query);
    attemptAI(query);
  }

  function renderAIContainer() {
    resultsContainer.innerHTML = '';
    aiConvEl = document.createElement('div');
    aiConvEl.className = 'qa-conv';
    resultsContainer.appendChild(aiConvEl);
    aiAnswerRaw = '';
  }

  // 开始新一轮：在对话流末尾追加「用户问题 + 空答案框 + 来源区」
  function scrollToBottom() {
    if (!resultsContainer) return;
    resultsContainer.scrollTop = resultsContainer.scrollHeight;
  }

  function startTurn(query) {
    if (!aiConvEl) renderAIContainer();
    var turn = document.createElement('div');
    turn.className = 'qa-turn';
    var q = document.createElement('div');
    q.className = 'qa-q';
    q.textContent = query;
    turn.appendChild(q);
    aiAnswerEl = document.createElement('div');
    aiAnswerEl.className = 'qa-answer';
    aiThinkingEl = document.createElement('div');
    aiThinkingEl.className = 'qa-thinking';
    aiThinkingEl.textContent = '正在思考…';
    aiAnswerEl.appendChild(aiThinkingEl);
    turn.appendChild(aiAnswerEl);
    aiSourcesEl = document.createElement('div');
    aiSourcesEl.className = 'qa-sources';
    turn.appendChild(aiSourcesEl);
    aiConvEl.appendChild(turn);
    aiAnswerRaw = '';
    scrollToBottom();
  }

  function attemptAI(query) {
    var endpoint = getQAEndpoint();
    if (!endpoint) {
      renderAIUnavailable();
      aiBusy = false;
      updateSendState();
      return;
    }
    var sources = [];
    var pendingSources = null;
    var sourcesRendered = false;
    function maybeRenderSources() {
      if (!sourcesRendered && pendingSources) renderSources(pendingSources);
    }
    // 重试前重置答案区（保留容器），首次仅确保提示文案
    if (aiRetryCount > 0) {
      aiAnswerRaw = '';
      if (aiAnswerEl) aiAnswerEl.innerHTML = '';
      if (aiThinkingEl) {
        aiThinkingEl.textContent = 'AI 服务较忙，正在重试（第 ' + aiRetryCount + ' 次）…';
        aiThinkingEl.style.display = '';
      }
      if (aiSourcesEl) aiSourcesEl.innerHTML = '';
      sourcesRendered = false;
      pendingSources = null;
    } else if (aiThinkingEl) {
      aiThinkingEl.textContent = '正在思考…';
    }
    // 多轮：把当前轮之前的历史回传 Worker（最近 AI_MAX_HISTORY 轮）
    var historyPayload = aiConversation
      .slice(-AI_MAX_HISTORY * 2)
      .map(function (h) {
        return { role: h.role, text: h.text };
      });
    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ question: query, history: historyPayload }),
    })
      .then(function (res) {
        if (res.status === 429) throw { retryable: true, message: 'AI 服务当前请求量较大（429）' };
        if (res.status >= 500) throw { retryable: true, message: '问答服务暂时不稳定（HTTP ' + res.status + '）' };
        if (!res.ok) throw { retryable: false, message: '服务返回 ' + res.status };
        if (!res.body) throw { retryable: false, message: '当前环境不支持流式读取' };
        return readSSE(res.body.getReader(), function (evt) {
          if (evt.type === 'sources') {
            // 先缓存，等答案开始后再渲染
            pendingSources = evt.sources || [];
          } else if (evt.type === 'delta') {
            if (aiThinkingEl && aiAnswerRaw === '') {
              maybeRenderSources();
            }
            appendDelta(evt.text || '');
          } else if (evt.type === 'done') {
            maybeRenderSources();
            finishAI(pendingSources || sources);
            // 多轮：把这一轮问答存入历史（供后续追问维持上下文）
            if (aiAnswerRaw) {
              aiConversation.push({ role: 'user', text: query });
              aiConversation.push({ role: 'assistant', text: aiAnswerRaw });
              if (aiConversation.length > AI_MAX_HISTORY * 2) {
                aiConversation = aiConversation.slice(-AI_MAX_HISTORY * 2);
              }
            }
          } else if (evt.type === 'error') {
            maybeRenderSources();
            var m = evt.message || '问答服务出错';
            if (isRetryableMsg(m) && aiRetryCount < AI_MAX_RETRY) {
              scheduleAIRetry(query);
              return;
            }
            renderAIError(m);
          }
        });
      })
      .then(function () {
        aiBusy = false;
        updateSendState();
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return; // 主动 abort（重试流程），不报错
        var retryable = err && err.retryable;
        var msg = err && err.message ? err.message : '网络异常，未能连接到问答服务';
        if (retryable && aiRetryCount < AI_MAX_RETRY) {
          scheduleAIRetry(query);
          return;
        }
        aiBusy = false;
        updateSendState();
        renderAIError(msg);
      });
  }

  function scheduleAIRetry(query) {
    aiRetryCount++;
    if (aiThinkingEl) {
      aiThinkingEl.textContent =
        'AI 服务较忙，' + AI_RETRY_DELAY / 1000 + ' 秒后自动重试（第 ' + aiRetryCount + ' 次）…';
    }
    setTimeout(function () {
      attemptAI(query);
    }, AI_RETRY_DELAY);
  }

  function readSSE(reader, onEvent) {
    var decoder = new TextDecoder('utf-8');
    var buf = '';
    function pump() {
      return reader.read().then(function (r) {
        if (r.done) {
          if (buf.trim()) dispatchBlock(buf, onEvent);
          return;
        }
        buf += decoder.decode(r.value, { stream: true });
        var parts = buf.split('\n\n');
        buf = parts.pop();
        for (var i = 0; i < parts.length; i++) dispatchBlock(parts[i], onEvent);
        return pump();
      });
    }
    return pump();
  }

  function dispatchBlock(block, onEvent) {
    var lines = block.split('\n');
    var dataLines = [];
    for (var i = 0; i < lines.length; i++) {
      var ln = lines[i];
      if (ln.indexOf('data:') === 0) dataLines.push(ln.slice(5).replace(/^ /, ''));
    }
    if (dataLines.length === 0) return;
    var raw = dataLines.join('\n');
    var evt;
    try { evt = JSON.parse(raw); } catch (e) { return; }
    if (evt && typeof evt === 'object') onEvent(evt);
  }

  function ensureAnswerEl() {
    if (aiThinkingEl && aiThinkingEl.parentNode) {
      aiAnswerEl.removeChild(aiThinkingEl);
      aiThinkingEl = null;
    }
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"]/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch];
    });
  }

  function renderCitations(rawText) {
    var out = '';
    var last = 0;
    var re = /\[(\d+)\]/g;
    var m;
    while ((m = re.exec(rawText)) !== null) {
      out += escapeHTML(rawText.slice(last, m.index));
      var n = m[1];
      out += '<sup class="qa-cite"><a href="#aih-search-ref-' + n + '" class="qa-cite-link">[' + n + ']</a></sup>';
      last = m.index + m[0].length;
    }
    out += escapeHTML(rawText.slice(last));
    return out;
  }

  function appendDelta(text) {
    ensureAnswerEl();
    if (!text) return;
    aiAnswerRaw += text;
    aiAnswerEl.innerHTML = renderCitations(aiAnswerRaw);
    scrollToBottom();
  }

  function safeHref(u) {
    if (!u) return '';
    if (/^https?:\/\//i.test(u) || u.charAt(0) === '/') return u;
    return '';
  }

  function renderSources(sources) {
    if (!aiSourcesEl) return;
    aiSourcesEl.innerHTML = '';
    if (!sources || sources.length === 0) {
      var note = document.createElement('div');
      note.className = 'qa-sources-title';
      note.textContent = '未检索到可引用的站内文章';
      aiSourcesEl.appendChild(note);
      return;
    }
    var title = document.createElement('div');
    title.className = 'qa-sources-title';
    title.textContent = '参考来源（' + sources.length + '）';
    aiSourcesEl.appendChild(title);
    for (var i = 0; i < sources.length; i++) {
      var s = sources[i];
      var a = document.createElement('a');
      a.className = 'qa-source';
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.id = 'aih-search-ref-' + (i + 1);
      var href = safeHref(s.url);
      if (href) {
        a.href = href;
        a.title = href;
      } else {
        a.setAttribute('aria-disabled', 'true');
      }
      var idx = document.createElement('span');
      idx.className = 'qa-source-idx';
      idx.textContent = '[' + (i + 1) + '] ';
      var label = document.createElement('span');
      label.className = 'qa-source-title';
      label.textContent = (s.title || s.url || '站内文章');
      a.appendChild(idx);
      a.appendChild(label);
      if (s.heading) {
        var heading = document.createElement('span');
        heading.className = 'qa-source-heading';
        heading.textContent = '小节：' + s.heading;
        a.appendChild(heading);
      }
      aiSourcesEl.appendChild(a);
    }
  }

  function finishAI(sources) {
    ensureAnswerEl();
    if (aiSourcesEl && aiSourcesEl.children.length === 0 && sources && sources.length) {
      renderSources(sources);
    }
    scrollToBottom();
    if (input) {
      input.value = '';
      input.placeholder = '继续追问…';
      input.focus();
    }
  }

  function renderAIUnavailable() {
    resultsContainer.innerHTML = '';
    var box = document.createElement('div');
    box.className = 'qa-error';
    box.textContent = '站内问答功能暂未接入（运营方尚未配置问答服务）。你仍可以在「搜文章」里检索全部已发文章。';
    resultsContainer.appendChild(box);
  }

  function renderAIError(msg) {
    if (aiAnswerEl && aiThinkingEl && aiThinkingEl.parentNode) {
      aiAnswerEl.removeChild(aiThinkingEl);
      aiThinkingEl = null;
    }
    if (aiAnswerEl && aiAnswerEl.textContent.trim() === '') {
      var box = document.createElement('div');
      box.className = 'qa-error';
      box.textContent = msg;
      aiAnswerEl.appendChild(box);
    } else {
      var err = document.createElement('div');
      err.className = 'qa-error';
      err.textContent = '（' + msg + '）';
      if (aiAnswerEl) aiAnswerEl.appendChild(err);
    }
  }

  function open() {
    if (!dialog || !overlay) return;
    isOpen = true;
    overlay.classList.add('active');
    dialog.classList.add('active');
    setTimeout(function () { if (input) input.focus(); }, 100);
    document.body.style.overflow = 'hidden';
  }

  function close() {
    if (!dialog || !overlay) return;
    isOpen = false;
    overlay.classList.remove('active');
    dialog.classList.remove('active');
    currentIndex = -1;
    // 关闭弹窗即新会话：清空多轮对话历史（避免下次打开残留悬空 DOM）
    aiConversation = [];
    aiConvEl = null;
    if (input) input.value = '';
    mode = 'ai';
    var tabs = dialog.querySelectorAll('.search-tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle('active', tabs[i].getAttribute('data-mode') === 'ai');
    }
    input.placeholder = '问 AI 任何关于组织、AI、人才战略的问题…';
    if (sendBtn) sendBtn.style.display = '';
    footerEl.innerHTML = '<kbd>Enter</kbd> 发送 · <kbd>Esc</kbd> 关闭';
    renderAIHint();
    document.body.style.overflow = '';
  }

  function toggle() { isOpen ? close() : open(); }

  function search(query) {
    if (!query) {
      resultsContainer.innerHTML = '<div class="search-no-results">输入关键词开始搜索</div>';
      return;
    }
    if (!indexLoaded || ARTICLES.length === 0) {
      resultsContainer.innerHTML = '<div class="search-no-results">文章索引加载中...</div>';
      return;
    }
    var q = query.toLowerCase();
    var results = [];
    for (var i = 0; i < ARTICLES.length; i++) {
      var a = ARTICLES[i];
      var ts = a.title.toLowerCase().indexOf(q);
      var cs = (a.category || '').toLowerCase().indexOf(q);
      if (ts !== -1 || cs !== -1) {
        results.push({ title: a.title, url: a.url, category: a.category || '', score: ts !== -1 ? ts : 1000 + cs });
      }
    }
    results.sort(function (a, b) { return a.score - b.score; });
    renderResults(results.slice(0, 12));
  }

  function renderResults(results) {
    if (!resultsContainer) return;
    if (results.length === 0) {
      resultsContainer.innerHTML = '<div class="search-no-results">未找到相关文章</div>';
      return;
    }
    var prefix = location.pathname.indexOf('/articles/') !== -1 ? '' : 'articles/';
    var html = '';
    for (var i = 0; i < results.length; i++) {
      html += '<a href="' + prefix + results[i].url + '" class="search-result-item">' +
        '<div class="result-title">' + escHtml(results[i].title) + '</div>' +
        '<div class="result-category">' + (results[i].category || '文章') + '</div>' +
        '</a>';
    }
    resultsContainer.innerHTML = html;
  }

  function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function navigateResults(e) {
    if (mode === 'ai') {
      if (e.key === 'Enter') {
        e.preventDefault();
        askAI(input.value.trim());
      }
      return;
    }
    e.preventDefault();
    var items = resultsContainer.querySelectorAll('.search-result-item');
    if (items.length === 0) return;
    if (e.key === 'ArrowDown') {
      currentIndex = Math.min(currentIndex + 1, items.length - 1);
    } else if (e.key === 'ArrowUp') {
      currentIndex = Math.max(currentIndex - 1, -1);
    } else if (e.key === 'Enter') {
      if (currentIndex >= 0 && items[currentIndex]) items[currentIndex].click();
      return;
    }
    for (var i = 0; i < items.length; i++) {
      items[i].style.background = i === currentIndex ? 'var(--bg-warm)' : '';
    }
  }

  function debounce(fn, delay) {
    var timer = null;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(fn, delay);
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();