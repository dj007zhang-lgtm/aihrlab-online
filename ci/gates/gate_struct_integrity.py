# -*- coding: utf-8 -*-
"""
gate_struct_integrity —— HTML 起始标签闭合完整性（样式/资源被吞的根因）

三次同源事故（2026-09 批量 SEO 脚本 + 2026-10-07 孤儿 description + 2026-10-11）：
  起始标签缺闭合 `>` 会让浏览器把「后面的标签与内容」当成属性值继续吞，
  直到遇到下一个 `>` 为止。后果按吞到什么而定：
    - 吞掉后续 <meta>        → SERP 摘要错乱（2026-09/Q3）
    - 吞掉后续 <meta> 链      → description 被截断成 6–29 字（2026-10-07）
    - 吞掉 <style>/<script>  → **整页失去 CSS 与脚本，渲染成裸 HTML**（2026-10-11）
  这类缺陷不会触发任何内容/字数/SEO 断言，只有浏览器渲染才暴露。

检测（纯静态、可重现）：
  对每个起始标签（meta/link），若其下一个 `<` 出现在下一个 `>` 之前，
  即判定为「缺闭合 >」 → BLOCK。

为何不限 miejsca articles：工具页/标签页/分类页恰恰是重灾区。
"""
import os
import time

from . import read, rel, GateReport, Finding, walk_html

SKIP_DIRS = {".git", "node_modules", "reports", "ci", "scripts", "__pycache__"}


def unterminated_tags(html, names=("meta", "link", "style", "script")):
    """返回缺闭合 > 的起始标签列表 [(pos, tagname)]。"""
    bad = []
    i = 0
    lower = html.lower()
    while True:
        j = lower.find("<", i)
        if j < 0:
            break
        # 判定标签名
        k = j + 1
        name = ""
        while k < len(lower) and (lower[k].isalnum()):
            name += lower[k]
            k += 1
        if name in names:
            gt = html.find(">", j)
            lt = html.find("<", j + 1)
            if gt < 0 or (lt >= 0 and lt < gt):
                bad.append((j, name))
                i = lt if lt >= 0 else len(html)
                continue
            i = gt + 1
        else:
            i = j + 1
    return bad


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    rep = GateReport("struct_integrity", "起始标签闭合完整性（样式/资源被吞检测）")
    rep.metrics = {"scanned": 0, "unterminated": 0}

    files = walk_html(site_root, None) if callable(walk_html) else None
    if files is None:
        files = []
        for root, dirs, fs in os.walk(site_root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in fs:
                if name.endswith(".html"):
                    files.append(os.path.join(root, name))

    for f in files:
        parts = f.replace(site_root, "").split(os.sep)
        if any(d in SKIP_DIRS for d in parts[:-1]):
            continue
        html = read(f)
        rep.metrics["scanned"] += 1
        bad = unterminated_tags(html)
        if bad:
            rep.metrics["unterminated"] += 1
            detail = "；".join(f"<{n}> @ char {pos}" for pos, n in bad[:5])
            rep.add(Finding(
                "BLOCK", "UNTERMINATED-TAG", file=rel(site_root, f),
                detail=f"起始标签缺闭合 >（共 {len(bad)} 处）：{detail}。"
                       f"浏览器会把后续标签/样式当作属性值吞掉，导致样式或脚本失效。"))

    n = rep.metrics["unterminated"]
    if n:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = f"{n} 个页面存在缺闭合 > 的起始标签（样式/资源会被吞），须修复后发布。"
    else:
        rep.status = "PASS"
        rep.summary = f"扫描 {rep.metrics['scanned']} 个页面，起始标签闭合完整（无被吞风险）。"
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
