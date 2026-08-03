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


# ---------- 报告名/信源真伪候选扫描（盲区补强层） ----------
# 段落级三锚判定只测「有没有标注出处」，测不出「出处是否真实 / 层级是否伪装」。
# 本模块扫描全站《...报告...》类引用，对照 reports/source_registry.json 的
# allow/deny 自动分级，把「需 WebSearch 核验」的候选暴露成可处理 backlog。
# 注：本模块只做「发现 + 分级」，不做真伪判定——真伪由 WebSearch 三问把关。
REPORT_KW = re.compile(
    r'(报告|白皮书|蓝皮书|研究|调研|洞察|年鉴|指数|绿皮书|统计|综述|观察|盘点|分析|图谱|发展报告|年度报告)')
BOOK = re.compile(r'《([^《》]{2,40}?)》')
PUB_KW = re.compile(
    r'(麦肯锡|McKinsey|BCG|波士顿|IDC|Gartner|德勤|Deloitte|普华永道|PwC|埃森哲|Accenture|'
    r'信通院|中国信通院|工信部|人社部|国家统计局|华为|腾讯|腾讯研究院|阿里|百度|字节|火山引擎|'
    r'微软|Microsoft|谷歌|Google|OpenAI|清华大学|北大|北京大学|智联|BOSS直聘|猎聘|'
    r'InfoQ|极客邦|深圳市人力资源管理协会|深圳人协|世界经济论坛|WEF|OECD|ILO|SHRM|'
    r'Forrester|尼尔森|凯度|艾瑞|易观|QuestMobile|摩根|高盛|中金|中国经营报|科技日报|'
    r'哈佛|MIT|斯坦福|Stanford|普林斯顿|Princeton|jimo\.studio|深蓝君)')


def _norm(s):
    return re.sub(r'[\s《》（）()·\-—–&./]', '', s).lower()


def load_registry():
    path = 'reports/source_registry.json'
    if not os.path.exists(path):
        return {'allow': [], 'deny': [], 'deny_publisher': []}
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return {'allow': [], 'deny': [], 'deny_publisher': []}


def report_source_census():
    """扫描全站《...报告...》类引用，对照 registry 分级：已核验(白)/黑名单(已清)/待核验。"""
    from collections import Counter, defaultdict
    reg = load_registry()
    allow_t = [_norm(x['title']) for x in reg.get('allow', [])]
    deny_tn = [(_norm(x.get('title', '')), x.get('reason', '')) for x in reg.get('deny', [])]
    deny_p = [p.lower() for p in reg.get('deny_publisher', [])]

    files = sorted(glob.glob('articles/*.html'))
    cands = []
    for p in files:
        raw = open(p, encoding='utf-8', errors='ignore').read()
        base = os.path.basename(p)
        for m in BOOK.finditer(raw):
            title = m.group(1).strip()
            if not REPORT_KW.search(title):
                continue
            start = m.start()
            before = raw[max(0, start - 40):start]
            pub_m = PUB_KW.search(before)
            publisher = pub_m.group(1) if pub_m else ''
            ln = raw.count('\n', 0, start) + 1
            nt, npub = _norm(title), _norm(publisher)
            status, hit = '待核验', ''
            for dtn, dr in deny_tn:
                if dtn and (dtn in nt or nt in dtn):
                    status, hit = '黑名单(已清)', dr
                    break
            if status == '待核验':
                for dp in deny_p:
                    if dp and (dp in npub or dp in nt):
                        status, hit = '黑名单(已清)', '归因错误/虚构出版方'
                        break
            if status == '待核验':
                for at in allow_t:
                    if at and (at in nt or nt in at):
                        status, hit = '已核验(白)', 'registry.allow'
                        break
            cands.append({'file': base, 'line': ln, 'title': title,
                          'publisher': publisher, 'status': status, 'note': hit})

    cnt = Counter(c['status'] for c in cands)
    groups = defaultdict(list)
    for c in cands:
        groups[c['status']].append(c)

    print("\n" + "=" * 74)
    print(f"报告名/信源真伪候选扫描 · {len(files)} 篇 · 命中 {len(cands)} 处")
    print("=" * 74)
    print(f"  已核验(白)   {cnt.get('已核验(白)',0):>5} 处  [registry.allow 已知真报告]")
    print(f"  黑名单(已清) {cnt.get('黑名单(已清)',0):>5} 处  [registry.deny 命中，须不再引用]")
    print(f"  待核验       {cnt.get('待核验',0):>5} 处  [需 WebSearch 三问核验]")

    print(f"\n【待核验 TOP 40】（WebSearch 核验队列）")
    for c in groups.get('待核验', [])[:40]:
        pub = f" [{c['publisher']}]" if c['publisher'] else ''
        print(f"  {c['file'][:38]:38} L{c['line']:<4} 《{c['title'][:18]}》{pub}")

    os.makedirs('reports', exist_ok=True)
    json.dump(cands, open('reports/report_source_census.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print("\n候选明细已写入 reports/report_source_census.json")
    return cands


if __name__ == '__main__':
    lv = None
    only_reports = '--reports-only' in sys.argv
    if '--list' in sys.argv:
        i = sys.argv.index('--list')
        lv = sys.argv[i + 1] if len(sys.argv) > i + 1 else 'R1'
    if only_reports:
        report_source_census()
    else:
        census(lv)
        report_source_census()
