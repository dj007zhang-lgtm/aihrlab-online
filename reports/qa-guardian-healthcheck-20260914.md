# AIHR 全站质量保障·深度体检报告（错不二犯机制）

- 体检对象：`site-migrated/ci/` 全站质量保障编排器 + 7 个 gate + baseline 回归锁
- 体检日期：2026-09-14
- 触发：交付前深层次体检（全面排查潜在隐患，验证旧 bug 已彻底修复且未引入新 bug）
- 结论：**🟢 通过**。机制可运行、可拦截、可自愈、可容错；体检过程中发现并修复 1 个会令两套回归闸静默失效的关键 schema bug。

---

## 1. 体检结论速览

| 维度 | 结果 |
|---|---|
| 全站检测（clean） | 🟢 GREEN，无阻断级债务 |
| 旧债固化（7 类） | ✅ 每类均有常驻 gate，已注入同类样本验证必拦 |
| 错不二犯注入证明 | ✅ 10/10 项通过 |
| 故障隔离（鲁棒性） | ✅ 单门崩溃 → ERROR 隔离、exit 0、baseline 不锁、显式告警 |
| 自愈链路 | ✅ `--heal` 重建 sitemap/index + 还原重定向契约 |
| 本次新发现缺陷 | 1 个关键 schema bug（见 §5）+ 3 篇占位符泄漏（已修，见 §4） |
| 是否引入新 bug | 否（注入测试后站点零残留、sitemap md5 一致） |

---

## 2. 机制架构（回应"主理人/质检 sub agent 未能及时诊断"盲点）

旧 QC 是**逐篇门禁**（quality_gate 21 关 + stability_guard 11 BLOCKER），数学上无法发现跨篇/全站级缺陷。本机制补第四层：

1. **预防门禁**——复用 `scripts/publish.py` 既有双闸（quality_gate + stability_guard）。
2. **全站检测**——本站 7 个 gate，覆盖跨篇克隆/桩页/死链/重定向契约/meta/设计资产/sitemap。
3. **异常预警**——软指标与 baseline 比对，回归超阈升级为 BLOCK。
4. **回归校验 + 自愈**——baseline 仅在全绿时更新（永锁坏状态）；`--heal` 做确定性自愈并自验。

**接入点（三道防线，任一阻断即不发布）：**
- `scripts/publish.py` STEP 2.5：发布前跑 `ci/qa_guardian.py`，BLOCK 即中止（不写远程）。
- `.github/workflows/quality-gate.yml`：PR/push 跑 QA Guardian 步骤。
- 自动化「AIHR 全站质量保障周检」：每周一 09:00 `--report-only` 只检测汇报（不发布）。

---

## 3. 旧债 → gate 固化对照表（错不二犯）

| 历史缺陷（2026-09 体检暴露） | 固化 gate | 拦截语义 | 当前状态 |
|---|---|---|---|
| 25 篇规模化克隆（scaled content abuse） | `gate_clone_detection` | ≥3 篇共享 ≥8 段 → BLOCK | PASS（0 集群，整改生效） |
| 30 个 <500 字实质桩页 | `gate_stub_detector` | 可索引页 <500 字 → BLOCK；基线感知（新增即拦） | WARN（15 已知债=baseline，未新增） |
| 41 处站内死链 / 重定向矛盾 | `gate_link_doctor` | 内链断链 / 真文却登记为重定向源 → BLOCK | PASS（无死链/矛盾） |
| meta description 污染 / 占位符残留 | `gate_meta_lint` | 导航样板前缀 / PLACEHOLDER/TODO → BLOCK | WARN（8 英文引号，仅告警） |
| 软 404（sitemap 漏收 / index 无效 slug） | `gate_sitemap_consistency` | sitemap URL 无文件 / index 无效 slug → BLOCK | PASS（326 URL 全对应） |
| 域名质量分（正文深度/覆盖率）下滑 | `gate_tracking_metrics` | 中位数跌 30% / 覆盖率降 ≥10pp → BLOCK | PASS（相对 baseline 无回归） |
| 自设计坏 CSS / 缺 OG 图 / 丢资源 | `gate_design_asset_lint` | 默认 WARN（不阻断内容），周检预警；可升级 BLOCK | WARN（4 处已知告警） |

---

## 4. 本次机制运行新捕获并已修复的缺陷（旧 QC 漏检的实证）

机制首次全站运行即捕获 **3 篇已上线文章残留模板占位符**（旧逐篇 QC 漏检，靠人工体检才发现——正是用户指出的盲点）：

- `articles/change-management-methodology-2026.html`：JSON-LD `headline`/`description` 为 `<!-- PLACEHOLDER_SCHEMA_HEADLINE -->`
- `articles/organizational-network-analysis-ona-2026.html`：同上 JSON-LD 占位符
- `articles/remote-team-management-challenges-2026.html`：broken `canonical`、og:description/keywords/answer-what/short-answer 占位符、JSON-LD 日期占位符、正文空 `<p>` 占位符

修复原则：**零虚构**填充（值取自本页 title/h1/description/首段/真实日期 2026-08-23，与 `<time>` 及 git 首提交一致），删除空 P1 段不编造正文。修复后 3 篇 JSON-LD 均 `json.loads` 通过，meta_lint 降为 WARN。

> 价值实证：若此机制早接入，3 篇占位符不会上线。

---

## 5. 体检发现并修复的关键 bug（silent failure，最高优先级）

**症状**：全站运行稳定 GREEN，但两套"回归锁"实际从未生效——典型静默失效。

**根因**：baseline 契约不一致。
- `save_baseline` 把各门快照存于 `baseline["metrics"]`（`{gate: metrics}` 嵌套）。
- `gate_tracking_metrics` 读 `baseline["metrics"]` 却当**扁平**指标用 → `median_words` 读到 `0` → 回归比较 `2630 < 0×0.7` 恒假 → **质量分回归永不被拦**。
- `gate_stub_detector` 读 `baseline["gates"]`（文件里不存在）→ 永远判为"首次运行" → 新增桩页**永不阻断**。

**修复**：
- `qa_guardian.save_baseline`：快照改存于 `baseline["gates"][gate_name]`（统一契约）。
- `gate_tracking_metrics.run`：基线读取改为 `baseline["gates"]["tracking_metrics"]`。
- `gate_stub_detector`：本就读 `["gates"]`，契约对齐后自动生效。
- 重新 `--reset-baseline` 以正确形状重锁（`stub_detector.thin_block=15`、`tracking_metrics.median_words=2630`）。

**修复前后行为对比（铁证）**：
| gate | 修复前 | 修复后 |
|---|---|---|
| stub_detector | 每次 "首次运行记录 15 为 baseline"（永远不拦新增） | "=baseline 15（未新增）"；新增即 FAIL |
| tracking_metrics | "INFO 首次运行无 baseline"（回归锁形同虚设） | "PASS 相对 baseline 无回归"（median 2630 / GEO 92.9%） |

---

## 6. 错不二犯注入证明（10/10）

在 `articles/` 注入每类历史 bug 的同类样本，确认对应 gate 必拦；测试后全部清理、sitemap 还原（md5 一致）、站点零残留。

| # | 注入样本 | 期望 | 结果 |
|---|---|---|---|
| 1 | 3 篇共享 8 段（克隆） | clone FAIL BLOCK | ✅ clusters=1/pages=3 |
| 2 | 1 篇 <500 字新增桩页 | stub FAIL BLOCK | ✅ thin=16 > baseline 15 |
| 3 | 1 篇内链指向不存在文件 | link FAIL BLOCK | ✅ dead=1 |
| 4 | 1 篇 meta 含 `PLACEHOLDER` | meta FAIL BLOCK | ✅ placeholder=1 |
| 5 | 1 篇 og:image 指向不存在资源 | design WARN | ✅ og_broken=2（默认 WARN by design） |
| 6 | sitemap 注入孤儿 URL | sitemap FAIL BLOCK | ✅ orphan=1；已原样还原 |
| 7 | 合成坏基线（median 5000） | tracking FAIL BLOCK | ✅ 回归锁定触发 |
| 8 | 真实 baseline | tracking 无误报 | ✅ PASS |
| 9 | 注入崩溃门（容错） | ERROR 隔离、exit 0、baseline 不锁 | ✅ 显式告警、不静默 |
| 10 | 清理后全站 | GREEN | ✅ blocking=0 / gate_errors=[] |

---

## 7. 鲁棒性验收（最高优先级）

- **故障隔离**：单 gate 抛异常 → `status=ERROR`、其余 gate 照常运行、baseline **不更新**（避免锁坏状态）、exit 0（不冻站）、报告显式列出异常（不静默，须人工排查）。
- **自愈闭环**：`--heal` 重建 sitemap + article-index + 还原重定向契约，均为确定性、可逆操作，自愈后重跑自验。
- **幂等**：检测门零副作用；自愈仅在 `--heal` 显式触发。
- **不冻站**：ERROR 不阻断发布（防单 gate bug 冻结全站），但记入 `gate_errors` 并每周 P1 预警。

---

## 8. 操作手册

```bash
cd site-migrated
python3 ci/qa_guardian.py                 # 检测 + 全绿时更新 baseline + 报告（发布链调用）
python3 ci/qa_guardian.py --report-only   # 只检测出报告，不更新 baseline（周检）
python3 ci/qa_guardian.py --reset-baseline# 以当前好状态重种 baseline（schema 变更/大改后）
python3 ci/qa_guardian.py --heal          # 确定性自愈后重验
```

报告：`reports/qa_guardian-report.md` + `reports/qa_guardian-status.json`；基线：`ci/baseline/health_baseline.json`；阈值：`ci/heuristics/thresholds.json`。

---

## 9. 已知非阻断债（WARN，进跟踪不阻断）

- `stub_detector`：15 篇已知薄内容页（=baseline，未新增）。建议后续合并/重写，不新增即不拦。
- `meta_lint`：8 篇 title/h1 含英文引号（须改「」角引号）。
- `design_asset_lint`：4 处（og 缺 3 / og 坏 1），属设计资产告警，默认不阻断内容发布。

---

## 10. 留给后续迭代的纪律

- baseline 契约（`baseline["gates"][gate_name]`）是机制正确性的命门；任何改动 `save_baseline` 或 gate 的 baseline 读取路径，必须重跑 §6 注入证明 + `--reset-baseline`。
- 新增 gate 必须实现 `run(site_root, cfg, baseline) -> GateReport` 且自身 try/except 由编排器兜底；不得假设 baseline 一定存在。
- 周检自动化只看报告不发布；若报告出现新 BLOCK/ERROR，须当周归因修复（技术归因优先，禁"新站不被收录"等笼统归因）。
