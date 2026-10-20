#!/usr/bin/env python3
"""P2 策展：信号线生成器

真源：brief/_lines/*.json（人工撰写，唯一真相源）
产物：
  1. brief/lines/<slug>.html     线页（五块契约：判断 / 状态 / 证据时间线 / 延伸阅读 / JSON-LD）
  2. assets/js/line-index.json   线索引（供站内检索与后续聚合页渲染）
  3. brief/index.html            信号线首页（判断卡片 + 状态图例 + 往期入口）

纪律：
  - 页面内数据列表一律由本脚本从真源渲染，禁止硬编码。
  - 零虚构：证据条目只做搬运与渲染，脚本不生成任何事实文本。
  - 幂等：重复运行结果一致。
  - 新增一条线 = 新增一个 _lines/*.json + 跑本脚本。
  - 版式面向读者：判断句是页面主角，状态用图例讲人话，禁用台账/挂钩类记账词汇。

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
STATUS_MEANING = {
    "稳固": "证据还在持续支持",
    "被挑战": "出现了反向证据，正在复核",
    "已翻转": "判断被推翻，原句保留可查",
    "归档": "不再追踪，记录归档",
}

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
.hub-wrap{max-width:680px;margin:0 auto;padding:2.5rem 1.25rem 4.5rem;}
.brief-back{display:inline-block;margin-bottom:1.4rem;color:var(--text-link);text-decoration:none;font-size:.9rem;}
.bf-hero{background:var(--accent-pale);border-radius:16px;padding:2.3rem 2.1rem 2.1rem;margin:1.6rem 0 1.8rem;}
.bf-eyebrow{font-size:.85rem;font-weight:700;letter-spacing:.12em;color:var(--accent);margin-bottom:.55rem;}
.bf-title{font-size:2.05rem;font-weight:800;color:var(--text);margin:0 0 .75rem;line-height:1.3;}
.bf-lede{font-size:1.03rem;line-height:1.95;color:var(--text-secondary);margin:0;max-width:58ch;}
.bf-legend{display:flex;flex-wrap:wrap;gap:.4rem 1.5rem;margin:0 0 2.2rem;padding:0;list-style:none;}
.bf-legend li{display:flex;align-items:center;gap:.45rem;font-size:.86rem;color:var(--text-secondary);}
.bf-status{display:inline-flex;align-items:center;gap:.4rem;font-size:.8rem;font-weight:700;color:var(--text);}
.bf-dot{width:9px;height:9px;border-radius:50%;background:var(--text-muted);flex:none;}
.bf-status[data-status="稳固"] .bf-dot{background:var(--accent);}
.bf-status[data-status="被挑战"] .bf-dot{background:#a86a2e;}
.bf-status[data-status="已翻转"] .bf-dot{background:#a32d2d;}
.bf-status[data-status="归档"] .bf-dot{background:var(--text-muted);}
.ln-h{display:flex;align-items:baseline;gap:.55rem;font-size:1.12rem;font-weight:800;color:var(--text);margin:0 0 1rem;}
.ln-count{font-size:.82rem;font-weight:600;color:var(--text-muted);}
.bf-cards{display:grid;gap:1rem;margin:0 0 2.6rem;padding:0;list-style:none;}
.bf-card{display:block;background:var(--bg-card);border:1px solid var(--line-strong);border-radius:14px;
  padding:1.35rem 1.5rem;text-decoration:none;color:var(--text);
  transition:transform .18s ease, box-shadow .18s ease;}
.bf-card:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,.09);}
.bf-card-top{display:flex;align-items:center;gap:.7rem;margin-bottom:.7rem;flex-wrap:wrap;}
.bf-chip{font-size:.78rem;font-weight:700;color:var(--accent);background:var(--accent-pale);
  border-radius:999px;padding:.2rem .75rem;white-space:nowrap;}
.bf-claim{font-size:1.12rem;font-weight:700;line-height:1.8;margin:0 0 .65rem;}
.bf-meta{font-size:.85rem;color:var(--text-muted);margin-bottom:.5rem;}
.bf-src{font-size:.88rem;line-height:1.7;color:var(--text-secondary);}
.bf-issue{background:transparent;border-style:dashed;}
/* 线页 */
.ln-hero{background:var(--accent-pale);border-radius:16px;padding:2.1rem;margin:1.6rem 0 1.6rem;}
.ln-claim{font-size:1.42rem;line-height:1.72;font-weight:800;color:var(--text);margin:.2rem 0 1rem;}
.ln-meta{font-size:.87rem;color:var(--text-secondary);display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;}
.ln-note{background:var(--bg-card);border-left:3px solid #a86a2e;border-radius:0 10px 10px 0;
  padding:.95rem 1.15rem;margin:0 0 2.2rem;font-size:.95rem;line-height:1.85;color:var(--text-secondary);}
.ln-note b{color:var(--text);display:block;margin-bottom:.25rem;font-size:.88rem;}
/* 跨线判断（索引页）*/
.bf-spine{background:var(--bg-card);border:1px solid var(--line-strong);border-left:3px solid var(--accent);
  border-radius:0 12px 12px 0;padding:1.35rem 1.4rem;margin:0 0 1.2rem;}
.bf-spine__label{font-size:.8rem;font-weight:700;letter-spacing:.06em;color:var(--accent);margin-bottom:.6rem;}
.bf-spine__claim{font-size:1.08rem;font-weight:700;line-height:1.85;color:var(--text);margin:0 0 .9rem;}
/* 推论块：与证据严格分层，推论不是证据 */
.bf-imply{background:var(--bg-subtle);border:1px dashed var(--line-strong);border-radius:10px;
  padding:1rem 1.15rem;margin:0 0 2.2rem;}
.bf-imply__label{font-size:.8rem;font-weight:700;color:#a86a2e;margin-bottom:.45rem;}
.bf-imply__text{font-size:.98rem;line-height:1.85;color:var(--text);margin:0;}
.bf-imply__falsify{font-size:.85rem;line-height:1.75;color:var(--text-muted);margin:.5rem 0 0;}
.bf-imply--in{margin:0;}
/* 证据时间线：竖轨 + 节点 */
.ev{list-style:none;padding:0;margin:0 0 2.4rem;}
.ev li{position:relative;padding:0 0 1.9rem 1.7rem;margin-left:.45rem;
  border-left:2px solid var(--line-strong);}
.ev li:last-child{border-left-color:transparent;}
.ev li::before{content:"";position:absolute;left:-6px;top:.3rem;width:10px;height:10px;
  border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--bg);}
.ev li[data-pol="削弱"]::before{background:#a86a2e;}
.ev-date{font-size:.87rem;font-weight:700;color:var(--text);}
.ev-pol{font-size:.78rem;font-weight:600;color:var(--accent);margin-left:.55rem;}
.ev li[data-pol="削弱"] .ev-pol{color:#a86a2e;}
.ev-fact{font-size:1rem;line-height:1.9;color:var(--text);margin:.35rem 0 .5rem;}
.ev-src{font-size:.87rem;color:var(--text-secondary);line-height:1.7;}
.ev-src a{color:var(--text-link);}
.ev-via{font-size:.85rem;color:var(--text-muted);margin-top:.35rem;}
.ev-via a{color:var(--text-link);}
.ln-links{margin:0 0 2.4rem;padding:0;list-style:none;}
.ln-links li{padding:.6rem 0;border-top:1px solid var(--line);font-size:.97rem;}
.ln-links li:first-child{border-top:0;padding-top:0;}
.ln-links a{color:var(--text-link);}
.ln-rel{display:block;font-size:.84rem;color:var(--text-muted);margin-top:.2rem;}
.ln-foot{margin-top:2.2rem;padding-top:1.1rem;border-top:1px solid var(--line);
  font-size:.88rem;color:var(--text-muted);line-height:1.8;}
"""

OG_IMAGE = "https://www.aihrlab.online/assets/images/og-covers/index-cover.webp"


def page(title, desc, body_html, url="", jsonld=None, og_title="", og_type="article",
         back="/brief/index.html", back_text="← 返回信号线"):
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


def status_html(status):
    return ('<span class="bf-status" data-status="%s"><span class="bf-dot"></span>%s</span>'
            % (escape(status), escape(status)))


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
        pol = e.get("polarity", "支持")
        via = ""
        if e.get("via"):
            via = '<div class="ev-via">本站全文：<a href="%s">%s</a></div>' % (
                escape(e["via"]), escape(e.get("via_title") or e["via"]))
        ev_html.append(
            '<li data-pol="%s"><div class="ev-date"><time datetime="%s">%s</time>'
            '<span class="ev-pol">%s</span></div>'
            '<p class="ev-fact">%s</p>'
            '<div class="ev-src">来源：%s</div>%s</li>' % (
                escape(pol), escape(e.get("date", "")), escape(e.get("date", "")),
                escape(pol), escape(e["fact"]), src_html, via))
    ev_html = "\n".join(ev_html)

    # 延伸阅读：与证据内已出现的 via 去重后渲染，由数据生成，页面列表不硬编码
    seen = {e.get("via") for e in evs if e.get("via")}
    ext_items = []
    for l in line.get("linked", []):
        if l.get("url") and l["url"] not in seen:
            seen.add(l["url"])
            rel = l.get("rel", "")
            rel_html = '<span class="ln-rel">%s</span>' % escape(rel) if rel else ""
            ext_items.append('<li><a href="%s">%s</a>%s</li>' % (
                escape(l["url"]), escape(l.get("title") or l["url"]), rel_html))
    ext_block = ('<h2 class="ln-h">延伸阅读</h2>\n<ul class="ln-links">\n%s\n</ul>'
                 % "\n".join(ext_items)) if ext_items else ""

    note = line.get("note", "")
    note_html = ('<div class="ln-note"><b>这条判断怎么会被推翻</b>%s</div>' % escape(note)
                 ) if note else ""

    # 组织含义：由数据真源搬运，标为推论（非证据），并写明失效条件
    imp = line.get("implication") or {}
    imp_html = ""
    if imp.get("text"):
        fals = ('<p class="bf-imply__falsify">推论失效条件：%s</p>' % escape(imp["falsify"])
                ) if imp.get("falsify") else ""
        imp_html = ('<div class="bf-imply"><div class="bf-imply__label">推论 · 这条线成立时，组织该动的地方</div>'
                    '<p class="bf-imply__text">%s</p>%s</div>' % (escape(imp["text"]), fals))

    body = """<section class="ln-hero">
<div class="bf-card-top"><span class="bf-chip">{domain}</span>{status}</div>
<h1 class="ln-claim">{claim}</h1>
<div class="ln-meta">首次记录 <time datetime="{first}">{first}</time> · 最近修订 {updated} · {n} 份证据</div>
</section>
{note}
<h2 class="ln-h">证据时间线<span class="ln-count">由新到旧</span></h2>
<ol class="ev">
{ev}
</ol>
{imp}
{ext_block}
<div class="ln-foot">每条判断只追加、不改写：如果哪天证据推翻了它，会在这里写明失效条件和日期，原句保留。</div>""".format(
        domain=escape(line.get("domain", "")), status=status_html(line["status"]),
        claim=escape(line["claim"]),
        first=escape(line.get("first_seen", "")), updated=escape(line.get("updated", "")),
        note=note_html, n=len(evs), ev=ev_html, imp=imp_html, ext_block=ext_block)

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


def render_imply(imp, extra_class=""):
    """推论块：与证据严格分层。推论是推论，不是证据，必须带失效条件。"""
    if not imp or not imp.get("text"):
        return ""
    fals = ('<p class="bf-imply__falsify">推论失效条件：%s</p>' % escape(imp["falsify"])
            ) if imp.get("falsify") else ""
    return ('<div class="bf-imply %s"><div class="bf-imply__label">推论 · 待检验</div>'
            '<p class="bf-imply__text">%s</p>%s</div>' % (
                extra_class, escape(imp["text"]), fals))


def render_index(lines, spine=None):
    spine_html = ""
    if spine and spine.get("claim"):
        imp = render_imply(
            {"text": spine.get("implication", ""), "falsify": spine.get("falsify", "")},
            extra_class="bf-imply--in")
        spine_html = ('<h2 class="ln-h">这些线连起来在说什么</h2>\n'
                      '<div class="bf-spine">'
                      '<div class="bf-spine__label">跨线判断 · %s</div>'
                      '<p class="bf-spine__claim">%s</p>%s</div>' % (
                          escape(spine.get("updated", "")),
                          escape(spine["claim"]), imp))
    cards = []
    for l in lines:
        src = escape(l["evidence"][-1]["source"]) if l["evidence"] else ""
        cards.append(
            '<li><a class="bf-card" href="/brief/lines/%s.html">'
            '<div class="bf-card-top"><span class="bf-chip">%s</span>%s</div>'
            '<p class="bf-claim">%s</p>'
            '<div class="bf-meta">%d 份证据 · 最近修订 %s</div>'
            '<div class="bf-src">最新证据来源：%s</div></a></li>' % (
                l["slug"], escape(l.get("domain", "")), status_html(l["status"]),
                escape(l["claim"]), len(l["evidence"]), escape(l.get("updated", "")), src))
    cards_html = "\n".join(cards)

    legend = "\n".join(
        '<li>%s<span>%s</span></li>' % (status_html(s), STATUS_MEANING[s])
        for s in STATUS_ORDER)

    dist = {}
    for l in lines:
        dist[l["status"]] = dist.get(l["status"], 0) + 1
    dist_html = " · ".join("%s %d" % (k, v) for k, v in sorted(
        dist.items(), key=lambda kv: STATUS_ORDER.get(kv[0], 9)))

    body = """<section class="bf-hero">
<div class="bf-eyebrow">AIHR 策展</div>
<h1 class="bf-title">信号线</h1>
<p class="bf-lede">这里放的是我们公开押上的判断。每条线盯一个可证伪的判断，一手证据随时间往上挂，判断后面还挂着它成立时组织该动的地方。被证据推翻时，我们在原句旁写明，不改口。</p>
</section>
{spine}
<ul class="bf-legend">
{legend}
</ul>
<h2 class="ln-h">正在追踪的判断<span class="ln-count">{n}</span></h2>
<ul class="bf-cards">
{cards}
</ul>
<h2 class="ln-h">往期</h2>
<ul class="bf-cards">
<li><a class="bf-card bf-issue" href="/brief/signal-brief-001.html">
<div class="bf-card-top"><span class="bf-chip">第 001 期</span><span class="bf-meta">2026 年 9 月 26 日</span></div>
<p class="bf-claim">创刊号：组织设计、人才趋势、双轨劳动力、agent 成本、科技裁员</p>
<div class="bf-meta">旧形态存档，已被信号线取代</div>
</a></li>
</ul>""".format(n=len(lines), dist=escape(dist_html), legend=legend,
               cards=cards_html, spine=spine_html)

    return page("信号线 | AIHR数智引擎",
                "AIHR 信号线：每条线是一条公开押上的判断，挂一手证据与修订记录；被推翻会写明失效条件，不改原文。",
                body, url="/brief/index.html", jsonld=None,
                og_title="信号线", og_type="website",
                back="/index.html", back_text="← 返回首页")


def load_spine():
    """跨线判断真源（人工撰写）。缺失时索引页不渲染该块，不报错。"""
    p = os.path.join(ROOT, "brief", "_spine.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


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
        print("  ✅ 线页 %s（%d 份证据）" % (url, len(l["evidence"])))

    idx = [{
        "slug": l["slug"], "claim": l["claim"], "status": l["status"],
        "domain": l.get("domain", ""), "updated": l.get("updated", ""),
        "first_seen": l.get("first_seen", ""),
        "evidence_count": len(l["evidence"]),
        "implication": l.get("implication", {}).get("text", ""),
        "url": "/brief/lines/%s.html" % l["slug"],
    } for l in lines]
    json.dump(idx, open(INDEX_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("  ✅ line-index.json（%d 条）" % len(idx))

    spine = load_spine()
    open(INDEX_PAGE, "w", encoding="utf-8").write(render_index(lines, spine))
    print("  ✅ brief/index.html（%d 条线）" % len(lines))


if __name__ == "__main__":
    main()
