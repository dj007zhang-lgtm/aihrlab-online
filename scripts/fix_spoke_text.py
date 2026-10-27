#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_spoke_text.py — 把枢纽页 spoke 列表的链接文字对齐到目标文章真实 H1

Gate10 铁律：相关链接文字必须逐字复制目标文章 H1。
违例形态是「改过标题后没有同步」：加了修饰后缀、换了数据来源描述、
全半角引号混用、把完整标题缩成短语。枢纽页里这类残留实测 44 处。

只修 <li><a href="/articles/x.html">…</a></li> 形式的列表项。
正文 <p> 里内嵌的叙述性引用（如「《…》这篇讲了什么」）是刻意措辞，不在此列。

纪律：
  - 逐字对齐，不做任何润色、不加后缀、不缩写。
  - 幂等：已一致的不动，重复执行零改动。
  - 精确字面量替换 + 计数断言 + 字节对账。
"""
import os
import re
import sys
import subprocess

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip() or \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUBDIR = os.path.join(ROOT, "hub")
ART = os.path.join(ROOT, "articles")

LI_RE = re.compile(r'<li><a href="/articles/([a-z0-9\-]+)\.html">(.*?)</a></li>')


def h1_of(slug):
    p = os.path.join(ART, slug + ".html")
    if not os.path.exists(p):
        return None
    h = open(p, encoding="utf-8", errors="ignore").read()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else None


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    apply = "--apply" in sys.argv
    total = 0
    pages = 0
    report = []

    for f in sorted(os.listdir(HUBDIR)):
        if not f.endswith(".html") or f == "index.html":
            continue
        p = os.path.join(HUBDIR, f)
        html = open(p, encoding="utf-8").read()
        orig = html
        fixed = []

        for m in list(LI_RE.finditer(html)):
            slug, txt = m.group(1), m.group(2)
            if slug == "index":
                continue
            real = h1_of(slug)
            if real is None or txt == real:
                continue
            new_li = '<li><a href="/articles/%s.html">%s</a></li>' % (slug, esc(real))
            old_li = m.group(0)
            if html.count(old_li) != 1:
                print("❌ 非唯一匹配，跳过: %s / %s" % (f, slug))
                continue
            html = html.replace(old_li, new_li, 1)
            fixed.append((slug, txt, real))

        if not fixed:
            continue

        # 字节对账：长度差必须等于替换净增
        delta = sum(len(esc(r)) - len(t) for _, t, r in fixed)
        if len(html) - len(orig) != delta:
            print("❌ 字节对账失败，回滚该页: %s" % f)
            continue

        if apply:
            open(p, "w", encoding="utf-8").write(html)
        pages += 1
        total += len(fixed)
        report.append((f, fixed))

    print("=== spoke 文字对齐（%s）===" % ("落盘" if apply else "dry-run"))
    for f, fixed in report:
        print("  %s  修正 %d 处" % (f, len(fixed)))
        for slug, old, new in fixed[:3]:
            print("      %s" % slug)
            print("        - %s" % old[:70])
            print("        + %s" % new[:70])
    print("\n合计：%d 个枢纽页 / %d 处" % (pages, total))
    if not apply:
        print("\n[dry-run] 未写入。加 --apply 落盘。")


if __name__ == "__main__":
    main()
