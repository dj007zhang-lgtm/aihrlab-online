# AIHR 事件字典（唯一真名）

**建立日**：2026-09-21　**归属**：P0-1 关闭门控埋点盲区　**维护人**：AI（工程）
**唯一发送出口**：`window.aihrTrack(event, params)`，实现在 `assets/js/analytics-loader.js`
**接收方**：百度统计（hm.baidu.com），事件落在「访问分析 → 事件分析」，字段为 `_trackEvent(category, action, label, value)`

> 纪律：**禁止再造别名**。历史上 `qr_modal_open` / `gate_view` 两套名字并存、且都发往已下线的 GA4，
> 导致门控数据 12 周不可信。新增事件必须先登记到本文件，再写代码；改名必须同步本文件与所有调用点。

---

## 一、事件表

| 事件名 | 类别 category | 触发时机 | 关键参数 | 用途 |
|---|---|---|---|---|
| `gate_view` | gate | 门控区块（二维码/关注区）进入视口 | `target` | 门控曝光分母 |
| `gate_open` | gate | 用户主动打开门控（点击唤起二维码弹层） | `target:'qr_modal'` | 私域意图强度信号 |
| `qr_code_view` | gate | 二维码图片进入视口 ≥50% | — | 私域入口可见性 |
| `qr_code_click` | gate | 二维码点击或长按（含 `action:'longpress'`） | `cta_variant` | **私域转化主事件** |
| `scroll_depth` | engagement | 滚动到 25/50/75/90/100% | `value`、`label:'75%'` | 真实阅读深度 |
| `article_end_view` | engagement | 正文末尾进入视口 ≥30% | `max_scroll_depth` | 读完率 |
| `engagement_ping` | engagement | 每 30 秒（页面可见时） | `engaged_seconds` | 停留时长校准 |
| `engagement_pause` | engagement | 页面切到后台 | `total_engaged_seconds` | 有效停留 |
| `page_exit` | engagement | 离开页面 | `max_scroll_depth` | 跳出率的替代解释变量 |
| `internal_link_click` | engagement | 站内链接点击（未分类者） | `target` | 二跳意向 |
| `cta_click` | engagement | 导航栏/文中 CTA 点击 | `cta_type` | 路径选择 |
| `hub_click` | conversion | 站内点击 → `/hub/` 专题枢纽 | `target` | **P0-2 枢纽承接率** |
| `assessment_start` | conversion | 站内点击 → `/tools/` 测评 | `target` | 测评承接率 |
| `copilot_open` | conversion | 站内点击 → `/ask/` AI 问答 | `target` | Copilot 承接率 |
| `next_path_click` | conversion | 「读完这篇，下一步」模块点击 | `target_type: hub\|article\|assessment\|copilot` | **P0-2 主度量** |

## 二、参数约定

| 参数 | 含义 | 备注 |
|---|---|---|
| `page_path` | 当前页路径 | 缺省自动取 `location.pathname` |
| `target` | 被点击/曝光的对象（href 或组件 id） | 无 href 时退化为元素文本前 80 字 |
| `target_type` | 转化目标类型 | 仅 `next_path_click` 必填 |
| `label` | 百度统计事件标签 | 缺省取 `target`，截断 255 字 |
| `value` | 数值（仅数值型事件） | `scroll_depth` 用 |

## 三、采集机制

1. **统一出口**：所有事件经 `window.aihrTrack`，内部 `_hmt.push(['_trackEvent', category, action, label, value])`。
2. **声明式采集**：任何元素加 `data-track="<事件名>" data-target-type="<类型>"`，点击即上报，
   由 `analytics-loader.js` 的捕获阶段监听统一处理（P0-2 的转化模块依赖此机制，无需为每处写监听）。
3. **自动分类**：`main.js` 模块 10 对站内 `<a>` 点击按 URL 自动归类
   （`/ask/` → `copilot_open`，`/tools/` → `assessment_start`，`/hub/` → `hub_click`，其余 → `internal_link_click`）。
4. **调试**：URL 加 `?aihr_debug=1`，控制台逐条打印；本地环形缓冲 `window.__aihrEvents`（最近 50 条）供 QA 实测。

## 四、已停用的历史命名（禁止复活）

| 旧名 | 状态 | 处理 |
|---|---|---|
| `qr_modal_open` | 已废（2026-09-21） | 7 篇历史文章内联脚本已归口到 `gate_open` |
| `gate_view`（GA4 版） | 已重接 | 同名保留，但改为经 `aihrTrack` 发送 |
| `engagement-tracking.js` | 文件已停用 | 逻辑并入 `main.js` 模块 0/10，文件留空壳防 404 |

## 五、核验

- 脚本：`python3 scripts/check_analytics_coverage.py`（断言覆盖率 100%、无 gtag 残留、字典与代码无漂移）
- 人力核验：线上访问任一文章页加 `?aihr_debug=1`，控制台应出现 `gate_view` / `qr_code_view`；
  次日百度统计「事件分析」应能看到 `gate` 类事件非零。
