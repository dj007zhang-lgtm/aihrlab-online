#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical four-source sync for 6 remaining overseas HR articles.

Fetches the REAL remote main versions of the 4 sync targets, inserts exactly
6 new articles, and writes local = remote + 6.
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
        "slug": "global-compensation-design-2026",
        "title": "全球薪酬：公平感与本地市场价的政治",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("全球薪酬的难点不是定数字，而是在公平感、本地市场价与总部统一之间做政治平衡。"
                 "欧盟薪酬透明指令把公平感变成可度量合规项，技能定价正在取代岗位定价。"),
        "tags": ["全球薪酬","出海薪酬","技能定价","美世","薪酬透明度","外派薪酬","公平感","本地市场价","薪酬治理"],
    },
    {
        "slug": "eor-employer-of-record-2026",
        "title": "名义雇主（EOR）：合规的过渡，不是终局",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("EOR 解决合法雇佣，不解决组织治理。它是无实体或单国试探期的过渡方案，"
                 "长期用 EOR 会把组织记忆锁在服务商侧。正确路径是买时间，再转自建实体。"),
        "tags": ["名义雇主","EOR","出海雇佣","合规过渡","Deel","本地实体","组织记忆","用工身份","跨境雇佣"],
    },
    {
        "slug": "expatriate-vs-localization-2026",
        "title": "外派还是本地化：人才策略的钟摆",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("外派失败率超 40%，说明外派不是低成本扩张手段。本地化率是组织记忆沉淀指标，"
                 "不是简单的国籍比例。人才策略要在控制权、成本与知识转移之间摆动。"),
        "tags": ["外派","本地化","人才策略","出海","外派失败率","回任","组织记忆","远程总部","本地节点"],
    },
    {
        "slug": "overseas-labor-risk-2026",
        "title": "海外劳动风险：解雇难度决定组织韧性",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("海外劳动风险的核心不是成本，而是纠偏速度。OECD 就业保护严格度指数显示不同市场"
                 "解雇成本与程序差异巨大，解法是把冗余预算、证据链与组织韧性写进前端设计。"),
        "tags": ["海外劳动风险","解雇难度","OECD EPL","就业保护","组织韧性","出海用工","劳动法","纠偏速度"],
    },
    {
        "slug": "ai-in-overseas-hr-2026",
        "title": "AI 出海 HR：先过监管，再过效率",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("很多出海企业把 AI 在 HR 的落地顺序搞反了。欧盟把招聘定为高风险系统，"
                 "GDPR 第 22 条约束自动化决定，德国企业委员会可挡住上线。合规是前置条件，效率是结果。"),
        "tags": ["AI出海HR","欧盟AI法案","GDPR","高风险系统","数据跨境","企业委员会","合规前置","招聘自动化"],
    },
    {
        "slug": "overseas-hr-metrics-2026",
        "title": "出海 HR 度量：先量对，再谈好",
        "category": "组织变革",
        "date": "2026-09-09",
        "date_display": "2026.09.09",
        "desc": ("用国内 KPI 套海外等于用体温计测血压。出海 HR 要量本地化率、实体与 EOR 覆盖率、"
                 "合规事件率、知识回流率。错配的 KPI 比没有 KPI 更危险。"),
        "tags": ["出海HR度量","本地化率","合规事件率","EOR覆盖率","外派失败率","知识回流","跨文化绩效","HR指标"],
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

    # ---- 1. article-index.json (append seven) ----
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

    # rebuild ItemList: new 7 at top, then old renumbered
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
            f'        <lastmod>{a["date"]}T09:00:00+08:00</lastmod>\n'
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

    print("=== surgical sync done (local == remote + 7 articles) ===")


if __name__ == "__main__":
    main()
