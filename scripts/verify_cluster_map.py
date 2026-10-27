#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_cluster_map.py — 簇归属闭环校验

存在的理由（E-023/024/025）：簇归属此前散在三处、互不校验，任何一个
环节出错都没有工具会报警。实测后果：
  - 260 篇里 88 篇从来没有归属（孤儿）
  - 枢纽页与文章声明双向不一致：错链 87 条、缺链 149 条
  - 两个枢纽页 100% 克隆（performance 是 ai-org-transformation 的整页复制，
    连 spoke 链接文字都改了，违反 Gate10）
内链闭环是主题权威能否累积的前提。这个校验器是让闭环可验证的唯一手段。

检查项：
  V1 归属唯一且存在：非桩页文章必须恰好有一条归属声明，
     或明确登记为「刻意不归枢纽」（cluster-map 中 hub=null）。
  V2 枢纽页存在：声明指向的 /hub/x.html 必须真实存在，防 404。
  V3 声明与真相源一致：文章页写的不许与 cluster-map 相左。
  V4 枢纽页 spoke 双向一致：页内列出的 == cluster-map 成员，
     错链（列了不该列的）与缺链（该列的没列）分别计数。
  V5 Gate10：spoke 链接文字必须逐字等于目标文章 H1。
  V6 枢纽清单一致：cluster-map 里的枢纽都必须有对应页面。

退出码：0 全过 / 1 仅警告 / 2 存在 BLOCK。
"""
import os
import re
import sys
import json
import subprocess

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip() or \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "ci", "cluster-map.json")
ART = os.path.join(ROOT, "articles")
HUBDIR = os.path.join(ROOT, "hub")

REFRESH_RE = re.compile(r'http-equiv="refresh"')
NOINDEX_RE = re.compile(r'name="robots"[^>]*noindex')
DECL_RE = re.compile(r'本文收录于.{0,400}?href="/hub/([^"]+?)\.html"', re.S)
SPOKE_RE = re.compile(r'href="/articles/([a-z0-9\-]+)\.html">(.*?)</a>')
# Gate10 只约束 spoke 列表项（<li><a>…</a></li>）。
# 正文 <p> 里带书名号的叙述性引用（「…《某篇》讲到…」）是刻意措辞，不在此列，
# 把它算进违例会淹没有效信号——实测正文引用 49 处 vs 真实 spoke 违例 44 处。
SPOKE_LI_RE = re.compile(r'<li><a href="/articles/([a-z0-9\-]+)\.html">(.*?)</a></li>')


def is_stub(html):
    return bool(REFRESH_RE.search(html) and NOINDEX_RE.search(html))


def h1_of(slug):
    p = os.path.join(ART, slug + ".html")
    if not os.path.exists(p):
        return None
    h = open(p, encoding="utf-8", errors="ignore").read()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else None


def main():
    cmap = json.load(open(MAP, encoding="utf-8"))
    members = cmap["members"]
    hubs = set(cmap["hubs"])

    blocks, warns = [], []
    link_wrong = link_missing = 0

    # ---------- V1/V2/V3：文章侧
    orphan, notdeclared, mismatch, missing_page = [], [], [], []
    for f in sorted(os.listdir(ART)):
        if not f.endswith(".html") or f == "index.html":
            continue
        slug = f[:-5]
        html = open(os.path.join(ART, f), encoding="utf-8", errors="ignore").read()
        if is_stub(html):
            continue
        entry = members.get(slug)
        if entry is None:
            notdeclared.append(slug)          # 文章不在真相源里
            continue
        want = entry["hub"]
        m = DECL_RE.search(html)
        got = m.group(1) if m else None
        if want is None:
            if got is not None:
                mismatch.append((slug, got, "刻意不归枢纽，却有声明"))
            continue
        if got is None:
            orphan.append(slug)
        elif got != want:
            mismatch.append((slug, got, want))
        if want and not os.path.exists(os.path.join(HUBDIR, want + ".html")):
            missing_page.append((slug, want))

    # ---------- V4/V5：枢纽侧
    ten_violations = []
    hub_missing_page = [h for h in hubs if not os.path.exists(
        os.path.join(HUBDIR, h + ".html"))]
    for hub in sorted(hubs):
        p = os.path.join(HUBDIR, hub + ".html")
        if not os.path.exists(p):
            continue
        h = open(p, encoding="utf-8").read()
        # 必须保留全部匹配，不能转成 dict：同一篇文章在一页里可能既出现在
        # spoke 列表又出现在正文引用，dict 会让后者静默覆盖前者，
        # 掩盖真实违例（实测把 44 处报成 2 处）。
        all_spoke = [(s, t) for s, t in SPOKE_RE.findall(h) if s != "index"]
        have = {s for s, _ in all_spoke}
        exp = {k for k, v in members.items() if v["hub"] == hub}
        wrong = sorted(have - exp)
        miss = sorted(exp - have)
        link_wrong += len(wrong)
        link_missing += len(miss)
        if wrong or miss:
            warns.append("V4 %s：错链 %d / 缺链 %d" % (hub, len(wrong), len(miss)))
        for slug, txt in SPOKE_LI_RE.findall(h):
            if slug == "index":
                continue
            real = h1_of(slug)
            if real is None:
                ten_violations.append((hub, slug, "目标页缺失"))
            elif txt != real:
                ten_violations.append((hub, slug, "文字≠H1"))

    # ---------- 判定
    if notdeclared:
        blocks.append("V1 文章不在 cluster-map 中（%d 篇）: %s"
                      % (len(notdeclared), ", ".join(notdeclared[:5])))
    if orphan:
        blocks.append("V1 有枢纽归属却无归属声明（%d 篇）: %s"
                      % (len(orphan), ", ".join(orphan[:5])))
    if mismatch:
        blocks.append("V3 声明与真相源冲突（%d 篇）: %s"
                      % (len(mismatch), "; ".join("%s:%s→%s" % m for m in mismatch[:5])))
    if missing_page:
        blocks.append("V2 声明指向不存在的枢纽页（%d 处）: %s"
                      % (len(missing_page), ", ".join("%s→%s" % m for m in missing_page[:5])))
    if hub_missing_page:
        blocks.append("V6 cluster-map 的枢纽缺页面: %s" % ", ".join(hub_missing_page))
    if ten_violations:
        blocks.append("V5 Gate10 链接文字≠目标 H1（%d 处）: %s"
                      % (len(ten_violations),
                         "; ".join("%s/%s" % (h, s) for h, s, _ in ten_violations[:5])))

    print("=" * 74)
    print("簇归属闭环校验")
    print("=" * 74)
    print(f"  真相源成员            : {len(members)}")
    print(f"  枢纽                  : {len(hubs)}")
    print(f"  V4 枢纽页错链         : {link_wrong}")
    print(f"  V4 枢纽页缺链         : {link_missing}")
    print(f"  V5 Gate10 违例        : {len(ten_violations)}")
    print()

    for w in warns:
        print("  ⚠️  " + w)
    if warns:
        print()

    if blocks:
        for b in blocks:
            print("  ❌ " + b)
        print("\n结果: BLOCK（%d 项）" % len(blocks))
        sys.exit(2)

    if warns:
        print("结果: WARN（%d 项）—— 内链闭环尚未完成" % len(warns))
        sys.exit(1)

    print("  ✅ 内链双向闭环，无违例")
    sys.exit(0)


if __name__ == "__main__":
    main()
