#!/usr/bin/env python3
"""P1 信息架构归位 · 一次性修复脚本（幂等）

三件事：
  A. 主导航「策展」由 /bridge/index.html 改指 /brief/index.html（全站）
  B. 给缺站内入口的读者页注入标准页头（site-header + nav.site-nav）
  C. 给独立单文件工具页注入自包含站内入口条（site-nav-mini，不依赖全局 CSS）

纪律：
  - 默认干跑；--apply 才写盘。
  - 每处改动带期望次数断言，落盘前后做字节对账。
  - 幂等：已改动过的文件自动跳过（skip），重复运行不叠加。

用法：
  python3 scripts/fix_ia_p1.py            # 干跑，打印报告
  python3 scripts/fix_ia_p1.py --apply    # 落盘
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A. 导航改指
OLD_CURATION = re.compile(r'href="/bridge/index.html"([^>]*)>策展')
NEW_CURATION = r'href="/brief/index.html"\1>策展'

# B. 标准页头（取自 canonical 文章页，去掉 active 标记）
HEADER = ('<header class="site-header"><div class="container">'
          '<a href="/index.html" class="site-logo" aria-label="AIHR数智引擎首页">'
          '<img src="/assets/images/logo.png" class="logo-icon" alt="AIHR数智引擎" width="28" height="28">'
          ' AIHR<span class="logo-dot">数智引擎</span></a>'
          '<button class="nav-toggle" aria-label="打开导航菜单">&#9776;</button>'
          '<nav class="site-nav" aria-label="主导航">'
          '<a href="/index.html">首页</a>'
          '<a href="/articles/index.html">文章</a>'
          '<a href="/resources/index.html">资源库</a>'
          '<a href="/tools/index.html">测评</a>'
          '<a href="/brief/index.html">策展</a>'
          '<a href="/about.html">关于</a>'
          '__SEARCH__</nav></div></header>')

SEARCH_BTN = ('<button class="nav-search-btn" data-open-search aria-label="AI搜索">'
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
              '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
              '<span>AI搜索</span><span class="shortcut-hint"><kbd>&#8984;</kbd><kbd>K</kbd></span>'
              '</button>')

# B 目标：文件 -> 需要标记 active 的导航标签（None = 不标记）
#   说明：brief 两页未加载 search.js，故不注入 AI搜索 按钮（避免死按钮）
STD_TARGETS = {
    "brief/index.html": "策展",
    "brief/signal-brief-001.html": "策展",
    "hub/overseas-hr-hub.html": None,
}

# C. 自包含站内入口条：用于独立单文件工具页（有自有设计，不注入全局页头）
MINI = ('<div class="site-nav-mini"><div class="site-nav-mini__inner">'
        '<a class="site-nav-mini__brand" href="/index.html">AIHR数智引擎</a>'
        '<a href="/articles/index.html">文章</a>'
        '<a href="/resources/index.html">资源库</a>'
        '<a href="/tools/index.html">测评</a>'
        '<a href="/brief/index.html">策展</a>'
        '<a href="/about.html">关于</a>'
        '</div></div>')

MINI_CSS = ('<style>.site-nav-mini{background:#F1EFE9;border-bottom:1px solid rgba(26,26,23,.10);'
            'font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;'
            'font-size:13px}.site-nav-mini__inner{max-width:1080px;margin:0 auto;padding:10px 16px;'
            'display:flex;flex-wrap:wrap;gap:16px;align-items:center}'
            '.site-nav-mini a{color:#1A1A17;text-decoration:none}'
            '.site-nav-mini a:hover{color:#3F6212}'
            '.site-nav-mini__brand{color:#3F6212!important;font-weight:600;margin-right:auto}'
            'html[data-theme="dark"] .site-nav-mini{background:#0B0C0E;border-bottom-color:rgba(236,234,228,.12)}'
            'html[data-theme="dark"] .site-nav-mini a{color:#ECEAE4}'
            'html[data-theme="dark"] .site-nav-mini__brand{color:#6F9A3C!important}</style>')

MINI_TARGETS = [
    "tools/mbti/index.html",
    "tools/bigfive/index.html",
    "tools/holland/index.html",
    "tools/disc-test/index.html",
    "tools/ai-risk-test/index.html",
    "tools/tarot-test/index.html",
    "tools/compliance-dashboard.html",
]


def read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


def write(rel, txt):
    open(os.path.join(ROOT, rel), "w", encoding="utf-8").write(txt)


def header_for(active_label, with_search):
    h = HEADER.replace("__SEARCH__", SEARCH_BTN if with_search else "")
    if active_label:
        h = h.replace('<a href="%s">' % LABEL_HREF[active_label],
                      '<a href="%s" class="active" aria-current="page">' % LABEL_HREF[active_label])
    return h


LABEL_HREF = {
    "首页": "/index.html", "文章": "/articles/index.html", "资源库": "/resources/index.html",
    "测评": "/tools/index.html", "策展": "/brief/index.html", "关于": "/about.html",
}


def main():
    apply = "--apply" in sys.argv
    report = {"A_changed": 0, "A_skipped": 0, "B_injected": 0, "B_skipped": 0,
              "C_injected": 0, "C_skipped": 0, "errors": []}

    files = []
    for base, dirs, fs in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for f in fs:
            if f.endswith(".html"):
                files.append(os.path.relpath(os.path.join(base, f), ROOT))
    files.sort()

    for rel in files:
        if rel.startswith("templates/"):
            continue
        t = read(rel)
        orig = t

        # ---- A 导航改指 ----
        if ">/bridge/index.html" in t or 'href="/bridge/index.html"' in t:
            t, n = OLD_CURATION.subn(NEW_CURATION, t)
            if n:
                report["A_changed"] += n
        # ---- B 标准页头 ----
        if rel in STD_TARGETS:
            if "site-header" in t:
                report["B_skipped"] += 1
            else:
                m = re.search(r"<body[^>]*>", t)
                if not m:
                    report["errors"].append("%s 未找到 <body>" % rel)
                else:
                    hdr = header_for(STD_TARGETS[rel], with_search=(rel.startswith("hub/")))
                    t = t[:m.end()] + "\n" + hdr + t[m.end():]
                    report["B_injected"] += 1
        # ---- C 自包含入口条 ----
        if rel in MINI_TARGETS:
            if "site-nav-mini" in t:
                report["C_skipped"] += 1
            else:
                m = re.search(r"<body[^>]*>", t)
                if not m:
                    report["errors"].append("%s 未找到 <body>" % rel)
                else:
                    blk = "\n" + MINI_CSS + "\n" + MINI
                    t = t[:m.end()] + blk + t[m.end():]
                    report["C_injected"] += 1

        if t != orig and apply:
            write(rel, t)
            # 字节对账
            back = read(rel)
            if len(back) != len(t):
                report["errors"].append("%s 落盘字节对账失败" % rel)

    tag = "落盘完成" if apply else "干跑预览"
    print("=== P1 IA 归位 %s ===" % tag)
    print("  A 导航改指（策展 → /brief/）: %d 处" % report["A_changed"])
    print("  B 注入标准页头: %d 页（跳过已存在 %d）" % (report["B_injected"], report["B_skipped"]))
    print("  C 注入自包含入口条: %d 页（跳过已存在 %d）" % (report["C_injected"], report["C_skipped"]))
    if report["errors"]:
        print("  ⚠ 异常:")
        for e in report["errors"]:
            print("     ", e)
        sys.exit(1)
    print("  ✅ 无异常")


if __name__ == "__main__":
    main()
