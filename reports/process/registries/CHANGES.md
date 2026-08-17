# 编码变更 CHANGES

> 编码阶段产物。关联 DES；commit sha 在原子提交后回填（发布前标 pending）。

| ID | 范围 | 关联 DES | commit sha | 状态 | 上游 | 下游 | 备注 |
|---|---|---|---|---|---|---|---|
| CHG-20260817-001 | `index.html`（hero 改风格③）+ `about.html`（JSON-LD slogan + about-hero tagline 改风格①） | DES-20260817-001 | 58109883 | 已发布（DEP 收口 2026-08-17） | DES-20260817-001 | TST-20260817-001 | 改动文件须单独 atomic commit，严禁混入 228 篇 related-reading 批量 / 265 未提交文件 |
| CHG-20260817-002 | 新建 `reports/content-redlines.md`（作者绝不写·14 条显式红线） | DES-20260817-002 | N/A（仓库 report，非站点页） | 已立标（doc review 通过） | DES-20260817-002 | — | 受 SDLC §3.1 retire 纪律约束；消费方＝aihr-hardcore-writing Stage 5 L5 |
| CHG-20260817-003 | 改写 `~/.workbuddy/skills/aihr-hardcore-writing/SKILL.md` Stage 5：增 L5 禁忌门读 content-redlines.md + 标注独立 sub-agent 审稿 | DES-20260817-003 | N/A（skill，非站点页） | 已立标（doc review 通过） | DES-20260817-003 | — | 各审稿轮由独立 sub-agent 重读规则文件，禁初稿模型自评 |
| CHG-20260817-004 | 改写 `reports/process/SDLC-v1.md`：新增 §8 sub-agent 协作纪律（4 规则）+ LESSONS 加 LSN-20260817-003 | DES-20260817-004 | N/A（仓库 report，非站点页） | 已立标（doc review 通过） | DES-20260817-004 | — | 受 §3.1 retire 约束；非站点页不跑发布双闸 |
| CHG-20260817-005 | 批量替换全站 footer-brand `<p>`（169 旧 boilerplate + 1 漂移变体）→ 新标语；修 `_chrome.html` SSOT 同文案 | DES-20260817-005 | 10e36b61 | 已发布（DEP 收口 2026-08-17） | DES-20260817-005 | TST-20260817-005 | 仅提交 footer 归一化文件，严禁混入 228/265 无关未提交文件 |
| CHG-20260817-006 | P0 内容集合化地基：新建 `assets/css/article.css`（81 规则·单暖沙 :root）；25 篇「既引又内联」文章删 `<style>` 改引 article.css + `templates/article-v2.html` 同步（pod-redesign-fails-2026 因预存双闸 BLOCKER 排除，未发布草稿） | 架构蓝图 P0（reports/architecture-vision-blueprint-2026-08-17.md） | b2cd6c02 | 已发布（DEP 收口 2026-08-17） | 架构蓝图 P0 | TST-20260817-006 | 级联顺序 style.min.css→article.css 不变；覆盖校验 MISSING=0；统一 35 核心选择器值（以模板 v2 为权威基底）；25 篇白底 `--bg:#fff` 归一为暖沙 `--bg:#f1efe9`（消除与 113 篇沙底文章的不一致） |

| CHG-20260817-007 | `articles/pod-redesign-fails-2026.html`（控制平面/Pod 改组深度文；原 P0 排除草稿，补齐 banner + 信源复核 + 双闸清零后收口）+ `assets/images/banners/org-control-plane-2026.webp`（新建 1200×821 WEBP）+ `assets/js/article-index.json`/`articles/index.html`（索引同步） | 架构蓝图 P0（pod-redesign 为 P0 排除草稿的收口）/ 内容宪法 | 457e0382 | 已发布（DEP 收口 2026-08-17） | 架构蓝图 P0 / DES-20260817-001 | TST-20260817-007 | Coinbase 信源修正为 DRI 单一责任人表述（信源复核 #639）；QR CTA 修复为规范「HR 变革」（Gate8）；原双闸 BLOCKER（缺 banner/Gate11 URL 不一致）已清零；收口了 CHG-20260817-006 排除的 pod-redesign-fails-2026 草稿 |

<!-- 发布后回填：commit sha、HEAD、sitemap 覆盖率前后 → 同步 DEPLOYS.md -->
