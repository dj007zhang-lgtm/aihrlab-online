#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站硬数据「陈旧度 + 跨文一致性」审计（非质量门，主理人发布前主动核验工具）。

背景：Gate 13 只确保「写了硬数字就得挂来源」，无法判断「这个数字是不是过期了」。
2026-08-03 实测踩坑：字节豆包日均 Token 站内长期写「30 万亿」（2025.9 旧数），
而 2026.3 实际已达 120 万亿——挂了来源、过了质量门，但事实已陈旧 10 个月。

本脚本补两个视角：
  A. 陈旧度：文章定位「当前/2026」，但硬数字所在语境只有 ≤2025 的年份锚 → 疑似旧数撑新论。
  B. 跨文一致性：同一实体（关键词组合）在不同文章中出现互斥数值 → 站内自相矛盾。

输出仅为「候选清单」，需人工 WebSearch 复核，不自动改稿、不阻断发布。
"""
import os
import re
import sys
import json
from collections import defaultdict

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(SITE_ROOT, 'articles')

# 硬数字（带单位）
NUM = re.compile(r'([\d][\d,.]*)\s*(万亿|亿|万|%|倍|×)')
YEAR = re.compile(r'(20[1-2][0-9])\s*年?')
# 现时指示词：出现即表示作者在描述"此刻的状态"，用旧数据支撑就是陈旧
NOW_WORD = re.compile(r'当前|如今|目前|现在|今天|截至目前|眼下|已经突破|已突破|最新')
# 明确的历史叙述标记：出现则该句合法引用旧数据
HIST_WORD = re.compile(r'年初|去年|此前|曾经|当年|历史|回顾|彼时|早期|最初|相比|较.{0,6}年|从.{0,6}到')

CUR_YEAR = 2026


def body_text(html):
    b = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    b = re.sub(r'<style[\s\S]*?</style>', ' ', b, flags=re.I)
    m = re.search(r'<article[\s\S]*?</article>', b, re.I | re.S)
    if m:
        b = m.group(0)
    b = re.sub(r'<[^>]+>', ' ', b)
    return re.sub(r'\s+', ' ', b)


def split_sent(text):
    parts = re.split(r'(?<=[。！？；\n])', text)
    return [p.strip() for p in parts if p.strip()]


def is_stub(html):
    return 'http-equiv="refresh"' in html or 'window.location.replace' in html


def audit():
    files = sorted(
        os.path.join(ART_DIR, f) for f in os.listdir(ART_DIR) if f.endswith('.html')
    )
    stale, unanchored = [], []
    # 跨文一致性：key = 规范化实体词, value = [(数值, 单位, 文件, 句子)]
    entity_vals = defaultdict(list)
    # 站内关注的核心实体（高频被引用、易过期）
    ENTITIES = {
        '豆包Token日均': r'(豆包|火山引擎|字节).{0,40}?(Token|token)',
        '微软WTI': r'(微软|WTI|工作趋势指数)',
        'IDC预测': r'IDC',
        'Copilot渗透': r'Copilot',
        'AI岗位替代率': r'(替代率|被替代|岗位.{0,6}(消失|裁撤))',
    }

    scanned = 0
    for path in files:
        fn = os.path.basename(path)
        try:
            html = open(path, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        if is_stub(html):
            continue
        head = html[:html.find('</head>')] if '</head>' in html else html[:8000]
        # 只审「定位当前/2026」的文章
        if '2026' not in head and '2026' not in fn:
            continue
        scanned += 1
        text = body_text(html)
        for sent in split_sent(text):
            nums = NUM.findall(sent)
            if not nums:
                continue
            years = [int(y) for y in YEAR.findall(sent)]
            has_now = bool(NOW_WORD.search(sent))
            has_hist = bool(HIST_WORD.search(sent))

            # A1 陈旧：现时表述 + 硬数字 + 只有旧年份锚 + 非历史对比句
            if years and CUR_YEAR not in years and has_now and not has_hist:
                stale.append({
                    'file': fn, 'year_anchor': sorted(set(years)),
                    'nums': [''.join(n) for n in nums][:4],
                    'sent': sent[:180],
                })
            # A2 无锚：现时表述 + 硬数字 + 完全无年份
            elif not years and has_now:
                unanchored.append({
                    'file': fn,
                    'nums': [''.join(n) for n in nums][:4],
                    'sent': sent[:180],
                })

            # B 跨文一致性
            for ename, pat in ENTITIES.items():
                if re.search(pat, sent):
                    for v, u in nums:
                        entity_vals[ename].append((v + u, fn, sent[:120]))

    return scanned, stale, unanchored, entity_vals


def main():
    scanned, stale, unanchored, entity_vals = audit()
    print(f'=== 全站硬数据陈旧度审计 | 扫描「定位2026」文章 {scanned} 篇 ===\n')

    print(f'【A1 疑似陈旧】现时表述+硬数字，但年份锚只有 ≤2025： {len(stale)} 处')
    for s in stale:
        print(f'  ✗ {s["file"]}')
        print(f'    锚年={s["year_anchor"]} 数字={s["nums"]}')
        print(f'    「{s["sent"]}」')
    print()

    print(f'【A2 时效无锚】现时表述+硬数字，但全句无任何年份： {len(unanchored)} 处')
    bycount = defaultdict(int)
    for u in unanchored:
        bycount[u['file']] += 1
    for f, c in sorted(bycount.items(), key=lambda x: -x[1])[:12]:
        print(f'  · {f}: {c} 处')
    print()

    print('【B 跨文数值一致性】同一实体在站内出现的数值分布：')
    for ename, vals in entity_vals.items():
        uniq = defaultdict(set)
        for v, fn, _ in vals:
            uniq[v].add(fn)
        if len(uniq) <= 1:
            continue
        print(f'  ▸ {ename}（{len(uniq)} 种取值，跨 {len(set(f for _, f, _ in vals))} 文）')
        for v, fns in sorted(uniq.items(), key=lambda x: -len(x[1]))[:8]:
            print(f'      {v:>12}  ← {len(fns)} 文  {sorted(fns)[0]}')
    print()

    out = os.path.join(SITE_ROOT, 'reports', 'data_freshness_audit.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'scanned': scanned, 'stale': stale,
                   'unanchored': unanchored}, f, ensure_ascii=False, indent=1)
    print(f'明细已写入 {os.path.relpath(out, SITE_ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
