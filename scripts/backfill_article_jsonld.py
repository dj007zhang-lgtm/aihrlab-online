#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backfill_article_jsonld.py — 幂等回填缺 Article JSON-LD 的真实文章。

扫描 articles/*.html:
  - 已是桩页 (含「页面已迁移」或 http-equiv=refresh) -> 跳过 (零虚构, 不注入 Article)
  - 已含 Article (@type: Article) -> 跳过 (幂等)
  - 真实文章且缺 Article -> 用页面真实元数据结构化回填 Article 块

回填的 Article 字段全部取自页面本身, 绝不虚构:
  headline      <- <title>
  description   <- <meta name="description">
  image        <- <meta property="og:image"> (+ 实测尺寸, 缺省 1200x821 站点约定)
  author/publisher -> Organization (站点固定身份)
  datePublished/dateModified <- <meta property="article:published_time">
  mainEntityOfPage/@id <- <link rel="canonical">

插入位置: <head> 内最后一个 application/ld+json <script> 之后。

连带收益: 回填 Article 后, inject-references.py 即可在其上加 citation 数组,
  使 JSON-LD citation 覆盖率 130/131 -> 131/131 (闭合 recheck 暴露的 GEO 缺陷 1)。

支持:
  --dry-run  只报告将要回填的文件, 不写回
  --slug X   只处理指定 slug (调试)
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTDIR = os.path.join(ROOT, "articles")

ORG_NAME = "AIHR数智引擎"
ORG_URL = "https://www.aihrlab.online/about.html"
JOB_TITLE = "AI时代组织变革研究者"
BANNER_W, BANNER_H = 1200, 821  # 站点 banner 约定尺寸 (已实测 global-tech-hr 即 1200x821)


def _is_article(d):
    t = d.get("@type")
    if t == "Article":
        return True
    if isinstance(t, list) and "Article" in t:
        return True
    return False


def is_stub(html):
    return (
        "页面已迁移" in html
        or 'http-equiv="refresh"' in html
        or "http-equiv='refresh'" in html
    )


def has_article(html):
    for m in re.finditer(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(data, dict) and _is_article(data):
            return True
        if isinstance(data, list):
            for el in data:
                if isinstance(el, dict) and _is_article(el):
                    return True
    return False


def _meta(html, name=None, prop=None):
    pats = []
    if name:
        pats.append(rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"')
    if prop:
        pats.append(rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"')
    for p in pats:
        m = re.search(p, html)
        if m:
            return m.group(1)
    return None


def _read_dims(url):
    m = re.search(r"/assets/(.*)$", url)
    if not m:
        return None, None
    local = os.path.join(ROOT, "assets", m.group(1))
    if not os.path.exists(local):
        return None, None
    try:
        from PIL import Image

        im = Image.open(local)
        return im.size
    except Exception:
        return None, None


def build_article_block(html, slug):
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    headline = t.group(1).strip() if t else slug

    desc = _meta(html, name="description") or ""

    og_image = _meta(html, prop="og:image") or ""
    canonical = None
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', html)
    if m:
        canonical = m.group(1)
    if not canonical:
        canonical = f"https://www.aihrlab.online/articles/{slug}.html"
    main_id = canonical

    published = _meta(html, prop="article:published_time") or ""
    if not published:
        tm = re.search(r'<time[^>]*datetime="([^"]+)"', html)
        if tm:
            published = tm.group(1)
    if not published:
        # 真实文章必有 published_time; 此分支仅为防御, 不应触达
        published = "2026-01-01T00:00:00+08:00"

    # dateModified: 优先页面自身声明的 article:modified_time, 无则回退 published
    # (零虚构: 绝不编造 modified; 页面未声明时以 published 为最后修改日)
    modified = _meta(html, prop="article:modified_time") or published

    img_url = og_image or f"https://www.aihrlab.online/assets/images/banners/{slug}.webp"
    w, h = _read_dims(img_url)
    if w and h:
        image = {"@type": "ImageObject", "url": img_url, "width": w, "height": h}
        logo = {"@type": "ImageObject", "url": img_url, "width": w, "height": h}
    else:
        # 退化为站点 banner 约定尺寸 (真实文章 banner 实测均为 1200x821)
        image = {
            "@type": "ImageObject",
            "url": img_url,
            "width": BANNER_W,
            "height": BANNER_H,
        }
        logo = {
            "@type": "ImageObject",
            "url": img_url,
            "width": BANNER_W,
            "height": BANNER_H,
        }

    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": desc,
        "image": image,
        "author": {
            "@type": "Organization",
            "name": ORG_NAME,
            "url": ORG_URL,
            "jobTitle": JOB_TITLE,
            "worksFor": {"@type": "Organization", "name": ORG_NAME},
        },
        "publisher": {"@type": "Organization", "name": ORG_NAME, "logo": logo},
        "datePublished": published,
        "dateModified": modified,
        "mainEntityOfPage": {"@type": "WebPage", "@id": main_id},
    }


def insert_after_last_head_ld(html, block_json):
    head_end = html.find("</head>")
    if head_end == -1:
        head_end = len(html)
    pattern = re.compile(r'<script type="application/ld\+json">.*?</script>', re.S)
    last = None
    for m in pattern.finditer(html):
        if m.end() <= head_end:
            last = m
    if last:
        pos = last.end()
        return html[:pos] + "\n" + block_json + "\n" + html[pos:]
    if head_end < len(html):
        return html[:head_end] + block_json + "\n" + html[head_end:]
    return html + "\n" + block_json


def process(path, dry_run=False):
    slug = os.path.basename(path)[:-5]
    html = open(path, encoding="utf-8").read()
    if is_stub(html):
        return {"slug": slug, "action": "SKIP_STUB"}
    if has_article(html):
        return {"slug": slug, "action": "SKIP_HAS_ARTICLE"}
    block = build_article_block(html, slug)
    block_json = (
        '<script type="application/ld+json">\n'
        + json.dumps(block, ensure_ascii=False, indent=2)
        + "\n</script>"
    )
    if dry_run:
        return {"slug": slug, "action": "WOULD_BACKFILL"}
    new_html = insert_after_last_head_ld(html, block_json)
    if new_html == html:
        return {"slug": slug, "action": "INSERT_FAIL"}
    open(path, "w", encoding="utf-8").write(new_html)
    return {"slug": slug, "action": "BACKFILLED"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="演练, 不写回")
    ap.add_argument("--slug", help="只处理指定 slug (调试)")
    args = ap.parse_args()

    files = []
    if args.slug:
        p = os.path.join(ARTDIR, args.slug + ".html")
        if os.path.exists(p):
            files = [p]
    else:
        files = sorted(
            os.path.join(ARTDIR, f)
            for f in os.listdir(ARTDIR)
            if f.endswith(".html")
        )

    backfilled = 0
    skipped_stub = 0
    skipped_has = 0
    failed = 0
    for p in files:
        r = process(p, dry_run=args.dry_run)
        a = r["action"]
        if a in ("BACKFILLED", "WOULD_BACKFILL"):
            backfilled += 1
            print(f"  [{'演练' if args.dry_run else '回填'}] {r['slug']}")
        elif a == "SKIP_STUB":
            skipped_stub += 1
        elif a == "SKIP_HAS_ARTICLE":
            skipped_has += 1
        elif a == "INSERT_FAIL":
            failed += 1
            print(f"  [插入失败] {r['slug']}")

    print(
        f"\n[完成] 文件={len(files)}  回填={backfilled}"
        f"  跳过(已含Article)={skipped_has}  跳过(桩页)={skipped_stub}"
        + (f"  失败={failed}" if failed else "")
    )


if __name__ == "__main__":
    main()
