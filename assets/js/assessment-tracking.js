/*
 * assessment-tracking.js — 测评完成匿名埋点（2026-11-05）
 * ---------------------------------------------------------------------------
 * 目的：把「有多少人做完测评、做出什么类型」变成可读的匿名数据，零后端、零数据库。
 *
 * 数据边界（红线，不得放宽）：
 *   只上报「测评 ID + 结果类别」两个匿名标签。
 *   不采答卷、不采各题分数、不采总分、不采用户标识、不采任何输入框内容。
 *   结果类别统一清洗为不含 emoji / 标点 / 空白的短字符串（保留中英文与数字）。
 *
 * 上报格式：
 *   window.aihrTrack('assessment_complete', {
 *     label: '<测评ID>:<结果类别>',   // 百度统计「事件分析」按 label 分组即得完成次数与类型分布
 *     target: '<测评ID>',
 *     result_type: '<结果类别>'
 *   })
 *
 * 幂等口径：
 *   同一浏览器会话内，同一「测评 ID + runKey」只计一次，防止刷新结果页 / 重复点
 *   结果按钮造成虚高。runKey 由调用点在「重新抽一次 / 重做一次」时改变；
 *   未传 runKey 时退化为结果类别（同会话同类型重做不重复计入）。
 *   sessionStorage 不可用时降级为「每次都上报」，宁可不多算也不静默丢事件。
 *
 * 事件字典（唯一真名）：reports/events.md
 * 依赖：assets/js/analytics-loader.js 必须先于本文件加载。
 */
(function () {
  "use strict";

  var EVENT = "assessment_complete";
  var PREFIX = "aihr_ac_v1:";

  /* 只保留 CJK 汉字、ASCII 字母数字、下划线与连字符；emoji / 标点 / 空白一律剔除 */
  function clean(s) {
    try {
      s = String(s == null ? "" : s);
    } catch (e) {
      return "unknown";
    }
    var out = s.replace(/[^\u4e00-\u9fa5A-Za-z0-9_-]/g, "").slice(0, 32);
    return out || "unknown";
  }

  function dedupeKey(id, category, runKey) {
    var token = (runKey === undefined || runKey === null || runKey === "") ? category : clean(runKey);
    return PREFIX + id + ":" + token;
  }

  function alreadySent(k) {
    try {
      return !!(window.sessionStorage && window.sessionStorage.getItem(k));
    } catch (e) {
      return false;
    }
  }

  function markSent(k) {
    try {
      if (window.sessionStorage) window.sessionStorage.setItem(k, "1");
    } catch (e) {}
  }

  /**
   * 上报一次测评完成。
   * @param {string} id       测评 ID，如 disc / holland / mbti
   * @param {string} type     匿名结果类别；无天然类别时传 'completed'
   * @param {string} [runKey] 本次测评的会话内唯一标记，用于允许「再测一次」另计
   * @returns {boolean} 是否真实发送
   */
  function aihrAssessmentComplete(id, type, runKey) {
    try {
      if (typeof window.aihrTrack !== "function") return false;

      var aid = clean(id);
      var category = clean(type === undefined || type === null || type === "" ? "completed" : type);
      var label = aid + ":" + category;

      var k = dedupeKey(aid, category, runKey);
      if (alreadySent(k)) return false;
      markSent(k);

      window.aihrTrack(EVENT, {
        label: label,
        target: aid,
        result_type: category,
        page_path: (window.location && window.location.pathname) || ""
      });
      return true;
    } catch (e) {
      return false;
    }
  }

  window.aihrAssessmentComplete = aihrAssessmentComplete;
})();
