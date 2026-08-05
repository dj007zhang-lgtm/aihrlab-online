#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引号修复脚本（一次性清理历史债，配合 check_title_consistency.py）
==============================================================
把中文文本里混用的英文双引号 " 成对转为「」（中文规范）。
仅处理文本元素：<title> / <h1> / <h2> / <h3> / 延伸阅读链接文字。
不处理属性值（href/content 的引号是 HTML 语法，不可动）。

实现：每个元素用整段标签作为锚点做精确字符串替换，不重写 HTML 结构。
改完请用 validate_article.py 复核。
"""
import os
import re

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TITLE_RE = re.compile(r"(<title>)(.*?)(</title>)", re.S | re.I)
H1_RE = re.compile(r"(<h1[^>]*>)(.*?)(</h1>)", re.S | re.I)
H2_RE = re.compile(r"(<h2[^>]*>)(.*?)(</h2>)", re.S | re.I)
H3_RE = re.compile(r"(<h3[^>]*>)(.*?)(</h3>)", re.S | re.I)
INLINE_LINK_RE = re.compile(r'(<a[^>]*href=["\']/articles/[^"\']+["\'][^>]*>)(.*?)(</a>)', re.S | re.I)


def clean_quotes(s):
    """英文双引号成对转「」；奇数则整体包「」（兜底）。"""
    if '"' not in s:
        return s
    parts = s.split('"')
    res = parts[0]
    for i in range(1, len(parts)):
        q = "「" if i % 2 == 1 else "」"
        res += q + parts[i]
    return res


def fix_element(content, regex):
    """对匹配到的每个元素，替换其内部文本引号，返回新 content 与改动数。"""
    changed = 0
    for m in regex.finditer(content):
        pre, inner, post = m.group(1), m.group(2), m.group(3)
        new_inner = clean_quotes(inner)
        if new_inner != inner:
            full = m.group(0)
            new_full = pre + new_inner + post
            content = content.replace(full, new_full, 1)
            changed += 1
    return content, changed


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
            if any(x in fn for x in ["baidu_", "google", "BingSiteAuth", "verify"]) or "404" in fn:
                continue
            with open(fp, "r", encoding="utf-8") as fh:
                content = fh.read()
            if 'http-equiv="refresh"' in content:
                continue

            c = content
            c, n1 = fix_element(c, TITLE_RE)
            c, n2 = fix_element(c, H1_RE)
            c, n3 = fix_element(c, H2_RE)
            c, n4 = fix_element(c, H3_RE)
            c, n5 = fix_element(c, INLINE_LINK_RE)
            n = n1 + n2 + n3 + n4 + n5
            if n > 0:
                with open(fp, "w", encoding="utf-8") as fh:
                    fh.write(c)
                total += n
                files_changed.append((rel, n))

    print(f"引号修复完成：{total} 处元素内英文双引号转「」，涉及 {len(files_changed)} 个文件。")
    for rel, n in files_changed[:40]:
        print(f"  {rel}: {n} 处")


if __name__ == "__main__":
    main()
