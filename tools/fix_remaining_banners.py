# -*- coding: utf-8 -*-
"""
专用修正脚本：处理 v2 仍无法定位的 8 篇（头部结构异类 + 残留错插 banner）。
策略：清除残留 figure → 以「</h1> 之后」为通用锚点重插（所有形态都有 h1，
且 </h1> 必在文章容器内、标题之下，保证渲染位置正确）。
仅处理下列 8 个 slug，不触碰其余 87 篇已正确插入的文章。
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from banner_clusters import SLUG_TO_BANNER

ARTICLES_DIR = os.path.join(ROOT, "articles")
FIG_RE = re.compile(r'<figure class="article-banner">.*?</figure>\s*', re.S)

# 需修正的 8 篇
TARGETS = [
    'AI裁员7飙到40你的公司在做减法还是乘法',
    'ai-hr-landing-3-high-roi-plays',
    'ai-layoff-regret',
    'ai-layoff-to-rebuild-hr-stand-firm',
    'bytedance-7000-interns',
    'idc-2026-hr-ai-agent-guide',
    'mckinsey-6-percent-trust-architecture',
    'ai-hr-org-cluster',
]

BANNER_TPL = '''    <figure class="article-banner">
      <img src="/assets/images/banners/{fname}" alt="{alt} 题图" width="1216" height="832" loading="lazy" decoding="async">
    </figure>'''


def extract_h1(html):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else None


def main():
    for stem in TARGETS:
        f = os.path.join(ARTICLES_DIR, stem + '.html')
        if not os.path.exists(f):
            print(f"  ✗ 文件不存在: {stem}"); continue
        html = open(f, encoding='utf-8').read()
        if stem not in SLUG_TO_BANNER:
            print(f"  ✗ 无映射: {stem}"); continue
        # 1) 清除残留 figure
        cleaned = FIG_RE.sub('', html)
        # 2) 锚点：</h1> 之后
        m = re.search(r'</h1>', cleaned)
        if not m:
            print(f"  ✗ 无 </h1>: {stem}"); continue
        key, fname = SLUG_TO_BANNER[stem]
        title = extract_h1(cleaned) or stem
        figure = BANNER_TPL.format(fname=fname, alt=title)
        new_html = cleaned[:m.end()] + '\n' + figure + cleaned[m.end():]
        # 校验
        if new_html.count('article-banner') != cleaned.count('article-banner') + 1:
            print(f"  ✗ 校验失败: {stem}"); continue
        open(f, 'w', encoding='utf-8').write(new_html)
        body_pos = new_html.find('<body')
        fig_pos = new_html.find('<figure class="article-banner">')
        ok = fig_pos > body_pos
        print(f"  {'✓' if ok else '✗'} {stem}  →  {fname}  (banner在body后: {ok})")


if __name__ == "__main__":
    main()
