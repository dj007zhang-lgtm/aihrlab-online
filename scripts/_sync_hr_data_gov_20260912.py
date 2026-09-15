#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical +1 four-source sync for hr-data-governance-2026.html.
Base = current local files (== remote main as of 2026-09-11 run).
Only appends, never rewrites existing entries. Validates after.
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TITLE = "HR 数据治理：AI 时代谁为数据负责"
SLUG = "hr-data-governance-2026"
CAT = "核心方法论"
DATE = "2026-09-12"
TAGS = ["HR数据治理", "数据治理", "AI治理", "组织数据", "数据可信度",
        "决策权", "人力分析", "新职能", "AI原生组织"]
SUMMARY = ("HR 数据治理在 AI 时代从 IT 后台支撑变成 HR 必须自己拥有的前台职能。"
           "组织是信息网络加利益分配网络，AI 把招聘、绩效、薪酬、规划每条决策的数据依赖"
           "放大成组织级风险，数据的可信度、归属与问责决定 AI 决策质量。2026 年一手数据："
           "Deloitte 显示 61% 的领导者认识到劳动力数据可信度重要但仅 5% 取得进展，"
           "64% 认为 AI 决策治理重要但仅 5% 自认领先；Gartner 预测到 2030 年 50% 的组织"
           "将用自主 AI agent 把治理政策转译为机器可验证的数据合约。")


def sync_index_json():
    p = os.path.join(ROOT, "assets", "js", "article-index.json")
    data = json.load(open(p, encoding="utf-8"))
    if any(e["url"] == SLUG for e in data):
        print("[index.json] already present, skip")
        return
    # Append at END to mirror ItemList end convention (9/11 three-pillar landed at last position)
    data.append({
        "title": TITLE, "url": SLUG, "category": CAT, "date": DATE, "tags": TAGS
    })
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[index.json] appended -> {len(data)} entries")


def sync_articles_index():
    p = os.path.join(ROOT, "articles", "index.html")
    html = open(p, encoding="utf-8").read()

    # 1) Card: append at END of #article-grid (after last </article> that is an article-card)
    card = (
        '\n<article class="article-card" data-category="%s">\n'
        '  <a href="/articles/%s.html" class="card-link">\n'
        '    <span class="card-tag">%s</span>\n'
        '    <h3 class="article-title">%s</h3>\n'
        '    <p class="card-excerpt">%s</p>\n'
        '    <time class="article-date" datetime="%s">%s</time>\n'
        '  </a>\n'
        '</article>\n'
    ) % (CAT, SLUG, CAT, TITLE, SUMMARY[:120] + "…" if len(SUMMARY) > 120 else SUMMARY,
         DATE, DATE.replace("-", "."))
    # find last article-card close tag
    last = html.rfind("</article>")
    assert last != -1, "no article-card found"
    html = html[:last + len("</article>")] + card + html[last + len("</article>"):]

    # 2) CollectionPage ItemList: parse, append at END (position = max+1)
    m = re.search(r'("itemListElement":\s*\[)(.*?)(\]\})', html, re.S)
    arr_txt = m.group(2)
    arr = json.loads("[" + arr_txt + "]")
    maxpos = max(x["position"] for x in arr)
    arr.append({
        "@type": "ListItem", "position": maxpos + 1, "name": TITLE,
        "url": f"https://www.aihrlab.online/articles/{SLUG}.html"
    })
    new_arr = json.dumps(arr, ensure_ascii=False)
    html = html[:m.start(2)] + new_arr + html[m.end(2):]
    open(p, "w", encoding="utf-8").write(html)
    print(f"[articles/index.html] card + ItemList pos {maxpos+1} appended; "
          f"cards={html.count('article-card')}")


def sync_sitemap():
    p = os.path.join(ROOT, "sitemap.xml")
    sm = open(p, encoding="utf-8").read()
    block = (f'<url><loc>https://www.aihrlab.online/articles/{SLUG}.html</loc>'
             f'<lastmod>{DATE}</lastmod><changefreq>weekly</changefreq>'
             f'<priority>0.8</priority></url>')
    # insert before </urlset>
    idx = sm.rfind("</urlset>")
    sm = sm[:idx] + block + "\n" + sm[idx:]
    open(p, "w", encoding="utf-8").write(sm)
    print(f"[sitemap.xml] url block appended; count={sm.count('<url>')}")


def sync_llms():
    p = os.path.join(ROOT, "llms-full.txt")
    ll = open(p, encoding="utf-8").read()
    nums = [int(x) for x in re.findall(r'^### (\d+)\.', ll, re.M)]
    n = max(nums) + 1
    block = (f"\n### {n}. {TITLE}\n"
             f"URL: https://www.aihrlab.online/articles/{SLUG}.html\n"
             f"分类: {CAT}\n日期: {DATE}\n摘要: {SUMMARY}\n")
    ll = ll.rstrip() + "\n" + block
    open(p, "w", encoding="utf-8").write(ll)
    print(f"[llms-full.txt] block ### {n} appended")


if __name__ == "__main__":
    sync_index_json()
    sync_articles_index()
    sync_sitemap()
    sync_llms()
    print("SYNC DONE")
