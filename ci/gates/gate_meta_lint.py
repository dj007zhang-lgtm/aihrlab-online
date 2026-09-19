# -*- coding: utf-8 -*-
"""
gate_meta_lint —— meta description 污染 / 占位符残留 / 引号规范

固化 2026-09-14 的线上回归：批量提取脚本把导航文本、站级样板、甚至另一篇导语
写进 description，造成 SERP 摘要与主题不符，直接抵消 CTR 刹车解除成果。
该回归当时已上线、靠人工体检才发现 —— 本门使其永久不可复犯。

检测项：
  - description 缺失 / 过短（< desc_min_cjk 中文字）→ WARN
  - description 以导航垃圾/站级样板前缀开头 → BLOCK（SERP 污染）
  - 占位符残留 PLACEHOLDER/TODO/待填写/{{ }} → BLOCK
  - title/h1 含英文引号 → WARN（Gate9 角引号纪律）
  - title 正文 > warn_title_len_cjk 字 → WARN
"""
import re
import time
from . import (walk_html, read, is_indexable, count_cjk, rel, GateReport, Finding)

DESC_PAT = re.compile(r'<meta\s+[^>]*name=["\']description["\']\s+content=["\'](.*?)["\']', re.I | re.S)
TITLE_PAT = re.compile(r'<title>(.*?)</title>', re.S | re.I)
H1_PAT = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S | re.I)
PLACEHOLDER_PAT = re.compile(r'(?<![a-z])PLACEHOLDER(?![a-z])|\bTODO\b[\s:]|待填写|待补充|待替换|\{\{.*?\}\}|YOUR_DESCRIPTION_HERE|YOUR_TITLE_HERE')


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    p = cfg.get("params", {})
    scan_dirs = p.get("scan_dirs", ["articles"])
    desc_min = p.get("desc_min_cjk", 30)
    nav_junk = p.get("nav_junk_prefixes", [])
    warn_title_len = p.get("warn_title_len_cjk", 60)
    block_placeholder = p.get("block_placeholder", True)

    rep = GateReport("meta_lint", "meta description 污染 / 占位符 / 引号规范")
    rep.metrics = {"scanned": 0, "corrupt_desc": 0, "placeholder": 0, "bad_quotes": 0, "long_title": 0}

    for f in walk_html(site_root, scan_dirs):
        html = read(f)
        if not is_indexable(html):
            continue
        rep.metrics["scanned"] += 1
        relf = rel(site_root, f)

        # description
        dm = DESC_PAT.search(html)
        if not dm:
            rep.add(Finding("WARN", "DESC-MISSING", file=relf, detail="无 meta description。"))
        else:
            desc = dm.group(1).strip()
            dlen = count_cjk(desc)
            if dlen < desc_min:
                rep.add(Finding("WARN", "DESC-SHORT", file=relf,
                                detail=f"description 仅 {dlen} 中文字（< {desc_min}），弱兜底。"))
            for pre in nav_junk:
                if desc.startswith(pre):
                    rep.add(Finding("BLOCK", "DESC-CORRUPT", file=relf,
                                    detail=f"description 以站级/导航样板开头「{pre}…」，SERP 污染。"))
                    rep.metrics["corrupt_desc"] += 1
                    break

        # 占位符
        if block_placeholder and PLACEHOLDER_PAT.search(html):
            rep.add(Finding("BLOCK", "PLACEHOLDER", file=relf, detail="含模板占位符残留（PLACEHOLDER/TODO/待填写/{{ }}）。"))
            rep.metrics["placeholder"] += 1

        # 引号
        tm = TITLE_PAT.search(html)
        hm = H1_PAT.search(html)
        bad = False
        for mm in (tm, hm):
            if mm:
                t = mm.group(1)
                if '"' in t or '"' in t or "&quot;" in t or "&#x22;" in t:
                    bad = True
        if bad:
            rep.add(Finding("WARN", "EN-QUOTE", file=relf, detail="title/h1 含英文引号（须用「」角引号）。"))
            rep.metrics["bad_quotes"] += 1

        # 标题长度
        if tm:
            tclean = re.sub(r"\s*[|\-]\s*AIHR.*$", "", tm.group(1).strip())
            if len(tclean) > warn_title_len:
                rep.add(Finding("WARN", "TITLE-LONG", file=relf,
                                detail=f"title 正文 {len(tclean)} 字（> {warn_title_len}）。"))
                rep.metrics["long_title"] += 1

    blocks = rep.metrics["corrupt_desc"] + rep.metrics["placeholder"]
    if blocks > 0:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = f"description 污染 {rep.metrics['corrupt_desc']} / 占位符 {rep.metrics['placeholder']}。"
    elif rep.metrics["scanned"] == 0:
        rep.status = "ERROR"
        rep.summary = "未扫描到任何可索引页，请检查 scan_dirs 配置。"
    else:
        rep.status = "PASS" if (rep.metrics["bad_quotes"] + rep.metrics["long_title"]) == 0 else "WARN"
        rep.summary = (f"扫描 {rep.metrics['scanned']} 篇；"
                       f"引号 {rep.metrics['bad_quotes']} / 长标题 {rep.metrics['long_title']}（仅告警）。")
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
