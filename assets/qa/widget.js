/* ============================================================
   AIHR 站内问答挂件 · widget.js
   - 纯前端，零依赖；直接注入任意页面的 [data-qa-widget] 容器
   - 调 Cloudflare Worker（中继持密钥）→ SSE 流式渲染
   - 安全：API key 不进前端；回答只渲染文本（textContent，零 XSS 注入）
   - 健壮性：429 / 服务繁忙时自动重试（最多 3 次，间隔 3 秒），不白屏
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

  function escapeHTML(s) {
    return String(s).replace(/[&<>"]/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch];
    });
  }

  // 把正文里的 [N] 引用渲染成上标链接；其余文本做 HTML 转义。
  function renderCitations(rawText) {
    var out = '';
    var last = 0;
    var re = /\[(\d+)\]/g;
    var m;
    while ((m = re.exec(rawText)) !== null) {
      out += escapeHTML(rawText.slice(last, m.index));
      var n = m[1];
      out += '<sup class="qa-cite"><a href="#qa-ref-' + n + '" class="qa-cite-link">[' + n + ']</a></sup>';
      last = m.index + m[0].length;
    }
    out += escapeHTML(rawText.slice(last));
    // 保留后端下发的换行（降级作答为结构化文本，含段落与 ■ 标题）
    return out.replace(/\n/g, '<br>');
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
        '问答服务尚未接入。请在部署腾讯云 SCF 后端后，于挂载点设置 ' +
        '<code>data-qa-endpoint="https://qa.aihrlab.online/ask"</code>，' +
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

    // 判断服务返回的错误是否可重试（429 / 限流 / 服务繁忙）
    function isRetryableMsg(msg) {
      if (!msg) return false;
      return /429|较忙|限流|服务.*忙|AI 服务|稍后|retry|繁忙/i.test(msg);
    }

    function finalize() {
      busy = false;
      send.disabled = false;
      input.disabled = false;
      input.focus();
    }

    // 多轮对话：维护对话历史，供追问时回传 Worker 维持上下文
    var conversation = [];
    var MAX_HISTORY = 10; // 最近 10 轮

    // 流式提问（含自动重试：429 / 服务繁忙时 3 秒后自动重发，最多 3 次）
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
      aText.textContent = '正在思考…';
      a.appendChild(aText);
      var sourcesBox = el('div', 'qa-sources');
      a.appendChild(sourcesBox);
      turn.appendChild(a);
      conv.appendChild(turn);
      scrollDown();

      // 隐藏示例，减少干扰
      if (exWrap && exWrap.parentNode) exWrap.style.display = 'none';

      var retryCount = 0;
      var MAX_RETRY = 3;
      var RETRY_DELAY_MS = 3000;
      var controller = null;
      var scheduledRetry = false;

      function scheduleRetry() {
        scheduledRetry = true;
        retryCount++;
        if (controller) controller.abort();
        aText.classList.add('is-empty', 'is-streaming');
        aText.textContent =
          'AI 服务较忙，' + RETRY_DELAY_MS / 1000 + ' 秒后自动重试（第 ' + retryCount + ' 次）…';
        scrollDown();
        setTimeout(attempt, RETRY_DELAY_MS);
      }

      function attempt() {
        scheduledRetry = false;
        controller = new AbortController();

        // 多轮：把当前轮之前的历史回传 Worker（最近 MAX_HISTORY 轮）
        var historyPayload = conversation
          .slice(-MAX_HISTORY * 2)
          .map(function (h) {
            return { role: h.role, text: h.text };
          });

        fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: JSON.stringify({ question: question, history: historyPayload }),
          signal: controller.signal,
        })
          .then(function (resp) {
            if (resp.status === 429) {
              throw { retryable: true, message: 'AI 服务当前请求量较大（429），正在自动重试…' };
            }
            if (resp.status === 403) {
              throw {
                retryable: false,
                message: '当前来源未被允许访问问答服务（需在 Worker 配置 CORS 白名单）。',
              };
            }
            if (resp.status >= 500) {
              throw {
                retryable: true,
                message: '问答服务暂时不稳定（HTTP ' + resp.status + '），正在自动重试…',
              };
            }
            if (!resp.ok) {
              throw { retryable: false, message: '问答服务暂不可用（HTTP ' + resp.status + '）。' };
            }
            if (!resp.body) throw { retryable: false, message: '当前浏览器不支持流式响应。' };

            var reader = resp.body.getReader();
            var decoder = new TextDecoder();
            var buf = '';
            var firstDelta = true;
            var pendingSources = null;
            var sourcesRendered = false;

            function renderSources(sources) {
              sourcesBox.innerHTML = '';
              if (!sources || !sources.length) {
                sourcesBox.appendChild(el('div', 'qa-sources-empty', '（未匹配到站内文献）'));
                return;
              }
              sourcesBox.appendChild(el('div', 'qa-sources-label', '参考来源'));
              sources.forEach(function (s, idx) {
                var link = el('a', 'qa-source');
                link.href = s.url;
                link.id = 'qa-ref-' + (idx + 1);
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.title = s.url;
                link.appendChild(el('span', 'qa-source-idx', '[' + (idx + 1) + '] '));
                link.appendChild(el('span', 'qa-source-title', s.title || s.url));
                if (s.heading) link.appendChild(el('span', 'qa-source-heading', '小节：' + s.heading));
                sourcesBox.appendChild(link);
              });
              sourcesRendered = true;
            }

            function maybeRenderSources() {
              if (!sourcesRendered && pendingSources) renderSources(pendingSources);
            }

            // 累积原始文本，每次重新渲染以保证 [N] 上标链接完整
            var answerRaw = '';

            function handleEvent(evt) {
              if (!evt || typeof evt !== 'object') return;
              if (evt.type === 'sources') {
                // 答案先于来源：先缓存，等第一个 delta 出来再一起渲染
                pendingSources = evt.sources || [];
              } else if (evt.type === 'delta') {
                if (firstDelta) {
                  firstDelta = false;
                  aText.classList.remove('is-empty');
                  answerRaw = '';
                  maybeRenderSources();
                }
                answerRaw += evt.text || '';
                aText.innerHTML = renderCitations(answerRaw);
                scrollDown();
              } else if (evt.type === 'error') {
                // 流中途出错：可重试则自动重试（不立即报错），否则致命报错
                var m = evt.message || '未知错误';
                if (isRetryableMsg(m) && retryCount < MAX_RETRY) {
                  scheduleRetry();
                  return;
                }
                aText.classList.remove('is-streaming');
                aText.classList.add('is-empty');
                aText.textContent = '';
                maybeRenderSources();
                showError('回答生成出错：' + m);
              } else if (evt.type === 'done') {
                maybeRenderSources();
                if (firstDelta) {
                  // 无 delta（如零召回兜底文本已通过 delta 下发；此分支仅保险）
                  aText.classList.remove('is-empty');
                  if (!aText.textContent) aText.textContent = '（暂无回答）';
                }
                // 多轮：把这一轮问答存入历史（供后续追问维持上下文）。done 仅触发一次，重试不会重复 push。
                if (!turn._stored && answerRaw) {
                  turn._stored = true;
                  conversation.push({ role: 'user', text: question });
                  conversation.push({ role: 'assistant', text: answerRaw });
                  if (conversation.length > MAX_HISTORY * 2) {
                    conversation = conversation.slice(-MAX_HISTORY * 2);
                  }
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
            if (err && err.name === 'AbortError') return; // 主动 abort（重试流程），不报错
            var retryable = err && err.retryable;
            var msg = err && err.message ? err.message : '网络异常，无法连接问答服务。';
            if (retryable && retryCount < MAX_RETRY) {
              scheduleRetry();
              return;
            }
            aText.classList.remove('is-streaming', 'is-empty');
            aText.textContent = '';
            showError(msg);
          })
          .then(function () {
            // 仅在确定不再重试时释放输入（重试期间 busy 保持）
            if (!scheduledRetry) finalize();
          });
      }

      attempt();
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
