#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical +1 four-source sync for ai-hr-shared-services-2026.html.
Base = authoritative REMOTE main (ref=main) freshly fetched, NOT local drift.
Appends only; validates ItemList parses and card counts align.
"""
import os, re, json, base64, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "dj007zhang-lgtm/aihrlab-online"
API = "https://api.github.com/repos/%s/contents/%%s?ref=main" % REPO

TITLE = "AI 重写 HR 共享服务：集中化的终点"
SLUG = "ai-hr-shared-services-2026"
CAT = "组织变革"
DATE = "2026-09-15"
TAGS = ["HR共享服务", "共享服务中心", "SSC", "HR运营模型", "AI agent",
        "Tier 0 Tier 1", "GBS", "能力中台", "AI原生组织"]
SUMMARY = ("AI 没有消灭 HR 共享服务中心，而是把它的第一性原理重写了。组织是信息网络"
           "加利益分配网络，共享服务中心存在的理由是靠集中把事务性交易的边际成本压"
           "到最低。AI 把这笔边际成本打到趋近于零，集中化的理由随之瓦解。2026 年一手"
           "数据：Gartner 称 AI agent 将接管 HR 运营当前大部分 Tier 0 与 Tier 1 活动，"
           "到 2030 年约 50% 的 HR 交易会被自动化或由 agent 处理；Gartner 2026 HR 优先级"
           "调研显示近 29% 的 AI 生产力收益来自重设 HR 运营模型本身。结论：共享服务中心"
           "不死，是重排，从事务工厂变为规则、数据与兜底的能力中台。")
URL = "https://www.aihrlab.online/articles/%s.html" % SLUG
# current last ItemList entry (the 9/14 trust article) — insertion anchor
LAST_ITEM_URL = "https://www.aihrlab.online/articles/ai-era-organizational-trust-2026.html"


def fetch(path):
    req = urllib.request.Request(API % path,
                                 headers={"Accept": "application/vnd.github+json",
                                           "User-Agent": "aihr-sync"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    return base64.b64decode(d["content"]).decode("utf-8")


def sync_index_json():
    p = os.path.join(ROOT, "assets", "js", "article-index.json")
    data = json.loads(fetch("assets/js/article-index.json"))
    n0 = len(data)
    assert not any(e["url"] == SLUG for e in data), "already present"
    data.append({"title": TITLE, "url": SLUG, "category": CAT,
                 "date": DATE, "tags": TAGS})
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    assert len(data) == n0 + 1, f"index count {n0}->{len(data)}"
    print(f"[index.json] {n0} -> {len(data)} (OK)")


def sync_articles_index():
    p = os.path.join(ROOT, "articles", "index.html")
    html = fetch("articles/index.html")
    assert "</html>" in html and "</body>" in html, "TRUNCATED remote index.html!"

    excerpt = SUMMARY if len(SUMMARY) <= 120 else SUMMARY[:120] + "…"
    card = (
        '\n<article class="article-card" data-category="%s">\n'
        '  <a href="/articles/%s.html" class="card-link">\n'
        '    <span class="card-tag">%s</span>\n'
        '    <h3 class="article-title">%s</h3>\n'
        '    <p class="card-excerpt">%s</p>\n'
        '    <time class="article-date" datetime="%s">%s</time>\n'
        '  </a>\n'
        '</article>\n'
    ) % (CAT, SLUG, CAT, TITLE, excerpt, DATE, DATE.replace("-", "."))
    last = html.rfind("</article>")
    assert last != -1, "no article-card found"
    html = html[:last + len("</article>")] + card + html[last + len("</article>"):]

    anchor = '"url": "%s"}' % LAST_ITEM_URL
    i = html.find(anchor)
    assert i != -1, "last-item anchor not found in ItemList"
    new_item = (', {"@type": "ListItem", "position": 273, "name": "%s", '
                '"url": "%s"}' % (TITLE, URL))
    html = html[:i + len(anchor)] + new_item + html[i + len(anchor):]

    open(p, "w", encoding="utf-8").write(html)

    m = re.search(r'"itemListElement"\s*:\s*(\[.*?\]\s*\])', html, re.S)
    assert m, "ItemList block not found"
    val = json.loads(m.group(1))
    inner = val[0] if (isinstance(val, list) and val and isinstance(val[0], list)) else val
    positions = [x["position"] for x in inner]
    assert positions == list(range(1, 274)), f"ItemList positions broken: {positions[:3]}..{positions[-3:]}"
    assert html.count("article-card") == 273, f"card count {html.count('article-card')}"
    print(f"[articles/index.html] card + ItemList pos 273; "
          f"cards={html.count('article-card')}; ItemList={len(inner)} (1..273 OK)")


def sync_sitemap():
    p = os.path.join(ROOT, "sitemap.xml")
    sm = fetch("sitemap.xml")
    n0 = sm.count("<url>")
    block = (f'<url><loc>{URL}</loc>'
             f'<lastmod>{DATE}</lastmod><changefreq>weekly</changefreq>'
             f'<priority>0.8</priority></url>')
    idx = sm.rfind("</urlset>")
    sm = sm[:idx] + block + "\n" + sm[idx:]
    open(p, "w", encoding="utf-8").write(sm)
    assert sm.count("<url>") == n0 + 1, f"sitemap url count {n0}->{sm.count('<url>')}"
    locs = re.findall(r"<loc>(.*?)</loc>", sm)
    bad = [l for l in locs if not all(ord(c) < 128 for c in l)]
    assert not bad, f"non-ASCII loc: {bad[:3]}"
    print(f"[sitemap.xml] {n0} -> {sm.count('<url>')}; 0 non-ASCII loc (OK)")


def sync_llms():
    p = os.path.join(ROOT, "llms-full.txt")
    ll = fetch("llms-full.txt")
    nums = [int(x) for x in re.findall(r'^### (\d+)\.', ll, re.M)]
    n = max(nums) + 1
    block = (f"\n### {n}. {TITLE}\n"
             f"URL: {URL}\n"
             f"分类: {CAT}\n日期: {DATE}\n摘要: {SUMMARY}\n")
    ll = ll.rstrip() + "\n" + block
    open(p, "w", encoding="utf-8").write(ll)
    print(f"[llms-full.txt] block ### {n} appended (prev max {max(nums)})")


if __name__ == "__main__":
    sync_index_json()
    sync_articles_index()
    sync_sitemap()
    sync_llms()
    print("SYNC DONE")
