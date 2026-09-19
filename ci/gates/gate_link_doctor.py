# -*- coding: utf-8 -*-
"""
gate_link_doctor —— 站内死链 + 重定向契约一致性

覆盖 2026-09 体检的"41 死链/二级跳转漏斗"债：
  1) 内链断裂：可索引页的 .html 内链解析到磁盘不存在、且不在 redirects.json 源集
     → 真死链（BLOCK）。
  2) 重定向契约矛盾：redirects.json 的源路径若在磁盘存在但不是 noindex 桩
     → 真文却登记为重定向源（BLOCK，与 full_debt_audit 维度13 一致）。
  3) 孤儿重定向条目：源文件不在磁盘（WARN，软化处理）。

注意：指向 redirects.json 源 key 的链接视为可达（源页是桩会 302 到真文），不算死链。
"""
import os
import re
import json
import time
from . import (walk_html, read, is_indexable, is_stub_html, rel, GateReport, Finding)


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    p = cfg.get("params", {})
    scan_dirs = p.get("scan_dirs", ["articles", "hub", "resources", "tools", "products"])

    # 磁盘 html 全集（用于死链判定）
    disk_html = set()
    for dirpath, dirnames, filenames in os.walk(site_root):
        if any(s in dirpath.split(os.sep) for s in ("node_modules", ".git", "__pycache__")):
            continue
        for fn in filenames:
            if fn.endswith(".html"):
                disk_html.add(os.path.relpath(os.path.join(dirpath, fn), site_root))

    # redirects.json 契约
    rj = os.path.join(site_root, "redirects.json")
    redirects = {}
    if os.path.exists(rj):
        try:
            redirects = json.load(open(rj, encoding="utf-8"))
        except Exception:
            pass
    redirect_sources = set(os.path.relpath(os.path.join(site_root, k.lstrip("/")), site_root)
                            for k in redirects)

    rep = GateReport("link_doctor", "站内死链 + 重定向契约一致性")
    rep.metrics = {"broken_links": 0, "redirect_conflicts": 0, "orphan_redirects": 0}

    link_pat = re.compile(r'href=["\']([^"\']*\.html[^"\']*)["\']')
    for f in walk_html(site_root, scan_dirs):
        html = read(f)
        if not is_indexable(html):
            continue
        src_rel = rel(site_root, f)
        src_dir = os.path.dirname(f)
        for m in link_pat.finditer(html):
            href = m.group(1)
            if href.startswith(("http://", "https://", "#", "mailto:", "tel:")):
                continue
            href_clean = re.sub(r"[?#].*$", "", href)
            target_abs = os.path.normpath(os.path.join(src_dir, href_clean))
            if not target_abs.startswith(site_root):
                continue  # 解析到站外（合法根导航）
            target_rel = os.path.relpath(target_abs, site_root).replace(os.sep, "/")
            if target_rel in disk_html or os.path.exists(target_abs):
                continue  # 存在（含桩页）→ 可达
            if target_rel in redirect_sources:
                continue  # 源 key → 桩会跳转 → 可达
            rep.add(Finding("BLOCK", "DEAD-LINK", file=src_rel,
                            detail=f"内链断链 → {target_rel}（磁盘不存在且非重定向源）"))
            rep.metrics["broken_links"] += 1

    # 重定向契约矛盾
    for src in redirect_sources:
        abs_path = os.path.join(site_root, src)
        if not os.path.exists(abs_path):
            rep.add(Finding("WARN", "ORPHAN-REDIRECT", detail=f"redirects.json 源 {src} 磁盘无对应文件"))
            rep.metrics["orphan_redirects"] += 1
            continue
        head = read(abs_path)[:2000]
        if not is_stub_html(head):
            rep.add(Finding("BLOCK", "REDIRECT-CONFLICT", file=src,
                            detail="登记为重定向源但磁盘文件非 noindex 桩（真文不应是重定向源）"))
            rep.metrics["redirect_conflicts"] += 1

    if rep.metrics["broken_links"] > 0 or rep.metrics["redirect_conflicts"] > 0:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = f"死链 {rep.metrics['broken_links']} 处 / 重定向矛盾 {rep.metrics['redirect_conflicts']} 处。"
    elif rep.metrics["orphan_redirects"] > 0:
        rep.status = "WARN"
        rep.summary = f"无死链/矛盾；{rep.metrics['orphan_redirects']} 条孤儿重定向（源文件缺失）。"
    else:
        rep.status = "PASS"
        rep.summary = "无死链、无重定向矛盾。"
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
