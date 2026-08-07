#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIHR 数智引擎 — 文章同步脚本

用法:
    python3 scripts/sync-articles.py

功能:
    1. 扫描 articles/ 目录下所有 .html 文件（排除 index.html）
    2. 从每篇文章中提取标题、分类、发布日期
    3. 重建 assets/js/article-index.json（搜索索引）
    4. 重建 articles/index.html 中的文章卡片列表（按日期倒序）
    5. 输出同步报告

前置条件:
    - 文章 HTML 中包含 class="article-title" 的元素（标题）
    - 文章 HTML 中包含 data-category="xxx" 属性（分类）
    - 文章 HTML 中包含 datetime="YYYY-MM-DD" 属性（日期）
    - 缺少以上元素的文件会被标记并跳过

约定:
    - 分类为空时默认填 "核心方法论"
    - 日期为空时默认填文件修改日期
    - 卡片按日期倒序排列（最新在前）
"""

import os
import re
import json
import html as html_lib
from datetime import datetime
from collections import Counter

# ============ 路径配置 ============
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(BASE_DIR, 'articles')
INDEX_HTML = os.path.join(ARTICLES_DIR, 'index.html')
INDEX_JSON = os.path.join(BASE_DIR, 'assets', 'js', 'article-index.json')

# ============ 分类优先级（用于卡片排序） ============
# 同一天的文章按此顺序排列
CATEGORY_ORDER = [
    'AI时代组织变革',
    'AI裁员',
    '组织变革',
    '大厂实践',
    '前沿创新',
    '前沿理论',
    'AI转型',
    '核心方法论',
]

# ============ UI 筛选标签集合（与 articles/index.html 的 filter-btn 对齐） ============
UI_CATEGORIES = {
    '核心方法论', '组织变革', '大厂实践', 'AI转型', 'AI组织变革', '研究报告',
}

# 旧分类名 → UI 标签 的归一化映射
CATEGORY_NORMALIZE = {
    'AI时代组织变革': '组织变革',
    'AI裁员': '组织变革',
    '前沿创新': '核心方法论',
    '前沿理论': '核心方法论',
    '行业报告': '研究报告',
    '权威报告': '研究报告',
    '权威研究报告': '研究报告',
    'AI组织': 'AI组织变革',
    'AI组织变革': 'AI组织变革',
}


def normalize_category(cat):
    """把任意来源的分类名归一化到 UI 标签集合；无法识别的返回原值。"""
    if not cat:
        return ''
    cat = cat.strip()
    if cat in UI_CATEGORIES:
        return cat
    return CATEGORY_NORMALIZE.get(cat, cat)


def infer_category(slug, title):
    """当文章没有显式 data-category 时，根据 slug + 标题关键词自动推断分类。

    优先级（高→低）：大厂实践 > 研究报告 > AI组织变革 > 组织变革 > AI转型 > 核心方法论。
    仅输出 UI_CATEGORIES 中的分类名，兜底返回 '核心方法论'。
    """
    s = (slug + ' ' + title).lower()
    # 1) 大厂实践：具体企业 / 产品 / 代表人物（最明确，优先拦截）
    if re.search(r'alibaba|蚂蚁|ant-|ant group|bytedance|字节|baidu|百度|tencent|腾讯|'
                 r'huawei|华为|meta|microsoft|微软|anthropic|google|谷歌|amazon|亚马逊|'
                 r'unitree|宇树|dingtalk|钉钉|nvidia|英伟达|cisco|思科|apple|苹果|kimi|'
                 r'perplexity|deepmind|openai|jd|京东|pinduoduo|拼多多|keling|可灵|jimeng|'
                 r'即梦|gtc|musk|karpathy|openclaw|huoshui|活水|lisa su|苏姿丰|amd|'
                 r'meituan|美团|wangxing|王兴|wwdc|'
                 r'global-tech|大厂', s):
        return '大厂实践'
    # 2) 研究报告：咨询公司 / 数据盘点 / 报告索引 / 年中复盘
    if re.search(r'mckinsey|deloitte|mercer|idc|凯捷|bcg|麦肯锡|德勤|美世|'
                 r'报告|report|review|midyear|mid-year|outlook|key-reports|key report|'
                 r'census|盘点|复盘|年中|白皮书|成熟度|调研|索引', s):
        return '研究报告'
    # 3) AI组织变革：AI原生 / 范式 / 组织进化 / 智能组织 / 组织OS / 组织能力 / 组织重构(无企业)
    if re.search(r'原生组织|ai原生|组织范式|范式图谱|组织进化|组织os|智能组织|'
                 r'组织能力|组织阳谋|ai组织|ai-org|org-transformation|two-models|'
                 r'three-routes|军团|组织重构|组织进化论', s):
        return 'AI组织变革'
    # 4) 组织变革：通用组织 / HR 话题（裁员 / 绩效 / 培训 / 人才 / 扁平化 / HR转型 / 招聘 / 面试 / 治理 / 技能 / 数字员工 / DRI / 组织图）
    if re.search(r'裁员|layoff|组织僵化|扁平化|flatten|中层|绩效|培训|人才画像|talent|'
                 r'岗位|hr转型|hr一号位|轮岗|rotation|组织信号|组织解耦|去经验化|'
                 r'情境管理|复合型人才|kpi|人才|招聘|recruit|hiring|面试|interview|'
                 r'治理|governance|技能|skill|数字员工|数字组织|dri|组织图|org-chart|'
                 r'hr体系|sme|中小企业|bounded|rationality|human-ai|equation|pod|'
                 r'org-|restructure|rebuild|重组|重构|变革|rigidity|组织|'
                 r'jobs|digital-employee|change|evaluation|评估', s):
        return '组织变革'
    # 5) AI转型：转型 / 落地 / ROI / 选型 / 部署 / 采纳
    if re.search(r'转型|transformation|落地|landing|roi|选型|部署|采纳|应用', s):
        return 'AI转型'
    return '核心方法论'


def extract_article_info(filepath, filename):
    """从文章 HTML 中提取标题、分类、日期"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    slug = filename.replace('.html', '')

    # 1. 提取标题：优先 article-title，其次 h1，最后用 slug
    title = None
    title_match = re.search(r'class="article-title"[^>]*>\s*(.*?)\s*</', content, re.DOTALL)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

    if not title:
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL)
        if h1_match:
            title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()

    if not title:
        title = slug.replace('-', ' ').replace('_', ' ')

    # 2. 提取分类：优先 data-category，其次 article-tag
    category = ''
    cat_match = re.search(r'data-category="([^"]+)"', content)
    if cat_match:
        category = cat_match.group(1).strip()

    if not category:
        tag_match = re.search(r'class="article-tag"[^>]*>\s*(.*?)\s*</', content, re.DOTALL)
        if tag_match:
            category = re.sub(r'<[^>]+>', '', tag_match.group(1)).strip()

    if not category:
        category = infer_category(slug, title)

    # 归一化到 UI 筛选标签集合（处理旧分类名 / 显式非 UI 分类）
    category = normalize_category(category)
    if not category:
        category = '核心方法论'

    # 3. 提取日期：优先 datetime 属性
    pub_date = ''
    date_match = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', content)
    if date_match:
        pub_date = date_match.group(1)

    if not pub_date:
        # 尝试从 <time> 标签提取
        time_match = re.search(r'<time[^>]*>(\d{4}[\.\-/]\d{2}[\.\-/]\d{2})', content)
        if time_match:
            raw = time_match.group(1).replace('.', '-').replace('/', '-')
            pub_date = raw

    if not pub_date:
        # 用文件修改时间
        mtime = os.path.getmtime(filepath)
        pub_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

    # 4. 提取摘要（meta description 或正文首段）
    excerpt = ''
    desc_match = re.search(r'name="description"\s+content="([^"]+)"', content)
    if desc_match:
        excerpt = desc_match.group(1).strip()[:120]
    else:
        # 取正文第一段
        p_match = re.search(r'<p[^>]*>(.*?)</p>', content, re.DOTALL)
        if p_match:
            excerpt = re.sub(r'<[^>]+>', '', p_match.group(1)).strip()[:120]

    return {
        'slug': slug,
        'title': title,
        'category': category,
        'date': pub_date,
        'excerpt': excerpt,
    }


def build_card_html(article):
    """生成单篇文章卡片的 HTML"""
    slug = article['slug']
    title = html_lib.escape(article['title'])
    category = html_lib.escape(article['category'])
    date = article['date']
    date_display = date.replace('-', '.') if date else ''

    # 摘要截断到 100 字
    excerpt = article.get('excerpt', '')
    if len(excerpt) > 100:
        excerpt = excerpt[:100] + '...'
    excerpt = html_lib.escape(excerpt)

    return f'''<article class="article-card" data-category="{category}">
  <a href="/articles/{slug}.html" class="card-link">
    <span class="card-tag">{category}</span>
    <h3 class="article-title">{title}</h3>
    <time class="article-date" datetime="{date}">{date_display}</time>
  </a>
</article>'''


def sort_articles(articles):
    """按日期倒序排列，同日期按分类优先级"""
    cat_priority = {c: i for i, c in enumerate(CATEGORY_ORDER)}

    def sort_key(a):
        date_str = a['date'] or '0000-00-00'
        cat_idx = cat_priority.get(a['category'], 99)
        return (date_str, -cat_idx)

    return sorted(articles, key=sort_key, reverse=True)


def rebuild_index_json(articles):
    """重建 article-index.json"""
    data = []
    for a in articles:
        data.append({
            'title': a['title'],
            'url': a['slug'],
            'category': a['category'],
            'date': a['date'],
        })

    with open(INDEX_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return len(data)


def rebuild_index_html(articles):
    """重建 articles/index.html 中的文章卡片区域"""
    with open(INDEX_HTML, 'r', encoding='utf-8') as f:
        html = f.read()

    # 找到 article-grid 区域的边界
    grid_start_marker = '<div class="article-grid" id="article-grid">'
    grid_end_marker = '</div></section>'

    start_idx = html.find(grid_start_marker)
    if start_idx < 0:
        print('  ✗ 未找到 article-grid 区域，跳过 index.html 更新')
        return False

    end_idx = html.find(grid_end_marker, start_idx)
    if end_idx < 0:
        print('  ✗ 未找到 article-grid 结束位置，跳过 index.html 更新')
        return False

    # 生成所有卡片 HTML
    sorted_articles = sort_articles(articles)
    cards_html = '\n\n'.join(build_card_html(a) for a in sorted_articles)

    # 替换区域内容
    old_block = html[start_idx:end_idx + len(grid_end_marker)]
    new_block = grid_start_marker + '\n' + cards_html + '\n\n' + grid_end_marker

    html = html[:start_idx] + new_block + html[end_idx + len(grid_end_marker):]

    with open(INDEX_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    return len(sorted_articles)


def main():
    print('=' * 60)
    print('AIHR 数智引擎 — 文章同步脚本')
    print('=' * 60)
    print()

    # 1. 扫描文章文件
    if not os.path.isdir(ARTICLES_DIR):
        print(f'✗ 文章目录不存在: {ARTICLES_DIR}')
        return

    all_files = [f for f in os.listdir(ARTICLES_DIR)
                 if f.endswith('.html') and f != 'index.html']

    print(f'扫描到 {len(all_files)} 个文章文件')
    print()

    # 2. 提取每篇文章信息
    articles = []
    skipped = []

    for filename in sorted(all_files):
        filepath = os.path.join(ARTICLES_DIR, filename)
        try:
            info = extract_article_info(filepath, filename)
            articles.append(info)
        except Exception as e:
            skipped.append((filename, str(e)))
            print(f'  ⚠ 跳过 {filename}: {e}')

    if skipped:
        print(f'\n跳过 {len(skipped)} 个文件')

    print(f'成功解析 {len(articles)} 篇文章')
    print()

    # 3. 分类统计
    cats = Counter(a['category'] for a in articles)
    print('分类分布:')
    for cat, cnt in cats.most_common():
        print(f'  {cat}: {cnt} 篇')
    print()

    # 4. 重建 article-index.json
    json_count = rebuild_index_json(articles)
    print(f'✓ 已重建 article-index.json ({json_count} 篇)')

    # 5. 重建 articles/index.html 卡片
    html_count = rebuild_index_html(articles)
    if html_count:
        print(f'✓ 已重建 articles/index.html 卡片 ({html_count} 篇)')

    # 6. 检查缺失项
    no_title = [a for a in articles if not a['title'] or a['title'] == a['slug'].replace('-', ' ')]
    no_date = [a for a in articles if not a['date']]
    no_cat = [a for a in articles if a['category'] == '核心方法论' and not a.get('excerpt')]

    print()
    print('=' * 60)
    print('同步报告')
    print('=' * 60)
    print(f'  文章总数: {len(articles)}')
    print(f'  JSON 索引: {json_count} 篇')
    print(f'  HTML 卡片: {html_count} 篇')

    if no_title:
        print(f'\n⚠ 缺少标题的文章 ({len(no_title)}):')
        for a in no_title:
            print(f'    - {a["slug"]}')

    if no_date:
        print(f'\n⚠ 缺少日期的文章 ({len(no_date)}):')
        for a in no_date:
            print(f'    - {a["slug"]}')

    print()
    print('✓ 同步完成')
    print()
    print('下一步:')
    print('  1. 检查 articles/index.html 卡片是否正确')
    print('  2. git add -A && git commit -m "sync: 同步文章索引" && git push')


if __name__ == '__main__':
    main()
