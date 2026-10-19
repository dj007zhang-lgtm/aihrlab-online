#!/usr/bin/env python3
"""P2 策展：信号线台账生成器

真源：brief/_lines/*.json（人工撰写，唯一真相源）
产物：
  1. brief/lines/<slug>.html     线页（五块契约：判断 / 状态 / 证据时间线 / 站内挂接 / JSON-LD）
  2. assets/js/line-index.json   线索引（供站内检索与后续聚合页渲染）
  3. brief/index.html            台账首页（按主题域分组 + 状态分布 + 卷期入口）

纪律：
  - 页面内列表一律由本脚本从真源渲染，禁止硬编码。
  - 零虚构：证据条目只做搬运与渲染，脚本不生成任何事实文本。
  - 幂等：重复运行结果一致。
  - 新增一条线 = 新增一个 _lines/*.json + 跑本脚本。

用法：
  python3 scripts/build_brief.py
"""
import json
import os
import re
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINES_DIR = os.path.join(ROOT, "brief", "_lines")
OUT_LINES = os.path.join(ROOT, "brief", "lines")
INDEX_JSON = os.path.join(ROOT, "assets", "js", "line-index.json")
INDEX_PAGE = os.path.join(ROOT, "brief", "index.html")
HOST = "https://www.aihrlab.online"

STATUS_ORDER = {"稳固": 0, "被挑战": 1, "已翻转": 2, "归档": 3}

HEADER = ('<header class="site-header"><div class="container">'
          '<a href="/index.html" class="site-logo" aria-label="AIHR数智引擎首页">'
          '<img src="/assets/images/logo.png" class="logo-icon" alt="AIHR数智引擎" width="28" height="28">'
          ' AIHR<span class="logo-dot">数智引擎</span></a>'
          '<button class="nav-toggle" aria-label="打开导航菜单">&#9776;</button>'
          '<nav class="site-nav" aria-label="主导航">'
          '<a href="/index.html">首页</a><a href="/articles/index.html">文章</a>'
          '<a href="/resources/index.html">资源库</a><a href="/tools/index.html">测评</a>'
          '<a href="/brief/index.html" class="active" aria-current="page">策展</a>'
          '<a href="/about.html">关于</a></nav></div></header>')

CSS = """
.hub-wrap{max-width:680px;margin:0 auto;padding:3rem 1.25rem 4.5rem;}
.hub-series{font-size:.85rem;color:var(--text-muted);margin-bottom:.4rem;}
.hub-title{font-size:1.7rem;font-weight:700;color:var(--text);margin:0 0 .8rem;}
.hub-lede{font-size:1.02rem;line-height:1.9;color:var(--text-secondary);margin:0 0 2rem;}
.hub-list{list-style:none;padding:0;margin:0;}
.hub-item{display:block;text-decoration:none;color:var(--text);border-top:1px solid var(--line);padding:1.5rem 0;}
.hub-item:first-child{border-top:none;padding-top:0;}
.hub-item .num{font-size:.82rem;color:var(--text-muted);}
.hub-item .it{font-size:1.1rem;font-weight:700;color:var(--text);margin:.3rem 0 .5rem;}
.hub-item .de{font-size:.95rem;line-height:1.8;color:var(--text-secondary);}
.brief-back{display:inline-block;margin-bottom:1.6rem;color:var(--text-link);text-decoration:none;font-size:.9rem;}
.ln-domain{display:inline-block;font-size:.72rem;font-weight:600;color:var(--accent);background:var(--accent-pale);border-radius:6px;padding:.14rem .5rem;margin-bottom:.6rem;}
.ln-claim{font-size:1.22rem;line-height:1.75;font-weight:700;color:var(--text);margin:0 0 .8rem;padding-left:.9rem;border-left:3px solid var(--accent);}
.ln-meta{font-size:.82rem;color:var(--text-muted);margin:0 0 .4rem;}
.ln-status{display:inline-block;font-size:.78rem;font-weight:600;border:1px solid var(--line-strong);border-radius:999px;padding:.16rem .6rem;margin-right:.5rem;}
.ln-status[data-s="稳固"]{color:var(--accent);border-color:var(--accent);}
.ln-status[data-s="被挑战"]{color:#a86a2e;border-color:#a86a2e;}
.ln-status[data-s="已翻转"]{color:#a32d2d;border-color:#a32d2d;}
.ln-status[data-s="归档"]{color:var(--text-muted);}
.ln-note{font-size:.92rem;line-height:1.8;color:var(--text-secondary);background:var(--bg-subtle);border-radius:8px;padding:.8rem 1rem;margin:1rem 0 1.8rem;}
.ln-h{font-size:1rem;font-weight:700;color:var(--text);margin:1.6rem 0 .6rem;}
.ev{list-style:none;padding:0;margin:0;}
.ev li{padding:.9rem 0;border-top:1px solid var(--line);}
.ev li:first-child{border-top:0;}
.ev-date{font-size:.78rem;color:var(--text-muted);}
.ev-fact{font-size:.98rem;line-height:1.85;color:var(--text);margin:.25rem 0 .4rem;}
.ev-src{font-size:.85rem;color:var(--text-secondary);line-height:1.6;}
.ev-src a{color:var(--text-link);}
.ev-pol{display:inline-block;font-size:.72rem;border:1px solid var(--line-strong);border-radius:4px;padding:.05rem .4rem;margin-right:.4rem;color:var(--text-secondary);}
.ev-via{font-size:.82rem;color:var(--text-muted);margin-top:.25rem;}
.ev-via a{color:var(--text-link);}
.ln-links{margin:0;padding:0;list-style:none;}
.ln-links li{padding:.35rem 0;border-top:1px solid var(--line);font-size:.95rem;}
.ln-links li:first-child{border-top:0;}
.ln-links a{color:var(--text-link);}
.ln-rel{display:block;font-size:.82rem;color:var(--text-muted);margin-top:.15rem;}
.ln-foot{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--line);font-size:.85rem;color:var(--text-muted);line-height:1.7;}
"""


OG_IMAGE = "https://www.aihrlab.online/assets/images/og-covers/index-cover.webp"


def page(title, desc, body_html, url="", jsonld=None, og_title="", og_type="article",
         back="/brief/index.html", back_text="← 返回信号线台账"):
    # R-16/R-17：<title> 可带品牌后缀，og:title / twitter:title 必须与 h1 一致且不带后缀
    og = og_title or title
    ld = ""
    if jsonld:
        ld = '\n<script type="application/ld+json">%s</script>' % json.dumps(
            jsonld, ensure_ascii=False, separators=(",", ":"))
    tpl = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<script>(function(){try{var t=localStorage.getItem('aihr_theme');if(!t){t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','light');}})();</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:type" content="__OGTYPE__">
<meta property="og:url" content="__URL__">
<meta name="twitter:card" content="summary_large_image">
<meta property="og:image" content="__OGIMG__">
<meta name="twitter:title" content="__OGTITLE__">
<meta name="twitter:description" content="__DESC__">
<link rel="canonical" href="__URL__">
<link rel="stylesheet" href="/assets/css/style.min.css">
<link rel="stylesheet" href="/assets/css/article.css">
<style>__CSS__</style>__LD__
</head>
<body>
__HDR__
<main class="hub-wrap">
<a class="brief-back" href="__BACK__">__BACKTEXT__</a>
__BODY__
</main>
<script src="/assets/js/main.js" defer></script>
</body>
</html>
"""
    for k, v in (("__TITLE__", escape(title)), ("__DESC__", escape(desc)), ("__OGTITLE__", escape(og)), ("__OGIMG__", OG_IMAGE), ("__OGTYPE__", og_type),
                 ("__URL__", HOST + url), ("__CSS__", CSS), ("__LD__", ld),
                 ("__HDR__", HEADER), ("__BACK__", back),
                 ("__BACKTEXT__", back_text), ("__BODY__", body_html)):
        tpl = tpl.replace(k, v)
    return tpl


def render_line(line):
    slug = line["slug"]
    url = "/brief/lines/%s.html" % slug
    evs = sorted(line["evidence"], key=lambda e: e.get("date", ""), reverse=True)

    ev_html = []
    for e in evs:
        src = escape(e["source"])
        if e.get("source_url"):
            src_html = '<a href="%s" rel="nofollow noopener" target="_blank">%s</a>' % (
                escape(e["source_url"]), src)
        else:
            src_html = src
        via = ""
        if e.get("via"):
            via = '<div class="ev-via">本站留痕：<a href="%s">%s</a></div>' % (
                escape(e["via"]), escape(e.get("via_title") or e["via"]))
        ev_html.append(
            '<li><div class="ev-date">%s · <span class="ev-pol">%s</span></div>'
            '<p class="ev-fact">%s</p>'
            '<div class="ev-src">来源：%s</div>%s</li>' % (
                escape(e.get("date", "")), escape(e.get("polarity", "支持")),
                escape(e["fact"]), src_html, via))
    ev_html = "\n".join(ev_html)

    # 站内挂接：证据出处（via）与延伸挂钩（linked）分开渲染，均由数据生成，页面列表不硬编码
    seen, src_items = set(), []
    for e in evs:
        v = e.get("via")
        if v and v not in seen:
            seen.add(v)
            src_items.append('<li><a href="%s">%s</a></li>' % (
                escape(v), escape(e.get("via_title") or v)))
    ext_items = []
    for l in line.get("linked", []):
        if l.get("url") and l["url"] not in seen:
            seen.add(l["url"])
            rel = l.get("rel", "")
            rel_html = '<span class="ln-rel">%s</span>' % escape(rel) if rel else ""
            ext_items.append('<li><a href="%s">%s</a>%s</li>' % (
                escape(l["url"]), escape(l.get("title") or l["url"]), rel_html))
    src_block = ('<h2 class="ln-h">证据出处（本站）</h2>\n<ul class="ln-links">\n%s\n</ul>'
                 % "\n".join(src_items)) if src_items else ""
    ext_block = ('<h2 class="ln-h">站内挂钩</h2>\n<ul class="ln-links">\n%s\n</ul>'
                 % "\n".join(ext_items)) if ext_items else ""

    body = """<div class="ln-domain">{domain}</div>
<h1 class="ln-claim">{claim}</h1>
<div class="ln-meta"><span class="ln-status" data-s="{status}">{status}</span>首次记录 <time datetime="{first}">{first}</time> · 最近修订 {updated}</div>
{note}
<h2 class="ln-h">证据时间线（{n} 条，倒序）</h2>
<ol class="ev">
{ev}
</ol>
{src_block}
{ext_block}
<div class="ln-foot">判断句不会被静默改写。若后续证据推翻这条判断，会追加失效条件与修订日期，原表述保留在页面上。</div>""".format(
        domain=escape(line.get("domain", "")), claim=escape(line["claim"]),
        status=escape(line["status"]), first=escape(line.get("first_seen", "")),
        updated=escape(line.get("updated", "")),
        note=('<div class="ln-note">%s</div>' % escape(line["note"])) if line.get("note") else "",
        n=len(evs), ev=ev_html, src_block=src_block, ext_block=ext_block)

    jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": line["claim"],
        "datePublished": line.get("first_seen", ""),
        "dateModified": line.get("updated", ""),
        "url": HOST + url,
        "about": {"@type": "Thing", "name": line.get("domain", "")},
        "hasPart": {
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 # 证据日期用 dateCreated，避免与本文 datePublished 混淆
                 # （嵌套 datePublished 会让引擎误读页面发布日）
                 "item": {"@type": "Claim", "text": e["fact"],
                          "dateCreated": e.get("date", ""),
                          "author": {"@type": "Organization", "name": e["source"]},
                          "url": e.get("source_url", "") or ""}}
                for i, e in enumerate(evs)
            ],
        },
    }
    title = "%s | AIHR数智引擎" % line["claim"]
    desc = line["claim"]
    return url, page(title, desc, body, url=url, jsonld=jsonld, og_title=line["claim"])


def render_index(lines):
    by_domain = {}
    for l in lines:
        by_domain.setdefault(l.get("domain", "其他"), []).append(l)
    blocks = []
    for d in sorted(by_domain):
        items = []
        for l in sorted(by_domain[d], key=lambda x: (STATUS_ORDER.get(x["status"], 9),
                                                     x.get("updated", "")), reverse=False):
            items.append(
                '<li><a class="hub-item" href="/brief/lines/%s.html">'
                '<div class="num">%s · %d 条证据 · 最近修订 %s</div>'
                '<div class="it">%s</div>'
                '<div class="de">%s</div></a></li>' % (
                    l["slug"], escape(l["status"]), len(l["evidence"]),
                    escape(l.get("updated", "")), escape(l["claim"]),
                    escape(l["evidence"][-1]["source"]) if l["evidence"] else ""))
        blocks.append('<h2 class="ln-h">%s</h2><ul class="hub-list">%s</ul>' % (
            escape(d), "\n".join(items)))

    dist = {}
    for l in lines:
        dist[l["status"]] = dist.get(l["status"], 0) + 1
    dist_html = " · ".join("%s %d 条" % (k, v) for k, v in sorted(
        dist.items(), key=lambda kv: STATUS_ORDER.get(kv[0], 9)))

    body = """<div class="hub-series">AIHR 策展</div>
<h1 class="hub-title">信号线台账</h1>
<p class="hub-lede">这里追踪的是判断，不是新闻。每条线是一条可证伪的判断，下面挂着支持或削弱它的一手证据；证据随时间追加，判断被推翻时会写明失效条件，不改原文。</p>
<div class="ln-meta">共 {n} 条线 · {dist}</div>
{blocks}
<h2 class="ln-h">卷期归档</h2>
<ul class="hub-list">
<li><a class="hub-item" href="/brief/signal-brief-001.html">
<div class="num">第 001 期 · 2026 年 9 月 26 日</div>
<div class="it">创刊号：组织设计、人才趋势、双轨劳动力、agent 成本、科技裁员</div>
</a></li>
</ul>""".format(n=len(lines), dist=escape(dist_html), blocks="\n".join(blocks))

    return page("信号线台账：持续追踪的判断与一手证据 | AIHR数智引擎",
                "AIHR 信号线台账：每条线是一条可证伪的判断，挂一手证据与修订记录。判断可追溯，推翻会写明失效条件。",
                body, url="/brief/index.html", jsonld=None,
                og_title="信号线台账", og_type="website",
                back="/index.html", back_text="← 返回首页")


def main():
    os.makedirs(OUT_LINES, exist_ok=True)
    lines = []
    for fn in sorted(os.listdir(LINES_DIR)):
        if not fn.endswith(".json"):
            continue
        lines.append(json.load(open(os.path.join(LINES_DIR, fn), encoding="utf-8")))
    lines.sort(key=lambda l: (STATUS_ORDER.get(l["status"], 9), l.get("updated", "")),
               reverse=False)

    for l in lines:
        url, html = render_line(l)
        open(os.path.join(ROOT, url.lstrip("/")), "w", encoding="utf-8").write(html)
        print("  ✅ 线页 %s（%d 条证据）" % (url, len(l["evidence"])))

    idx = [{
        "slug": l["slug"], "claim": l["claim"], "status": l["status"],
        "domain": l.get("domain", ""), "updated": l.get("updated", ""),
        "first_seen": l.get("first_seen", ""),
        "evidence_count": len(l["evidence"]),
        "url": "/brief/lines/%s.html" % l["slug"],
    } for l in lines]
    json.dump(idx, open(INDEX_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("  ✅ line-index.json（%d 条）" % len(idx))

    open(INDEX_PAGE, "w", encoding="utf-8").write(render_index(lines))
    print("  ✅ brief/index.html（%d 条线，%d 个主题域）" % (
        len(lines), len({l.get("domain", "") for l in lines})))


if __name__ == "__main__":
    main()
