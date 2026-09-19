# -*- coding: utf-8 -*-
"""
gate_clone_detection —— 规模化模板内容（scaled content abuse）跨篇克隆检测

为什么必须有这个门（错不二犯根因）：
  2026-09 全站体检才发现 25 篇文章共用同一套正文（14 个段落原文相同），
  属搜索引擎明确打击的 scaled content abuse，连累整个域名评分。
  该算法此前只在一次性整改脚本里硬编码 24 个 URL，从未固化为常驻门。
  本门把它变成永久、自动、每次发布+每周跑的检测，新克隆集群当天即被拦下。

算法：倒排索引（O(段落总数) 而非 O(n²)）
  1) 每篇正文抽段落哈希集合（剔除 CTA/回链/延伸阅读注入块，过短段过滤）。
  2) 倒排：paragraph_hash -> 含它的文章下标集合。
  3) 仅对出现 >=2 次的段落，把共现文章两两连边（权=共享段落数）。
  4) 连通分量成簇；簇内共享段落数 >= min_shared_paragraphs 且簇大小 >= min_cluster_size
     → 判定为规模化克隆（BLOCK）。
"""
import os
import time
from collections import defaultdict
from . import (walk_html, read, is_stub_html, is_indexable, extract_paragraphs,
               rel, GateReport, Finding)


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    p = cfg.get("params", {})
    scan_dirs = p.get("scan_dirs", ["articles"])
    min_cjk = p.get("min_para_cjk", 20)
    min_shared = p.get("min_shared_paragraphs", 8)
    min_cluster = p.get("min_cluster_size", 3)

    files = [f for f in walk_html(site_root, scan_dirs) if is_indexable(read(f))]
    # 抽指纹
    hashes_per_file = []
    valid = []
    for f in files:
        h = extract_paragraphs(read(f), min_cjk=min_cjk)
        if h:
            hashes_per_file.append(h)
            valid.append(f)

    # 倒排索引
    inv = defaultdict(list)
    for i, hs in enumerate(hashes_per_file):
        for h in hs:
            inv[h].append(i)

    # 共现连边
    adj = defaultdict(int)
    for h, ids in inv.items():
        if len(ids) < 2:
            continue
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                adj[(ids[a], ids[b])] += 1

    # 连通分量
    parent = list(range(len(valid)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for (a, b), w in adj.items():
        if w >= 2:  # 至少共享 2 段才连边，降低噪声
            union(a, b)

    comps = defaultdict(list)
    for i in range(len(valid)):
        comps[find(i)].append(i)

    rep = GateReport("clone_detection", "跨篇克隆集群检测（scaled content abuse）")
    rep.metrics = {
        "scanned_indexable": len(valid),
        "clone_clusters": 0,
        "clone_pages": 0,
        "min_shared_paragraphs": min_shared,
        "min_cluster_size": min_cluster,
    }

    for root, members in comps.items():
        if len(members) < min_cluster:
            continue
        # 簇内共享段落数 = 簇内两两共享的最小值近似：取边权中位数偏保守，
        # 这里用「公共段落哈希数」= 各成员哈希交集
        common = set(hashes_per_file[members[0]])
        for m in members[1:]:
            common &= hashes_per_file[m]
        shared = len(common)
        if shared < min_shared:
            continue
        cluster_files = [rel(site_root, valid[m]) for m in members]
        rep.add(Finding(
            "BLOCK", "CLONE-CLUSTER",
            detail=f"共享 {shared} 段 / {len(members)} 篇克隆: " + ", ".join(cluster_files[:8])
                    + (" …" if len(cluster_files) > 8 else ""),
        ))
        rep.metrics["clone_clusters"] += 1
        rep.metrics["clone_pages"] += len(members)

    if rep.findings:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = f"发现 {rep.metrics['clone_clusters']} 个规模化克隆集群（{rep.metrics['clone_pages']} 篇），须合并下线。"
    else:
        rep.status = "PASS"
        rep.summary = f"扫描 {len(valid)} 篇可索引正文，无规模化克隆集群。"
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
