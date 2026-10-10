# -*- coding: utf-8 -*-
"""
gate_content_container —— 正文容器缺失检测（行宽崩坏预防）

背景（2026-10-10 主理人发现）：
  ai-era-* 系列文章由另一条生成链路产出，缺少 `.article-body` 容器；
  而 CSS 的行宽约束（max-width 720px）正是挂在容器上。结果正文直接作为
  <article> 的子节点渲染，段落横跨整个视口（实测 1440px / 约 80 汉字每行），
  页面在视觉上等同于"没排版的纯文本"。同批共 17 篇文章受影响。

为何必须机器拦截：
  这类缺陷不会触发任何字数/链接/SEO 类闸门——页面结构与内容都是"好的"，
  只是缺一个包裹层。人眼才会发现，而人眼只会在事后发现。

检测规则：
  可索引（无 noindex）且有 <h1> 的文章，必须存在以下任一正文容器：
    .article-body（v2 模板） / .article-content-wrapper 或 .article-content（v1 模板）
  缺失 → BLOCK。

输出：
  缺失容器 → BLOCK（PREVENT-LINE-OVERFLOW）。
"""
import time

from . import (walk_html, read, is_indexable, rel, GateReport, Finding)

CONTAINERS = ("article-body", "article-content-wrapper", "article-content")


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    p = cfg.get("params", {})
    scan_dirs = p.get("scan_dirs", ["articles"])

    rep = GateReport("content_container", "正文容器缺失检测（行宽崩坏预防）")
    rep.metrics = {"scanned": 0, "missing_container": 0}

    for f in walk_html(site_root, scan_dirs):
        html = read(f)
        if "<h1" not in html:
            continue
        if not is_indexable(html):
            continue  # 不收录的页面（含迁移桩、未扩写的薄页）不参与正文版式要求
        rep.metrics["scanned"] += 1
        has_container = any(c in html for c in CONTAINERS)
        if not has_container:
            rep.metrics["missing_container"] += 1
            rep.add(Finding(
                "BLOCK", "MISSING-CONTAINER", file=rel(site_root, f),
                detail="可索引文章缺正文容器（.article-body / .article-content-wrapper），"
                       "正文行宽将拉满视口，须包裹容器后再发布。"))

    n = rep.metrics["missing_container"]
    if n:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = f"{n} 篇可索引文章缺正文容器（行宽会拉满视口），须包裹后发布。"
    else:
        rep.status = "PASS"
        rep.summary = f"扫描 {rep.metrics['scanned']} 篇可索引文章，正文容器齐备（行宽受约束）。"
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
