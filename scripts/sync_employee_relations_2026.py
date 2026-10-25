"""Four-source incremental sync for ai-era-employee-relations-2026 (2026-10-13).

Baseline = the local copies of the four files, which were overwritten with the
byte-exact remote main content fetched via api.github.com in this run. No
full-rebuild (sync-articles.py known to drop ~50 entries); every edit is an
asserted single-anchor insertion.
"""
import json, re, os

ROOT = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"

SLUG = "ai-era-employee-relations-2026"
TITLE = "AI 起草的申诉在变多，员工关系的受理能力没跟上"
CATEGORY = "核心方法论"
DATE = "2026-10-13"
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"
CARD_EXCERPT = ("AI 抹平了申诉的表达门槛，员工关系的真实水位才露出来。HR Acuity 2026 调研显示"
                "歧视骚扰与报复类指控升至每千人 15.5 件创历史新高，而员工关系编制只从 0.6 微升到 0.68。"
                "WorkNest 调研中仅 12% 雇主有信心中层能处理复杂申诉案。HR 要补的是受理能力。")
LLMS_SUMMARY = ("AI 抹平了申诉的表达门槛，员工关系的真实水位才露出来。HR Acuity 第十次年度员工关系基准调研"
                "显示歧视骚扰与报复类指控升至每千名员工 15.5 件创调研历史最高，案件量 145.5 件/千人接近十年高位，"
                "而编制仅从每千人 0.6 人微升至 0.68 人。WorkNest 2026 年 7 月调研（n=921）中 70% 雇主发现"
                "疑似 AI 起草的申诉上升、仅 12% 有信心中层能处理复杂案件。Gallup 2026 年数据显示管理者敬业度"
                "降至 22%。受理端三处空白：38% 无强制调查流程、62% 不记单案议题数、仅约三分之一按议题类型"
                "追踪成立率。结论：员工关系缺的不是工具，是受理能力的建制化。")

idx_path = os.path.join(ROOT, "assets/js/article-index.json")
html_path = os.path.join(ROOT, "articles/index.html")
sm_path = os.path.join(ROOT, "sitemap.xml")
llms_path = os.path.join(ROOT, "llms-full.txt")

# ---- 0. idempotency guard ----
for p in (idx_path, html_path, sm_path, llms_path):
    assert SLUG not in open(p, encoding="utf-8").read(), f"already synced: {p}"

# ---- 1. article-index.json ----
idx = json.load(open(idx_path, encoding="utf-8"))
assert isinstance(idx, list)
before = len(idx)
assert idx[-1]["url"] == "ai-era-promotion-rules-2026", idx[-1]["url"]
idx.append({"title": TITLE, "url": SLUG, "category": CATEGORY, "date": DATE, "tags": [CATEGORY]})
with open(idx_path, "w", encoding="utf-8") as f:
    json.dump(idx, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(f"[1] article-index.json {before} -> {len(idx)}")

# ---- 2. articles/index.html ----
html = open(html_path, encoding="utf-8").read()

# 2a. prepend card at top of grid
card = (
    '<article class="article-card" data-category="' + CATEGORY + '">\n'
    '  <a href="/articles/' + SLUG + '.html" class="card-link">\n'
    '    <span class="card-tag">' + CATEGORY + '</span>\n'
    '    <h3 class="article-title">' + TITLE + '</h3>\n'
    '    <p class="card-excerpt">' + CARD_EXCERPT + '</p>\n'
    '    <time class="article-date" datetime="' + DATE + '">' + DATE.replace("-", ".") + '</time>\n'
    '  </a>\n</article>\n\n'
)
grid_anchor = '<div class="article-grid" id="article-grid">'
assert html.count(grid_anchor) == 1
gpos = html.find(grid_anchor) + len(grid_anchor)
assert html[gpos:gpos + 2] == "\n\n", repr(html[gpos:gpos + 4])
html = html[:gpos + 1] + card + html[gpos + 1:]
n_cards = len(re.findall(r'class="article-card"', html))
print(f"[2a] index.html cards -> {n_cards}")

# 2b. append ItemList entry (nested mainEntity.itemListElement == [[...]])
m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
d = json.loads(m.group(1))
assert d["@type"] == "CollectionPage", d.get("@type")
il = d["mainEntity"]["itemListElement"][0]
maxpos = max(x.get("position", 0) for x in il)
assert il[-1]["url"].endswith("ai-era-promotion-rules-2026.html"), il[-1]["url"]
il.append({"@type": "ListItem", "position": maxpos + 1, "name": TITLE, "url": URL})
new_json = json.dumps(d, ensure_ascii=False, indent=2)
html = html[:m.start(1)] + new_json + html[m.end(1):]
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"[2b] index.html ItemList {maxpos} -> {maxpos + 1}")

# ---- 3. sitemap.xml (alphabetical insert, preserve ordering invariant) ----
sm = open(sm_path, encoding="utf-8").read()
n_urls = len(re.findall(r'<loc>', sm))
loc = f"https://www.aihrlab.online/articles/{SLUG}.html"
assert loc not in sm
# generate the full url list to find the alphabetical successor
locs = re.findall(r'<loc>([^<]+)</loc>', sm)
succ = next((u for u in locs if u > loc), None)
assert succ is not None, "no alphabetical successor found"
block = f'    <url>\n        <loc>{loc}</loc>\n        <lastmod>{DATE}</lastmod>\n    </url>\n'
succ_block_pos = sm.find(f'    <url>\n        <loc>{succ}</loc>')
assert succ_block_pos != -1, succ
sm = sm[:succ_block_pos] + block + sm[succ_block_pos:]
assert len(re.findall(r'<loc>', sm)) == n_urls + 1
with open(sm_path, "w", encoding="utf-8") as f:
    f.write(sm)
print(f"[3] sitemap.xml {n_urls} -> {n_urls + 1} (inserted before {succ.split('/')[-1]})")

# ---- 4. llms-full.txt ----
llms = open(llms_path, encoding="utf-8").read()
nums = [int(x) for x in re.findall(r'^### (\d+)\.', llms, re.M)]
n = max(nums)
assert n == 198, n
entry = (
    "\n### " + str(n + 1) + ". " + TITLE + "\n"
    "URL: " + URL + "\n"
    "分类: " + CATEGORY + "\n"
    "日期: " + DATE + "\n"
    "摘要: " + LLMS_SUMMARY + "\n"
)
llms = llms.rstrip("\n") + "\n" + entry
# keep the declared site-wide count consistent with index.html ItemList length
old_count = f"- 文章总数：{maxpos} 篇"
assert llms.count(old_count) == 1, old_count
llms = llms.replace(old_count, f"- 文章总数：{maxpos + 1} 篇")
with open(llms_path, "w", encoding="utf-8") as f:
    f.write(llms)
print(f"[4] llms-full.txt ### {n} -> ### {n + 1}; 文章总数 {maxpos} -> {maxpos + 1}")
print("DONE")
