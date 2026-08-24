# AIHR 数智引擎 · 产品 Roadmap 与重构方案（2026-08 v2 · 架构前置版）

> 版本：v2（执行稿） ｜ 更新：2026-08-12 ｜ 作者：主理人（AI 自主起草，用户验收）
> 定位：AI+HR 垂直可信品牌站（aihrlab.online，GitHub Pages）。本版把「架构级重构」从尾部评估提升为**前置一等公民 Track A**，原 Phase 1/2/3 降为其下执行层 B/C/D。阶段 KPI 仅作仪表盘，不反向定义架构。
> 配合文档：`architecture-target-state-spec.md`（终点态锚，§8 迁移深度已锁 C 混合）、`aihr-reconstruction-team.md`（子代理职能与交付）、乐享知识库「AIHR 架构重构作战室 2026-08」（项目 KB + 任务看板）。

---

## 0. 愿景锚（以终为始，不被阶段 KPI 困住）

- **使命**：成为 AI+HR 领域最可信的中文知识中枢——既被从业者日常依赖（高阅读/点赞/收藏），也被生成式引擎稳定引用（GEO）。
- **愿景态架构特征（内容网站理想态）**：① 内容即结构化资产（内容集合，而非 130+ 散落手写 HTML）；② 内容优先静态生成（零 JS 默认、快、稳）；③ 卓越阅读体验（流体排版 + measure 控制 + sticky TOC）；④ 可发现性内建进结构（非事后补丁）；⑤ 自带用户沉淀层（邮件+社区，不只有公众号）；⑥ 资源库即知识中枢（统一存取层）。
- **纪律**：A1–F 等 KPI 是**阶段性仪表盘**，用来诊断缺口、制定达标杠杆；不是目标本身，更不反向定义架构。架构重构是为了让站点从根上适配「内容网站」，使仪表盘长期自然向好。

---

## 1. 为什么「GitHub 借鉴站」是架构级输入，不是参考透镜

用户拉那批建站/设计站，意图是**以终为始地重构框架与结构**，使站点从根上适配内容网站——这是**架构级、前置**考虑。因此本版把「架构重构」从原 Roadmap 的 Phase 3 尾巴，提升为**前置一等公民 Track A**；原 Phase 1/2/3 降为其下执行层 B/C/D。

**参考站评审结论（借用 / 否决）：**

| 借鉴 | 用途 | 否决 | 原因 |
|---|---|---|---|
| Astro 内容集合 | 终点态内容模型候选（本期混合 C 已拿红利，不强迁） | Next.js SaaS / saas-starter | 重 JS、营销属性、稳性风险 |
| Fumadocs / Nimbus / just-the-docs | 文档级排版范式（type scale / measure / TOC 节律） | AI 克隆站 / open-lovable | 偏离内容站气质、不可控 |
| FMHY | 资源库即知识中枢（分类+标签+索引统一存取） | 3D 滚动 / WebGL / react-bits | 稳定性与克制审美冲突 |
| 微信生态工具 | 工作流 / 双轨沉淀 | — | — |

---

## 2. 四层 Track 总览（架构前置）

```
终点态(使命/愿景)
 └─ Track A 架构级重构（前置 · 混合 C：新内容走集合/MDX，旧130篇逐步重制）
      ├─ Track B 体验层（排版/阅读统一，原Phase1）      → 主攻 KPI D 跳出率
      ├─ Track C 沉淀层（邮件订阅/社区，原Phase2）      → 主攻 KPI F 转化
      └─ Track D 增长层（标签/资源库/GEO，原Phase3）    → 主攻 C2/GEO集中度、E索引
   阶段 KPI(A1–F) 贯穿各 Track 作仪表盘
```

**执行单元**：主理人（AI）下辖 5 个子代理（A-Architect / B-Typographer / C-Growth / D-SEO / Q-Guard），职能与交付见 `aihr-reconstruction-team.md` 与乐享「子代理职能与交付产出」页。每个子代理独立收口、双闸零回归、验收交主理人。

---

## 3. Track A — 架构级重构（前置 · 混合 C，已拍板）

| 子项 | 目标 | 交付 | 验收 |
|---|---|---|---|
| A0 地基收口 | 干净基线 | 三批本地改动（hero P0 / 归档折叠 / bridge v7，约 198 文件）走双闸增量发布；双闸固化进 CI（`.github/workflows/ci.yml`）；CHANGELOG + 编辑日历 + 基线整合脚本化 | 每批发布后 API 取新 HEAD 的 parent == 发布前真 HEAD；PR 双闸自动红 |
| A1 内容模型与 schema | 内容即资产 | 7 类 typed collections（article/resource/product/tool/glossary/hub/bridge）字段 schema + 校验脚本 | schema 校验脚本过；旧文 frontmatter 抽字段脚本化 |
| A2 新内容 MDX 化（增量） | 不中断增长 | 即日起新文走集合/MDX + 集合模板 | 新文双闸过；零回归 |
| A3 排版系统 token 化 | 一次定义全复用 | 把 hero 已验证 `clamp()` 提升为全站设计 token（type scale + 正文 measure 68–72ch + sticky TOC + 统一 callout） | 全集合复用、无裸 `font-size` 硬编码 |
| A4 旧 130 篇分批重制 | 零回归迁移 | 按 IA 优先级（article→resource→glossary→hub→tool→product→bridge）分批，每批双闸全绿才发 | Gate17 零告警、双闸绿、主理人验收 |

---

## 4. Track B — 体验层（阅读统一 · 主攻 KPI D 跳出率 96.59%→<85%）

| 子项 | 交付 | 验收 |
|---|---|---|
| B1 全站 h1–h4 `clamp()` 推广（复用 A3 token） | 全站 h1–h4 改引用 token | 无裸 `font-size:2.xrem` 硬编码（Gate 扫描） |
| B2 正文 measure 68–72ch + 行高/段距节律 | 正文 `max-width` 收至 72ch、`text-wrap:pretty` | 移动/桌面正文不超 72ch、不断行难看 |
| B3 sticky TOC + 阅读进度 | 文章/资源/产品右侧 sticky 目录 | 长文导航与停留提升 |
| B4 四类卡片间距对齐 DS v5 | articles/resources/glossary/tools 卡片节律统一 | 四类页卡片间距差异 ≤ 设计容差 |
| B5 深色模式对比度复检 | 复检 R1 后新增组件对比度 | 所有新增块对比度达标，无透明/爆亮 |
| B6 读者视角 Gate14 常态化 | `reader_perspective_gate.py --all` 纳入 CI | 每篇新文综合 ≥80 才放行 |

---

## 5. Track C — 沉淀层（主攻 KPI F 转化 +50%）

| 子项 | 交付 | 验收 |
|---|---|---|
| C1 Buttondown 免费邮件订阅（≤100，隐私向） | 全站订阅条 + 桥页订阅表单 | 表单可提交、confirm 邮件可达 |
| C2 PIPL 合规 | 订阅勾选同意 + `/privacy` 隐私政策页（含跨境说明，Buttondown 美服）+ 退订链接 | 隐私政策含数据用途/跨境说明，过审 |
| C3 桥页招聘 intake 优化 | bridge 表单字段精简 + 落地承接文案 | 提交转化率可观测 |
| C4 公众号双轨（保留） | 不弃现有公众号导流 | — |

---

## 6. Track D — 增长层（内容组织与可发现性）

| 子项 | 交付 | 验收 |
|---|---|---|
| D1 标签导航孤儿修复 | taxonomy 页补导航入口（灭 Gate17 告警） | taxonomy 页非孤儿、内链图谱无告警 |
| D2 资源库即知识中枢 | FMHY 范式（分类+标签+索引统一存取）落地资源页 | 资源页可被 Bing/GSC 抓取 |
| D3 GEO 集中度降 | BLUF 前 30% 直击；文内归因优于文末清单 | C2 85.8%→<50% 可观测 |
| D4 可发现性内建 | JSON-LD / sitemap / 内链图谱随集合自动生成 | sitemap 含全部真实非桩页 |
| D5 Astro 远期评估 | 保留候选，本期混合 C 已拿红利，不强迁 | memo（可选） |

---

## 7. KPI 仪表盘映射

| KPI | 现状 → 目标 | 主责 Track |
|---|---|---|
| A1 Bing 曝光 | 1750 → 5000/周 | D4 + 内容量 |
| A2 Bing 点击 | 110 → 350/周 | B（SERP 体验） |
| B1 GSC 曝光 | 10.5 → 100/周 | D4（被展示） |
| B2 GSC 点击 | 0 → 5/周 | B + D3 |
| C1 AI 引用 | 282 → 800/周 | D3（GEO） |
| C2 GEO 集中度 | 85.8% → <50% | D3 |
| **D 跳出率** | **96.59% → <85%** | **B（头号硬伤）** |
| E 中文索引 | 0 → 152 URL | D4 |
| F 转化 | +50% | C |

> 口径铁律：任何「X/周」必须标原始总量+除数；口径错误须同步修正所有历史文档，禁双版本并存。

---

## 8. 关键决策状态（已锁）

- **架构迁移深度（§8）= C 混合，已拍板**：新内容走集合/MDX，旧 130 篇逐步重制。A 全量 Astro / B 增量硬化 作为备选不再主推。
- **邮件 ESP**：拟 Buttondown（≤100 免费、隐私向）；跨境 PIPL 待 C2 落地时以 `/privacy` 明示，用户已知晓。
- **归档每月默认篇数**：当前 8 篇（7 月 22、8 月 90 出按钮）；日更 30+ 后单月将达 90+，维持 8（乐享看板可后续调）。
- **子代理机制**：主理人可创建子代理，职能/交付见 `aihr-reconstruction-team.md`；项目 KB + 任务看板沉淀于乐享。
- **鲁棒性护栏（最高优先级）**：双闸（quality_gate 21 关 + stability_guard 11 项）零绕过、固化进 CI；零回归逐批迁移；无硬编码密钥（`AIHR_GITHUB_TOKEN` / gitignored `scripts/.github_token`）；JS 改后必 `node --check`；原子发布重试。

---

## 9. 执行顺序与里程碑

1. **M0（本周）**：A0 收口三批本地改动 + 双闸进 CI → 干净基线 + 乐享看板初始化。
2. **M1（1–2 周）**：A1 schema + A2 新文 MDX 化 + A3 排版 token。
3. **M2（2–4 周）**：B 全站排版统一（冲 D 跳出率）+ A4 旧文首批重制（高价值 30 篇）。
4. **M3（持续）**：C 沉淀层 + D 增长层滚动推进。

每阶段结束先跑双闸 + 读者视角 Gate14，再发布；不跨阶段混发。验收权归用户。

---

## 附：相关既有文档（避免重复造轮）

- `reports/architecture-target-state-spec.md`（终点态锚，§8 锁 C）
- `reports/aihr-reconstruction-team.md`（子代理职能与交付）
- `reports/design-system-v5-evaluation-2026-08-05.md`（DS v5）
- `reports/R1-dark-mode-charter.md`（深色模式宪章）
- `reports/stability-guard.md` + `reports/p0-stability-impact-assessment-2026-08-08.md`
- `reports/resource-library-plan.md`（资源库计划，D2 基础）
- `scripts/title_standards.py`（标题阈值单一真相源）
- MEMORY.md 发布铁律 / Ghost token 护栏 / 口径铁律
- 乐享知识库「AIHR 架构重构作战室 2026-08」：项目 KB + 任务看板（回溯主线）

---

## 10. 状态更新日志（2026-08-24 周复盘）

> 详情 `reports/weekly-review-2026-08-24.md`

- **P0 红线**：Google GSC 有效索引页 3（站内 228 篇）、28 日点击 0；Bing 对照健康。KPI B1/B2/E 实际受阻于 Google 单侧 + 用户侧提交动作，非技术债。
- **KPI 现状快览**：A1/A2/C1 健康但远低于目标（近 7 日 1,677/95/266 每周围基线，目标 5,000/350/800）；D 跳出率 94.66% 仍头号硬伤（目标 <85%）；B1/B2/E/F 数据缺口或待用户。
- **自主优化**：本周发布 commit `f7295500`（22 文件，双闸全绿）；待修项见周复盘第五节。
