#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical four-source sync for strategic-workforce-planning-ai-2026.

Fetches the REAL remote main versions of the 4 sync targets, inserts exactly
one new article (no other modifications -> local becomes remote + 1 article,
zero drift), and writes the result to local disk for the atomic publish.

Does NOT pull in the 17 pre-existing orphan articles (live on main but absent
from index json + sitemap) -> out of scope for this single-article publish.
"""
import os, sys, json, base64, re, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_atomic as ga

ROOT = ga.ROOT
TOKEN = ga.TOKEN
CONTENTS = ga.CONTENTS
BRANCH = ga.BRANCH

SLUG = "strategic-workforce-planning-ai-2026"
TITLE = "战略人力规划失效：不是算不准，是算错对象"
CATEGORY = "核心方法论"
DATE = "2026-09-09"
DATE_DISPLAY = "2026.09.09"
DESC = ("战略人力规划的失效不是预测精度问题，是规划对象错了：传统 SWP 以人头为单位，"
        "AI 时代被重排的却是任务与能力的配比。本文基于 Mercer《2026 全球人才趋势》、"
        "Gartner 战略人力规划研究与 2026 CHRO 优先级、ETHRWorld《2026 全球学习与技能报告》"
        "一手数据，拆解只有 15% 的组织真做 SWP 的结构性原因，并给出从人头预算到能力推演的"
        "四个可验收动作。")
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"
TAGS = ["战略人力规划", "能力推演", "技能可见性", "工作重设计"]


def fetch_remote(rel, ref):
    u = f"{CONTENTS}/{rel}?ref={ref}"
    req = urllib.request.Request(u)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", "aihr-sync")
    req.add_header("Accept", "application/vnd.github+json")
    d = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return base64.b64decode(d["content"]).decode("utf-8", "ignore")


def main():
    head = ga._req("GET", f"refs/heads/{BRANCH}")["object"]["sha"]
    print(f"remote HEAD = {head}")

    # ---- 1. article-index.json (append) ----
    idx_txt = fetch_remote("assets/js/article-index.json", head)
    idx = json.loads(idx_txt)
    assert all(e["url"] != SLUG for e in idx), "article already in index json!"
    idx.append({
        "title": TITLE,
        "url": SLUG,
        "category": CATEGORY,
        "date": DATE,
        "tags": TAGS,
    })
    with open(os.path.join(ROOT, "assets/js/article-index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print(f"  [1] article-index.json -> {len(idx)} entries")

    # ---- 2. articles/index.html (card + ItemList) ----
    html = fetch_remote("articles/index.html", head)
    card_html = (
        f'<article class="article-card" data-category="{CATEGORY}">\n'
        f'  <a href="/articles/{SLUG}.html" class="card-link">\n'
        f'    <span class="card-tag">{CATEGORY}</span>\n'
        f'    <h3 class="article-title">{TITLE}</h3>\n'
        f'    <p class="card-excerpt">{DESC[:100]}...</p>\n'
        f'    <time class="article-date" datetime="{DATE}">{DATE_DISPLAY}</time>\n'
        f'  </a>\n'
        f'</article>'
    )
    marker = '<div class="article-grid" id="article-grid">'
    assert marker in html, "article-grid marker missing"
    html = html.replace(marker, marker + "\n\n" + card_html, 1)

    # rebuild ItemList
    new_items = [{"@type": "ListItem", "position": 1, "name": TITLE, "url": URL}]
    for blk in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(blk.group(1))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "CollectionPage":
            old = data["mainEntity"]["itemListElement"]
            for i, it in enumerate(old, start=2):
                it["position"] = i
                new_items.append(it)
            data["mainEntity"] = {"@type": "ItemList", "itemListElement": new_items}
            new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            html = html[:blk.start()] + f'<script type="application/ld+json">{new_json}</script>' + html[blk.end():]
            break
    with open(os.path.join(ROOT, "articles/index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [2] articles/index.html -> +1 card, ItemList {len(new_items)} items")

    # ---- 3. sitemap.xml (append before </urlset>) ----
    sm = fetch_remote("sitemap.xml", head)
    assert f"<loc>{URL}</loc>" not in sm, "article already in sitemap!"
    block = (
        '    <url>\n'
        f'        <loc>{URL}</loc>\n'
        f'        <lastmod>{DATE}</lastmod>\n'
        '    </url>\n'
    )
    assert "</urlset>" in sm, "</urlset> missing"
    sm = sm.replace("</urlset>", block + "</urlset>", 1)
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sm)
    print(f"  [3] sitemap.xml -> +1 url")

    # ---- 4. llms-full.txt (append ### block) ----
    ll = fetch_remote("llms-full.txt", head)
    nums = [int(m) for m in re.findall(r'^###\s*(\d+)\.', ll, re.M)]
    next_n = (max(nums) + 1) if nums else 1
    block = (
        f"\n\n### {next_n}. {TITLE}\n"
        f"URL: {URL}\n"
        f"分类: {CATEGORY}\n"
        f"日期: {DATE}\n"
        f"摘要: {DESC}\n"
    )
    if not ll.endswith("\n"):
        ll += "\n"
    ll += block
    with open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8") as f:
        f.write(ll)
    print(f"  [4] llms-full.txt -> ### {next_n}. block appended")

    print("=== surgical sync done (local == remote + 1 article) ===")


if __name__ == "__main__":
    main()
