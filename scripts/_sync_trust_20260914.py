#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical +1 four-source sync for ai-era-organizational-trust-2026.html.
Base = authoritative REMOTE main (ref 957e24b1) freshly fetched into local.
Appends only, validates ItemList parses and card counts align.
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TITLE = "AI 时代，组织信任正在被重写"
SLUG = "ai-era-organizational-trust-2026"
CAT = "组织变革"
DATE = "2026-09-14"
TAGS = ["AI组织信任", "组织信任", "算法管理", "算法监控", "员工信任",
        "程序公平", "透明治理", "AI原生组织", "信任重建"]
SUMMARY = ("AI 没有消灭信任，而是把组织内部信任的底层合约重写了。组织是信息网络"
           "加利益分配网络，信任是两张网的货币，AI 同时重写两张网，让信任从默认"
           "状态变成需要被持续证明的状态。2026 年一手数据：Edelman 显示仅 31% "
           "员工信任雇主会公平透明地使用 AI，自动化裁员公司里跌到 19%；Microsoft "
           "发现管理者带头示范 AI 使用能让团队对智能体的信任提升 30 个点；ILO 工作"
           "论文指出算法监控正在侵蚀自主与信任；PwC 显示每天使用 GenAI 的员工工作"
           "安全感是偶尔使用者的 1.6 倍。")
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"
# last pre-existing item in ItemList (the 9/13 retention article) — insertion anchor
LAST_ITEM_URL = "https://www.aihrlab.online/articles/ai-era-employee-retention-2026.html"


def sync_index_json():
    p = os.path.join(ROOT, "assets", "js", "article-index.json")
    data = json.load(open(p, encoding="utf-8"))
    assert not any(e["url"] == SLUG for e in data), "already present"
    data.append({"title": TITLE, "url": SLUG, "category": CAT,
                 "date": DATE, "tags": TAGS})
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[index.json] appended -> {len(data)} entries")


def sync_articles_index():
    p = os.path.join(ROOT, "articles", "index.html")
    html = open(p, encoding="utf-8").read()
    assert "</html>" in html and "</body>" in html, "TRUNCATED index.html!"

    # 1) Card: append after last </article>
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

    # 2) ItemList: anchor on LAST_ITEM_URL, insert new item after its closing brace.
    anchor = '"url": "%s"}' % LAST_ITEM_URL
    i = html.find(anchor)
    assert i != -1, "last-item anchor not found in ItemList"
    new_item = (', {"@type": "ListItem", "position": 272, "name": "%s", '
                '"url": "%s"}' % (TITLE, URL))
    html = html[:i + len(anchor)] + new_item + html[i + len(anchor):]

    open(p, "w", encoding="utf-8").write(html)

    # 3) Validate ItemList parses and has 272 continuous positions
    m = re.search(r'"itemListElement"\s*:\s*(\[.*?\]\s*\])', html, re.S)
    assert m, "ItemList block not found"
    val = json.loads(m.group(1))
    inner = val[0] if (isinstance(val, list) and val and isinstance(val[0], list)) else val
    positions = [x["position"] for x in inner]
    assert positions == list(range(1, 273)), f"ItemList positions broken: {positions[:3]}..{positions[-3:]}"
    assert html.count("article-card") == 272, f"card count {html.count('article-card')}"
    print(f"[articles/index.html] card + ItemList pos 272 appended; "
          f"cards={html.count('article-card')}; ItemList={len(inner)} (1..272 OK)")


def sync_sitemap():
    p = os.path.join(ROOT, "sitemap.xml")
    sm = open(p, encoding="utf-8").read()
    block = (f'<url><loc>{URL}</loc>'
             f'<lastmod>{DATE}</lastmod><changefreq>weekly</changefreq>'
             f'<priority>0.8</priority></url>')
    idx = sm.rfind("</urlset>")
    sm = sm[:idx] + block + "\n" + sm[idx:]
    open(p, "w", encoding="utf-8").write(sm)
    assert sm.count("<url>") == 355, f"sitemap url count {sm.count('<url>')}"
    # no non-ASCII in any <loc>
    locs = re.findall(r"<loc>(.*?)</loc>", sm)
    bad = [l for l in locs if not all(ord(c) < 128 for c in l)]
    assert not bad, f"non-ASCII loc: {bad[:3]}"
    print(f"[sitemap.xml] url block appended; count={sm.count('<url>')}; 0 non-ASCII loc")


def sync_llms():
    p = os.path.join(ROOT, "llms-full.txt")
    ll = open(p, encoding="utf-8").read()
    nums = [int(x) for x in re.findall(r'^### (\d+)\.', ll, re.M)]
    n = max(nums) + 1
    print(f"[llms] current max block = {max(nums)}; next = {n}")
    block = (f"\n### {n}. {TITLE}\n"
             f"URL: {URL}\n"
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
