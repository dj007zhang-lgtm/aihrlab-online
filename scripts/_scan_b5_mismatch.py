#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B5 扫描：信源区条目 vs 正文引用错配。
输出每篇「信源区列了但正文 0 次出现」的疑似装饰性条目，以及正文高频机构关键词但未入信源区的疑似遗漏。
"""
import json, glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, 'articles')
IDX = os.path.join(ROOT, 'assets/js/article-index.json')

idx = json.load(open(IDX, encoding='utf-8'))
idx_keys = {os.path.basename(e['url'])[:-5] if e['url'].endswith('.html') else os.path.basename(e['url'])
            for e in idx}

# 已知机构归一化词典（meta 片段 -> 正文候选关键词）
ORG_KEYWORDS = {
    '信通院': ['信通院', '中国信通院', 'caict'],
    '小米': ['小米'],
    'stanford': ['stanford', 'ai index', '斯坦福'],
    'mckinsey': ['mckinsey', '麦肯锡', 'mckinsey & company'],
    'deloitte': ['deloitte', '德勤'],
    'bcg': ['bcg', '波士顿'],
    'gartner': ['gartner', '高德纳'],
    'infoq': ['infoq', '极客邦'],
    'hr partner': ['hr partner'],
    '深圳人协': ['深圳人协', '人力资源管理协会', 'szhrma'],
    '赛迪': ['赛迪'],
    '网商银行': ['网商银行'],
    'okta': ['okta'],
    '微软': ['微软', 'microsoft'],
    'anthropic': ['anthropic'],
    '谷歌': ['谷歌', 'google'],
    'openai': ['openai'],
    'ibm': ['ibm'],
    'harvard': ['哈佛', 'harvard', 'hbr'],
    'mit': ['mit'],
    '世界经济论坛': ['世界经济论坛', 'wef', '达沃斯'],
    '麦肯锡': ['麦肯锡', 'mckinsey'],
}

def extract_sources(html):
    """返回 [(title, meta), ...]"""
    sec = re.search(r'<section class="verified-sources".*?</section>', html, re.S)
    if not sec:
        return []
    items = re.findall(r'<li class="verified-sources__item">(.*?)</li>', sec.group(0), re.S)
    out = []
    for it in items:
        m_t = re.search(r'verified-sources__link"[^>]*>(.*?)</a>', it, re.S)
        m_m = re.search(r'verified-sources__meta">(.*?)</span>', it, re.S)
        title = re.sub(r'<[^>]+>', '', m_t.group(1)).strip() if m_t else ''
        meta = re.sub(r'<[^>]+>', '', m_m.group(1)).strip() if m_m else ''
        out.append((title, meta))
    return out

def body_text(html):
    t = re.sub(r'<script.*?</script>', '', html, flags=re.S)
    t = re.sub(r'<style.*?</style>', '', t, flags=re.S)
    t = re.sub(r'<section class="verified-sources".*?</section>', '', t, flags=re.S)
    t = re.sub(r'<aside class="toc-rail">.*?</aside>', '', t, flags=re.S)
    t = re.sub(r'延伸阅读.*?(?=<footer)', '', t, flags=re.S)
    t = re.sub(r'<footer.*?</footer>', '', t, flags=re.S)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t

def meta_org(meta):
    """从 meta 取机构名（· 前第一段）"""
    part = meta.split('·')[0].strip()
    # 去掉年份
    part = re.sub(r'\s*\d{4}\s*$', '', part)
    return part

# 报告标题特征词（用于判断正文是否以标题/改写方式引用了该信源）
TITLE_TOKENS = {
    '2026年中国企业ai人才与组织发展报告': ['人才与组织', 'ai人才', '中国企业ai', '组织发展报告'],
    'the state of ai in small business hr 2026': ['small business hr', 'hr 2026', 'small business'],
    '智能原生研究报告': ['智能原生'],
    'ai时代人力资源发展报告': ['ai时代人力资源', '人力资源发展报告'],
    '2026 global human capital trends': ['global human capital trends', '人力资本趋势', 'human capital'],
    'the 2026 ai index report': ['ai index', '人工智能指数'],
    'the state of organizations': ['state of organizations', '组织状态'],
}

def candidates_for(org, title=''):
    ol = org.lower()
    for k, kws in ORG_KEYWORDS.items():
        if k in ol:
            return kws
    toks = []
    tl = title.lower()
    for k, kws in TITLE_TOKENS.items():
        if k in tl:
            toks += kws
    if toks:
        return toks
    # 回退：取机构名前 4 字
    return [org[:4]] if org else []

# 入链数据
try:
    frc = json.load(open(os.path.join(ROOT, 'reports/fact_risk_census.json'), encoding='utf-8'))
    inlink_map = {e['file'][:-5]: e.get('inlink', 0) for e in frc}
except Exception:
    inlink_map = {}

results = []
for f in sorted(glob.glob(os.path.join(ART, '*.html'))):
    slug = os.path.basename(f)[:-5]
    if slug == 'index' or slug not in idx_keys:
        continue
    html = open(f, encoding='utf-8').read()
    srcs = extract_sources(html)
    if not srcs:
        continue
    body = body_text(html).lower()
    uncited = []  # (title, meta, org, candidates)
    for title, meta in srcs:
        org = meta_org(meta)
        cands = candidates_for(org, title)
        if not cands:
            cands = [org[:4]] if org else []
        hits = sum(body.count(c.lower()) for c in cands if c)
        if hits == 0:
            uncited.append((title, meta, org, cands))
    if uncited:
        results.append((slug, len(srcs), uncited, inlink_map.get(slug, 0)))

# 按入链降序，只看高曝光（入链>=5）的候选
results.sort(key=lambda x: x[3], reverse=True)
focus = [r for r in results if r[3] >= 5]
print(f"=== B5 疑似装饰性信源（正文 0 命中机构/标题特征词）===\n")
print(f"全站命中 {len(results)} 篇；其中高曝光(入链>=5) {len(focus)} 篇\n")
for slug, nsrc, uncited, inl in focus:
    print(f"● {slug}  (入链={inl}, 信源区{nsrc}条, 疑似装饰{len(uncited)}条)")
    for title, meta, org, cands in uncited:
        print(f"    - 机构={org!r} | 标题={title!r}")
print(f"\n高曝光候选共 {sum(len(u) for _,_,u,_ in focus)} 条疑似装饰性信源")
