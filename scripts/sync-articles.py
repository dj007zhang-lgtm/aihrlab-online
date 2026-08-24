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

    # 跳过重定向桩页（无真实内容，不应进入搜索 / 列表 / 分类 / 标签索引）
    if re.search(r'window\.location\.replace|本页面已迁移|http-equiv=["\']refresh', content):
        return None

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
        cat_span = re.search(r'<span class="cat">([^<]+)</span>', content)
        if cat_span:
            category = cat_span.group(1).strip()

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
    """生成单篇文章卡片的 HTML（含 2 行摘要，提升可扫性）"""
    slug = article['slug']
    title = html_lib.escape(article['title'])
    category = html_lib.escape(article['category'])
    date = article['date']
    date_display = date.replace('-', '.') if date else ''

    excerpt = article.get('excerpt', '')
    if len(excerpt) > 100:
        excerpt = excerpt[:100] + '...'
    excerpt = html_lib.escape(excerpt)
    excerpt_html = f'\n    <p class="card-excerpt">{excerpt}</p>' if excerpt else ''

    return f'''<article class="article-card" data-category="{category}">
  <a href="/articles/{slug}.html" class="card-link">
    <span class="card-tag">{category}</span>
    <h3 class="article-title">{title}</h3>{excerpt_html}
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


def rebuild_index_json(articles, tags_map=None):
    """重建 article-index.json（含可选 tags 维度）"""
    data = []
    for a in articles:
        entry = {
            'title': a['title'],
            'url': a['slug'],
            'category': a['category'],
            'date': a['date'],
        }
        if tags_map is not None:
            entry['tags'] = tags_map.get(a['slug'], [])
        data.append(entry)

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


def rebuild_index_jsonld(articles):
    """重建 articles/index.html 中 CollectionPage 的 ItemList 结构化数据。

    必须与卡片网格使用同一份「干净文章列表」（已排除 redirect stub），
    否则会出现「页面已迁移」桩页 + 重复 title（如《23万人被AI裁员后…》重复出现）。
    历史上该块由旧逻辑生成且 sync 脚本从不重写，导致索引长期含桩页与重复项。
    """
    with open(INDEX_HTML, 'r', encoding='utf-8') as f:
        html = f.read()

    target = None
    for blk in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        content = blk.group(1)
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get('@type') == 'CollectionPage':
            target = (blk, data)
            break

    if target is None:
        print('  ✗ 未找到 CollectionPage JSON-LD 块，跳过 ItemList 更新')
        return False

    blk, data = target
    sorted_articles = sort_articles(articles)
    item_list = []
    for i, a in enumerate(sorted_articles, start=1):
        item_list.append({
            '@type': 'ListItem',
            'position': i,
            'name': a['title'],
            'url': f'https://www.aihrlab.online/articles/{a["slug"]}.html',
        })
    data['mainEntity'] = {'@type': 'ItemList', 'itemListElement': item_list}

    new_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    new_block = f'<script type="application/ld+json">{new_json}</script>'
    html = html[:blk.start()] + new_block + html[blk.end():]

    with open(INDEX_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    return len(item_list)


# 时间归档（年/月分组）已于 2026-08-13 整体下线：对读者价值≈0，改用 main.js 页码分页。
# 全量文章链接仍完整保留在卡片网格中，内部链接的 SEO 面不受影响。


# ============ P1 标签 / 分类体系（2026-08-09） ============
# 标签为编辑型分类维度：先由关键词推导，写回 tags.json 供人工校正；重跑时尊重已有标注。
TAG_DEFS = [
    ('大厂实践', 'bigtech', ['大厂', 'alibaba', '蚂蚁', '字节', '百度', '腾讯', '华为', 'meta', 'microsoft', '微软', 'anthropic', 'google', '谷歌', 'amazon', '英伟达', 'nvidia', 'openai', '美团', '京东', '拼多多', 'apple', '苹果', '阿里']),
    ('AI裁员', 'layoff', ['裁员', 'layoff', '裁员潮', '优化', '组织瘦身', '降本']),
    ('组织扁平化', 'flattening', ['扁平化', 'flatten', '中层', '去中层', '层级']),
    ('组织变革', 'org-change', ['组织变革', '组织重构', '组织进化', '组织能力', '组织设计', '变革', '重组', 'restructure', 'rebuild']),
    ('敏捷组织', 'agile-org', ['敏捷', 'agile', '小团队', 'pod', '军团', '阿米巴']),
    ('绩效变革', 'performance', ['绩效', 'okr', 'kpi', '考核', '评价']),
    ('人才战略', 'talent', ['人才', 'talent', '人才战略', '人才画像', '招聘', 'recruit', 'hiring', '面试', '面试官']),
    ('技能优先', 'skills-first', ['技能优先', 'skills-first', '技能图谱', '技能']),
    ('AI转型', 'ai-transformation', ['转型', 'transformation', '落地', 'roi', '选型', '部署', '采纳']),
    ('AI原生组织', 'ai-native', ['ai原生', '原生组织', '智能组织', '组织os', 'org-os', '组织操作系统']),
    ('治理与伦理', 'governance', ['治理', 'governance', '伦理', '算法伦理', '合规', 'responsible']),
    ('智能体', 'agent', ['智能体', 'agent', '数字员工', 'digital employee', 'autonomous']),
    ('提示词工程', 'prompt', ['提示词', 'prompt', '提示工程']),
    ('知识管理', 'knowledge', ['知识管理', 'knowledge', '知识库', '第二大脑', 'second brain']),
    ('HR转型', 'hr-transformation', ['hr转型', 'hr一号位', 'hrbp', '人力资源', '人力资源职能']),
    ('测评工具', 'assessment', ['测评', '评估', 'assessment', '量表', '人格', '大五', 'mbti', 'disc']),
    ('远程与混合办公', 'remote', ['远程', '混合办公', 'remote', '分布式', '数字游民']),
    ('数字化转型', 'digital', ['数字化', 'digital']),
    ('领导力', 'leadership', ['领导力', 'leader', '管理者', '一号位', 'ceo', 'chro']),
    ('员工体验', 'ex', ['员工体验', 'ex', 'engagement', '敬业', '留任', '离职']),
]
TAG_SLUG = {name: slug for name, slug, _ in TAG_DEFS}
CATEGORY_SLUG = {
    '核心方法论': 'methodology',
    '组织变革': 'org-change',
    '大厂实践': 'bigtech',
    'AI转型': 'ai-transformation',
    'AI组织变革': 'ai-org',
    '研究报告': 'research-report',
}
# 分类 → 同源标签（让分类页与标签体系互通）
CATEGORY_TAG = {
    '大厂实践': '大厂实践',
    '组织变革': '组织变革',
    'AI转型': 'AI转型',
    'AI组织变革': 'AI原生组织',
}
TAGS_JSON = os.path.join(BASE_DIR, 'assets', 'js', 'tags.json')
TEMPLATE_TAX = os.path.join(BASE_DIR, 'templates', 'taxonomy.html')


def slugify_text(s):
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s.lower()).strip('-')
    return s or 'x'


def load_tags_override():
    if os.path.isfile(TAGS_JSON):
        try:
            with open(TAGS_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_tags_override(m):
    with open(TAGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def derive_tags(article):
    tags = []
    cat = article.get('category', '')
    if cat in CATEGORY_TAG:
        tags.append(CATEGORY_TAG[cat])
    text = (article.get('title', '') + ' ' + article.get('excerpt', '')).lower()
    for name, slug, kws in TAG_DEFS:
        if name in tags:
            continue
        for kw in kws:
            if kw.lower() in text:
                tags.append(name)
                break
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:4]


def resolve_tags(articles, override):
    """slug -> [tags]；已有标注优先，缺失则推导并写回 tags.json。"""
    current_slugs = {a['slug'] for a in articles}
    override = {k: v for k, v in override.items() if k in current_slugs}
    result = {}
    changed = False
    for a in articles:
        slug = a['slug']
        if slug in override:
            result[slug] = override[slug]
        else:
            t = derive_tags(a)
            result[slug] = t
            override[slug] = t
            changed = True
    if changed:
        save_tags_override(override)
    return result


def tax_desc(kind, name, n):
    """生成 ≥50 字、非模板残留的 taxonomy 页 meta description / 导引文案。"""
    if kind == 'category':
        return ('AIHR数智引擎「' + name + '」分类聚合页，收录 ' + str(n) + ' 篇深度文章，'
                '系统梳理 ' + name + ' 相关的战略、组织、人才与治理实践，帮助读者建立体系化认知。')
    elif kind == 'tag':
        return ('AIHR数智引擎标签「' + name + '」下的 ' + str(n) + ' 篇精选文章，'
                '聚焦 ' + name + ' 主题，覆盖前沿趋势、企业实践与方法论，体系化研读全部硬核深度内容。')
    return ('AIHR数智引擎内容标签云与分类导航，按主题（AI转型、组织变革、大厂动态、治理、人才等）'
            '快速检索全部深度文章，构建你的 AI+HR 知识体系。')


def render_taxonomy_page(out_path, title, desc, canonical, h1, intro, cards_html, breadcrumb_html):
    with open(TEMPLATE_TAX, 'r', encoding='utf-8') as f:
        tpl = f.read()
    tpl = tpl.replace('<!--TPL_TITLE-->', title)
    tpl = tpl.replace('<!--TPL_DESC-->', desc)
    tpl = tpl.replace('<!--TPL_CANONICAL-->', canonical)
    tpl = tpl.replace('<!--TPL_H1-->', h1)
    tpl = tpl.replace('<!--TPL_INTRO-->', intro)
    tpl = tpl.replace('<!--TPL_CARDS-->', cards_html)
    tpl = tpl.replace('<!--TPL_BREADCRUMB-->', breadcrumb_html)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(tpl)
    return out_path


def gen_categories(articles):
    by_cat = {}
    for a in articles:
        by_cat.setdefault(a['category'], []).append(a)
    count = 0
    for cat, items in by_cat.items():
        slug = CATEGORY_SLUG.get(cat, slugify_text(cat))
        cards = '\n'.join(build_card_html(x) for x in sort_articles(items))
        desc = tax_desc('category', cat, len(items))
        canonical = 'https://www.aihrlab.online/categories/' + slug + '.html'
        breadcrumb = '<a href="/articles/index.html">文章</a> / 分类：' + cat
        out = os.path.join(BASE_DIR, 'categories', slug + '.html')
        render_taxonomy_page(out, cat + ' · 文章分类 | AIHR数智引擎', desc, canonical, cat, desc, cards, breadcrumb)
        count += 1
    return count


def gen_tags(articles, tags_map):
    by_tag = {}
    for a in articles:
        for t in tags_map.get(a['slug'], []):
            by_tag.setdefault(t, []).append(a)
    count = 0
    for tag, items in sorted(by_tag.items(), key=lambda kv: -len(kv[1])):
        slug = TAG_SLUG.get(tag, slugify_text(tag))
        cards = '\n'.join(build_card_html(x) for x in sort_articles(items))
        desc = tax_desc('tag', tag, len(items))
        canonical = 'https://www.aihrlab.online/tags/' + slug + '.html'
        breadcrumb = '<a href="/tags/index.html">标签</a> / ' + tag
        out = os.path.join(BASE_DIR, 'tags', slug + '.html')
        render_taxonomy_page(out, tag + ' · 标签 | AIHR数智引擎', desc, canonical, tag, desc, cards, breadcrumb)
        count += 1
    return count


def gen_tag_index(articles, tags_map):
    by_tag = {}
    for a in articles:
        for t in tags_map.get(a['slug'], []):
            by_tag.setdefault(t, []).append(a)
    by_cat = {}
    for a in articles:
        by_cat.setdefault(a['category'], []).append(a)
    tag_links = ''.join(
        '<a class="tax-tag" href="/tags/' + TAG_SLUG.get(t, slugify_text(t)) + '.html">' + t + ' <span class="tax-count">' + str(len(items)) + '</span></a>'
        for t, items in sorted(by_tag.items(), key=lambda kv: -len(kv[1]))
    )
    cat_links = ''.join(
        '<a class="tax-tag" href="/categories/' + CATEGORY_SLUG.get(c, slugify_text(c)) + '.html">' + c + ' <span class="tax-count">' + str(len(items)) + '</span></a>'
        for c, items in sorted(by_cat.items(), key=lambda kv: -len(kv[1]))
    )
    cloud = ('<div class="tax-cloud"><h2 class="tax-h">按标签浏览</h2><div class="tax-tags">' + tag_links +
             '</div><h2 class="tax-h">按分类浏览</h2><div class="tax-tags">' + cat_links + '</div></div>')
    title = '标签与分类 | AIHR数智引擎'
    desc = tax_desc('index', '', 0)
    canonical = 'https://www.aihrlab.online/tags/index.html'
    breadcrumb = '<a href="/articles/index.html">文章</a> / 标签与分类'
    out = os.path.join(BASE_DIR, 'tags', 'index.html')
    render_taxonomy_page(out, title, desc, canonical, '标签与分类', desc, cloud, breadcrumb)
    return 1


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
            if info is None:
                skipped.append((filename, 'redirect stub (skipped)'))
                continue
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

    # 3.5 解析标签维度（读 tags.json 覆盖；缺失则推导并写回，供人工校正）
    override = load_tags_override()
    tags_map = resolve_tags(articles, override)
    tag_total = sum(len(v) for v in tags_map.values())
    print(f'标签维度: {len(tags_map)} 篇文章共标注 {tag_total} 个标签')

    # 4. 重建 article-index.json
    json_count = rebuild_index_json(articles, tags_map)
    print(f'✓ 已重建 article-index.json ({json_count} 篇，含 tags 维度)')

    # 5. 重建 articles/index.html 卡片
    html_count = rebuild_index_html(articles)
    if html_count:
        print(f'✓ 已重建 articles/index.html 卡片 ({html_count} 篇)')

    # 5.2 重建 articles/index.html 的 CollectionPage ItemList 结构化数据
    #     必须与卡片同源（同一份干净文章列表），防止桩页与重复 title 残留
    jsonld_count = rebuild_index_jsonld(articles)
    if jsonld_count:
        print(f'✓ 已重建 articles/index.html ItemList 结构化数据 ({jsonld_count} 篇)')

    # 5.5 生成分类 / 标签 / 标签云 页
    cat_n = gen_categories(articles)
    tag_n = gen_tags(articles, tags_map)
    idx_n = gen_tag_index(articles, tags_map)
    print(f'✓ 已生成分类页 {cat_n} 个 / 标签页 {tag_n} 个 / 标签云页 {idx_n} 个')

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
