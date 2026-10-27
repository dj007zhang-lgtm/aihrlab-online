#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_cluster_map.py — 构建簇归属单一真相源 ci/cluster-map.json

存在理由（E-023）：枢纽归属此前散在三处且互不校验——
  ① 文章页里的「本文收录于」块（close_all_clusters.py 关键词匹配写入）
  ② 枢纽页 hand-written 的 hub-links 列表（手工复制维护）
  ③ build_next_path.py 读取时的「两者并集」
三者不一致时，并集策略会静默掩盖矛盾：枢纽页列了 A 而 A 不认自己在这个枢纽里，
反之亦然。实测 260 篇里 172 篇有自声明归属，枢纽页名单与自声明名单的差集达数十篇。
本脚本把归属关进一个数据文件，两侧都从它派生。

纪律：
  - 键集合硬校验：判定表的键必须恒等于真实孤儿集合。多一个键＝虚构条目，
    少一个键＝有人漏判。任一情况都退出 2，不允许带着缺口生成。
  - 跳转壳（noindex + meta refresh）永不进入归属表，且不计入孤儿——
    它们是刻意存在的 URL 合并壳，按铁律绝不下线也不归位。
"""
import os
import re
import sys
import json
import subprocess

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip() or \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "articles")
ASSIGN = os.path.join(ROOT, "ci", "cluster-assignments.json")
OUT = os.path.join(ROOT, "ci", "cluster-map.json")

REFRESH_RE = re.compile(r'<meta[^>]+http-equiv="refresh"', re.I)
NOINDEX_RE = re.compile(r'<meta[^>]+name="robots"[^>]*noindex', re.I)
DECL_RE = re.compile(r'本文收录于.{0,400}?href="/hub/([^"]+?)\.html"', re.S)


def is_stub(html):
    return bool(REFRESH_RE.search(html) and NOINDEX_RE.search(html))


def scan():
    """返回 (已有归属映射, 孤儿集合, 跳转壳数)。"""
    inherited, orphans, stubs = {}, set(), 0
    for f in sorted(os.listdir(ART)):
        if not f.endswith(".html") or f == "index.html":
            continue
        html = open(os.path.join(ART, f), encoding="utf-8", errors="ignore").read()
        if is_stub(html):
            stubs += 1
            continue
        slug = f[:-5]
        m = DECL_RE.search(html)
        if m:
            inherited[slug] = m.group(1)
        else:
            orphans.add(slug)
    return inherited, orphans, stubs


def main():
    data = json.load(open(ASSIGN, encoding="utf-8"))
    assignments = data["assignments"]

    inherited, orphans, stubs = scan()
    keys = set(assignments)

    missing = orphans - keys          # 真实孤儿但没判定 → 漏判
    extra = keys - orphans            # 判定了但不是孤儿 → 虚构或已被归位

    print("=== 簇归属映射构建 ===")
    print(f"  非桩页文章        : {len(inherited) + len(orphans)}")
    print(f"  跳转壳（永不归位）: {stubs}")
    print(f"  已有历史归属      : {len(inherited)}")
    print(f"  本轮判定孤儿      : {len(orphans)}")

    if missing or extra:
        print("\n❌ 键集合校验失败 —— 判定表与站点现状不符：")
        for k in sorted(missing):
            print(f"     漏判（站点有孤儿，判定表没有）: {k}")
        for k in sorted(extra):
            print(f"     多余（判定表有，站点非孤儿）  : {k}")
        print("\n不允许带着缺口生成 cluster-map。请补齐后重跑。")
        sys.exit(2)

    print("  ✅ 键集合与孤儿集合完全一致")

    # 合并
    members = {}
    for slug, hub in inherited.items():
        members[slug] = {"hub": hub, "source": "inherited"}
    for slug, (hub, why) in assignments.items():
        members[slug] = {"hub": hub, "source": "curated", "why": why}

    # 统计
    from collections import Counter
    c = Counter(v["hub"] for v in members.values())
    print("\n=== 归位后各枢纽规模 ===")
    for hub, n in c.most_common():
        print(f"  {str(hub):<34} {n:>3}")

    if "--apply" in sys.argv:
        payload = {
            "_doc": "簇归属单一真相源。由 scripts/build_cluster_map.py 从 ci/cluster-assignments.json + 站内现状生成，勿手改。",
            "_generated_by": "scripts/build_cluster_map.py",
            "hubs": sorted({h for h in c if h}),
            "members": members,
        }
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        print(f"\n✅ 已写入 {os.path.relpath(OUT, ROOT)}（{len(members)} 条）")
    else:
        print("\n[dry-run] 未写入。加 --apply 生成。")


if __name__ == "__main__":
    main()
