#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性修复：templates/taxonomy.html 生成的所有聚合页 head 字段。

缺陷根因（已在模板侧修）:
  模板原写 <meta ... content="><!--TPL_DESC-->">，多余的 ">" 落在 content 值开头，
  产物变成 content=">AIHR数智引擎标签「组织变革」聚合 147 篇...">，导致
  ① 严格解析器取不到 description  ② 搜索摘要以 ">" 开头  ③ og:url 失效
  ④ og:title 携带品牌后缀（违 R-16）

本脚本不改正文、不重建索引，只就地修 head 四个字段，幂等可重跑。
usage: python3 scripts/fix_taxonomy_head.py [--apply]
"""

import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = "AIHR数智引擎"
APPLY = "--apply" in sys.argv

TARGETS = []
for d in ("categories", "tags"):
    base = os.path.join(ROOT, d)
    if not os.path.isdir(base):
        continue
    for fn in sorted(os.listdir(base)):
        if fn.endswith(".html"):
            TARGETS.append(os.path.join(base, fn))

FIX_Q = 0  # content="> 污染
FIX_OG = 0  # og:title 去后缀
FIX_TW = 0  # 补 twitter:title/description
SKIP = 0


def h1_of(t):
    m = re.search(r"<h1\b[^>]*>(.*?)</h1>", t, re.S | re.I)
    if not m:
        return None
    s = re.sub(r"<[^>]+>", "", m.group(1))
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def get_meta(t, attr, name):
    m = re.search(
        r"<meta[^>]+%s=[\"']%s[\"'][^>]*content=[\"']([^\"']*)[\"']" % (attr, re.escape(name)),
        t, re.I)
    if m:
        return m
    return re.search(
        r"<meta[^>]+content=[\"']([^\"']*)[\"'][^>]*%s=[\"']%s[\"']" % (attr, re.escape(name)),
        t, re.I)


def set_meta(t, attr, name, value):
    """把已存在的 meta 的 content 换成 value；返回 None 表示没找到。"""
    m = get_meta(t, attr, name)
    if not m:
        return None
    whole = m.group(0)
    new = re.sub(r"content=[\"'][^\"']*[\"']",
                 lambda _: 'content="%s"' % value, whole, count=1)
    return t.replace(whole, new, 1)


def add_meta_before(t, anchor, snippet):
    if snippet.strip() in t:
        return t
    return t.replace(anchor, snippet + "\n" + anchor, 1)


report = []
for path in TARGETS:
    rel = os.path.relpath(path, ROOT)
    raw = open(path, encoding="utf-8").read()
    t = raw
    head_end = t.find("</head>")
    head = t[:head_end] if head_end > 0 else t

    # 1) 清掉 content 值开头的 ">"
    if re.search(r"content=\">", head):
        head_new = head.replace('content=">', 'content="')
        FIX_Q += head.count('content=">')
        t = head_new + t[len(head):]
        head = head_new

    h1 = h1_of(t)
    if not h1:
        SKIP += 1
        report.append((rel, "SKIP 无 h1", ""))
        continue

    changed_local = []

    # 2) og:title 必须等于 h1 且不含品牌后缀（R-16）
    m = get_meta(t, "property", "og:title")
    if m and m.group(1) != h1:
        if BRAND in m.group(1) or m.group(1).lstrip(">") != h1:
            t = set_meta(t, "property", "og:title", h1) or t
            FIX_OG += 1
            changed_local.append("og:title")

    # 3) twitter:title / twitter:description 对齐 og
    desc_m = get_meta(t, "name", "description")
    desc = desc_m.group(1) if desc_m else ""
    tw = get_meta(t, "name", "twitter:title")
    if tw:
        if tw.group(1) != h1:
            t = set_meta(t, "name", "twitter:title", h1) or t
            FIX_TW += 1
            changed_local.append("twitter:title")
    else:
        anchor = '<meta name="twitter:card"'
        if anchor in t:
            t = add_meta_before(t, anchor,
                                '  <meta name="twitter:title" content="%s">' % h1)
            FIX_TW += 1
            changed_local.append("twitter:title+")
    twd = get_meta(t, "name", "twitter:description")
    if desc and not twd:
        anchor = '<meta name="twitter:card"'
        if anchor in t:
            t = add_meta_before(t, anchor,
                                '  <meta name="twitter:description" content="%s">' % desc)
            FIX_TW += 1
            changed_local.append("twitter:desc+")

    if t != raw:
        report.append((rel, "%d 处 head 污染" % raw.count('content=">'),
                       ",".join(changed_local) or "仅去污染"))
        if APPLY:
            open(path, "w", encoding="utf-8").write(t)

print("目标聚合页：%d" % len(TARGETS))
print("  content=\"> 污染修正：%d 处" % FIX_Q)
print("  og:title 归一到 h1 ：%d 处" % FIX_OG)
print("  twitter:* 补齐/归一：%d 处" % FIX_TW)
print("  跳过（无 h1）      ：%d 页" % SKIP)
print("-" * 60)
for rel, a, b in report[:40]:
    print("  %-34s %-14s %s" % (rel, a, b))
print("-" * 60)
print("模式：%s" % ("已写入磁盘" if APPLY else "DRY-RUN 预览（加 --apply 落盘）"))
