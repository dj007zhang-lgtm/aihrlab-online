#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
延伸阅读链接修复（一次性清理历史债，配合 check_inline_links.py）
==============================================================
把 inline-related 里被截断成目标 H1 前半截的链接文字，补全为目标文章 H1 全文。
仅当链接文字是目标 H1 的前缀（即被截断）时才改，已完整的短链接不动。

实现：精确替换 `<a href="X">OLD</a>` 整段，不重写结构。
改完请用 validate_article.py 复核。
"""
import os
import re

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INLINE_RE = re.compile(r'<div class=["\']inline-related["\'][^>]*>(.*)', re.S)
LINK_RE = re.compile(r'<a[^>]*href=["\']/articles/([^"\']+\.html)["\'][^>]*>(.*?)</a>', re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)


def _strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).strip()


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def _h1_of(slug_html):
    p = os.path.join(SITE_ROOT, "articles", slug_html)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8", errors="ignore") as fh:
        c = fh.read()
    m = H1_RE.search(c)
    return _strip_tags(m.group(1)) if m else None


def main():
    total = 0
    files_changed = []
    for root, dirs, fs in os.walk(SITE_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for fn in fs:
            if not fn.endswith(".html"):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, SITE_ROOT)
            if "templates/" in rel:
                continue
            with open(fp, "r", encoding="utf-8") as fh:
                content = fh.read()
            if "inline-related" not in content:
                continue

            new_content = content
            blocks = INLINE_RE.findall(content)
            changed_here = 0
            for block in blocks:
                for m in LINK_RE.finditer(block):
                    slug = m.group(1)
                    ltext = m.group(2)
                    full_tag = m.group(0)
                    link_text = _strip_tags(ltext)
                    h1 = _h1_of(slug)
                    if not h1 or not link_text:
                        continue
                    nh, nl = _norm(link_text), _norm(h1)
                    if nh and nl and nl.startswith(nh) and len(nh) < len(nl) - 1:
                        # 保留完整 <a> 标签（含 class 等属性），仅替换内部文字
                        new_tag = full_tag.replace(ltext, h1, 1)
                        if full_tag in new_content:
                            new_content = new_content.replace(full_tag, new_tag, 1)
                            changed_here += 1
                            total += 1
            if changed_here > 0:
                with open(fp, "w", encoding="utf-8") as fh:
                    fh.write(new_content)
                files_changed.append((rel, changed_here))

    print(f"延伸阅读链接修复完成：{total} 处补全为目标 H1 全文，涉及 {len(files_changed)} 个文件。")
    for rel, n in files_changed[:40]:
        print(f"  {rel}: {n} 处")


if __name__ == "__main__":
    main()
