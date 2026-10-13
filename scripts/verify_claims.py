#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_claims.py —— 汇报口径实测器（CLAIMS GATE）

为什么存在（2026-10-13 主理人批评「每次给的信息都不准确」后固化）：
  同一类错误在四个月内已复发四次，形态一致——**用记忆快照/上轮结论代替此刻实测**：
    1. 「59 篇 noindex」        → 实测全站 57（数字来自 MEMORY.md 旧条目，从未重测）
    2. 「51 篇空壳残骸待下线」  → 实为 50 个正常工作的 URL 合并跳转壳，0 死链（定性错）
    3. 「article-index 231 条」 → 实测 257（旧快照）
    4. 「全站 53 篇 noindex」   → 实测 articles/ 目录 51、全站 57（**测量范围 ≠ 表述范围**）
  根因不是不会核验，而是：核验只发生在「要动手改的对象」上，
  从不发生在「要说出口的结论」上。说出口的话没有闸门。

本脚本的契约：
  - 每一项状态数字都带 **scope**（测量范围）与 **时间戳**，不存在裸数字。
  - 输出即唯一可引用来源。**任何汇报中的状态数字必须能在本文输出里逐项对上**；
    对不上就是没测，不允许出口。
  - scope 必须显式区分 `articles/` 与 `全站`——历史最大的坑就是混用二者。

用法：
  python3 scripts/verify_claims.py            # 输出全部实测项
  python3 scripts/verify_claims.py --json     # 机器可读
"""
import os
import re
import sys
import json
import html as H
from datetime import datetime

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(SITE_ROOT, "articles")
SKIP_DIRS = (".git", "node_modules", "__pycache__", "_wip", "templates")

NOINDEX_RE = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*noindex', re.I)
REFRESH_RE = re.compile(r'http-equiv=["\']refresh["\']\s+content=["\'][^;]*;\s*url=([^"\']+)', re.I)


def _read(p):
    with open(p, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _iter_html(scope):
    """遍历 HTML。scope='site' 全站（排除模板/临时目录）；scope='articles' 只文章目录。"""
    if scope == "articles":
        for f in sorted(os.listdir(ARTICLES)):
            if f.endswith(".html"):
                yield os.path.join(ARTICLES, f)
        return
    for dp, dn, fn in os.walk(SITE_ROOT):
        if any(x in dp for x in SKIP_DIRS):
            continue
        for f in fn:
            if f.endswith(".html"):
                yield os.path.join(dp, f)


def _visible_len(seg):
    seg = re.sub(r"<!--.*?-->", " ", seg, flags=re.S)
    seg = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", seg, flags=re.S | re.I)
    seg = re.sub(r"<[^>]+>", " ", seg)
    return len(re.sub(r"\s+", " ", H.unescape(seg)).strip())


def _target_exists(target):
    """跳转目标是否真实存在。target 可能是绝对 URL 或站内相对路径。"""
    t = target.strip()
    for prefix in ("https://www.aihrlab.online", "http://www.aihrlab.online"):
        if t.startswith(prefix):
            t = t[len(prefix):]
    t = t.split("?")[0].split("#")[0]
    return os.path.exists(os.path.join(SITE_ROOT, t.lstrip("/")))


def measure(scope):
    files = list(_iter_html(scope))
    noindex, stubs, dead = [], [], []
    for p in files:
        h = _read(p)
        if NOINDEX_RE.search(h):
            noindex.append(os.path.relpath(p, SITE_ROOT))
        m = REFRESH_RE.search(h)
        if m:
            stubs.append(os.path.relpath(p, SITE_ROOT))
            if not _target_exists(m.group(1)):
                dead.append((os.path.relpath(p, SITE_ROOT), m.group(1)))
    return {
        "scope": scope,
        "html_files": len(files),
        "noindex": len(noindex),
        "redirect_stubs": len(stubs),
        "stub_dead_targets": dead,
        "noindex_non_stub": sorted(set(noindex) - set(stubs)),
    }


def main():
    facts = {
        "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "site_root": SITE_ROOT,
    }
    facts["articles_dir"] = measure("articles")
    facts["whole_site"] = measure("site")

    sm = _read(os.path.join(SITE_ROOT, "sitemap.xml"))
    facts["sitemap_urls"] = len(re.findall(r"<loc>([^<]+)</loc>", sm))

    idx = json.load(open(os.path.join(SITE_ROOT, "assets/js/article-index.json")))
    facts["article_index_entries"] = len(idx.get("articles", idx)) if isinstance(idx, dict) else len(idx)

    # 可索引薄内容（真正需要关注的对象：非跳转壳、非列表页）
    thin = []
    for p in _iter_html("articles"):
        h = _read(p)
        if NOINDEX_RE.search(h) or REFRESH_RE.search(h):
            continue
        m = re.search(r"<article\b[^>]*>(.*?)</article>", h, re.S | re.I)
        if not m:
            continue
        n = _visible_len(m.group(1))
        if n < 800:
            thin.append((os.path.relpath(p, SITE_ROOT), n))
    facts["indexable_thin_under_800"] = sorted(thin, key=lambda x: x[1])

    if "--json" in sys.argv:
        print(json.dumps(facts, ensure_ascii=False, indent=1))
        return

    print("=" * 64)
    print(f"  汇报口径实测  {facts['measured_at']}")
    print("  本输出是唯一可引用来源；scope 必须与你的表述一致")
    print("=" * 64)
    for key in ("articles_dir", "whole_site"):
        d = facts[key]
        print(f"\n[{d['scope']}]")
        print(f"  html 文件数        : {d['html_files']}")
        print(f"  noindex 页         : {d['noindex']}")
        print(f"  其中跳转壳         : {d['redirect_stubs']}")
        print(f"  跳转壳死目标       : {len(d['stub_dead_targets'])} {d['stub_dead_targets'][:3]}")
        print(f"  noindex 非跳转壳   : {len(d['noindex_non_stub'])} {d['noindex_non_stub'][:5]}")
    print(f"\n[索引]")
    print(f"  sitemap URL        : {facts['sitemap_urls']}")
    print(f"  article-index 条数 : {facts['article_index_entries']}")
    print(f"\n[可索引薄内容 <800 字（articles/，已排除跳转壳）]  {len(facts['indexable_thin_under_800'])} 篇")
    for r, n in facts["indexable_thin_under_800"][:10]:
        print(f"    {n:>5}  {r}")
    print("\n⚠️ 引用规则：说「全站」用 whole_site，说「文章」用 articles_dir。混用即为失真。")


if __name__ == "__main__":
    main()
