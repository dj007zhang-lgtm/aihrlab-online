# 测试记录 TESTS

> 测试阶段产物。**Q-Guard 独占双闸执行权**。结论未过则下游 DEP 不得生成。

| ID | 范围 | quality_gate(22) | stability_guard(11) | reader_perspective | 结论 | 上游 | 下游 | 证据路径 |
|---|---|---|---|---|---|---|---|---|
| TST-20260817-001 | 品牌分层 3 文件（index/about/design-principles） | 未跑（未发布，仅 grep 级结构一致性） | 未跑 | 未跑 | **部分/未封口** | CHG-20260817-001 | DEP-pending | 待发布时经 `publish.py` 跑真双闸回填 |
| TST-20260817-006 | P0 发布集 26 文件（article.css + 24 篇 live 文章 + 模板） | 全过(22)；仅 Gate2 pod-redesign(预存 BLOCKER·已排除)、Gate4 _chrome.html(模板片段·非发布集) | 全过(11)；仅 S5 pod-redesign(排除)、S4 WARN assessments/index.html(预存) | 内容结构未变，不重评（纯 CSS 抽取） | **通过**（发布集双闸干净；预存 BLOCKER 在排除的草稿与模板片段） | CHG-20260817-006 | DEP-20260817-006 | 远程真机核验：article.css 在线 11300B/暖沙 :root/无白底；ant-group(格式化头)+ai-hr-2026-midyear(压缩头) 均引 article.css、无内联、级联正确 |

> ⚠️ 诚实标注：本次为站点重构（CSS 抽取），非新内容发布，故 reader_perspective 不重评（正文结构零改动）。双闸 BLOCKER（S5/Gate2 pod-redesign 缺 banner）属预存草稿问题、不在发布集内，已排除；_chrome.html 为模板片段（无 viewport/title/CSS 链接，按设计豁免）。发布集 26 文件双闸全过。
