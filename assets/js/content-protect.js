// assets/js/content-protect.js
// 温和内容保护（不影响阅读/选中/搜索引擎抓取）：
//   1) 禁用右键菜单（爬虫不触发、不影响键盘与选区）
// 注：不设 user-select:none，避免干扰无障碍工具与抓取栈。
(function () {
  'use strict';

  // 规范文档(design-system)例外：允许自由复制参考
  if (location.pathname.indexOf('design-system') !== -1) return;

  // 禁用右键菜单
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault();
  });
})();
