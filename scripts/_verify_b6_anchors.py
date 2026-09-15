#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B6 核验：对高入链文章的 R1 数字断言，定位正文窗口，检查是否含机构/时间锚点。
输出每篇每条 R1 的窗口与 has_anchor 判定，供主理人逐条决策。
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, 'articles')
FRC = os.path.join(ROOT, 'reports/fact_risk_census.json')

d = json.load(open(FRC, encoding='utf-8'))
# 锚点关键词（机构/报告/时间）
ANCHORS = ['麦肯锡', 'mckinsey', '德勤', 'deloitte', 'stanford', '斯坦福', '信通院', 'ai index',
           'korn ferry', 'forrester', 'gartner', 'bcg', '波士顿', 'wef', '世界经济论坛',
           '世界经济论坛', 'o*net', 'ilt', 'pwc', '普华永道', '微软', 'microsoft', 'anthropic',
           'openai', '谷歌', 'google', 'ibm', 'harvard', 'mit', 'shrm', 'mercer', '美世',
           'idc', 'okta', '赛迪', '智联', '北大', '清华', '深圳人协', 'infoq', '极客邦',
           '2026', '2025', '2024', '2023', '报告', '研究', '调研', '调研显示', '调查显示',
           '数据', '样本', '据', '显示']

def body_text(html):
    t = re.sub(r'<script.*?</script>', '', html, flags=re.S)
    t = re.sub(r'<style.*?</style>', '', t, flags=re.S)
    t = re.sub(r'<section class="verified-sources".*?</section>', '', t, flags=re.S)
    t = re.sub(r'<aside class="toc-rail">.*?</aside>', '', t, flags=re.S)
    t = re.sub(r'<footer.*?</footer>', '', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t

# 优先：入链>=15 且 R1>=1
prio = [e for e in d if e.get('inlink', 0) >= 15 and len(e['R1']) >= 1]
prio.sort(key=lambda x: x['inlink'] * len(x['R1']), reverse=True)

total_flag = 0
for e in prio:
    f = os.path.join(ART, e['file'])
    if not os.path.exists(f):
        continue
    html = open(f, encoding='utf-8').read()
    body = body_text(html)
    print(f"\n### {e['file']}  (入链={e['inlink']}, R1={len(e['R1'])})")
    for r in e['R1']:
        snippet = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        # 定位片段在正文的位置（取前 20 字做锚）
        key = snippet[:20]
        idx = body.find(key)
        if idx < 0:
            # 尝试更短
            key = snippet[:10]
            idx = body.find(key)
        if idx < 0:
            print(f"   [未定位] {snippet[:40]}…")
            total_flag += 1
            continue
        win = body[max(0, idx-120): idx+len(snippet)+120]
        has = any(a.lower() in win.lower() for a in ANCHORS)
        tag = '✅有锚' if has else '❌缺锚'
        if not has:
            total_flag += 1
        print(f"   {tag} …{win[:160]}…")

print(f"\n=== 高入链优先集({len(prio)}篇) 真缺锚 R1 约 {total_flag} 条 ===")
