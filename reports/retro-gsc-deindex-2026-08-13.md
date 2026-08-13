# 复盘：GSC 有效页面暴跌（90 → 3）& 低水平失误模式

> 日期：2026-08-13
> 级别：P1（有效索引归零、搜索流量悬于一线）
> 类型：SEO 内容健康 / 质量门盲区
> 负责人：主理人（AI）
> 状态：已修复 + 已沉淀为 Gate 21 + token scope 预检

---

## 0. 一句话结论

GSC 有效页面直线下跌，**不是 robots/sitemap/noindex 的技术误杀，而是 `sitemap.xml` 主动提交了 17 个「页面已迁移」型重定向桩页 → Google 判定整域软 404 / 低质量 → 连坐取消索引**。

两次"低级失误"暴露的是**同一个系统性问题**：质量门系统很强（21+11 关），但**盲区恰好落在 SEO 内容健康与发布前置条件**，而这些是"资深运营本不该犯"的常识。

---

## 1. 事件

- GSC「有效页面」从约 **90** 跌到 **3**，几乎整域被取消索引。
- 用户截图提问："为什么 GSC 有效网站数直线下降"。

## 2. 影响

- 真实文章页被连坐 de-index，搜索流量面临归零风险。
- 恢复周期 1–4 周（Google 重新抓取 + 重新评估质量），且取决于 E-E-A-T / 外链补足，非纯技术可解。
- 间接损害：整域质量评分（site quality）被软 404 拖低，影响后续新页面收录速度。

## 3. 时间线（还原）

| 时间 | 动作 | 备注 |
|------|------|------|
| M0 发布 | 原子提交 226 文件，含 17 个重定向桩页 | 桩页当时**无 noindex**，且被 `sitemap.xml` 收录 |
| 数周 | Google 持续抓取桩页，判定软 404 | 质量评分累积下滑 |
| 2026-08-13 | 用户发现 GSC 有效页暴跌，要求复盘 | 本次事件暴露 |
| 2026-08-13 | 本地修复：17 桩页加 noindex + `build_sitemap.py` 排除重定向页 + 重建 sitemap（227→209） | 双闸全绿 |
| 2026-08-13 | 新增 Gate 21（Sitemap 卫生关）+ `git_atomic.verify_token_scopes()` 预检 | 防止再发 |

## 4. 根因

### 4.1 直接根因

1. `articles/` 下有 **17 个重定向桩页**（标题"页面已迁移"，`<meta http-equiv="refresh">` 跳转），正文只有一句跳转文案。
2. 这些旧 URL 全部被 `sitemap.xml` 主动提交给 Google（M0 发布时 build_sitemap 未排除它们）。
3. Google 抓回来看正文只有"本页面已迁移"→ 判定**软 404 / 低质量页面**。
4. 大量软 404 拖累整个域名质量评分 → 原本已索引的真实文章页被**连带取消**。

### 4.2 系统根因（为什么双闸没拦住）

- `build_sitemap.py` 的排除逻辑是**源头治理**（排除 404 / 验证桩 / `_backup`），但**没有把"重定向桩页"列入排除项**——这是一个缺失的枚举。
- 更关键：**没有任何质量门验证 `sitemap.xml` 的 OUTPUT 是否含软 404**。`quality_gate.py` 的 21 道门全部围绕"代码/结构/SEO 元数据/读者视角"，对"sitemap 输出卫生"是盲区。
- 重定向桩页在质量门里被**当成"需要跳过的对象"**（Gate 5/6/12/13/19/20 都 `if 'http-equiv="refresh"' in html: continue`），而不是"需要被确认不在 sitemap 里"——**门的设计默认桩页已被正确处置，但无人验证这个假设**。

> 这正是 cb_summary 里的历史教训重演：P0（JSON-LD 括号缺失）、R1（内联脚本被 `//` 吞码）、R3（内链死代码）都是"门没覆盖的盲区 → 双闸全绿却线上暴雷"。本次是同一模式的第四次。

## 5. 为何归类为"低级失误"

- 不向 sitemap 提交软 404 / 重定向页，是 SEO 101。
- 重定向桩页应默认带 `noindex`，是迁移基本功。
- 这两点本不该靠事后救火发现，而应写进发布门禁。

## 6. 另一处同源失误：PAT scope

- 用户依我"加 workflow scope"的指引重新生成 PAT，**只勾了 workflow，漏勾 repo** → `POST blobs` 稳定 404。
- 当时错误信息只有 "GitHub API 404"，**无 scope 提示**，误判为代理抖动，浪费多轮。
- 根因：我给的指引**不完整**（没同时给 repo + workflow 清单），且错误信号不可读。

## 7. 已修复

1. 17 个重定向桩页全部加 `<meta name="robots" content="noindex">`（15 新增 + 2 已有）。
2. `build_sitemap.py` 新增 `is_redirect_page()`，根目录 / articles / EXTRA_DIRS 三层收集逻辑统一排除 meta-refresh 页。
3. 重建 `sitemap.xml`：227 → 209 URL，17 个重定向桩 URL 全部移除。
4. 双闸验证：`quality_gate --all` 21 关 PASS、`stability_guard --all` 11 项 PASS。

## 8. 防再发机制（本次沉淀的核心）

### 8.1 Gate 21 — Sitemap 卫生关（新增，永久门禁）

`scripts/quality_gate.py::gate_sitemap_hygiene`，每次 push 前必过：

- sitemap.xml 中每个 URL 对应的本地 HTML **不得是 meta-refresh 重定向桩**；
- 全站所有 meta-refresh 重定向桩页**必须带 noindex**。

与 Gate 11（查 sitemap 之外的孤儿重定向桩）互补，形成"桩页既不在 sitemap、又带 noindex"的双重保险。

### 8.2 `git_atomic.verify_token_scopes()` 发布预检（新增）

- `atomic_commit` 发起前先 POST 一个极小探针 blob：
  - 201 → repo 写 scope OK；
  - 404 → **确定性**缺 repo scope，直接拦下并给人话提示（含"提交 `.github/workflows/*` 还需 workflow scope"）；
  - 其他异常（代理抖动）→ 不阻断，让真实写操作暴露真相，避免误杀合法发布。
- 同时把 `_req` 的 404 写操作错误从 "GitHub API 404" 升级为带 scope 提示的人话。

### 8.3 纪律固化

- 任何"新类型低级失误"→ 先补一个**永久质量门**，再写文档。文档是记录，门是机制，门优先级高于文档。
- 给用户的操作指引（如 PAT scope、发布步骤）必须给**完整勾选项清单**，不得只说"加 X"。

## 9. 横向教训（给主理人自己）

1. **质量门系统 = 它覆盖的盲区之和。** 门越多，越容易在"未覆盖的常识"上翻车。每次线上暴雷都应反推"哪道门该覆盖这个盲区"。
2. **"需要跳过的对象"≠"已被正确处置"。** 门里对桩页 `continue` 是假设它安全，但假设必须被一道独立的门验证。
3. **给用户的指引要可执行、完整。** "加 workflow scope" 漏了 repo，导致下游失败——指引必须是勾选清单，不是单点提示。
4. **错误信号要可读。** cryptic 404 浪费的轮次，本可用一行人话提示省下。
5. **发布后校验必须可信，否则比没有更糟。** 本次上线后 `publish.py` 的 `verify_remote_exists` 对中文路径未做 URL 编码，抛出 `'ascii' codec can't encode` 假 FAIL，但实际文件已 200 上线。假失败会触发"人工复核"误判、甚至 exit code 1 阻断 CI。**校验函数本身属于发布链路的一部分，必须和门禁同等对待**——任何校验逻辑都要先在真实远端验证其真假性，再投入使用。

## 10. 行动项

| # | 事项 | 状态 |
|---|------|------|
| A | 带 repo+workflow scope 的新 PAT 给用户后，原子发布 20 桩页 + build_sitemap.py + sitemap.xml + quality_gate.py + git_atomic.py | ✅ 已发布 commit `b8a69c05`（远程 HEAD 已核验一致） |
| B | 发布后 GSC 重新提交 sitemap、请求验证，观察 1–4 周恢复 | ⏳ 待你在 GSC 操作 |
| C | Gate 21 已并入双闸；后续新增内容默认过此门 | ✅ 已落地 |
| D | token scope 预检已并入发布链路；后续错 token 会确定性拦截 | ✅ 已落地 |
| E | 乐享知识库镜像本复盘（reports/ 为机器真相源） | ✅ 已镜像至当前个人知识库「AIHR 事故复盘库」 |
| F | `publish.py` 远程校验中文路径编码 bug 修复（消除假 FAIL） | ✅ 已发布 commit `e15be5fe` |

> 注：此前 cb_summary 所述「AIHR 架构重构作战室 2026-08」知识库创建于另一乐享身份，
> 当前会话连接的乐享身份（个人知识库 root `0ec3186ffb7d4c099c9f28ee166675e9`）不可达该库，
> 故本次复盘沉淀在当前个人知识库新建的「AIHR 事故复盘库」文件夹下。两处内容禁止双版本 divergent。

---

## 附：本次验证数据

| 检查项 | 修复前 | 修复后 |
|--------|--------|--------|
| sitemap URL 总数 | 227 | 209 |
| sitemap 内重定向桩页 | 17 | 0 |
| 全站缺 noindex 的重定向桩页 | 17 | 0 |
| `quality_gate --all` | — | 22 关 PASS（含新增 Gate 21） |
| `stability_guard --all` | — | 11 项 PASS |
| 远程 HEAD | 7aae76e1 (M0) | e15be5fe（含 A+F 两次修复提交） |
