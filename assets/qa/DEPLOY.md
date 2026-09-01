# AIHR 站内智能问答 · MVP 部署与运维说明

> 零成本栈：静态前端（GitHub Pages）+ 无服务器中继（Cloudflare Workers）+ 构建期本地切 chunk（纯 BM25，免向量库）。
> 安全红线（参考 @wshuyi 长文三道防线）：API key 仅存 Worker 环境变量、中继持密钥、公网必须 CORS 白名单 + 配额上限。

---

## 一、组件清单

| 文件 | 作用 | 是否进仓库 |
|------|------|-----------|
| `assets/qa/worker.js` | Cloudflare Worker 中继：拉 KB → BM25 召回 → 组装系统提示词 → SSE 流式转发 agnes-ai | ✅ |
| `assets/qa/wrangler.toml` | Worker 部署配置（明文变量 + 路由） | ✅ |
| `assets/qa/kb.json` | 知识库（222 篇 / 2089 chunk / 约 64 万字 / 2.2MB），由 ETL 生成 | ✅ |
| `assets/qa/kb.meta.json` | 知识库统计元信息 | ✅ |
| `assets/qa/widget.js` | 独立页挂件逻辑：SSE 流式渲染、引用链接、未收录优雅提示 | ✅ |
| `assets/qa/widget.css` | 挂件样式（对齐站点设计系统，浅/深色自动适配） | ✅ |
| `assets/js/search.js` | 全站搜索框双模式（搜文章 / 问 AI）：问 AI 模式复用同一 SSE 契约，答案+引用内联在弹窗结果区 | ✅ |
| `assets/js/qa-config.js` | 全局问答端点配置（`window.AIHR_QA_ENDPOINT`），发布时填 Worker 完整 /ask 地址；已自动注入全站 `<head>` | ✅ |
| `ask/index.html` | 独立问答页（已去简介，纯 copilot 挂件，复用全局端点） | ✅ |
| `scripts/build_qa_kb.py` | 知识库 ETL：把 `articles/*.html` 切成 chunk 输出 kb.json | ✅ |
| `assets/qa/test_retrieval.mjs` | 离线检索校验（10 用例，域问题全命中、域外弱召回） | ✅ |
| `AGNES_API_KEY` | agnes-ai API key（Secret） | ❌ 仅 Secret |

---

## 二、部署步骤

### 1. 准备密钥
```bash
cd site-migrated/assets/qa
npx wrangler secret put AGNES_API_KEY
# 交互粘贴 agnes-ai 平台申请的 key（sk-...）
```

### 2. 核对 wrangler.toml 变量
- `KB_URL`：默认 `https://aihrlab.online/assets/qa/kb.json`（已发布即可用）。
- `ALLOWED_ORIGINS`：**必须包含问答页实际部署的来源**。本地预览用 `http://localhost:...` 或 `http://127.0.0.1:...` 时需临时加进去；上线后只留 `aihrlab.online` 与 `www.aihrlab.online`。
- `AGNES_MODEL`：`agnes-2.0-flash`（默认；需要更强推理可改 `agnes-2.5-pro`）。
- 配额：`RATE_LIMIT_PER_MIN`（20/分/IP）、`DAILY_TOKEN_BUDGET`（20 万 token/日，≈ 数十元上限）。

### 3. 部署
```bash
npx wrangler deploy
# 成功返回 https://aihr-qa-relay.<你的子域>.workers.dev
```

### 4. 接通前端（一次填全站生效）
问答端点统一配置在 `assets/js/qa-config.js` 的 `window.AIHR_QA_ENDPOINT`，该文件已自动注入每个页面 `<head>`，因此**全站搜索框的「问 AI」入口与 `ask/` 独立页共用同一端点**，填一次即可：

```js
// assets/js/qa-config.js
window.AIHR_QA_ENDPOINT = "https://aihr-qa-relay.<子域>.workers.dev/ask";
```

- 端点必须是**完整 /ask 地址**（Worker 路由固定为 `/ask`）。
- 留空（默认）时：搜索框「问 AI」显示「暂未接入」提示、不报错；`ask/` 页挂件显示「尚未接入」。`AIHR_QA_ENDPOINT` 与 `data-qa-endpoint` 二选一即可（全局优先用 qa-config.js）。
- 两处前端共用契约：`POST {question}` → SSE 事件 `sources | delta(text) | done | error`。

### 5. 全站入口（已默认启用）
`search.js` 已在每个页面挂载双模式搜索框：默认「搜文章」，切到「问 AI」即 copilot，答案带引用内联在弹窗结果区；样式作用域限制在弹窗内（零全局 CSS 改动、零新模板注入）。无需再手动放置挂件容器。独立 `ask/` 页保留完整挂件形态，供需要多轮深聊的读者使用。

### 6. 健康检查（验证部署）
```bash
curl https://<你的worker>/health
# 返回 {"ok":true,"articles":222,"chunks":2089,"loadedAt":...}
```

---

## 三、知识库更新（发新文后）

每次发布新文章后，重建 KB 并提交，使问答覆盖新内容：
```bash
python3 scripts/build_qa_kb.py     # 重新生成 assets/qa/kb.json + kb.meta.json
git add assets/qa/kb.json assets/qa/kb.meta.json && git commit -m "chore: rebuild QA KB"
```
Worker 端有 1 小时内存缓存（TTL），重建后最迟 1 小时生效；紧急可 `wrangler deploy` 强制冷启动。

> 建议把「发新文 → 重建 KB → 提交」写进 `scripts/publish.py` 的发布流程，或在发稿自动化里加一步 ETL，避免问答与站点内容脱节。

---

## 四、费用估算

- Cloudflare Workers 免费套餐（每日 10 万次请求、CPU 限额）足够本 MVP；BM25 在 Worker 内计算，几乎零额外开销。
- agnes-ai `agnes-2.0-flash` 输出定价约 \$0.15 / 1M tokens（以平台当时定价为准，flash 档常有免费额度）。`DAILY_TOKEN_BUDGET=200000` 即每日上限约 200K 输出 token ≈ 数十元（即便触顶也封顶）。检索召回只在 Worker 内做，不消耗 agnes-ai token。

---

## 五、正见正念与质量门约束

1. **零虚构**：Worker 系统提示词硬规则——只能依据召回片段作答，资料未覆盖必须回「本站资料暂未收录该问题的相关内容」，严禁编造事实/数据/结论。
2. **可溯源**：回答附 2–4 条参考链接（标题：URL），前端渲染为可点击来源卡片。
3. **不营销、不 AI 腔**：提示词要求简体中文、专业克制、不渲染焦虑、不用对称排比等 AI 腔。
4. **域外问题兜底**：纯词法 BM25 对域外问题（如「今天北京天气」）也会弱召回，但**不靠硬闸门误杀真问题**——交由 LLM + 提示词兜底（弱/无关时答「未收录」）。离线测试已确认：域问题最佳分 19–44 命中正确文章，域外问题 8–15 明显偏弱。
5. **成本控制**：日预算 + 限速双护栏，避免被刷爆。

---

## 六、本地联调（不消耗 agnes-ai）

`test_retrieval.mjs` 复用 worker 的 tokenize/BM25 逻辑离线验证召回质量：
```bash
node assets/qa/test_retrieval.mjs
# 期望：10/10 通过（域问题命中预期文章，域外问题弱召回）
```

前端联调：用任意静态服务器在 `site-migrated/` 起服务，临时把 `ALLOWED_ORIGINS` 加 `http://127.0.0.1:xxxx`，并把 `AIHR_QA_ENDPOINT` 指向已部署 Worker，即可在 `ask/index.html` 实测 SSE 流式与引用渲染。
