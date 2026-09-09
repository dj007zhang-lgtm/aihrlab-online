/*
 * analytics-loader.js — 仅生产域名才上报统计。
 * 目的：排除本地预览 (127.0.0.1 / localhost) 与沙箱/其他环境对流量数据的污染。
 * 命中白名单域名才注入百度统计；否则仅留无副作用桩，避免埋点调用报错。
 *
 * 注：GA4（googletagmanager.com）在中国大陆被墙且长期无数据回收，已于 2026-09-08 弃用，
 * 改为仅保留百度统计（hm.baidu.com，CN 可达）。
 */
(function () {
  "use strict";

  var PROD_HOSTS = ["aihrlab.online", "www.aihrlab.online"];
  var host = (location.hostname || "").toLowerCase();
  var isProd = PROD_HOSTS.indexOf(host) !== -1;

  // 非生产环境：提供无副作用的桩，确保 engagement-tracking 等埋点调用不报错
  if (!isProd) {
    window._hmt = window._hmt || [];
    return;
  }

  // ===== 生产环境：真实上报（仅百度统计，CN 可达）=====

  // 百度统计
  window._hmt = window._hmt || [];
  (function () {
    var hm = document.createElement("script");
    hm.src = "https://hm.baidu.com/hm.js?b53ffd054b55836f535892622f1e4cc5";
    var s = document.getElementsByTagName("script")[0];
    s.parentNode.insertBefore(hm, s);
  })();
})();
