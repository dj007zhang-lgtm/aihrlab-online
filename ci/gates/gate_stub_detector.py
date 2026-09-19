# -*- coding: utf-8 -*-
"""
gate_stub_detector —— 薄内容/桩页检测

语义（区别于"刻意迁移桩"）：
  - 刻意迁移桩 = noindex + meta refresh → 故意存在，跳过。
  - 真问题 = 可被搜索引擎收录（无 noindex）却正文 < max_words 字 → 拖低域名质量分。
    这正是 2026-09 体检发现的 30 个 <500 字实质桩页债务。

输出：
  - 可索引且 < max_words 字 → BLOCK（薄内容）。
  - 可索引且 [max_words, warn_words) → WARN（临界，进 baseline 跟踪）。
"""
import time
from . import (walk_html, read, is_indexable, clean_text, count_cjk,
               rel, GateReport, Finding)


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    p = cfg.get("params", {})
    scan_dirs = p.get("scan_dirs", ["articles", "resources", "tools", "products"])
    max_words = p.get("max_words", 500)
    warn_words = p.get("warn_words", 800)

    rep = GateReport("stub_detector", "薄内容/桩页检测（可索引页正文深度）")
    rep.metrics = {"scanned": 0, "thin_block": 0, "thin_warn": 0, "max_words": max_words,
                   "warn_words": warn_words, "median_words": 0}
    counts = []
    for f in walk_html(site_root, scan_dirs):
        html = read(f)
        if not is_indexable(html):
            continue  # 跳过 noindex/refresh 桩（刻意存在）
        wc = count_cjk(clean_text(extract_body_guard(html)))
        counts.append(wc)
        rep.metrics["scanned"] += 1
        if wc < max_words:
            rep.add(Finding("BLOCK", "THIN-CONTENT", file=rel(site_root, f),
                            detail=f"可索引页正文仅 {wc} 字（< {max_words}），属实质桩页。"))
            rep.metrics["thin_block"] += 1
        elif wc < warn_words:
            rep.add(Finding("WARN", "THIN-BORDER", file=rel(site_root, f),
                            detail=f"可索引页正文 {wc} 字（临界区 {max_words}–{warn_words}）。"))
            rep.metrics["thin_warn"] += 1

    if counts:
        counts.sort()
        rep.metrics["median_words"] = counts[len(counts) // 2]

    base = (baseline or {}).get("gates", {}).get("stub_detector", {})
    base_thin = base.get("thin_block", None)
    if rep.metrics["thin_block"] > 0:
        if base_thin is None:
            # 首次运行（无 baseline）：记录已知债为 WARN，由编排器种 baseline，不阻断。
            for fnd in rep.findings:
                if fnd["severity"] == "BLOCK":
                    fnd["severity"] = "WARN"
            rep.blocking = False
            rep.status = "WARN" if rep.findings else "PASS"
            rep.summary = (f"首次运行记录 {rep.metrics['thin_block']} 个已知薄内容页"
                           f"（<{max_words}字）为 baseline；将按回归锁仅告警，新增即阻断。")
        elif rep.metrics["thin_block"] > base_thin:
            # 薄内容页数超过基线 → 新增债务 → 阻断（错不二犯）。
            rep.status = "FAIL"
            rep.blocking = True
            rep.summary = (f"薄内容页 {rep.metrics['thin_block']} > baseline {base_thin}"
                           f"（新增 {rep.metrics['thin_block']-base_thin} 篇），须合并/重写后再发布。")
        else:
            # 已知债未增加 → 仅告警。
            for fnd in rep.findings:
                if fnd["severity"] == "BLOCK":
                    fnd["severity"] = "WARN"
            rep.blocking = False
            rep.status = "WARN" if rep.findings else "PASS"
            rep.summary = (f"薄内容 {rep.metrics['thin_block']} 篇（=baseline {base_thin}，未新增），"
                           f"临界区 {rep.metrics['thin_warn']} 篇（{max_words}–{warn_words}字）。")
    elif rep.metrics["thin_warn"] > 0:
        rep.status = "WARN"
        rep.summary = f"无阻断级薄内容；{rep.metrics['thin_warn']} 篇处于临界区（{max_words}–{warn_words}字）。"
    else:
        rep.status = "PASS"
        rep.summary = f"扫描 {rep.metrics['scanned']} 篇可索引页，正文深度达标（中位数 {rep.metrics['median_words']} 字）。"
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep


def extract_body_guard(html):
    """复用 gates 的 body 截取；本模块独立避免循环依赖问题。"""
    from . import extract_article_body
    return extract_article_body(html)
