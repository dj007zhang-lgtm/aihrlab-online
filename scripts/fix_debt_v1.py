#!/usr/bin/env python3
"""
全站债务修复 v1 — 一次性修复 full_debt_audit.py 发现的真实债务
  1. 13 篇缺百度统计 → 在 </head> 前插入
  2. 1 篇缺 Bing 验证 meta → 在 <head> 内插入
  3. 3 篇缺 GEO short-answer → 从正文首段提取
  4. 8 篇缺 .inline-related → 在正文末尾（article-footer-qr 前）插入
"""

import os, re, sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(SITE_ROOT, 'articles')

# ========== 模板 ==========
BAIDU_SCRIPT = '''<script> var _hmt = _hmt || []; (function() { var hm = document.createElement("script"); hm.src = "https://hm.baidu.com/hm.js?b53ffd054b55836f535892622f1e4cc5"; var s = document.getElementsByTagName("script")[0]; s.parentNode.insertBefore(hm, s); })(); </script>'''

BING_META = '<meta name="msvalidate.01" content="EFE6B970983C4C6F951613B6E14571A0" />'


def get_articles():
    """获取所有文章 HTML"""
    skip_f = {'index', 'seo-monitor', 'prototype', 'bridge', 'hub', 'tools', 'about', '404'}
    articles = []
    for f in sorted(os.listdir(ARTICLES_DIR)):
        if not f.endswith('.html') or f in skip_f:
            continue
        fpath = os.path.join(ARTICLES_DIR, f)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, 'r', encoding='utf-8') as fh:
            head = fh.read(2000)
        # 跳过桩页
        if 'window.location.replace' in head or 'http-equiv="refresh"' in head:
            continue
        articles.append(fpath)
    return articles


# ========== Fix 1: 百度统计 ==========
def fix_baidu_missing(articles):
    print('\n=== Fix 1: 补入百度统计脚本 ===')
    pat = re.compile(r'b53ffd054b55836f535892622f1e4cc5')
    fixed = 0
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if pat.search(content):
            continue
        # 在 </head> 前插入
        if '</head>' in content:
            content = content.replace('</head>', BAIDU_SCRIPT + '\n</head>')
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed += 1
            print(f'  + {os.path.basename(fpath)}')
        else:
            print(f'  WARN: no </head> in {os.path.basename(fpath)}')
    print(f'  修复: {fixed} 篇')
    return fixed


# ========== Fix 2: Bing 统计 ==========
def fix_bing_missing(articles):
    print('\n=== Fix 2: 补入 Bing 验证 meta ===')
    pat = re.compile(r'EFE6B970983C4C6F951613B6E14571A0')
    fixed = 0
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if pat.search(content):
            continue
        # 在 <meta charset 或 <head> 后插入
        # 找到第一个 <meta 后插入（在 charset 之后）
        if '<meta charset' in content:
            # 找到第一个 <meta 标签结束后插入
            match = re.search(r'<meta[^>]+>', content)
            if match:
                pos = match.end()
                content = content[:pos] + '\n' + BING_META + content[pos:]
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed += 1
                print(f'  + {os.path.basename(fpath)}')
        else:
            print(f'  WARN: no <meta in {os.path.basename(fpath)}')
    print(f'  修复: {fixed} 篇')
    return fixed


# ========== Fix 3: GEO short-answer ==========
def fix_geo_short_answer(articles):
    """从正文首段提取 short-answer，补入 <head>"""
    print('\n=== Fix 3: 补入 GEO short-answer ===')
    sa_pat = re.compile(r'name=["\']short-answer["\']', re.I)
    fixed = 0

    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        if sa_pat.search(content):
            continue

        # 提取首段（</h1> 后的第一个 <p> 内容）
        h1_end = content.find('</h1>')
        if h1_end == -1:
            continue
        after_h1 = content[h1_end+6:h1_end+2000]

        p_match = re.search(r'<p[^>]*>([^<]+)</p>', after_h1)
        if not p_match:
            continue

        text = p_match.group(1).strip()
        # 过滤导读句
        if len(text) < 15 or any(k in text for k in ['读完本文你将获得', '点击查看', '扫码关注', '欢迎关注']):
            continue

        # 截断至合理长度
        if len(text) > 150:
            text = text[:147] + '...'

        meta_tag = f'\n<meta name="short-answer" content="{text}" />'

        # 在现有 GEO meta 附近插入（answer-for 之后）
        af_match = re.search(r'name=["\']answer-for["\'][^/]*/>', content)
        if af_match:
            pos = af_match.end()
            content = content[:pos] + '\n' + meta_tag + content[pos:]
        else:
            # 放在 </head> 前
            content = content.replace('</head>', meta_tag + '\n</head>')

        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        fixed += 1
        print(f'  + {os.path.basename(fpath)}: "{text[:60]}..."')

    print(f'  修复: {fixed} 篇')
    return fixed


# ========== Fix 4: inline-related ==========
def fix_inline_related(articles):
    """
    为缺少 .inline-related 的文章添加内联延伸阅读区块。
    从现有的「相关阅读」区块升级为 .inline-related 格式。
    """
    print('\n=== Fix 4: 补入 .inline-related 内联延伸阅读 ===')
    ir_pat = re.compile(r'class=["\'][^"]*inline-related', re.I)
    fixed = 0
    skipped = []

    for fpath in articles:
        fname = os.path.basename(fpath)
        if fname == 'index.html':
            continue  # 非文章

        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        if ir_pat.search(content):
            continue

        # 检查是否有「相关阅读」（related-reading）可升级
        has_related = bool(re.search(r'class=["\'][^"]*related-reading|class=["\'][^"]*related["\']', content, re.I))

        if not has_related:
            # 尝试找 article-footer-qr 前的位置插入
            qr_pos = content.find('article-footer-qr')
            if qr_pos == -1:
                skipped.append(fname)
                continue
            # 插一个最小的 inline-related 占位区块
            insert_pos = content.rfind('<div', max(0, qr_pos - 500), qr_pos)
            if insert_pos == -1:
                insert_pos = qr_pos
            # 不盲目生成内容——标记为需要人工补充
            skipped.append(f'{fname}(无相关阅读区块)')
            continue

        # 有 related-reading → 升级为 inline-related
        # 将相关阅读的 class 加入 inline-related
        # 简单策略：在相关阅读容器上加 inline-related class
        content_modified = re.sub(
            r'(class=["\'][^"]*)(related-reading)([^"]*["\'])',
            r'\1inline-related \2\3',
            content,
            count=1
        )

        if content_modified != content:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content_modified)
            fixed += 1
            print(f'  + {fname} (升级 existing related-reading)')
        else:
            skipped.append(fname)

    if skipped:
        print(f'  跳过（需手动处理）: {len(skipped)} 篇')
        for s in skipped[:5]:
            print(f'    - {s}')
    print(f'  修复: {fixed} 篇')
    return fixed, skipped


# ========== 主流程 ==========
def main():
    print('=' * 60)
    print('全站债务修复 v1')
    print('=' * 60)

    articles = get_articles()
    print(f'文章总数: {len(articles)}')

    f1 = fix_baidu_missing(articles)
    f2 = fix_bing_missing(articles)
    f3 = fix_geo_short_answer(articles)
    f4_count, f4_skip = fix_inline_related(articles)

    print('\n' + '=' * 60)
    print(f'修复汇总:')
    print(f'  百度统计: +{f1}')
    print(f'  Bing 统计: +{f2}')
    print(f'  GEO short-answer: +{f3}')
    print(f'  inline-related: +{f4_count} ({len(f4_skip)} 跳过)')
    print('=' * 60)


if __name__ == '__main__':
    main()
