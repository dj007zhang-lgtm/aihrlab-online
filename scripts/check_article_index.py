#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_article_index.py —— Gate 16：文章索引完整性门（前置架构健壮性护栏）

为什么需要这扇门：
  article-index.json 是全站搜索（search.js）的唯一数据源。实测曾出现 16 条指向
  重定向桩页、15 条标题退化为英文 slug 的脏数据，导致搜索返回坏结果。本门把
  「索引条目必须指向真实、非桩页、有中文标题的文章，且无重复」固化为可见护栏，
  防止脏数据再次进入索引。

检查项：
  1. 文件存在且为 JSON 数组。
  2. 每个条目含 url 与 title 字段。
  3. url 解析到的本地 HTML 真实存在（防止指向不存在/误删页面）。
  4. 该 HTML 不是重定向桩页（window.location.replace / 本页面已迁移）。
  5. title 至少含一个中文字符（拦住英文 slug 退化占位）。
  6. url 无重复。

用法：
  python3 scripts/check_article_index.py
  python3 scripts/check_article_index.py /path/to/site
  python3 scripts/check_article_index.py --selftest
"""
import os
import sys
import json
import re
import shutil

CJK = re.compile(r"[\u4e00-\u9fff]")
STUB_MARKERS = ("window.location.replace", "本页面已迁移")


def _is_stub(path):
    if not path or not os.path.exists(path):
        return False
    try:
        t = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return False
    return any(m in t for m in STUB_MARKERS)


def _resolve(url, site_root):
    u = url[1:] if url.startswith("/") else url
    cands = [
        os.path.join(site_root, "articles", u + ".html"),
        os.path.join(site_root, "articles", u),
        os.path.join(site_root, u + ".html"),
        os.path.join(site_root, u),
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def run(site_root):
    details = []
    p = os.path.join(site_root, "assets", "js", "article-index.json")
    if not os.path.exists(p):
        return False, ["article-index.json 不存在：" + p]
    try:
        data = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        return False, ["article-index.json 解析失败：" + str(e)]
    if not isinstance(data, list):
        return False, ["article-index.json 必须是数组，实际为 " + type(data).__name__]

    seen = set()
    for i, e in enumerate(data):
        if not isinstance(e, dict):
            details.append("条目 %d 不是对象" % i)
            continue
        url = e.get("url")
        title = e.get("title")
        if not isinstance(url, str) or not url:
            details.append("条目 %d 缺少有效 url" % i)
            continue
        if not isinstance(title, str) or not title.strip():
            details.append("条目 %s 缺少有效 title" % url)
            continue
        # 6) 重复 url
        if url in seen:
            details.append("url 重复（索引去重）：%s" % url)
        else:
            seen.add(url)
        # 3) 文件存在
        f = _resolve(url, site_root)
        if not f:
            details.append("url 指向的页面不存在：%s" % url)
            continue
        # 4) 非桩页
        if _is_stub(f):
            details.append("url 指向重定向桩页（应清理出索引）：%s" % url)
            continue
        # 5) 中文标题
        if not CJK.search(title):
            details.append("title 退化为非中文占位（应为真实文章标题）：%s -> %s" % (url, title))

    return (len(details) == 0), details


def _selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="cai_selftest_")
    try:
        os.makedirs(os.path.join(tmp, "assets", "js"))
        os.makedirs(os.path.join(tmp, "articles"))
        # 真实文章
        open(os.path.join(tmp, "articles", "real-article.html"), "w").write("<html><body>真实文章</body></html>")
        # 桩页
        open(os.path.join(tmp, "articles", "stub.html"), "w").write(
            '<html><body>本页面已迁移<script>window.location.replace("x")</script></body></html>')
        # 脏索引：1 真实 + 1 桩页 + 1 英文 slug + 1 缺文件 + 1 重复
        dirty = [
            {"title": "真实文章标题", "url": "real-article", "category": "x", "date": "2026-01-01"},
            {"title": "stub article", "url": "stub", "category": "x", "date": "2026-01-01"},
            {"title": "english slug title", "url": "real-article", "category": "x", "date": "2026-01-01"},
            {"title": "无此页面", "url": "ghost", "category": "x", "date": "2026-01-01"},
            {"title": "真实文章标题", "url": "real-article", "category": "x", "date": "2026-01-01"},
        ]
        json.dump(dirty, open(os.path.join(tmp, "assets", "js", "article-index.json"), "w"), ensure_ascii=False)

        ok, det = run(tmp)
        assert ok is False, "脏索引应 FAIL：%s" % det
        assert any("stub" in d for d in det), "应检出桩页：%s" % det
        assert any("english slug" in d for d in det), "应检出英文 slug：%s" % det
        assert any("ghost" in d for d in det), "应检出缺文件：%s" % det
        assert any("重复" in d for d in det), "应检出重复：%s" % det

        # 干净索引
        clean = [{"title": "真实文章标题", "url": "real-article", "category": "x", "date": "2026-01-01"}]
        json.dump(clean, open(os.path.join(tmp, "assets", "js", "article-index.json"), "w"), ensure_ascii=False)
        ok2, det2 = run(tmp)
        assert ok2 is True, "干净索引应 PASS：%s" % det2
        print("check_article_index selftest: PASS")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if _selftest() else 1)
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok, details = run(root)
    for d in details:
        print("  • " + d)
    print("Gate 16 (article index): " + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
