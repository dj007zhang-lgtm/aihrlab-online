#!/usr/bin/env python3
# 一次性外科手术式同步单篇文章到四源（不整体重写，避免扰动工作树其他已改文件）
import io, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SLUG = "bigtech-ai-dept-split-merge-2026"
TITLE = "大厂 AI 部门拆分合并：组织能力还是政治秀"
DATE = "2026-08-13"
CATEGORY = "组织变革"
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"
CARD_HTML = f'''<article class="article-card" data-category="{CATEGORY}">
  <a href="/articles/{SLUG}.html" class="card-link">
    <span class="card-tag">{CATEGORY}</span>
    <h3 class="article-title">{TITLE}</h3>
    <time class="article-date" datetime="{DATE}">{DATE.replace('-', '.')}</time>
  </a>
</article>

'''

# ---------- 1. article-index.json ----------
p1 = os.path.join(ROOT, "assets/js/article-index.json")
s1 = open(p1, encoding="utf-8").read()
assert f'"url": "{SLUG}"' not in s1, "article-index 已存在该条目"
assert s1.rstrip().endswith("]"), "article-index 应以 ] 结尾"
entry = '''  ,
  {
    "title": "%s",
    "url": "%s",
    "category": "%s",
    "date": "%s",
    "tags": [
      "AI组织变革",
      "大厂实践",
      "组织设计"
    ]
  }
]''' % (TITLE, SLUG, CATEGORY, DATE)
s1 = s1.rstrip()
if s1.endswith("]"):
    s1 = s1[:-1].rstrip() + entry
else:
    raise SystemExit("article-index 结尾格式异常")
open(p1, "w", encoding="utf-8").write(s1 if s1.endswith("\n") else s1 + "\n")
print("[ok] article-index.json +1")

# ---------- 2. articles/index.html ----------
p2 = os.path.join(ROOT, "articles/index.html")
s2 = open(p2, encoding="utf-8").read()
assert f'/articles/{SLUG}.html' not in s2, "index.html 已存在该卡片"
marker = '<article class="article-card"'
idx = s2.find(marker)
assert idx != -1, "找不到卡片起点"
s2 = s2[:idx] + CARD_HTML + s2[idx:]
# JSON-LD ItemList 追加 position 146
ld_marker = '}]}}</script>'
# 找到最后一个 ItemList 闭合（hr-skill-graph 之后）
assert ld_marker in s2, "找不到 ItemList 闭合"
item = ',{"@type":"ListItem","position":146,"name":"%s","url":"%s"}' % (TITLE, URL)
s2 = s2.replace(ld_marker, item + ld_marker, 1)
open(p2, "w", encoding="utf-8").write(s2)
print("[ok] articles/index.html 卡片+JSON-LD position 146")

# ---------- 3. sitemap.xml ----------
p3 = os.path.join(ROOT, "sitemap.xml")
s3 = open(p3, encoding="utf-8").read()
assert f"/articles/{SLUG}.html" not in s3, "sitemap 已存在该 url"
block = f'''    <url>
        <loc>{URL}</loc>
        <lastmod>{DATE}</lastmod>
    </url>
</urlset>'''
assert "</urlset>" in s3, "sitemap 无 </urlset>"
s3 = s3.replace("</urlset>", block, 1)
open(p3, "w", encoding="utf-8").write(s3)
print("[ok] sitemap.xml +1 <url>")

# ---------- 4. llms-full.txt ----------
p4 = os.path.join(ROOT, "llms-full.txt")
s4 = open(p4, encoding="utf-8").read()
assert f"articles/{SLUG}.html" not in s4, "llms-full 已存在该条目"
summary = ("2025 到 2026，大厂密集重组 AI 部门。微软建 CoreAI、Meta 组超级智能实验室，"
           "但 HR 要分清真重组与政治秀：看预算编制、决策权、激励是否随结构走，而非看新闻稿标题。"
           "给出三条判别信号与 HR 一号位拿到重组消息时该问的四句话。")
block4 = f"\n### 133. {TITLE}\n- URL: {URL}\n- 摘要: {summary}\n"
s4 = s4.rstrip() + "\n" + block4
open(p4, "w", encoding="utf-8").write(s4)
print("[ok] llms-full.txt ### 133")
print("ALL SYNC DONE")
