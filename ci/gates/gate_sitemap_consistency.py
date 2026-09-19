# -*- coding: utf-8 -*-
"""
gate_sitemap_consistency —— sitemap↔磁盘 + article-index.json 有效性

固化历史债：sitemap 漏收新文/标签归档页（爬虫慢爬）、article-index.json 含无效 slug
（搜索框/相关推荐指向 404）。2026-08 曾因软 404 连坐拖垮整批收录。
本门把"索引与磁盘一致"变成每次发布硬闸门。
"""
import os
import re
import json
import time
from . import (rel, GateReport, Finding)


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    rep = GateReport("sitemap_consistency", "sitemap↔磁盘 + article-index 有效性")
    rep.metrics = {"sitemap_urls": 0, "missing_on_disk": 0, "invalid_index_slugs": 0}

    # sitemap → 磁盘
    sp = os.path.join(site_root, "sitemap.xml")
    if os.path.exists(sp):
        content = open(sp, encoding="utf-8").read()
        urls = re.findall(r"<loc>(https?://[^<]+)</loc>", content)
        rep.metrics["sitemap_urls"] = len(urls)
        for url in urls:
            relp = url.split("//", 1)[-1].split("/", 1)[-1] if "//" in url else url.lstrip("/")
            abs_p = os.path.join(site_root, relp)
            if relp.endswith("/"):
                abs_p = os.path.join(abs_p, "index.html")
            elif not relp.endswith(".html"):
                abs_p += ".html"
            if not os.path.exists(abs_p):
                rep.add(Finding("BLOCK", "SITEMAP-ORPHAN", detail=f"sitemap URL 无对应文件：{relp}"))
                rep.metrics["missing_on_disk"] += 1

    # article-index.json
    aip = os.path.join(site_root, "assets", "js", "article-index.json")
    if not os.path.exists(aip):
        aip = os.path.join(site_root, "article-index.json")
    if os.path.exists(aip):
        try:
            data = json.load(open(aip, encoding="utf-8"))
            items = data if isinstance(data, list) else data.get("articles", [])
            arts_dir = os.path.join(site_root, "articles")
            for item in items:
                slug = item.get("url", "") or item.get("slug", "")
                slug = slug.lstrip("/").split("/")[-1]
                if not slug:
                    continue
                if not slug.endswith(".html"):
                    slug += ".html"
                if not os.path.exists(os.path.join(arts_dir, slug)):
                    rep.add(Finding("BLOCK", "INDEX-SLUG-INVALID", detail=f"article-index 无效 slug：{slug}"))
                    rep.metrics["invalid_index_slugs"] += 1
        except Exception as e:
            rep.add(Finding("ERROR", "INDEX-PARSE", detail=f"article-index.json 解析失败：{e}"))

    if rep.metrics["missing_on_disk"] > 0 or rep.metrics["invalid_index_slugs"] > 0:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = (f"sitemap 孤儿 {rep.metrics['missing_on_disk']} / "
                       f"index 无效 slug {rep.metrics['invalid_index_slugs']}。")
    else:
        rep.status = "PASS"
        rep.summary = f"sitemap {rep.metrics['sitemap_urls']} URL 全部对应磁盘；article-index 有效。"
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
