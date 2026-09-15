#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical four-source sync for two overseas cornerstone articles.

Fetches the REAL remote main versions of the 4 sync targets, inserts exactly
two new articles, and writes local = remote + 2.  Does not touch the 17
orphan articles that are live on main but missing from index/sitemap.
"""
import os, sys, json, base64, re, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_atomic as ga

ROOT = ga.ROOT
TOKEN = ga.TOKEN
CONTENTS = ga.CONTENTS
BRANCH = ga.BRANCH

ARTICLES = [
    {
        "slug": "overseas-employment-compliance-2026",
        "title": "海外用工合规：红线不在清单，在治理模式",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("海外用工合规的红线不在逐国清单，而在总部统一标准与本地法理的治理设计。"
                 "AI 招聘被欧盟定高风险，举证责任在雇主，德国工会可挡住系统上线，"
                 "EOR 与误分类的代价更远超清单本身。"),
        "tags": ["海外用工合规","出海合规","欧盟AI法案","GDPR","误分类","EOR","高风险系统","协同决定权"],
    },
    {
        "slug": "overseas-control-model-2026",
        "title": "出海管控模式：总部、区域、本地怎么分权",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("出海管控模式不是汇报关系，而是信息传递网络与利益分配网络的选择。"
                 "闻泰与安世半导体、vivo India、印尼镍矿、德国工会四个案例说明，"
                 "选错模式本地团队要么失控要么僵死。"),
        "tags": ["出海管控模式","全球化组织","分权","跨国模型","矩阵结构","联邦模式","闻泰","协同决定权"],
    },
]


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

    # ---- 1. article-index.json (append two) ----
    idx_txt = fetch_remote("assets/js/article-index.json", head)
    idx = json.loads(idx_txt)
    for a in ARTICLES:
        assert all(e["url"] != a["slug"] for e in idx), f"{a['slug']} already in index json!"
        idx.append({
            "title": a["title"],
            "url": a["slug"],
            "category": a["category"],
            "date": a["date"],
            "tags": a["tags"],
        })
    with open(os.path.join(ROOT, "assets/js/article-index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print(f"  [1] article-index.json -> {len(idx)} entries")

    # ---- 2. articles/index.html (cards + ItemList) ----
    html = fetch_remote("articles/index.html", head)
    cards_block = ""
    for a in ARTICLES:
        url = f"https://www.aihrlab.online/articles/{a['slug']}.html"
        cards_block += (
            f'<article class="article-card" data-category="{a["category"]}">\n'
            f'  <a href="/articles/{a["slug"]}.html" class="card-link">\n'
            f'    <span class="card-tag">{a["category"]}</span>\n'
            f'    <h3 class="article-title">{a["title"]}</h3>\n'
            f'    <p class="card-excerpt">{a["desc"][:100]}...</p>\n'
            f'    <time class="article-date" datetime="{a["date"]}">{a["date_display"]}</time>\n'
            f'  </a>\n'
            f'</article>\n'
        )
    marker = '<div class="article-grid" id="article-grid">'
    assert marker in html, "article-grid marker missing"
    html = html.replace(marker, marker + "\n\n" + cards_block, 1)

    # rebuild ItemList
    new_items = []
    for pos, a in enumerate(ARTICLES, start=1):
        url = f"https://www.aihrlab.online/articles/{a['slug']}.html"
        new_items.append({"@type": "ListItem", "position": pos, "name": a["title"], "url": url})
    for blk in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(blk.group(1))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("@type") == "CollectionPage":
            old = data["mainEntity"]["itemListElement"]
            for i, it in enumerate(old, start=len(ARTICLES) + 1):
                it["position"] = i
                new_items.append(it)
            data["mainEntity"] = {"@type": "ItemList", "itemListElement": new_items}
            new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            html = html[:blk.start()] + f'<script type="application/ld+json">{new_json}</script>' + html[blk.end():]
            break
    with open(os.path.join(ROOT, "articles/index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [2] articles/index.html -> +{len(ARTICLES)} cards, ItemList {len(new_items)} items")

    # ---- 3. sitemap.xml (append before </urlset>) ----
    sm = fetch_remote("sitemap.xml", head)
    insert = ""
    for a in ARTICLES:
        url = f"https://www.aihrlab.online/articles/{a['slug']}.html"
        assert f"<loc>{url}</loc>" not in sm, f"{a['slug']} already in sitemap!"
        insert += (
            '    <url>\n'
            f'        <loc>{url}</loc>\n'
            f'        <lastmod>{a["date"]}</lastmod>\n'
            '    </url>\n'
        )
    assert "</urlset>" in sm, "</urlset> missing"
    sm = sm.replace("</urlset>", insert + "</urlset>", 1)
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sm)
    print(f"  [3] sitemap.xml -> +{len(ARTICLES)} urls")

    # ---- 4. llms-full.txt (append numbered blocks) ----
    ll = fetch_remote("llms-full.txt", head)
    nums = [int(m) for m in re.findall(r'^###\s*(\d+)\.', ll, re.M)]
    next_n = (max(nums) + 1) if nums else 1
    if not ll.endswith("\n"):
        ll += "\n"
    for a in ARTICLES:
        url = f"https://www.aihrlab.online/articles/{a['slug']}.html"
        ll += (
            f"\n### {next_n}. {a['title']}\n"
            f"URL: {url}\n"
            f"分类: {a['category']}\n"
            f"日期: {a['date']}\n"
            f"摘要: {a['desc']}\n"
        )
        next_n += 1
    with open(os.path.join(ROOT, "llms-full.txt"), "w", encoding="utf-8") as f:
        f.write(ll)
    print(f"  [4] llms-full.txt -> ### {next_n - len(ARTICLES)}. to ### {next_n - 1}. appended")

    print("=== surgical sync done (local == remote + 2 articles) ===")


if __name__ == "__main__":
    main()
