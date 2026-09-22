/*
 * engagement-tracking.js — 已停用（2026-09-21，P0-1）
 * ---------------------------------------------------------------------------
 * 停用原因：本文件从未被任何页面引用（全站 0 页加载），且其逻辑以
 *   `if (typeof gtag !== "function") return;` 开头 —— GA4 于 2026-09-08 弃用后，
 *   即便被引用也会在第一行走空，scroll_depth / internal_link_click 从未真正上报过一次。
 *
 * 功能已并入两处，不要再往本文件加代码：
 *   1) scroll_depth / article_end_view / engagement_ping / page_exit
 *      → assets/js/main.js 模块 0（已由 trackEvent → window.aihrTrack 重新接线）
 *   2) 站内二跳分类（copilot_open / assessment_start / hub_click / internal_link_click）
 *      → assets/js/main.js 模块 10
 *   3) 事件统一出口 window.aihrTrack（百度统计 _hmt）
 *      → assets/js/analytics-loader.js
 *
 * 事件字典（唯一真名）：reports/events.md
 * 保留本文件仅为避免历史引用 404；下一个清理窗口可删除。
 */
