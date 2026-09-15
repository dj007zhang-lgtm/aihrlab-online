#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical +1 sync for ai-era-employee-retention-2026 (remote base == local)."""
import json, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets", "js", "article-index.json")
INDEX_HTML = os.path.join(ROOT, "articles", "index.html")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
LLMS = os.path.join(ROOT, "llms-full.txt")

SLUG = "ai-era-employee-retention-2026"
TITLE = "AI 改写岗位后，人凭什么留下"
DATE = "2026-09-13"
CAT = "组织变革"
EXCERPT = ("AI 没有消灭工作，而是把岗位从长期资产重排为流动的能力单元。"
           "组织留人的逻辑随之翻转：从承诺换忠诚，转向持续让人在价值再分配中"
           "留在升值的一侧。2026 一手数据给出断层……")

# ---- 1. article-index.json (append at end) ----
data = json.load(open(ASSETS, encoding="utf-8"))
assert SLUG not in [x.get("url") for x in data], "slug already indexed"
data.append({
    "title": TITLE,
    "url": SLUG,
    "category": CAT,
    "date": DATE,
    "tags": ["AI人才留存", "员工留存", "AI重塑岗位", "组织变革",
             "利益分配网络", "静默流失", "人才再配置", "人机协作", "留人逻辑"],
})
json.dump(data, open(ASSETS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("article-index.json ->", len(data), "entries")

# ---- 2. articles/index.html (card + ItemList) ----
html = open(INDEX_HTML, encoding="utf-8").read()
card = (
    '<article class="article-card" data-category="%s">\n'
    '  <a href="/articles/%s.html" class="card-link">\n'
    '    <span class="card-tag">%s</span>\n'
    '    <h3 class="article-title">%s</h3>\n'
    '    <p class="card-excerpt">%s</p>\n'
    '    <time class="article-date" datetime="%s">%s</time>\n'
    '  </a>\n'
    '</article>'
) % (CAT, SLUG, CAT, TITLE, EXCERPT, DATE, DATE.replace("-", "."))
anchor = "</article>\n\n\n</div></section>"
pos = html.rfind(anchor)
assert pos != -1, "grid closing anchor not found"
html = html[:pos] + "</article>\n\n" + card + "\n\n</div></section>"
assert html.count('<article class="article-card"') == 271, html.count('<article class="article-card"')
open(INDEX_HTML, "w", encoding="utf-8").write(html)
print("articles/index.html -> 271 cards")

# ItemList 271
item_anchor = ('{"@type": "ListItem", "position": 270, "name": "HR 数据治理：AI 时代谁为数据负责", '
              '"url": "https://www.aihrlab.online/articles/hr-data-governance-2026.html"}]')
assert item_anchor in html, "ItemList 270 anchor not found"
new_item = (',{"@type": "ListItem", "position": 271, "name": "%s", '
            '"url": "https://www.aihrlab.online/articles/%s.html"}' % (TITLE, SLUG))
html = html.replace(item_anchor, item_anchor + new_item, 1)
assert html.count('"position": 271') == 1
open(INDEX_HTML, "w", encoding="utf-8").write(html)
print("articles/index.html ItemList -> 271 items")

# ---- 3. sitemap.xml ----
sm = open(SITEMAP, encoding="utf-8").read()
assert SLUG not in sm, "sitemap already has slug"
url_block = ('<url><loc>https://www.aihrlab.online/articles/%s.html</loc>'
             '<lastmod>%s</lastmod><changefreq>weekly</changefreq>'
             '<priority>0.8</priority></url>\n</urlset>' % (SLUG, DATE))
sm = sm.replace("</urlset>", url_block, 1)
assert sm.count("<url>") == sm.count("</url>")
open(SITEMAP, "w", encoding="utf-8").write(sm)
print("sitemap.xml -> +1 url")

# ---- 4. llms-full.txt ----
llms = open(LLMS, encoding="utf-8").read()
nums = [int(x) for x in re.findall(r"^### (\d+)\.", llms, re.M)]
nxt = max(nums) + 1
assert SLUG not in llms, "llms already has slug"
block = (
    "\n### %d. %s\n"
    "URL: https://www.aihrlab.online/articles/%s.html\n"
    "分类: %s\n"
    "日期: %s\n"
    "摘要: %s\n"
) % (nxt, TITLE, SLUG, CAT, DATE, EXCERPT)
llms = llms.rstrip() + "\n" + block
open(LLMS, "w", encoding="utf-8").write(llms)
print("llms-full.txt -> ### %d." % nxt)

# ---- final sanity: no non-ASCII in sitemap locs ----
non_ascii = re.findall(r"<loc>(.*?)</loc>", sm)
bad = [u for u in non_ascii if any(ord(c) > 127 for c in u)]
print("sitemap non-ASCII locs:", len(bad))
print("ALL SYNC DONE")
