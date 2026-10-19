# AIHR 数智引擎 · 产品架构与实现规划（v2 锁定版）

> 版本：v2 · 2026-10-17 · 状态：**主理人/PM 锁定，按阶段执行**
> 真源：`reports/PRODUCT-ARCHITECTURE-v2-2026-10-17.md`
> 基线：`reports/baseline-2026-10-17.json`（`python3 scripts/freeze_baseline.py` 可复跑）
> 上位文档：`reports/architecture-target-state-spec.md`（2026-08-31，v1）、`reports/architecture-unification-spec.md`（2026-08-11）
> 关系：本文档是 v1 的**收口与冻结版**。v1 定义终点态愿景，本文档锁定「事实标准 + 执行路径」。二者冲突时以本文档为准，并在 §6.1 逐条说明变更。

---

## 0. 本文档的地位与变更纪律

### 0.1 为什么需要「锁定版」

v1（08-31）提出了终点态与「C 混合：新内容走集合/MDX」的迁移深度。**该路线的 Astro/MDX 部分从未落地**（现测：无 `astro.config`、无 `content/`、无 `src/`、无 `package.json`），实际在跑的是另一条事实路线。愿景文档与事实标准长期并存，导致每轮开工都在重新讨论「要不要重构」——这是本项目最大的隐性成本。

本文档的目的：**把事实标准升格为正式标准并冻结**，从此只在冻结清单内演进。

### 0.2 变更四问（任何变更提出时必须先答，答不出就不做）

| 问题 | 要求 |
|---|---|
| ① 原方案**在哪一点上失效** | 必须给出可复现的观测（命令 + 输出），不许用「不够优雅」「不够现代」 |
| ② 新方案**收益是什么** | 必须挂到具体 KPI 或具体读者任务，不许挂到「架构清洁度」这类内部审美 |
| ③ **迁移成本** | 受影响文件数、需改脚本数、预计批次、回归风险等级 |
| ④ **影响范围** | 哪些 URL / 索引 / 外链 / 已发布内容会被波及，回滚方案是什么 |

四问答完且收益 > 成本，才进入执行；执行前更新本文档对应章节。

---

## 1. 产品定位（锁定，不再讨论）

| 项 | 内容 |
|---|---|
| 使命 | AI 时代 HR 与组织变革领域最可信的中文知识中枢：被从业者日常依赖，也被生成式引擎稳定引用 |
| 站点性质 | **独立信息与知识载体**，不是公众号引流前端，不是变现渠道 |
| 价值三域 | VD1 AI 时代 HR 专业知识 / VD2 AI 转型与 AI Native 组织方法论 / VD3 大厂转型实践案例 |
| 增长主引擎 | **内容段位 + 产品化**，不是分发管道工程 |
| 非目标（红线） | 不带付费墙/电商/变现钩子；**不撮合、不抓 JD、不处理简历**；不在线生成个人画像；人格测试分不进能力测评 |
| 公众号 | 转化是顺带结果，不得反向绑架站点架构 |

---

## 2. 现状基线（2026-10-17 现测，非记忆）

复跑命令：`python3 scripts/freeze_baseline.py`（只读）／对比：`--diff reports/baseline-2026-10-17.json`

| 指标 | 值 | 说明 |
|---|---|---|
| HTML 文件总数 | 419 | 全站 |
| 可索引 / noindex | 361 / 58 | noindex 中 55 个是**跳转合并壳**（刻意保留，禁止批量下线） |
| sitemap URL | 341 | `build_sitemap.py` 生成 |
| `article-index.json` | 257 条 | 字段：title/url/category/date/tags |
| Copilot `kb.json` articles_indexed | 246 | 与 257 差 11，**P1 待核**（可能是口径差，非断言缺陷） |
| `/brief/` | 2 页（index + 001 期） | **进 sitemap = 0** |
| 导航一致性 | 344 页含导航，**20 页偏离** | 见 §3.3 |
| 真实孤儿页 | 9 | 其中 6 个为内部资产/验证页/草稿，见 §3.3 |

---

## 3. 信息架构 IA（锁定）

### 3.1 主导航固定 6 项（不可增减，除非走变更四问）

| 序 | 标签 | 目标 | 读者任务 |
|---|---|---|---|
| 1 | 首页 | `/index.html` | 我是谁、从哪进 |
| 2 | 文章 | `/articles/index.html` | 读懂 AI+HR 发生了什么 |
| 3 | 资源库 | `/resources/index.html` | 拿到明天能用的资产 |
| 4 | 测评 | `/tools/index.html` | 测我自己 / 我的组织 |
| 5 | 策展 | **`/brief/index.html`**（P1 变更，见 §3.4） | 这段时间该在意什么 |
| 6 | 关于 | `/about.html` | 谁在做、依据什么 |

附加项：`AI搜索`（⌘K，双 tab：搜文章 / 问 AI）— 是工具不是版块，不占版块位。

### 3.2 版块角色与入口（二级版块不进主导航，但必须有规范入口）

| 版块 | 角色 | 规范入口 |
|---|---|---|
| `articles/` | 认知主航道（257 可索引） | 主导航 + 首页 + 分类/标签页 |
| `hub/`（11） | 专题枢纽，按主题串文 | 首页「专题」区 + 文章页延伸阅读 |
| `resources/`（25） | 知识中枢（模板/SOP/卡/清单） | 主导航 |
| `tools/`（10） | 测评唯一入口 | 主导航 |
| `assessments/`（5） | **测评方法论与选型（内容页）**，非第二入口 | 从 `tools/index.html` 与首页进入（P1 收敛文案） |
| `brief/` | 策展：信号线台账 | 主导航（P1 归位） |
| `glossary/` | 术语词典 | 首页 + 文章内术语链接 |
| `products/`（4） | 深度手册（体系化长内容） | 首页 + 相关文章挂接 |
| `compare/` | 对比页 | 相关主题枢纽挂接 |
| `projects/` | 能力标准项目（CM-2026） | `bridge/` 转为该项目对外页（P1） |
| `ask/` | AI 问答（SCF） | ⌘K + 首页 |

### 3.3 IA 缺陷清单（P1 已清零，实测结果见 §7 P1 行）

| 缺陷 | 现测 | 处置 |
|---|---|---|
| 主航道索引页无导航 | `articles/index.html` NO_NAV | 补标准导航 |
| 6 个测评页无导航 | tools/{mbti,bigfive,holland,disc,ai-risk-test,tarot}/index.html、`tools/compliance-dashboard.html` | 补标准导航 |
| 策展页无导航且无入口 | brief/index.html、brief/signal-brief-001.html | 补导航 + 主导航归位 + 进 sitemap |
| 1 个枢纽页无导航 | `hub/overseas-hr-hub.html` | 补标准导航 |
| 资产页无返回入口 | `assets/ai-transformation-maturity.html` | 补最小导航或返回首页链接 |
| 不修（正确现状） | `404.html`、2 个搜索引擎验证文件、`seo-monitor.html`（已 noindex）、`templates/*`、55 个跳转壳 | 保持不动 |

### 3.4 变更说明：策展入口归位（已采纳，P1 执行）

| 项 | 内容 |
|---|---|
| 原方案失效原因 | 主导航「策展」指向 `bridge/index.html`，该页是**招聘撮合叙事**（一端用人难题、一端待证能力）。① 与「不撮合、不变现」红线冲突；② 真正的策展产品 `/brief/` 因此**零入口、零 sitemap、零内链**，出 1 期后停摆（现测：351 页的策展导航全部指向 bridge，`brief/` 内链数 = 0） |
| 新方案收益 | 策展获得主导航入口 + sitemap 覆盖；撮合叙事下线；策展产品与「可信过滤器」定位对齐 |
| 迁移成本 | 批量改 ~346 个页面的一个 `href`（脚本化，一次提交）；`bridge/index.html` 改写为 CM-2026 项目对外页（1 个文件）；`freeze_baseline.py` 的 `CANONICAL_NAV` 同步更新 |
| 影响范围 | `/bridge/` URL 保留（有历史外链与索引），不删除、不 404；仅内容改写。导航改动不影响文章正文与 schema |

---

## 4. 核心功能模块与优先级

| ID | 模块 | 层 | 优先级 | 现状 | 依赖 |
|---|---|---|---|---|---|
| M1 | 发布与门禁基建（quality_gate / stability_guard / qa_guardian / regression_rules / release_preflight / git_atomic） | 基建 | **P0 冻结维护** | 已建成并通过 | — |
| M2 | 站点信息架构归位 | 结构 | **P1** | 20 处偏离待清 | M1 |
| M3 | 策展：信号线台账 | 内容产品 | **P2 ★差异化** | 1 期简报（形态待改） | M2 |
| M4 | 文章层：pillar 主题簇 + 段位 | 内容 | **P3** | 1 个簇页 | M2 |
| M5 | 测评旅程（五象限串成路径） | 工具 | **P4** | 4 套公开 + 1 套孤立 | M2 |
| M6 | 能力标准罗盘（角色×阶段推荐） | 标准 | **P5** | 未实现 | M1 + CM-2026 标准层过校验 |
| M7 | 可发现层（sitemap / JSON-LD / 内链图谱 / GEO） | 贯穿 | 随 P1–P3 | 部分 | M1 |
| M8 | AI 问答 Copilot（腾讯云 SCF + kb.json） | 服务 | 维护级 | 已上线 | M1 |
| M9 | 资源库 / 产品 / 术语 | 内容 | 维护级 | 已上线 | — |

**优先级判据**：先做「入口与结构」（否则任何新内容都是孤儿），再做「差异化产品」（策展），最后做「体验优化」（旅程、罗盘）。M6 排在最后且**明确设闸**：标准层未过校验不得启动。

---

## 5. 数据模型与真源契约

### 5.1 四个真源（单一真相源，不允许第二份）

| 真源 | 内容 | 生成器 | 现状 |
|---|---|---|---|
| `assets/js/article-index.json` | 文章元数据（title/url/category/date/tags） | `sync-articles.py` | 257 条 |
| `assets/js/line-index.json` | 策展线（slug/claim/status/updated/domain/evidence_count/url） | **新增 `build_brief.py`（P2）** | 不存在 |
| `assets/qa/scf/kb.json` | Copilot 知识包，`articles_indexed` 须对齐可索引文章数 | 现有构建流程 | 246（待核） |
| `sitemap.xml` | 可索引 URL 全集 | `build_sitemap.py` | 341 |

### 5.2 铁律

1. **页面内列表禁止硬编码**，一律由生成器从真源渲染（现有 sync 已做到文章索引，P2 扩展到策展线）。
2. **新增一篇内容必须同步四源**：正文 / 索引页 / 分类标签页 / sitemap + Copilot KB。发布清单由 `release_preflight.py` 对账，缺一不放行。
3. **日期优先级**：`datetime` 属性 → JSON-LD `datePublished` → OG `article:published_time` → git 首次提交日期 → mtime（保底并告警）。禁止回退到 mtime 造成日期污染。
4. **跳转壳永不下线**：noindex + refresh + canonical 三件套 = 刻意的 URL 合并壳，删了就是 404 + 外链断裂。

### 5.3 策展线数据模型（P2 新建）

```
line = {
  "slug":         "flat-org-scale-limit",
  "claim":        "组织扁平化的收益存在规模边界：AI 团队过约 7000 人后协调成本反超精简收益",
  "status":       "稳固 | 被挑战 | 已翻转 | 归档",
  "first_seen":   "2026-09-26",
  "updated":      "2026-10-17",
  "domain":       "组织设计",
  "evidence":     [{"date":"2026-09-11","source":"Meta 内部公告 / 一手","text":"…","polarity":"支持|削弱"}],
  "linked":       {"articles":[], "tools":[], "hubs":[]}
}
```

状态机：`新建 → 稳固 ⇄ 被挑战 → 已翻转 / 归档`。**判断句禁止静默改写**，只能追加「失效条件 + 修订日期」，历史可见。

---

## 6. 关键技术选型（冻结）

| 领域 | 选型 | 状态 | 冻结理由 |
|---|---|---|---|
| 托管 | GitHub Pages（境外，无 ICP 备案） | 冻结 | 百度 CN 结构性封死已确认，战略分配到 Bing/Google/GEO，托管不因此变更 |
| 生成方式 | 静态 HTML + Python 生成器脚本（sync/build_sitemap/publish） | **冻结（本次收口）** | 见 §6.1 |
| 发布 | Git Data API 原子提交（`git_atomic.py`），唯一入口 `publish.py` | 冻结 | 22 关质量门 + 11 项稳定性自检已串通，旁路发布即违规 |
| 样式 | 全局 `style.min.css` + 文章层 `article.css`；深色键控 `html[data-theme]` | 冻结 | 单页 CSS 覆盖全站；组件级暗色必须跟随 data-theme（2026-10-16 事故已固化） |
| JS | 零框架，仅 search / analytics / copilot | 冻结 | 静态站默认零 JS，交互按需加载 |
| AI 问答 | 腾讯云 SCF + `kb.json`（⌘K 双 tab） | 冻结 | workers.dev 被墙后已迁移并上线 |
| 数据持久化 | 无后端数据库；localStorage 仅存主题与非敏感状态 | 冻结 | 零后端是测评产品线的既定约束 |
| 门禁 | quality_gate + stability_guard + qa_guardian + regression_rules + release_preflight + lint_diff | 冻结 | 双闸不可绕过 |

### 6.1 关于 Astro / MDX：正式撤销（变更四问答复）

| 项 | 答复 |
|---|---|
| ① 原方案失效点 | v1 的「C 混合：新内容走集合/MDX」**从未执行**：现测无 `astro.config`/`content/`/`src/`/`package.json`；近 3 个月发布记录全部是「HTML 正文 + 四源同步」。该路线是纸面方案 |
| ② 新方案收益 | 冻结现有生成器路线 = 消除「要不要重构」的反复讨论；把工程投入从架构迁移转到内容产品化（增长主引擎） |
| ③ 迁移成本 | 若真上 Astro：257 篇正文重制 + 150 个脚本中生成器部分重写 + 全部门禁与发布链路改造 + SEO/GEO 回退风险。**收益为架构清洁度，不挂任何 KPI** |
| ④ 影响范围 | 全站 URL 与 schema；期间增长停滞 |

**结论：撤销 Astro/MDX 迁移，锁定「静态 HTML + 生成器 + 双闸」。**
**重启门槛（同时满足才允许再提案）**：① 可索引文章 > 500 篇且人工维护索引出现可复现事故；② 有稳定的第二产能（人或可靠自动化）；③ 迁移能在独立分支完成全量门禁回归。三条不满足，任何人不许重开此议题。

---

## 7. 分阶段路线图

| 阶段 | 主题 | 交付物 | 验收标准（可脚本/可访问验证） | 回滚边界 |
|---|---|---|---|---|
| **P0** | 基线冻结 ✅ 已完成 | 本文档 + `scripts/freeze_baseline.py` + `reports/baseline-2026-10-17.json` | 脚本可复跑；`--diff` 结果为空 | 只读，无回滚需求 |
| **P1** | IA 归位 ✅ 已完成 | ① 主导航「策展」→ `/brief/`：355 个页面、692 处（页头 + 页脚）② 10 个缺入口页面补齐（brief×2 注入标准页头；hub/overseas-hr-hub 注入标准页头；tools×7 注入自包含入口条）③ `bridge/` 改写为 CM-2026 能力标准项目对外页 ④ `assessments/` 声明「本页不提供测试，入口在 /tools/」⑤ `build_sitemap.py` 补录 `brief`（根因：EXTRA_DIRS 漏列） | **实测**：`nav_deviation_count` 20 → **0**；`orphan_count` → **0**；`sitemap_url_count` 341 → **343**；`brief_in_sitemap` 0 → **2**；全部门禁绿；线上 curl 复核 | 单批提交（361 文件），可整体 revert |
| **P2** | 策展信号线台账 ✅ 已完成 | ① 3 条首发线 `/brief/lines/{ai-payoff-gap, hr-seat-not-skill-gap, intake-capacity-gap}.html`（3/3/4 条一手证据）② `brief/_lines/*.json` 为真源线数据 ③ `scripts/build_brief.py` 幂等渲染线页 + `assets/js/line-index.json` + `brief/index.html`④ `signal-brief-001.html` 改为「本期增量」diff 页（原 5 条信号全部保留）⑤ `build_sitemap.py` EXTRA_DIRS 改递归，`brief/lines/` 与 7 个 `tools/*/index.html` 入图 | 实测：线上 5 个 brief 页 HTTP 200；sitemap 353 URL 含全部 brief 页与新文章；`nav_deviation_count` 0、`orphan_count` 0、`article_index_count` 258、`kb_articles_indexed` 258；quality_gate 22/22 + stability_guard 11/11 + qa_guardian 10 门 GREEN | 新增页面 + 索引/分类标签/sitemap 同步（第二批） |
| **P3** | 文章层产品化 | ① 3 个 pillar 主题簇（挂 3–8 篇）② 长文段位补强 ③ 内链图谱校验入门禁 | 簇页每页挂 ≥3 篇真实长文；`articles/index.html` 与簇页互链；GEO 集中度观测值下降；门禁新增「簇页必挂文章」断言 | 新增页面 + 索引同步 |
| **P4** | 测评旅程 | ① `/tools/index.html` 改四段式旅程入口 ② 五象限归位 ③ 旅程事件埋点（百度统计） | 每段有引导词、出口、挂接文章；孤立工具全部归位；无人格分进能力测评（红线断言） | 单页改造 + 索引同步 |
| **P5** | 能力标准罗盘 | 角色×阶段 → 静态推荐路径 | **前置闸：CM-2026 标准层通过校验 + SHRM 一手核验完成**。未过闸不得启动 | 新增页面 |

每阶段完成即停下交付确认，确认后才进入下一阶段。每阶段独立提交批次，回滚边界互不重叠。

---

## 8. 稳定演进约束原则（10 条，违反即违规）

1. **真源单一**：任何列表不许硬编码；页面只能渲染真源。
2. **变更四问**：改动先答失效点/收益/成本/影响范围（§0.2）。
3. **发布唯一入口**：`publish.py`；禁止手工 git push 或直接改线上。
4. **门禁不可绕过**：quality_gate + stability_guard + qa_guardian 全绿才发。
5. **口径纪律**：对外数字一律现测（`verify_claims.py` / `freeze_baseline.py`）；说「全站」用全站口径，说「文章」用 articles 口径，不混用。
6. **零虚构 + 信源三级标准**：A 级补源、B 级留机构去数字、C 级删除改结构论述；无把握的 URL 一律不写。
7. **组件级暗色键控 `html[data-theme]`**：禁止再出现 `prefers-color-scheme` 控制站内组件（2026-10-16 事故）。
8. **不删历史 URL**：合并用跳转壳；下线前必须确认无外链与索引。
9. **新增内容同步四源**：正文 / 索引 / 分类标签 / sitemap+KB，缺一不放行。
10. **教训断言化**：被否决的模式写进 `ci/regression_rules.json`，不写散文。

### 8.1 汇报纪律（针对历史病根）

- 出口状态数字必须先跑校验脚本且能对上；
- 定性前先问「这个指标和我要判的性质有因果关系吗」，没有就换判据（本轮基线脚本已踩到一次：把跳转壳当孤儿，已修正）；
- 宁可说「`articles/` 目录下」，不混用范围词。

---

## 9. 观测与风险

| 风险 | 观测手段 | 处置 |
|---|---|---|
| 搜索生命体征归零（GSC 有效页/曝光/点击） | vitals_monitor 每周一 | P0：先于一切工作 |
| 策展断更 | 期页 `updated` 与当期日期差 > 21 天 | 触发告警并暂停后续阶段 |
| 门禁被绕过 | 发布印记 `reports/publish-manifest.json` | 违规即回滚 |
| 线上与本地不一致 | 发布后 curl 复核 3 个入口（CDN 延迟 60–90s） | 延迟复核，不即时判定 |
| 孤儿页再生 | 每阶段跑 `freeze_baseline.py --diff` | 新增孤儿即阻断 |

---

## 10. 当前状态

- **P0 已完成**：基线冻结（脚本 + 快照）+ 本文档。
- **P1 已完成**：IA 归位，验收标准全部达成（见 §7 P1 行）。
- **P2 已完成**：策展信号线台账（3 条线 + 索引 + 增量期页 + 生成器 + 四源同步），已上线并 curl 复核通过（见 §7 P2 行）。

### 10.1 P1 附带发现（不属于 P1 范围，已记录待处置）

| 发现 | 实测 | 处置 |
|---|---|---|
| Copilot 知识包落后于站点 | 重建前 `articles_indexed`=246 / 索引 257；12 篇新文（`ai-era-*` 系列等）不在 KB 内 | 已本地重建 `build_qa_kb.py`：246 → **257**，chunks 2682 → **2959**（+10%）。**SCF 需单独部署**（SCF 与 GP 是两条管线，kb.json 不进 GP 清单），待下一批 |
| 基线脚本两处测量缺陷 | ① 导航只扫前 20KB → `articles/index.html`（导航在 42KB 后）误报 NO_NAV ② 跳转壳计入孤儿 | 已修：全文扫描；跳转壳与非读者页（404/验证桩/seo-monitor/templates/assets/未发布草稿）豁免；自包含入口条计为合规入口 |
| `assets/` 下 3 个资产页无入口 | design-system / hr-prompt-cards / iceberg-model | 判定为静态资源目录内容（不进 sitemap），不补导航；若未来要发布为资源库资产，需单独立项 |


### 10.2 P2 附带发现与处置（不属于 P2 范围的，均需主理人确认后再动）

| 发现 | 实测 | 处置 | 状态 |
|---|---|---|---|
| 新建文章从未进管线 | `articles/ai-era-collective-bargaining-2026.html`（10,640 字正文，UNI Europa / Littler / CWA 一手信源）落盘但不在 article-index.json、sitemap、KB 内 → 孤儿页 + 质量门第 11 关 FAIL | 补齐管线：sync → index 257→258、sitemap 入图、KB 257→258（chunks 2972） | 已随 P2 上线 |
| 仪表盘被判为薄内容 | `tools/compliance-dashboard.html` 可见中文仅 156 字（其余是内联 CSS），stub_detector BLOCK；**线上版本来带 `noindex,follow`**，是生成器重跑把外部补丁冲掉了 | 把 robots meta 写进生成器 `compliance_dashboard.py`（与 SITE_ENTRY 同族修法），重生成后恢复 noindex 并自动退出 sitemap | 已修 |
| 分类/标签页导航被 sync 改回旧 URL | 跑 sync 重建 30 个 `tags/` `categories/` 页后，`nav_deviation_count` 0 → 30 | 根因是 `templates/taxonomy.html` 与 `templates/_chrome.html` 真相源仍写死 `/bridge/index.html`；改真源后重生成 → 0。并新增断言 `R-STALE-CURATION-NAV` 全站封死 | 已修 + 已断言化 |
| Pages 部署状态会误报 | Pages REST `status=errored`，但 Actions 工作流 `pages build and deployment` 最后一次为 success；实际原因是新 commit 长期 queued | **部署真相源＝Actions 工作流 `pages build and deployment`，不是 Pages REST `builds`**。新路径上线需等 Actions 跑完（本次约 6 分钟），不是 CDN 60–90s | 已记入口径 |
| Copilot KB 需单独部署 | 已重建；`assets/qa/scf/kb.json` 同步完成 | SCF 与 GP 是两条管线，kb.json 不进 GP 清单，需单独打包 + `release_preflight.py --scf` | **待办** |
