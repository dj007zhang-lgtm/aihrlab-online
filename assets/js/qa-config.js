/* AIHR 站内问答（copilot）端点配置
 * -------------------------------------------------------------
 * 部署时把 Cloudflare Worker 的完整 /ask 地址填到 AIHR_QA_ENDPOINT。
 * 例如：window.AIHR_QA_ENDPOINT = "https://aihr-qa.your-subdomain.workers.dev/ask";
 * 该值与 /ask/ 独立页挂件共用同一契约（POST {question}，SSE 回传 sources/delta/done/error）。
 *
 * 留空（""）时：
 *   - 全站搜索框的「问 AI」模式显示「暂未接入」提示，不报错；
 *   - /ask/ 独立页的挂件读自身的 data-qa-endpoint，互不影响。
 *
 * 该文件由 scripts 在发布前统一注入到每个页面 <head>，
 * 让搜索框里的 copilot 入口在所有文章页、资源页、测评页都可用。
 */
(function () {
  'use strict';
  // 已存在则不覆盖（允许页面级 meta 或内联覆盖优先）。
  if (window.AIHR_QA_ENDPOINT && window.AIHR_QA_ENDPOINT !== '') return;
  // 生产端点（Cloudflare Worker /ask 地址）
  window.AIHR_QA_ENDPOINT = "https://aihr-qa-relay.dj007zhang.workers.dev/ask";
})();
