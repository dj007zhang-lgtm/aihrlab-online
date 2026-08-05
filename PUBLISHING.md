# 发布流程纪律（MANDATORY · 不可跳过）

本文件是网站内容的**强制发布流程**。违反任一条即属发布事故。

## 0. 唯一发布入口（强制）

**所有上线动作只能通过 `scripts/publish.py` 完成。** 禁止直接调用
`scripts/git_atomic.py` 的 `atomic_commit` 绕过质量门。

```bash
python3 scripts/publish.py "feat: 提交说明" file1.html file2.png ...
python3 scripts/publish.py "fix: ..." --dry-run path/to/x.html   # 演练，不写远程
```

`publish.py` 内部顺序（任一失败立即中止，不写远程）：
1. 强制运行 `scripts/quality_gate.py --all`（含 **Gate 0 二维码唯一关**）。
2. 强制运行 `scripts/stability_guard.py --all`（稳定性 / 专业性 / 真实性自检，
   详见 `reports/stability-guard.md`）。任何 BLOCKER（空白页 / 加载失败 / 内容错乱 /
   链接失效 / 品牌色回退 / 导航错乱）即中止推送、零远程写入。
3. 双闸全绿 → 原子推送 → 远程校验。

> 稳定性自检是发布前第二道强制闸门。它专门拦截「让用户秒关页面、拉高跳出率」
> 的低级硬伤——这是过往几次发布后用户高跳出率的根因。新增 `scripts/stability_guard.py`，
> 由 `publish.py` 自动调用，无需手动触发；本地实时守护可用
> `python3 scripts/stability_guard.py --serve`。

## 1. 新文必须源自模板（强制）

- 新文章**必须从 `templates/article-v2.html` 复制**，不得用任意旧文当样板。
- 模板纪律：站点 Footer **禁止**放置公众号二维码；每篇文章仅通过
  `.article-footer-qr` 展示一个二维码 CTA。
- 违反后果：复制带 `.footer-col--qr` 页脚 → Gate 0 FAIL → 推送被阻。

## 2. 发布前自查清单（强制，push 前逐项确认）

- [ ] 文章从 `templates/article-v2.html` 复制，未引入页脚二维码。
- [ ] 全站仅一个二维码：页面含 `.article-footer-qr` 且 **恰好 1 个**，
      无任何 `.footer-col--qr`。
- [ ] 内链文字与目标 H1 **逐字相等**（Gate 10）。
- [ ] 四源同步：article-index.json / articles/index.html / sitemap.xml / llms-full.txt。
- [ ] `python3 scripts/publish.py "..." files...` 跑通（质量门全绿 + 稳定性自检全绿 + 推送 + 远程校验）。
- [ ] 稳定性自检无 BLOCKER：`python3 scripts/stability_guard.py --all` 退出码为 0（空白页 / 资源 404 / 链接失效 / 品牌色回退 / 导航错乱 均为 0）。

## 3. 二维码路径铁律（强制）

- 全站唯一真源：`/assets/images/qrcode-wechat.webp`（webp 优先，jpg 仅后备）。
- 禁用：`/assets/images/wechat-qr.png`（从未存在，致命 broken）、
  `/assets/images/wechat-qrcode.*`（与 canonical MD5 重复的冗余，已删）。
- 页面引用的 QR 资源必须真实存在于仓库（Gate 14 静态资源存在性检查）。

## 4. 监控（强制 · 周度自动化）

- 已挂周度自动化：定期运行 `python3 scripts/monitor_qr_uniqueness.py`。
- 退出码非 0 = 发现违规 → 自动化告警 → 必须当周修复并重新推送。
- 全站每页仅一个公众号二维码，无 `.article-footer-qr` 与 `.footer-col--qr` 重复。

## 5. 违规定义

出现以下任一即视为发布事故，须立即回滚/修复：
- 同一页同时存在 `.article-footer-qr` 与 `.footer-col--qr`；
- 单页 `.article-footer-qr` 出现 ≥ 2 次；
- 引用不存在的二维码资源路径；
- 绕过 `publish.py` 直接原子推送导致未过质量门即上线。
