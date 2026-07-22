// assets/js/content-protect.js
// 温和内容保护（不影响阅读/选中/搜索引擎抓取）：
//   1) 禁用右键菜单（爬虫不触发、不影响键盘与选区）
//   2) 复制时自动追加出处（不阻止复制，仅带署名）
//   3) 文章页(<article>)动态注入原创署名块
// 注：不设 user-select:none，避免干扰无障碍工具与抓取栈。
(function () {
  'use strict';

  // 规范文档(design-system)例外：允许自由复制参考
  if (location.pathname.indexOf('design-system') !== -1) return;

  var SITE = 'aihrlab.online';
  var BRAND = 'AIHR数智引擎';

  // 1) 禁用右键菜单
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault();
  });

  // 2) 复制时追加出处（不阻止复制，仅带署名）
  document.addEventListener('copy', function (e) {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed) return; // 未选中文本不处理
    var text = sel.toString();
    if (!text) return;
    var footer = '\n\n—— 本文转载自 ' + BRAND + '（' + SITE + '），转载请注明出处。';
    try {
      if (e.clipboardData && e.clipboardData.setData) {
        e.clipboardData.setData('text/plain', text + footer);
        e.preventDefault();
      }
    } catch (err) { /* 不支持 clipboardData 时放行原生复制 */ }
  });

  // 3) 文章页注入原创署名块（仅 <article> 容器存在时，防重复）
  function injectDeclare() {
    var article = document.querySelector('article');
    if (!article || article.querySelector('.article-declare')) return;
    var block = document.createElement('div');
    block.className = 'article-declare';
    block.setAttribute('role', 'note');
    block.innerHTML = '<p>本文为 <strong>' + BRAND + '</strong> 原创内容，首发于 ' +
      '<a href="https://' + SITE + '" rel="nofollow">' + SITE + '</a>。' +
      '转载请注明出处，非授权请勿用于商业用途。</p>';
    article.appendChild(block);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectDeclare);
  } else {
    injectDeclare();
  }
})();
