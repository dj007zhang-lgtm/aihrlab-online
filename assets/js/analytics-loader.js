/*
 * analytics-loader.js — 统计装载 + 全站统一事件层（aihrTrack）
 * ---------------------------------------------------------------------------
 * 一、装载职责（原有）
 *   仅生产域名（aihrlab.online）注入百度统计；本地预览/沙箱只留无副作用桩，避免污染数据。
 *   GA4（googletagmanager.com）在中国大陆被墙且长期无数据回收，已于 2026-09-08 弃用。
 *
 * 二、事件层职责（2026-09-21 新增，P0-1 关闭门控埋点盲区）
 *   GA4 下线后，main.js / engagement-tracking.js / 7 篇历史文章里的 gtag('event', ...)
 *   原样保留 —— typeof gtag === 'undefined' 时静默空转，事件零采集。这是「私域漏斗不可观测」
 *   的工程根因：不是没埋点，是埋点全发往一个已下线的接收方。
 *   本文件是全站唯一持有「统计接收方」知识的地方，因此事件层也放在这里：
 *     window.aihrTrack(event, params)
 *       → 百度统计事件 _hmt.push(['_trackEvent', category, action, label, value])
 *       → 本地环形缓冲 window.__aihrEvents（QA 实测可读，最多 50 条）
 *       → 若未来重新接入 gtag，仍双发，调用点不用改
 *   事件字典（唯一真名，禁止再造别名）：reports/events.md
 *   调试：URL 加 ?aihr_debug=1 时控制台逐条打印。
 *
 * 三、data-track 统一采集
 *   任何元素加 data-track="<事件名>" data-target-type="<类型>"，点击即上报，
 *   避免每处各写一份监听器（P0-2 的「读完这篇，下一步」模块即依赖此机制）。
 */
(function () {
  "use strict";

  var PROD_HOSTS = ["aihrlab.online", "www.aihrlab.online"];
  var host = (location.hostname || "").toLowerCase();
  var isProd = PROD_HOSTS.indexOf(host) !== -1;

  /* ===== 事件字典：事件名 → 百度统计事件类别（唯一真名，禁止别名） ===== */
  var CAT = {
    // 门控 / 私域意图
    gate_view: "gate",
    gate_open: "gate",
    qr_code_view: "gate",
    qr_code_click: "gate",
    // 阅读互动
    scroll_depth: "engagement",
    article_end_view: "engagement",
    engagement_ping: "engagement",
    engagement_pause: "engagement",
    page_exit: "engagement",
    internal_link_click: "engagement",
    cta_click: "engagement",
    // 转化路径（P0-2）
    next_path_click: "conversion",
    copilot_open: "conversion",
    assessment_start: "conversion",
    hub_click: "conversion"
  };

  var DEBUG = false;
  try {
    DEBUG = /[?&]aihr_debug=1/.test(location.search);
  } catch (e) {}

  window.__aihrEvents = window.__aihrEvents || [];

  function aihrTrack(event, params) {
    params = params || {};
    if (!params.page_path) {
      try { params.page_path = location.pathname; } catch (e) { params.page_path = ""; }
    }
    var category = CAT[event] || "aihr";
    var label = params.label || params.target || params.event_label || params.page_path || "";
    try { label = String(label).slice(0, 255); } catch (e) { label = ""; }

    try {
      window._hmt = window._hmt || [];
      var arr = ["_trackEvent", category, event, label];
      if (typeof params.value === "number" && isFinite(params.value)) {
        arr.push(Math.round(params.value));
      }
      window._hmt.push(arr);
    } catch (e) {}

    try {
      window.__aihrEvents.push({ event: event, params: params, t: Date.now() });
      if (window.__aihrEvents.length > 50) window.__aihrEvents.shift();
    } catch (e) {}

    if (DEBUG) {
      try { console.log("[aihrTrack]", event, params); } catch (e) {}
    }

    /* 若未来重新接入 gtag，此处双发，调用点无需改动 */
    if (typeof window.gtag === "function") {
      try { window.gtag("event", event, params); } catch (e) {}
    }
    return true;
  }

  aihrTrack.CAT = CAT;
  aihrTrack.EVENTS = Object.keys(CAT);
  window.aihrTrack = aihrTrack;

  /* data-track 统一采集：带该属性的元素点击即上报（next_path_click 等） */
  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest ? e.target.closest("[data-track]") : null;
    if (!el) return;
    var name = el.getAttribute("data-track") || "";
    if (!name) return;
    var href = el.getAttribute("href") || "";
    aihrTrack(name, {
      target: href,
      target_type: el.getAttribute("data-target-type") || "",
      label: href || (el.textContent || "").trim().slice(0, 80)
    });
  }, true);

  /* ===== 非生产环境：提供无副作用桩，确保埋点调用不报错 ===== */
  if (!isProd) {
    window._hmt = window._hmt || [];
    return;
  }

  /* ===== 生产环境：真实上报（仅百度统计，CN 可达） ===== */
  window._hmt = window._hmt || [];
  (function () {
    var hm = document.createElement("script");
    hm.src = "https://hm.baidu.com/hm.js?b53ffd054b55836f535892622f1e4cc5";
    var s = document.getElementsByTagName("script")[0];
    s.parentNode.insertBefore(hm, s);
  })();
})();
