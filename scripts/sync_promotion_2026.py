import json, re, subprocess, os

ROOT = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"

SLUG = "ai-era-promotion-rules-2026"
TITLE = "AI 改写了晋升规则：资历梯子塌了，能力怎么算"
CATEGORY = "核心方法论"
DATE = "2026-10-11"
DATE_ISO = "2026-10-11"
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"
CARD_EXCERPT = ("AI 改写了晋升规则的核心判点：晋升是组织分配权力与地位的核心机制，"
               "资历不再等于准备好上一级。Gartner 2026 指出本级绩效不再是更高层级就绪度的代理，"
               "初级台阶被 AI 抽走，组织失去积累判断样本的路径。HR 要从资历阶梯转向技能本位内部流动。")
LLMS_SUMMARY = ("AI 改写了晋升规则的核心判点：晋升是组织分配权力、薪酬与地位的核心机制，"
               "它的依据被 AI 同时撬动两端。Gartner 2026 年 5 月指出本级绩效不再是更高层级就绪度的代理；"
               "初级台阶被 AI 抽走，组织失去积累判断样本的路径。组织转向技能本位内部流动补位，"
               "但内部流动率停滞、岗位架构陈旧、技能数据薄弱，补不上漏洞。结论：HR 要重写的是利益分配网络的依据。")


def git_show(path):
    return subprocess.check_output(["git", "show", f"origin/main:{path}"], cwd=ROOT).decode("utf-8")


# ---- 1. article-index.json ----
idx = json.loads(git_show("assets/js/article-index.json"))
idx.append({"title": TITLE, "url": SLUG, "category": CATEGORY, "date": DATE, "tags": [CATEGORY]})
with open(os.path.join(ROOT, "assets/js/article-index.json"), "w", encoding="utf-8") as f:
    json.dump(idx, f, ensure_ascii=False, indent=2)
print("article-index.json ->", len(idx), "entries")

# ---- 2. articles/index.html ----
html = open("/tmp/remote_index.html", encoding="utf-8").read()

# 2a. insert card at top of grid (before first <article class="article-card")
card = (
    '<article class="article-card" data-category="' + CATEGORY + '">\n'
    '  <a href="/articles/' + SLUG + '.html" class="card-link">\n'
    '    <span class="card-tag">' + CATEGORY + '</span>\n'
    '    <h3 class="article-title">' + TITLE + '</h3>\n'
    '    <p class="card-excerpt">' + CARD_EXCERPT + '</p>\n'
    '    <time class="article-date" datetime="' + DATE_ISO + '">' + DATE_ISO.replace("-", ".") + '</time>\n'
    '  </a>\n</article>\n\n'
)
pos = html.find('<article class="article-card"')
assert pos != -1, "card anchor not found"
html = html[:pos] + card + html[pos:]

# 2b. append ItemList entry (nested: mainEntity.itemListElement == [ [items] ])
m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
d = json.loads(m.group(1))
il = d["mainEntity"]["itemListElement"][0]
maxpos = max(x.get("position", 0) for x in il)
il.append({"@type": "ListItem", "position": maxpos + 1, "name": TITLE, "url": URL})
new_json = json.dumps(d, ensure_ascii=False, indent=2)
html = html[:m.start(1)] + new_json + html[m.end(1):]
with open(os.path.join(ROOT, "articles/index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("articles/index.html -> ItemList max pos", maxpos, "->", maxpos + 1)

# ---- 3. sitemap.xml ----
sm = git_show("sitemap.xml")
block = (
    '    <url>\n'
    '        <loc>' + URL + '</loc>\n'
    '        <lastmod>' + DATE_ISO + '</lastmod>\n'
    '    </url>\n'
)
sm = sm.replace("</urlset>", block + "</urlset>", 1)
with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
    f.write(sm)
print("sitemap.xml -> url appended")

# ---- 4. llms-full.txt ----
llms = git_show("llms-full.txt")
# count existing ### entries
n = len(re.findall(r'^### \d+\.', llms, re.M))
entry = (
    "\n### " + str(n + 1) + ". " + TITLE + "\n"
    "URL: " + URL + "\n"
    "分类: " + CATEGORY + "\n"
    "日期: " + DATE_ISO + "\n"
    "摘要: " + LLMS_SUMMARY + "\n"
)
llms = llms.rstrip("\n") + "\n" + entry
with open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8") as f:
    f.write(llms)
print("llms-full.txt -> ###", n + 1)
print("DONE")
