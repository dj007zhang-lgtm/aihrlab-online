/* ============================================================
   AIHR 站内问答挂件 · widget.js
   - 纯前端，零依赖；直接注入任意页面的 [data-qa-widget] 容器
   - 调 Cloudflare Worker（中继持密钥）→ SSE 流式渲染
   - 安全：API key 不进前端；回答只渲染文本（textContent，零 XSS 注入）
   ============================================================ */
(function () {
  'use strict';

  // 默认示例问题（可经 window.AIHRQA_CONFIG.examples 覆盖）
  var DEFAULT_EXAMPLES = [
    '大厂 AI 组织重构有哪些共性打法？',
    'Pod 结构和传统科层制有什么区别？',
    'AI 落地到 HR 有哪些具体场景？',
    'DRI 机制怎么落地？',
    '人才密度模型怎么理解？',
  ];

  // 解析问答服务地址：data-qa-endpoint > window.AIHR_QA_ENDPOINT > 全局配置
  function resolveEndpoint(root) {
    var ep =
      (root && root.getAttribute('data-qa-endpoint')) ||
      (window.AIHR_QA_ENDPOINT) ||
      (window.AIHRQA_CONFIG && window.AIHRQA_CONFIG.endpoint) ||
      '';
    return (ep || '').trim();
  }

  function getExamples() {
    if (window.AIHRQA_CONFIG && Array.isArray(window.AIHRQA_CONFIG.examples)) {
      return window.AIHRQA_CONFIG.examples;
    }
    return DEFAULT_EXAMPLES;
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function buildWidget(root) {
    var endpoint = resolveEndpoint(root);

    var wrap = el('div', 'qa');

    // 头部
    var header = el('div', 'qa-header');
    header.appendChild(el('span', 'qa-header-dot'));
    header.appendChild(el('h2', 'qa-header-title', '站内知识库问答'));
    header.appendChild(el('span', 'qa-header-sub', '仅依据本站已发布文章'));
    wrap.appendChild(header);

    // 未配置：显式提示并禁用
    if (!endpoint || endpoint.indexOf('REPLACE_WITH') === 0) {
      var note = el('div', 'qa-config-note');
      note.innerHTML =
        '问答服务尚未接入。请在部署 Cloudflare Worker 后，于挂载点设置 ' +
        '<code>data-qa-endpoint="https://你的worker/ask"</code>，' +
        '或在前脚本定义 <code>window.AIHR_QA_ENDPOINT</code>。';
      wrap.appendChild(note);
      root.appendChild(wrap);
      return;
    }

    // 对话区
    var conv = el('div', 'qa-conv');
    conv.setAttribute('aria-live', 'polite');
    wrap.appendChild(conv);

    // 示例问题
    var examples = getExamples();
    if (examples.length) {
      var exWrap = el('div', 'qa-examples');
      exWrap.appendChild(el('div', 'qa-examples-label', '试试这样问：'));
      examples.forEach(function (q) {
        var chip = el('button', 'qa-chip', q);
        chip.type = 'button';
        chip.addEventListener('click', function () {
          input.value = q;
          autoGrow();
          input.focus();
        });
        exWrap.appendChild(chip);
      });
      wrap.appendChild(exWrap);
    }

    // 输入区
    var form = el('form', 'qa-form');
    form.setAttribute('autocomplete', 'off');
    var input = el('textarea', 'qa-input');
    input.rows = 1;
    input.maxLength = 500;
    input.placeholder = '就 AI+HR、组织变革、大厂实践提问……（Enter 发送，Shift+Enter 换行）';
    var send = el('button', 'qa-send', '提问');
    send.type = 'submit';
    form.appendChild(input);
    form.appendChild(send);
    wrap.appendChild(form);

    // 底部免责
    wrap.appendChild(
      el(
        'div',
        'qa-foot',
        '回答由 AI 基于本站文章检索生成，附带来源链接以供溯源；资料未覆盖时会有提示，仅供参考，不构成专业建议。'
      )
    );

    root.appendChild(wrap);

    var busy = false;

    function autoGrow() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 160) + 'px';
    }
    input.addEventListener('input', autoGrow);

    function scrollDown() {
      conv.scrollTop = conv.scrollHeight;
    }

    function showError(msg) {
      var turn = el('div', 'qa-turn');
      var a = el('div', 'qa-a');
      a.appendChild(el('div', 'qa-error', msg));
      turn.appendChild(a);
      conv.appendChild(turn);
      scrollDown();
    }

    // 流式提问
    function ask(question) {
      if (busy) return;
      busy = true;
      send.disabled = true;
      input.disabled = true;

      // 渲染这一轮：用户问题 + 空答案框
      var turn = el('div', 'qa-turn');
      turn.appendChild(el('div', 'qa-q', question));
      var a = el('div', 'qa-a');
      var aText = el('div', 'qa-a-text is-empty is-streaming');
      aText.textContent = '正在检索站内资料…';
      a.appendChild(aText);
      var sourcesBox = el('div', 'qa-sources');
      a.appendChild(sourcesBox);
      turn.appendChild(a);
      conv.appendChild(turn);
      scrollDown();

      // 隐藏示例，减少干扰
      if (exWrap && exWrap.parentNode) exWrap.style.display = 'none';

      var controller = new AbortController();

      fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ question: question }),
        signal: controller.signal,
      })
        .then(function (resp) {
          if (resp.status === 429) {
            throw new Error('提问过于频繁，请稍后再试。');
          }
          if (resp.status === 403) {
            throw new Error('当前来源未被允许访问问答服务（需在 Worker 配置 CORS 白名单）。');
          }
          if (!resp.ok) {
            throw new Error('问答服务暂不可用（HTTP ' + resp.status + '）。');
          }
          if (!resp.body) throw new Error('当前浏览器不支持流式响应。');

          var reader = resp.body.getReader();
          var decoder = new TextDecoder();
          var buf = '';
          var firstDelta = true;

          function renderSources(sources) {
            sourcesBox.innerHTML = '';
            if (!sources || !sources.length) {
              sourcesBox.appendChild(el('div', 'qa-sources-empty', '（未匹配到站内文献）'));
              return;
            }
            sourcesBox.appendChild(el('div', 'qa-sources-label', '参考来源'));
            sources.forEach(function (s) {
              var link = el('a', 'qa-source');
              link.href = s.url;
              link.target = '_blank';
              link.rel = 'noopener noreferrer';
              link.appendChild(el('span', 'qa-source-title', s.title || s.url));
              if (s.heading) link.appendChild(el('span', 'qa-source-heading', '小节：' + s.heading));
              sourcesBox.appendChild(link);
            });
          }

          function handleEvent(evt) {
            if (!evt || typeof evt !== 'object') return;
            if (evt.type === 'sources') {
              renderSources(evt.sources);
            } else if (evt.type === 'delta') {
              if (firstDelta) {
                firstDelta = false;
                aText.classList.remove('is-empty');
                aText.textContent = '';
              }
              aText.textContent += evt.text || '';
              scrollDown();
            } else if (evt.type === 'error') {
              aText.classList.remove('is-streaming');
              aText.classList.add('is-empty');
              aText.textContent = '';
              showError('回答生成出错：' + (evt.message || '未知错误'));
            } else if (evt.type === 'done') {
              if (firstDelta) {
                // 无 delta（如零召回兜底文本已通过 delta 下发；此分支仅保险）
                aText.classList.remove('is-empty');
                if (!aText.textContent) aText.textContent = '（暂无回答）';
              }
            }
          }

          function pump() {
            return reader.read().then(function (r) {
              if (r.done) {
                aText.classList.remove('is-streaming');
                return;
              }
              buf += decoder.decode(r.value, { stream: true });
              var parts = buf.split('\n\n');
              buf = parts.pop();
              for (var i = 0; i < parts.length; i++) {
                var s = parts[i].trim();
                if (!s || s.indexOf('data:') !== 0) continue;
                var payload = s.slice(5).trim();
                if (!payload) continue;
                var evt;
                try {
                  evt = JSON.parse(payload);
                } catch (e) {
                  continue;
                }
                handleEvent(evt);
              }
              scrollDown();
              return pump();
            });
          }

          return pump();
        })
        .catch(function (err) {
          aText.classList.remove('is-streaming', 'is-empty');
          aText.textContent = '';
          if (err && err.name === 'AbortError') return;
          showError(err && err.message ? err.message : '网络异常，无法连接问答服务。');
        })
        .then(function () {
          busy = false;
          send.disabled = false;
          input.disabled = false;
          input.focus();
        });
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var q = input.value.trim();
      if (!q || busy) return;
      ask(q);
      input.value = '';
      autoGrow();
    });

    // Enter 发送，Shift+Enter 换行
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });
  }

  function init() {
    var roots = document.querySelectorAll('[data-qa-widget]');
    for (var i = 0; i < roots.length; i++) {
      if (roots[i]._aihrQaReady) continue;
      roots[i]._aihrQaReady = true;
      buildWidget(roots[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
