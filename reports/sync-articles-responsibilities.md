# 同步脚本职责清单（Sync-Articles Responsibilities）

> 日期：2026-08-19
> 关联事故：INC-20260819-001
> 关联教训：LSN-20260819-001

本文档记录 `sync-articles.py` 所有输出块的责任归属，确保每个被用户或 SEO 工具读取的输出块都有且仅有一个明确的写作者。

---

## 输出块清单

### 1. articles/index.html 的卡片网格（article-grid）
- **写作者**: rebuild_index_html()
- **触发**: main() 第 557 行调用
- **校验**: Gate 16 文章索引完整性关 + Gate 11 6d HTML 卡片重复检测

### 2. assets/js/article-index.json
- **写作者**: rebuild_index_json()
- **触发**: main() 第 520 行调用
- **校验**: Gate 16 文章索引完整性关 + Gate 11 6c article-index 重复 slug 检测

### 3. articles/index.html 的 JSON-LD ItemList（CollectionPage）
- **写作者**: rebuild_index_jsonld()（新增，2026-08-19）
- **触发**: main() 第 601 行调用
- **校验**: Gate 19 结构化数据合法性关

### 4. sitemap.xml
- **写作者**: build_sitemap.py（独立脚本）
- **触发**: publish.py 调用
- **校验**: Gate 21 Sitemap 卫生关

### 5. redirects.json
- **写作者**: 手动维护 + build_sitemap.py 自动补充
- **触发**: 文章迁移时手动添加
- **校验**: Gate 11 6b 重定向桩完整性检测

---

## 历史盲区（已修复）

| 盲区 | 影响 | 修复方式 |
|------|------|----------|
| JSON-LD ItemList 从未被同步脚本重写 | 长期 stale，含旧 slug 和重复 title | 新增 rebuild_index_jsonld() 函数 |
| Gate 11 只检查 article-index.json，不扫描 HTML 卡片网格 | 旧 slug 页若不在 index.json 则完全不可见 | 新增 6d（HTML 卡片重复检测）+ 6e（交叉验证） |

---

## 维护纪律

1. 新增输出块时，必须在本清单中登记写作者和校验门
2. 任何输出块的修改必须同步更新对应质量门
3. 禁止绕过质量门直接修改输出文件（除非紧急 hotfix）

---

## 相关文档

- 事故报告：`reports/incident-20260819-index-duplicate.md`
- 教训沉淀：`reports/process/registries/LESSONS.md`（LSN-20260819-001）
- 变更记录：`reports/process/registries/CHANGES.md`（CHG-20260819-003）
