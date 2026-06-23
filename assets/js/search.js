// ============================================
// AIHR数智引擎 — 搜索系统 (Medium风格)
// 支持快捷键 Ctrl+K / ⌘+K
// 自动从 article-index.json 加载文章索引
// ============================================

(function() {
  'use strict';

  // ── 文章索引 ──
  var ARTICLES = [];
  var indexLoaded = false;

  // 计算当前页面所在目录深度，确定JSON路径
  function getBasePath() {
    var path = window.location.pathname;
    // /articles/xxx.html -> ../, / -> ./
    if (path.indexOf('/articles/') !== -1) return '../';
    return './';
  }

  // ── DOM 元素缓存 ──
  var overlay = null;
  var dialog = null;
  var input = null;
  var resultsContainer = null;
  var isOpen = false;

  // ── 初始化：先加载索引，再创建UI ──
  function init() {
    createSearchUI();
    bindEvents();
    loadIndex();
  }

  function loadIndex() {
    var base = getBasePath();
    fetch(base + 'assets/js/article-index.json')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        ARTICLES = data || [];
        indexLoaded = true;
      })
      .catch(function() {
        // 静默失败 — 索引加载失败时搜索功能不可用
        indexLoaded = true;
      });
  }

  function createSearchUI() {
    // 遮罩层
    overlay = document.createElement('div');
    overlay.className = 'search-overlay';
    overlay.addEventListener('click', close);

    // 对话框
    dialog = document.createElement('div');
    dialog.className = 'search-dialog';
    dialog.innerHTML =
      '<div class="search-input-wrap">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>' +
        '<input type="text" class="search-input" placeholder="搜索文章..." autocomplete="off" spellcheck="false">' +
        '<button class="search-close-btn" title="关闭 (Esc)">&times;</button>' +
      '</div>' +
      '<div class="search-results"><div class="search-no-results">正在加载文章索引...</div></div>' +
      '<div class="search-footer">按 <kbd>↑</kbd><kbd>↓</kbd> 导航 · <kbd>Enter</kbd> 打开 · <kbd>Esc</kbd> 关闭</div>';

    input = dialog.querySelector('.search-input');
    resultsContainer = dialog.querySelector('.search-results');
    dialog.querySelector('.search-close-btn').addEventListener('click', close);

    document.body.appendChild(overlay);
    document.body.appendChild(dialog);
  }

  function bindEvents() {
    // 全局快捷键
    document.addEventListener('keydown', function(e) {
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

    // 搜索按钮（事件委托）
    document.addEventListener('click', function(e) {
      var btn = e.target.closest('.nav-search-btn, .nav-search-btn-article, [data-open-search]');
      if (btn) {
        e.preventDefault();
        open();
      }
    });

    // 输入事件
    if (input) {
      input.addEventListener('input', debounce(function() {
        search(input.value.trim());
      }, 150));
    }
  }

  function open() {
    if (!dialog || !overlay) return;
    isOpen = true;
    overlay.classList.add('active');
    dialog.classList.add('active');
    setTimeout(function() { if (input) input.focus(); }, 100);
    document.body.style.overflow = 'hidden';
  }

  function close() {
    if (!dialog || !overlay) return;
    isOpen = false;
    overlay.classList.remove('active');
    dialog.classList.remove('active');
    currentIndex = -1;
    if (input) input.value = '';
    renderResults([]);
    document.body.style.overflow = '';
  }

  function toggle() { isOpen ? close() : open(); }

  // ── 搜索逻辑 ──
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
        results.push({
          title: a.title,
          url: a.url,
          category: a.category || '',
          score: ts !== -1 ? ts : 1000 + cs
        });
      }
    }

    results.sort(function(a, b) { return a.score - b.score; });
    renderResults(results.slice(0, 12));
  }

  function renderResults(results) {
    if (!resultsContainer) return;
    if (results.length === 0) {
      resultsContainer.innerHTML = '<div class="search-no-results">未找到相关文章</div>';
      return;
    }

    // 确定链接前缀：在文章页需要加 "../"
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

  // ── 键盘导航 ──
  var currentIndex = -1;
  function navigateResults(e) {
    e.preventDefault();
    var items = resultsContainer.querySelectorAll('.search-result-item');
    if (items.length === 0) return;

    if (e.key === 'ArrowDown') {
      currentIndex = Math.min(currentIndex + 1, items.length - 1);
    } else if (e.key === 'ArrowUp') {
      currentIndex = Math.max(currentIndex - 1, -1);
    } else if (e.key === 'Enter') {
      if (currentIndex >= 0 && items[currentIndex]) {
        items[currentIndex].click();
      }
      return;
    }

    for (var i = 0; i < items.length; i++) {
      items[i].style.background = i === currentIndex ? 'var(--bg-warm)' : '';
    }
  }

  // ── 工具函数 ──
  function debounce(fn, delay) {
    var timer = null;
    return function() {
      clearTimeout(timer);
      timer = setTimeout(fn, delay);
    };
  }

  // ── 启动 ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
