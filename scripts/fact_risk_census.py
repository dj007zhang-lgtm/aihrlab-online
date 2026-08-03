#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站事实风险普查（段落级）

分级（锚点在「所在块 + 其上文最近标题」范围内判定，避免把小标题误判为无源）：
  R1 高危 = 数值断言 且 无时间锚 且 无出处锚   → 写错了也无从追溯，必须人工核验
  R2 中危 = 数值断言 且 缺其一
  R3 低危 = 数值断言 且 两锚俱全

噪音过滤：序号/章节号、比例式表述（1/3）、ROI 测算等自算数字、纯排版数字。

用法：
  python3 scripts/fact_risk_census.py            # 普查
  python3 scripts/fact_risk_census.py --list R1  # 打印全部 R1 明细
"""
import re, os, glob, json, math, sys

# ---------- 断言识别 ----------
NUM = re.compile(r'(?<![\w.])(\d[\d,]*\.?\d*)\s*(万亿|千亿|亿|万|%|％|倍|个百分点|人|名|美元|元|pp)')
# 时间锚
TIME = re.compile(r'(20[12]\d\s*年|20[12]\d[-/.]\d|[一二三四五六七八九十]{1,2}月|Q[1-4]|上半年|下半年|年初|年底|年中|截至|自\s*20[12]\d|财年|季度)')
# 出处锚
SRC = re.compile(
    r'(据|来源|依据|引自|披露|公布|发布的|报告显示|调研显示|数据显示|统计显示|白皮书|研报|财报|年报|招股书|'
    r'麦肯锡|McKinsey|IDC|Gartner|德勤|Deloitte|普华永道|PwC|埃森哲|Accenture|波士顿|BCG|SHRM|LinkedIn|领英|'
    r'微软|Microsoft|谷歌|Google|OpenAI|Anthropic|Meta|Amazon|亚马逊|甲骨文|Oracle|戴尔|Dell|IBM|Salesforce|'
    r'字节|抖音|火山引擎|腾讯|阿里|百度|华为|京东|美团|小米|网易|拼多多|快手|'
    r'世界经济论坛|WEF|ILO|国际劳工|OECD|世界银行|国家统计局|人社部|工信部|智联|BOSS直聘|猎聘|脉脉|前程无忧|'
    r'第一财经|晚点|36氪|界面新闻|财新|证券时报|每日经济|中国经营报|科技日报|新京报|21世纪|虎嗅|钛媒体|'
    r'QuestMobile|艾瑞|易观|野村|高盛|摩根|中金|招银|Challenger|Layoffs\.fyi|Indeed|Glassdoor|'
    r'研究|论文|期刊|Nature|Science|Harvard|哈佛|MIT|斯坦福|Stanford|普林斯顿|Princeton)')

# 噪音：章节序号、比例式、内部测算
NOISE = re.compile(r'^\s*(0?\d|[一二三四五六七八九十]+)\s*[.、．]|^\s*\d+\.\d+\s|^#{1,4}\s')
NOISE_UNIT = re.compile(r'(1\s*/\s*\d|第\s*\d+\s*(章|节|步|层|类|个)|Top\s*\d+|TOP\s*\d+|前\s*\d+\s*(名|位|大))')

BLOCK = re.compile(r'<(p|li|h[1-6]|td|blockquote|figcaption)\b[^>]*>(.*?)</\1>', re.S | re.I)
HEAD = re.compile(r'^h[1-6]$', re.I)


def article_body(html):
    m = re.search(r'<article\b[^>]*>(.*?)</article>', html, re.S | re.I)
    return m.group(1) if m else html


def strip_tags(s):
    s = re.sub(r'<(script|style)\b.*?</\1>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def has_ext_link(chunk):
    for m in re.finditer(r'href="(https?://[^"]+)"', chunk):
        u = m.group(1)
        if not any(d in u for d in ('aihrlab.online', 'googletagmanager', 'hm.baidu', 'bing.com')):
            return True
    return False


def sentences(t):
    return [x.strip() for x in re.split(r'(?<=[。！？；])|\n', t) if x and x.strip()]


def census(list_level=None):
    files = sorted(glob.glob('articles/*.html'))
    # 入链统计
    inlink = {}
    all_html = {}
    for p in files:
        all_html[p] = open(p, encoding='utf-8', errors='ignore').read()
    for p in files:
        slug = os.path.basename(p)
        inlink[slug] = sum(1 for q in files if q != p and slug in all_html[q])

    rows = []
    tot = {'R1': 0, 'R2': 0, 'R3': 0, 'noise': 0}
    for p in files:
        body = article_body(all_html[p])
        rec = {'file': os.path.basename(p), 'R1': [], 'R2': [], 'R3': 0,
               'inlink': inlink[os.path.basename(p)]}
        cur_head = ''
        for m in BLOCK.finditer(body):
            tag, raw = m.group(1).lower(), m.group(2)
            txt = strip_tags(raw)
            if not txt:
                continue
            if HEAD.match(tag):
                cur_head = txt
                continue  # 标题本身不作断言判定，只作上文锚
            # 块级锚点范围 = 本块 + 最近上文标题
            scope = cur_head + ' ' + txt
            ext = has_ext_link(raw)
            for s in sentences(txt):
                if not NUM.search(s):
                    continue
                if NOISE.match(s) or NOISE_UNIT.search(s):
                    tot['noise'] += 1
                    continue
                t_ok = bool(TIME.search(scope))
                s_ok = bool(SRC.search(scope)) or ext
                if t_ok and s_ok:
                    rec['R3'] += 1; tot['R3'] += 1
                elif t_ok or s_ok:
                    rec['R2'].append(s[:120]); tot['R2'] += 1
                else:
                    rec['R1'].append(s[:120]); tot['R1'] += 1
        rows.append(rec)

    n = max(1, tot['R1'] + tot['R2'] + tot['R3'])
    print("=" * 74)
    print(f"全站事实风险普查（段落级锚点） · {len(files)} 篇")
    print("=" * 74)
    print(f"  数值断言总量（去噪后）        {n:>5} 条   [噪音过滤 {tot['noise']} 条]")
    print(f"  R3 低危（时间锚+出处锚俱全）  {tot['R3']:>5} 条  {tot['R3']/n*100:5.1f}%")
    print(f"  R2 中危（缺其一）             {tot['R2']:>5} 条  {tot['R2']/n*100:5.1f}%")
    print(f"  R1 高危（两锚全无）           {tot['R1']:>5} 条  {tot['R1']/n*100:5.1f}%")

    for r in rows:
        r['score'] = len(r['R1']) * math.log(r['inlink'] + 2) + len(r['R2']) * 0.15
    rows.sort(key=lambda x: -x['score'])

    print(f"\n【处置优先级 TOP 15】（R1 数 × 入链权重）")
    print(f"  {'文章':46} {'入链':>4} {'R1':>4} {'R2':>4} {'R3':>4}")
    for r in rows[:15]:
        if r['score'] <= 0:
            break
        print(f"  {r['file'][:45]:46} {r['inlink']:>4} {len(r['R1']):>4} {len(r['R2']):>4} {r['R3']:>4}")

    clean = sum(1 for r in rows if not r['R1'] and not r['R2'])
    print(f"\n【文章级】完全无风险断言（R1=0 且 R2=0）：{clean} / {len(files)} 篇")
    print(f"          含 R1 高危断言：{sum(1 for r in rows if r['R1'])} 篇")

    if list_level:
        print(f"\n===== {list_level} 明细 =====")
        for r in rows:
            items = r.get(list_level) or []
            if isinstance(items, int) or not items:
                continue
            print(f"\n## {r['file']}  (入链{r['inlink']})")
            for s in items:
                print(f"   · {s}")

    os.makedirs('reports', exist_ok=True)
    json.dump(rows, open('reports/fact_risk_census.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print("\n明细已写入 reports/fact_risk_census.json")
    return rows


if __name__ == '__main__':
    lv = None
    if '--list' in sys.argv:
        i = sys.argv.index('--list')
        lv = sys.argv[i + 1] if len(sys.argv) > i + 1 else 'R1'
    census(lv)
