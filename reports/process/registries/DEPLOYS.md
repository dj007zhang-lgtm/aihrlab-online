# 部署记录 DEPLOYS

> 部署阶段产物。仅当对应 TST 结论=通过 才可登记。

| ID | 范围 | manifest 路径 | HEAD sha | sitemap 覆盖率前→后 | 状态 | 上游 |
|---|---|---|---|---|---|---|
| CHG-20260817-001 | 品牌分层（index hero 风格③ + about 风格①）| `reports/publish-manifest.json` | 58109883 | 211→211 | 已发布（2026-08-17）| TST-20260817-001 |
| CHG-20260817-005 | footer 全站 slogan 归一化（169 旧 boilerplate + 1 漂移变体文件）| `reports/publish-manifest.json` | 10e36b61 | 211→211 | 已发布（2026-08-17）| TST-20260817-005 |

<!-- 发布流程：scripts/publish.py → 双闸 → git_atomic 原子提交 → IndexNow；留 publish-manifest.json 供覆盖率溯源 -->
