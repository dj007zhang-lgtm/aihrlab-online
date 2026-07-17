# -*- coding: utf-8 -*-
"""
幂等 banner 插入引擎 v2（修复定位 bug）：
- 锚点：<header class="article-header"> 自身的 </header> 之后（文章头与正文之间）
- 之前 v1 误匹配了站点顶部导航的 </header>（位于 <body> 之前），已修复
- 先清理任何错位的 figure，再按正确锚点插入
- alt：取该文 <h1> 标题 + " 题图"
- 幂等：已含「正确位置」banner 则跳过；可重复运行
- 排除：重定向桩页、文章库列表页 index、3 篇试点
"""
import os, re, glob, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from banner_clusters import SLUG_TO_BANNER, EXCLUDE_STUBS, EXCLUDE_LISTING, PILOT

BANNER_TPL = '''    <figure class="article-banner">
      <img src="/assets/images/banners/{fname}" alt="{alt} 题图" width="1216" height="832" loading="lazy" decoding="async">
    </figure>'''

ARTICLES_DIR = os.path.join(ROOT, "articles")
FIG_RE = re.compile(r'<figure class="article-banner">.*?</figure>\s*', re.S)
HEADER_RE = re.compile(r'(<header class="article-header">.*?</header>)', re.S)


def extract_h1(html):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else None


def process():
    files = sorted(glob.glob(os.path.join(ARTICLES_DIR, "*.html")))
    inserted, skipped_have, skipped_stub, skipped_index, skipped_pilot, skipped_nomap, skipped_noheader = (
        [], [], [], [], [], [], [])
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        html = open(f, encoding='utf-8').read()

        if 'http-equiv="refresh"' in html:
            skipped_stub.append(stem); continue
        if stem in EXCLUDE_LISTING:
            skipped_index.append(stem); continue
        if stem in PILOT:
            skipped_pilot.append(stem); continue
        if stem not in SLUG_TO_BANNER:
            skipped_nomap.append(stem); continue

        # 判断是否已有「正确位置」的 banner（在 <body> 之后）
        has_fig = '<figure class="article-banner">' in html
        if has_fig:
            body_pos = html.find('<body')
            fig_pos = html.find('<figure class="article-banner">')
            if body_pos != -1 and fig_pos > body_pos:
                skipped_have.append(stem); continue  # 已正确插入，跳过
        # 否则：清理任何错位的 figure，准备重插
        cleaned = FIG_RE.sub('', html)

        m = HEADER_RE.search(cleaned)
        if not m:
            skipped_noheader.append(stem); continue

        key, fname = SLUG_TO_BANNER[stem]
        title = extract_h1(cleaned) or stem
        figure = BANNER_TPL.format(fname=fname, alt=title)
        new_html = HEADER_RE.sub(r'\1\n' + figure, cleaned, count=1)

        # 校验
        if new_html.count('article-banner') != cleaned.count('article-banner') + 1:
            print(f"  ✗ 校验失败跳过: {stem}"); continue
        open(f, 'w', encoding='utf-8').write(new_html)
        inserted.append((stem, key, fname))

    print(f"✓ 已插入(或修正): {len(inserted)} 篇")
    print(f"  跳过-已有正确banner: {len(skipped_have)}")
    print(f"  跳过-重定向桩页: {len(skipped_stub)}")
    print(f"  跳过-列表页: {len(skipped_index)}")
    print(f"  跳过-试点: {len(skipped_pilot)}")
    print(f"  跳过-无映射: {len(skipped_nomap)}")
    print(f"  跳过-无article-header: {len(skipped_noheader)}")
    if skipped_nomap: print("  ⚠ 无映射:", skipped_nomap)
    if skipped_noheader: print("  ⚠ 无article-header:", skipped_noheader)
    from collections import Counter
    c = Counter(k for _, k, _ in inserted)
    print("\n各簇分布:")
    for k, n in sorted(c.items()):
        print(f"  {k}: {n}")


if __name__ == "__main__":
    process()
