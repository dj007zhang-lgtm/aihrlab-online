#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
延伸阅读链接截断检测（Inline-Related Link Truncation Check）
============================================================
目的：捕捉"写文时手滑把延伸阅读链接文字复制成目标文章标题的前半截"这一系统性 bug。
      此前 meta-pod-structure 等页面出现「AI正在系统性优」「工程师在变成「」等截断链接，
      全站扫描曾发现 90 处。这种截断：①读者看到半句不知所云 ②内部锚文本权重传递失真。

判定：inline-related 区块内每个 <a href="/articles/SLUG.html">TEXT</a>，
      若 TEXT 是目标文章 H1 的【严格前缀】（且明显更短）= 物理截断 → FAIL。

用法：
  python3 scripts/check_inline_links.py            # 全站扫描
  python3 scripts/check_inline_links.py articles/x.html  # 单文件
返回：发现任意 FAIL 则 exit 1，否则 exit 0。
"""

import os
import re
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INLINE_BLOCK_RE = re.compile(r'<div class=["\']inline-related["\'][^>]*>(.*?)</div>\s*</div>', re.S)
# 更宽松：匹配 inline-related 到其闭合（兼容嵌套）
INLINE_RE = re.compile(r'<div class=["\']inline-related["\'][^>]*>(.*)', re.S)
LINK_RE = re.compile(r'<a[^>]*href=["\']/articles/([^"\']+\.html)["\'][^>]*>(.*?)</a>', re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)


def _strip_tags(s):
    if not s:
        return ""
    return re.sub(r"<[^>]+>", "", s).strip()


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def _h1_of(slug_html):
    """从目标文章抽取 H1（健壮）。"""
    p = os.path.join(SITE_ROOT, "articles", slug_html)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8", errors="ignore") as fh:
        c = fh.read()
    m = H1_RE.search(c)
    return _strip_tags(m.group(1)) if m else None


def check_file(path):
    issues = []
    rel = os.path.relpath(path, SITE_ROOT)
    if "templates/" in rel:
        return issues
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        content = fh.read()
    if "inline-related" not in content:
        return issues

    # 抽取所有 inline-related 区块
    blocks = INLINE_RE.findall(content)
    for block in blocks:
        # 截到下一个同层 div 结束较复杂，直接用链接正则扫整个 block 即可
        for slug, ltext in LINK_RE.findall(block):
            link_text = _strip_tags(ltext)
            h1 = _h1_of(slug)
            if not h1 or not link_text:
                continue
            nh, nl = _norm(link_text), _norm(h1)
            if nh and nl and nl.startswith(nh) and len(nh) < len(nl) - 1:
                issues.append((
                    "FAIL",
                    f"{rel}: 延伸阅读链接文字被截断成目标 H1 的前半截"
                    f" —— 链接「{link_text}」 vs 目标「{h1}」 (/{slug})",
                ))
    return issues


def main():
    args = sys.argv[1:]
    files = []
    if args:
        for a in args:
            p = a if os.path.isabs(a) else os.path.join(SITE_ROOT, a)
            if os.path.exists(p):
                files.append(p)
    else:
        for root, dirs, fs in os.walk(SITE_ROOT):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
            for f in fs:
                if f.endswith(".html"):
                    files.append(os.path.join(root, f))

    all_issues = []
    checked = 0
    for p in sorted(files):
        if "inline-related" in open(p, "r", encoding="utf-8", errors="ignore").read():
            checked += 1
        all_issues.extend(check_file(p))

    fails = [i for i in all_issues if i[0] == "FAIL"]
    print("=" * 60)
    print("  延伸阅读链接截断检测 (Inline-Related Link Check)")
    print("=" * 60)
    if not fails:
        print(f"  🟢 未发现延伸阅读链接截断（扫描含 inline-related 的页面 {checked} 个）")
    else:
        print(f"\n  ❌ FAIL × {len(fails)}")
        for _, m in fails:
            print(f"    • {m}")
    print("=" * 60)
    print(f"  扫描文件: {len(files)} | 含 inline-related: {checked} | FAIL: {len(fails)}")
    print("=" * 60)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
