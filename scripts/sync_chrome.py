#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_chrome.py — 全站 chrome（头部 / 页脚 / 面包屑位序 / 共享脚本）单一真相源同步器

背景（根因）
------------
全站长期靠「手写 + 复制粘贴」维护 site-header / site-footer，结果漂移严重：
  · 150 篇文章页出现 6 种 header 变体、7 种 footer 变体；
  · 导航 URL 两种形态并存（/articles/ 与 /articles/index.html）；
  · assessments/ 5 页停留在早已废弃的旧导航，且完全没有 site-footer；
  · 部分页面页脚退化成一行版权，站内内链全丢（直接推高跳出率）；
  · breadcrumb-nav 被放在 <header> 之前，渲染时贴在视口最左侧、盖在吸顶导航上方。

治理方式
--------
templates/_chrome.html 是唯一真相源。本脚本负责：
  1. 从真相源抽取 canonical header / footer；
  2. 按页面所属版块打 active 态；
  3. 幂等覆盖每页的 header / footer（保留页脚内的二维码块等页面级附加内容）；
  4. 把 breadcrumb-nav 从 header 之前移动到 header 之后（修正层叠与对齐）；
  5. 补齐共享脚本（analytics-loader / main / search / content-protect），
     其中 analytics-loader 缺失＝该页访问完全不被统计，属数据黑洞。

用法
----
  python3 scripts/sync_chrome.py --check     # 只报告漂移，有漂移退出码 1
  python3 scripts/sync_chrome.py --apply     # 写盘修复
  python3 scripts/sync_chrome.py --apply --sign   # 顺带签署 data-section-unified
  python3 scripts/sync_chrome.py --check --verbose
"""

import os
import re
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_SRC = os.path.join(SITE_ROOT, "templates", "_chrome.html")

# ---------------------------------------------------------------- 排除规则

# 独立单文件应用 / 校验桩 / 内部看板：不纳入 chrome 管辖
EXCLUDE_PREFIXES = (
    "templates/",
    "assets/",
    "_backup/",
    "articles-backup/",
    "tools/bigfive/",
    "tools/mbti/",
    "tools/disc-test/",
    "tools/holland/",
    "tools/ai-risk-test/",
)
EXCLUDE_FILES = {
    "seo-monitor.html",       # 内部监控看板，不对外
    "404.html",               # 保留独立极简版式
}

HEADER_RE = re.compile(r'<header class="site-header".*?</header>', re.S)
FOOTER_RE = re.compile(r'<footer class="site-footer".*?</footer>', re.S)
BODY_OPEN_RE = re.compile(r'<body[^>]*>')
BREADCRUMB_RE = re.compile(r'<nav class="breadcrumb-nav".*?</nav>', re.S)
QR_IN_FOOTER_RE = re.compile(r'<div class="article-footer-qr">.*?</div>\s*(?=<div class="footer-bottom")', re.S)

SHARED_SCRIPTS = [
    ('analytics-loader.js', '<script src="/assets/js/analytics-loader.js" defer></script>'),
    ('js/main.js',          '<script src="/assets/js/main.js" defer></script>'),
    ('js/qa-config.js',     '<script src="/assets/js/qa-config.js" defer></script>'),
    ('js/search.js',        '<script src="/assets/js/search.js" defer></script>'),
]
PROTECT_SCRIPT = ('content-protect.js', '<script src="/assets/js/content-protect.js" defer></script>')


# ---------------------------------------------------------------- 真相源

def load_chrome():
    """从 templates/_chrome.html 抽取 canonical header / footer。"""
    with open(CHROME_SRC, encoding="utf-8") as f:
        src = f.read()
    h = re.search(r'<!-- CHROME:HEADER -->\s*(.*?)\s*<!-- /CHROME:HEADER -->', src, re.S)
    ft = re.search(r'<!-- CHROME:FOOTER -->\s*(.*?)\s*<!-- /CHROME:FOOTER -->', src, re.S)
    if not h or not ft:
        raise SystemExit(f"[FATAL] 真相源缺少 CHROME:HEADER / CHROME:FOOTER 标记：{CHROME_SRC}")
    return h.group(1).strip(), ft.group(1).strip()


def active_nav_for(rel):
    """返回该页在主导航中应高亮的 href；None 表示不高亮。"""
    if rel == "index.html":
        return "/index.html"
    if rel == "about.html":
        return "/about.html"
    if rel.startswith("articles/"):
        return "/articles/index.html"
    if rel.startswith("resources/") or rel.startswith("products/"):
        return "/resources/index.html"
    if rel.startswith("tools/") or rel.startswith("assessments/"):
        return "/tools/index.html"
    if rel.startswith("bridge/"):
        return "/bridge/index.html"
    return None


def build_header(canonical, rel):
    """按页面打 active 态（幂等：canonical 本身不含 active）。"""
    href = active_nav_for(rel)
    if not href:
        return canonical
    return canonical.replace(
        f'<a href="{href}">',
        f'<a href="{href}" class="active" aria-current="page">',
        1,
    )


def build_footer(canonical, extra_html):
    """把页面级附加块（如页脚二维码）填回 FOOTER_EXTRA 占位。"""
    return canonical.replace("<!-- CHROME:FOOTER_EXTRA -->", extra_html or "")


# ---------------------------------------------------------------- 单页处理

def process(path, canonical_header, canonical_footer, sign=False):
    """返回 (new_html, changes[list[str]])。不写盘。"""
    rel = os.path.relpath(path, SITE_ROOT)
    with open(path, encoding="utf-8", errors="ignore") as f:
        html = f.read()
    original = html
    changes = []

    # --- 1) 页脚：先取出页面级附加块，再整体替换为 canonical
    old_footer = FOOTER_RE.search(html)
    extra = ""
    if old_footer:
        qr = QR_IN_FOOTER_RE.search(old_footer.group(0))
        if qr:
            extra = qr.group(0).strip()
    new_footer = build_footer(canonical_footer, extra)
    if old_footer:
        if old_footer.group(0) != new_footer:
            html = html[:old_footer.start()] + new_footer + html[old_footer.end():]
            changes.append("footer:同步")
    else:
        if "</body>" in html:
            html = html.replace("</body>", new_footer + "\n</body>", 1)
            changes.append("footer:补建")

    # --- 2) 头部
    new_header = build_header(canonical_header, rel)
    old_header = HEADER_RE.search(html)
    if old_header:
        if old_header.group(0) != new_header:
            html = html[:old_header.start()] + new_header + html[old_header.end():]
            changes.append("header:同步")
    else:
        m = BODY_OPEN_RE.search(html)
        if m:
            html = html[:m.end()] + "\n" + new_header + html[m.end():]
            changes.append("header:补建")

    # --- 3) 面包屑位序：header 之前 → header 之后
    bc = BREADCRUMB_RE.search(html)
    if bc:
        hdr = HEADER_RE.search(html)
        if hdr and bc.start() < hdr.start():
            block = bc.group(0)
            html = html[:bc.start()] + html[bc.end():]
            hdr = HEADER_RE.search(html)  # 位置已变，重新定位
            html = html[:hdr.end()] + "\n" + block + html[hdr.end():]
            changes.append("breadcrumb:移至头部之后")

    # --- 4) 共享脚本补齐
    missing = [tag for key, tag in SHARED_SCRIPTS if key not in html]
    if missing and "</head>" in html:
        html = html.replace("</head>", "".join(missing) + "\n</head>", 1)
        changes.append(f"scripts:补 {len(missing)} 个")
    if PROTECT_SCRIPT[0] not in html and "</body>" in html:
        html = html.replace("</body>", "  " + PROTECT_SCRIPT[1] + "\n</body>", 1)
        changes.append("scripts:补 content-protect")

    # --- 5) 契约签署
    if sign and 'data-section-unified="true"' not in html:
        m = BODY_OPEN_RE.search(html)
        if m:
            tag = m.group(0)
            new_tag = tag[:-1].rstrip() + ' data-section-unified="true">'
            html = html[:m.start()] + new_tag + html[m.end():]
            changes.append("契约:签署")

    return (html if html != original else original), changes


# ---------------------------------------------------------------- 目标发现

def discover():
    """所有受 chrome 管辖的页面（相对路径）。"""
    targets = []
    for root, dirs, files in os.walk(SITE_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for fn in files:
            if not fn.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), SITE_ROOT)
            if rel.startswith(EXCLUDE_PREFIXES) or rel in EXCLUDE_FILES:
                continue
            p = os.path.join(root, fn)
            try:
                head = open(p, encoding="utf-8", errors="ignore").read(4000)
            except Exception:
                continue
            if 'http-equiv="refresh"' in head:        # 301 桩页
                continue
            if os.path.getsize(p) < 600:              # 搜索引擎验证桩
                continue
            targets.append(rel)
    return sorted(targets)


def main():
    args = set(sys.argv[1:])
    apply_mode = "--apply" in args
    sign = "--sign" in args
    verbose = "--verbose" in args
    if not apply_mode and "--check" not in args:
        print(__doc__)
        return 0

    canonical_header, canonical_footer = load_chrome()
    targets = discover()

    drifted = []
    for rel in targets:
        path = os.path.join(SITE_ROOT, rel)
        new_html, changes = process(path, canonical_header, canonical_footer, sign=sign)
        if not changes:
            continue
        drifted.append((rel, changes))
        if apply_mode:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_html)

    print("=" * 62)
    print(f"  chrome 单一真相源同步  |  模式: {'APPLY' if apply_mode else 'CHECK'}")
    print(f"  真相源: templates/_chrome.html")
    print("=" * 62)
    print(f"扫描页面: {len(targets)}    漂移页面: {len(drifted)}")
    if drifted:
        buckets = {}
        for rel, ch in drifted:
            for c in ch:
                buckets.setdefault(c.split(":")[0] + ":" + c.split(":")[1], []).append(rel)
        for k in sorted(buckets):
            print(f"  · {k:<28} {len(buckets[k])} 页")
        if verbose:
            print()
            for rel, ch in drifted:
                print(f"    {rel:<62} {', '.join(ch)}")
    else:
        print("  全站 chrome 与真相源一致 ✅")

    if apply_mode:
        print(f"\n已写盘 {len(drifted)} 个文件。")
        return 0
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
