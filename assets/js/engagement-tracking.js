/*
 * engagement-tracking.js — D 支柱：补齐真实互动度量，替代盲猜跳出率。
 * 依赖全局 gtag（GA4 基础片段已注入）。无 gtag 时静默退出，不报错。
 * 事件：
 *   1) scroll_depth  — 25/50/75/100% 各触发一次（被动监听，节流到阈值）
 *   2) internal_link_click — 站内链接点击（含 next-path / ilink / related），捕捉真实二跳意向
 */
(function () {
  if (typeof gtag !== "function") return;
  var depths = [25, 50, 75, 100];
  var fired = {};

  function onScroll() {
    var doc = document.documentElement;
    var scrolled = window.pageYOffset + window.innerHeight;
    var total = doc.scrollHeight;
    if (!total) return;
    var pct = (scrolled / total) * 100;
    for (var i = 0; i < depths.length; i++) {
      var d = depths[i];
      if (!fired[d] && pct >= d) {
        fired[d] = true;
        gtag("event", "scroll_depth", {
          event_category: "engagement",
          event_label: d + "%",
          value: d,
        });
      }
    }
    if (fired[100]) window.removeEventListener("scroll", onScroll);
  }
  window.addEventListener("scroll", onScroll, { passive: true });

  document.addEventListener("click", function (e) {
    var t = e.target;
    var a = t && t.closest ? t.closest("a") : null;
    if (!a) return;
    var href = a.getAttribute("href") || "";
    if (!href || href.charAt(0) === "#") return;
    var isInternal =
      href.charAt(0) === "/" ||
      href.indexOf(location.host) > -1 ||
      href.indexOf("aihrlab.online") > -1;
    if (!isInternal) return;
    gtag("event", "internal_link_click", {
      event_category: "engagement",
      event_label: href,
    });
  });
})();
