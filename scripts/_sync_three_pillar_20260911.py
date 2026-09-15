#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical +1 four-source sync for ai-hr-three-pillar-model-2026.
Fetches the REAL remote main (api.github.com) for each of the 4 targets,
inserts exactly one new article, writes locally. Does NOT run full sync
(site has 17 historical orphan articles not on remote; blind sync would
pull them in). Mirrors the proven 9/09 approach.
"""
import json, base64, urllib.request, re, os

REPO = "dj007zhang-lgtm/aihrlab-online"
BRANCH = "main"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_remote(path):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl"})
    d = json.load(urllib.request.urlopen(req))
    return base64.b64decode(d["content"]).decode("utf-8")


SLUG = "ai-hr-three-pillar-model-2026"
TITLE = "AI 重排 HR 三支柱：事务瘦身，专家升维"
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"
CAT = "核心方法论"
DATE = "2026-09-11"
EXCERPT = ("HR 三支柱（SSC、COE、HRBP）在 AI 时代的命运不是被推翻，而是被重排。"
           "SSC 的集中逻辑被瓦解、COE 的稀缺性被削弱，只有上下文无法被集中，"
           "HRBP 的嵌入价值反而上升。2026 一手数据给出底座。")


def write_local(rel, content):
    p = os.path.join(ROOT, rel)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote", rel, os.path.getsize(p), "bytes")


# 1) article-index.json (newest-first -> prepend)
idx = json.loads(get_remote("assets/js/article-index.json"))
entry = {"title": TITLE, "url": SLUG, "category": CAT, "date": DATE,
         "tags": ["HR三支柱", "Ulrich模型", "共享服务中心", "COE", "HRBP",
                  "AI重塑HR", "HR运营模式", "三支柱模型", "组织设计"]}
idx.insert(0, entry)
write_local("assets/js/article-index.json", json.dumps(idx, ensure_ascii=False, indent=2))


# 2) articles/index.html (append card + ItemList position 269)
html = get_remote("articles/index.html")
card = (
    '\n  <article class="article-card" data-category="' + CAT + '">\n'
    '    <a href="/articles/' + SLUG + '.html" class="card-link">\n'
    '      <span class="card-tag">' + CAT + '</span>\n'
    '      <h3 class="article-title">' + TITLE + '</h3>\n'
    '      <p class="card-excerpt">' + EXCERPT + '</p>\n'
    '      <time class="article-date" datetime="' + DATE + '">' + DATE.replace("-", ".") + '</time>\n'
    '    </a>\n  </article>'
)
last_article = html.rfind("</article>")
assert last_article != -1, "no card found"
html = html[:last_article + len("</article>")] + card + html[last_article + len("</article>"):]
# ItemList: append after the last item (xiaomi, position 268)
anchor = ',"url":"https://www.aihrlab.online/articles/xiaomi-2026-org-evolution.html"}]'
assert anchor in html, "itemlist anchor missing"
new_item = (',{"@type":"ListItem","position":269,"name":"' + TITLE + '","url":"' + URL + '"}')
html = html.replace(anchor, new_item + "]", 1)
write_local("articles/index.html", html)


# 3) sitemap.xml (insert <url> before </urlset>)
sm = get_remote("sitemap.xml")
block = ("\n  <url><loc>" + URL + "</loc><lastmod>" + DATE +
         "</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>")
sm = sm.replace("</urlset>", block + "\n</urlset>", 1)
write_local("sitemap.xml", sm)


# 4) llms-full.txt (append ### 177 block)
llms = get_remote("llms-full.txt")
block = ("\n### 177. " + TITLE + "\n"
         "URL: " + URL + "\n"
         "分类: " + CAT + "\n"
         "日期: " + DATE + "\n"
         "摘要: HR 三支柱模型（Ulrich：SSC、COE、HRBP）在 AI 时代不是被推翻，而是被重排。"
         "三支柱是一套信息路由架构，SSC 靠集中事务换规模、COE 靠集中稀缺知识换深度、"
         "HRBP 靠嵌入现场换上下文。AI 改写了三条边的成本：事务边际成本趋零瓦解 SSC 的集中理由，"
         "知识检索成本趋零削弱 COE 的稀缺性，而上下文无法被集中，HRBP 的嵌入价值反而上升。"
         "2026 年一手数据：Gartner 对 426 名 CHRO 调研显示演进 HR 运营模式对 AI 生产力增益影响最高达 29%、"
         "50% 的 HR 任务到 2030 年由 agent 接管；Bersin 判断 30% 至 40% 的 HR 岗位因 agent 消失、"
         "战略工作占比从约 30% 升到 75%；Deloitte 显示 66% 的 C-suite 认为传统职能必须改变但仅 7% 取得进展。"
         "新稳态是薄 SSC、升维 COE、唯一有人脸的 HRBP。\n")
llms = llms.rstrip("\n") + "\n" + block
write_local("llms-full.txt", llms)

print("SYNC DONE")
