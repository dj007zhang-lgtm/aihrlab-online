# -*- coding: utf-8 -*-
"""AIHRlab(网站) · og:title / twitter:title 对齐 h1。

体系归属：AIHRlab 网站侧（与公众号规则无关）。
纪律（R-16/R-17）：h1 == og:title == twitter:title，三者均不得含 "| AIHR数智引擎" 后缀；
只有 <title> 允许带后缀。本脚本只改 og:title / twitter:title 两个字段，绝不动 <title> 与 h1。

安全约束：
  - 精确整标签字面量匹配，不用贪婪正则；
  - 每字段命中数必须恰好 1，否则跳过该文件并报错（不产生半改）；
  - 幂等：已对齐的文件重跑 0 改动；
  - 跳过 noindex + meta refresh 的跳转壳（URL 合并壳，禁止改动）。

用法：python3 scripts/align_og_title.py [--apply]   （无 --apply 为 dry-run）
"""

import re, glob, html, sys, os, json

APPLY = "--apply" in sys.argv
ROOT = os.getcwd()

META_RE = re.compile(r'<meta\s+([^>]*?)/?>', re.I | re.S)

def meta_tags(s):
    """返回 [(field, raw_content, full_tag)]"""
    out = []
    for m in META_RE.finditer(s):
        a = m.group(1)
        k = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', a, re.I)
        v = re.search(r'content\s*=\s*["\']([^"\']*)["\']', a, re.I)
        if k and v:
            out.append((k.group(1).lower(), v.group(1), m.group(0)))
    return out

def get_h1(s):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.I | re.S)
    if not m: return None
    return re.sub(r'<[^>]+>', '', m.group(1)).strip()

def esc(x):
    return html.escape(x, quote=True)

files = sorted(sum([glob.glob(p) for p in (
    "articles/*.html","hub/*.html","assessments/*.html","resources/*.html","products/*.html")], []))

jobs = []      # (file, field, old_tag, new_tag)
skipped = []
for f in files:
    s = open(f, encoding="utf-8").read()
    if re.search(r'name=["\']robots["\'][^>]+noindex', s, re.I) and re.search(r'http-equiv=["\']refresh', s, re.I):
        continue
    h1 = get_h1(s)
    if not h1: continue
    for fld, raw, tag in meta_tags(s):
        if fld not in ("og:title", "twitter:title"): continue
        cur = html.unescape(raw).strip()
        if cur == h1: continue
        # 只换 content 值，保持标签其余结构不变（含引号样式）
        new_tag = re.sub(r'content\s*=\s*["\'][^"\']*["\']',
                         lambda m: m.group(0).split("=")[0] + '="' + esc(h1) + '"', tag, count=1)
        jobs.append((f, fld, tag, new_tag, cur, h1))

print(f"待替换 {len(jobs)} 处，涉及 {len(set(j[0] for j in jobs))} 个文件")
for f, fld, tag, new_tag, cur, h1 in jobs:
    print(f"\n  {f}  [{fld}]")
    print(f"    旧: {cur}")
    print(f"    新: {h1}")

if not APPLY:
    print("\n[DRY-RUN] 未落盘。加 --apply 执行。")
    sys.exit(0)

# ---- 落盘：按文件聚合，逐文件计数断言 + 字节对账 ----
byfile = {}
for f, fld, tag, new_tag, cur, h1 in jobs:
    byfile.setdefault(f, []).append((fld, tag, new_tag))

fail = 0; changed = 0
for f, items in byfile.items():
    s = open(f, encoding="utf-8").read()
    before = s
    for fld, tag, new_tag in items:
        n = s.count(tag)
        if n != 1:
            print(f"  ❌ {f} [{fld}] 命中 {n} 次（期望 1）—— 跳过该文件")
            fail += 1; s = None; break
        s = s.replace(tag, new_tag, 1)
    if s is None: continue
    if s == before:
        print(f"  ⚠ {f} 无变化"); continue
    open(f, "w", encoding="utf-8").write(s)
    changed += 1
    print(f"  ✅ {f}  [{len(before)} → {len(s)} bytes, Δ{len(s)-len(before)}]")

print(f"\n落盘 {changed} 个文件，失败 {fail} 个")
