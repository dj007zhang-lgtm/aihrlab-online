#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical +1 four-source sync for cross-cultural-team-management-2026.

Merges onto the authoritative remote main (commit 721d1390) by prepending one
new article to each of the four targets. Does NOT pull in the 17 historical
orphan articles (remote articles/ dir > index). Remote base is the source of
truth; local disk is only the publish working copy.
"""
import json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "cross-cultural-team-management-2026"
TITLE = "跨文化团队：权力距离不靠翻译解决"
CAT = "组织变革"
DATE = "2026-09-10"
URL = "https://www.aihrlab.online/articles/%s.html" % SLUG
URL_REL = "/articles/%s.html" % SLUG

# ---- 1. article-index.json ----
idx = json.load(open("/tmp/idxjson_dec.txt", encoding="utf-8"))
assert isinstance(idx, list)
new_entry = {
    "title": TITLE,
    "url": SLUG,
    "category": CAT,
    "date": DATE,
    "tags": ["跨文化团队", "权力距离", "全球虚拟团队", "文化智力", "决策权",
             "互动协议", "心理安全", "出海组织", "AI翻译"],
}
idx.insert(0, new_entry)  # newest-first to match card / ItemList order
with open(os.path.join(ROOT, "assets/js/article-index.json"), "w", encoding="utf-8") as f:
    json.dump(idx, f, ensure_ascii=False, indent=2)
print("article-index.json:", len(idx), "entries")

# ---- 2. articles/index.html ----
html = open("/tmp/idx_api.json", "rb").read()
# decode the API json wrapper to get html
_api = json.loads(html)
_html = _api["content"]
import base64
html = base64.b64decode(_html).decode("utf-8")

# 2a. insert card right after the grid opener
card = ('''<article class="article-card" data-category="组织变革">
  <a href="%s" class="card-link">
    <span class="card-tag">组织变革</span>
    <h3 class="article-title">%s</h3>
    <p class="card-excerpt">跨文化团队最大的失效不在翻译，在互动协议。AI 翻译把语言成本打到趋零，却抹不平权力距离；Hofstede 与 2026 全球虚拟团队研究说明，低权力距离总部管高权力距离本地会失灵。</p>
    <time class="article-date" datetime="%s">%s</time>
  </a>
</article>
''' % (URL_REL, TITLE, DATE, DATE.replace("-", ".")))
marker = '<div class="article-grid" id="article-grid">'
pos = html.find(marker) + len(marker)
html = html[:pos] + "\n\n" + card + html[pos:]

# 2b. rebuild ItemList (prepend new, renumber)
m = re.search(r'("itemListElement":\s*\[)(.*?)(\])', html, re.S)
head, block, tail = m.group(1), m.group(2), m.group(3)
items = re.findall(r'\{\s*"@type":\s*"ListItem".*?\}', block, re.S)
new_items = ['{"@type":"ListItem","position":1,"name":%s,"url":%s}'
             % (json.dumps(TITLE, ensure_ascii=False), json.dumps(URL, ensure_ascii=False))]
for it in items:
    mm = re.search(r'"position":\s*(\d+)', it)
    old_pos = int(mm.group(1))
    new_items.append(it.replace('"position":%d' % old_pos, '"position":%d' % (old_pos + 1)))
new_block = ",".join(new_items)
html = html[:m.start()] + head + new_block + tail + html[m.end():]
with open(os.path.join(ROOT, "articles/index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("articles/index.html: cards + ItemList updated, new position 1")

# ---- 3. sitemap.xml ----
sm = open("/tmp/sitemap_dec.xml", encoding="utf-8").read()
new_url = ("\n    <url>\n"
           "        <loc>%s</loc>\n"
           "        <lastmod>%s</lastmod>\n"
           "    </url>\n</urlset>" % (URL, DATE))
sm = sm.replace("</urlset>", new_url, 1)
with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
    f.write(sm)
print("sitemap.xml: <loc> count =", sm.count("<loc>"))

# ---- 4. llms-full.txt ----
ll = open("/tmp/llms_dec.txt", encoding="utf-8").read()
# find last numbered block
nums = [int(x) for x in re.findall(r'^###\s*(\d+)\.', ll, re.M)]
next_n = max(nums) + 1
block = ("\n### %d. %s\nURL: %s\n分类: %s\n日期: %s\n摘要: %s\n"
         % (next_n, TITLE, URL, CAT, DATE,
            "跨文化团队最大的失效不在翻译，在互动协议。组织等于信息传递网络加利益分配网络，"
            "语言只是信息流载体，文化才是决策权硬约束。AI 翻译把语言成本打到趋零却抹不平权力距离；"
            "Hofstede 权力距离指数、Wiley 与 Acta Commercii 2026 全球虚拟团队研究、Microsoft WTI 2026 说明，"
            "低权力距离总部管高权力距离本地会失灵，正确做法是把互动协议写成接口。"))
ll = ll.rstrip() + "\n" + block
with open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8") as f:
    f.write(ll)
print("llms-full.txt: next block =", next_n)
