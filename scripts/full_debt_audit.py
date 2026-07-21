#!/usr/bin/env python3
"""
全站债务扫描 v2 — 全维度历史债务清查
覆盖所有已知问题类型，每项输出精确数字。

维度清单：
  1. GA4 脚本覆盖率（G-BWLGRVRRGN）
  2. 百度统计覆盖率（b53ffd054b55836f535892622f1e4cc5）
  3. Bing 统计覆盖率
  4. GEO 元数据完整度（short-answer + answer-for）
  5. .inline-related 内链覆盖率（正文内联延伸阅读）
  6. QR 码覆盖率（article-footer-qr）
  7. canonical 链接完整性
  8. OG 标签完整性（og:title + og:description）
  9. JSON-LD 结构化数据（Article/FAQPage）
 10. 模板占位符残留（PLACEHOLDER / TODO / 待填写）
 11. 中文引号规范性（标题/正文中含英文引号）
 12. 标题长度 >28 字
 13. redirects.json 源路径在磁盘存在（矛盾）
 14. sitemap URL 对应磁盘文件
 15. article-index.json slug 有效性
 16. 内链断裂（href 指向不存在文件）
"""

import os, re, json, sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(SITE_ROOT, 'articles')

def get_all_articles():
    """获取所有文章 HTML（排除模板/重定向桩/功能性页面）"""
    articles = []
    skip_dirs = {'templates', 'microsoft-ai-decoupling'}
    skip_f = {'index', 'seo-monitor', 'prototype', 'bridge', 'hub', 'tools', 'about', '404'}
    for f in sorted(os.listdir(ARTICLES_DIR)):
        if not f.endswith('.html'):
            continue
        if f in skip_f or f.replace('.html', '') in skip_f:
            continue
        # 跳过子目录中的非文章
        fpath = os.path.join(ARTICLES_DIR, f)
        if not os.path.isfile(fpath):
            continue
        # 跳过重定向桩页
        with open(fpath, 'r', encoding='utf-8') as fh:
            head = fh.read(2000)
        if 'window.location.replace' in head or 'http-equiv="refresh"' in head:
            continue
        articles.append(fpath)
    return articles


# ============================================================
# 维度扫描函数
# ============================================================

def check_ga4(articles):
    """维度1: GA4 脚本覆盖率"""
    pattern = re.compile(r'G-BWLGRVRRGN')
    missing = []
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not pattern.search(content):
            missing.append(os.path.basename(fpath))
    return missing


def check_baidu_tongji(articles):
    """维度2: 百度统计覆盖率"""
    pattern = re.compile(r'b53ffd054b55836f535892622f1e4cc5')
    missing = []
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not pattern.search(content):
            missing.append(os.path.basename(fpath))
    return missing


def check_bing_tongji(articles):
    """维度3: Bing 统计覆盖率"""
    pattern = re.compile(r'EFE6B970983C4C6F951613B6E14571A0')
    missing = []
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not pattern.search(content):
            missing.append(os.path.basename(fpath))
    return missing


def check_geo_metadata(articles):
    """维度4: GEO 元数据完整度"""
    missing_answer_for = []
    missing_short_answer = []
    geo_pattern_sa = re.compile(r'<meta\s+[^>]*name=["\'](?:twitter|short-answer)["\']|<meta\s+[^>]*content=["\'][^"\']{10,}["\'][^>]*name=["\'](?:twitter|short-answer)["\']', re.I)
    geo_pattern_af = re.compile(r'<meta\s+name=["\']answer-for["\']\s+content=["\']([^"\']+)["\']|<meta\s+content=["\'][^"\']+["\'][^>]*name=["\']answer-for["\']', re.I)

    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        has_af = bool(geo_pattern_af.search(content))
        has_sa = bool(geo_pattern_sa.search(content))
        if not has_af:
            missing_answer_for.append(os.path.basename(fpath))
        if not has_sa:
            missing_short_answer.append(os.path.basename(fpath))

    return missing_answer_for, missing_short_answer


def check_inline_related(articles):
    """维度5: .inline-related 内链覆盖率"""
    pattern = re.compile(r'class=["\'][^"]*inline-related')
    missing = []
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not pattern.search(content):
            missing.append(os.path.basename(fpath))
    return missing


def check_qr_code(articles):
    """维度6: QR 码覆盖率（article-footer-qr）"""
    pattern = re.compile(r'article-footer-qr|footer-qr')
    missing = []
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not pattern.search(content):
            missing.append(os.path.basename(fpath))
    return missing


def check_canonical(articles):
    """维度7: canonical 链接完整性（顺序无关）"""
    pattern = re.compile(r'<link\s+[^>]*rel=["\']canonical["\']|<link\s+[^>]*href=["\'][^"\']*["\'][^>]*rel=["\']canonical["\']', re.I)
    missing = []
    wrong = []
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        m = pattern.search(content)
        if not m:
            missing.append(os.path.basename(fpath))
        else:
            # 检查 canonical 是否指向 aihrlab.online（顺序无关）
            can_pattern = re.compile(r'<link\s+(?:[^>]*href=["\'](https?://[^"\']+)["\']|[^>]*rel=["\']canonical["\'])[^(?:href)]*?(?:href=["\'](https?://[^"\']+)["\']|rel=["\']canonical["\'])', re.I)
            cm = can_pattern.search(content)
            if cm:
                url = cm.group(1) or cm.group(2)
                if url and 'aihrlab.online' not in url:
                    wrong.append((os.path.basename(fpath), url))

    return missing, wrong


def check_og_tags(articles):
    """维度8: OG 标签完整性（顺序无关：同时匹配 property/name 两种写法和 content 前后两种顺序）"""
    missing_title = []
    missing_desc = []
    # 只要 meta 标签里同时出现 og:title 和 content= 即算有
    pat_title = re.compile(r'<meta\s+[^>]*(?:property|name)["\']*=["\']*og:title', re.I)
    pat_desc = re.compile(r'<meta\s+[^>]*(?:property|name)["\']*=["\']*og:description', re.I)

    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not pat_title.search(content):
            missing_title.append(os.path.basename(fpath))
        if not pat_desc.search(content):
            missing_desc.append(os.path.basename(fpath))

    return missing_title, missing_desc


def check_json_ld(articles):
    """维度9: JSON-LD 结构化数据"""
    pattern = re.compile(r'application/ld\+json')
    no_schema = []
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not pattern.search(content):
            no_schema.append(os.path.basename(fpath))
    return no_schema


def check_placeholder_residual(articles):
    """维度10: 模板占位符残留"""
    patterns = [
        # 排除 HTML 属性 placeholder="..." 的误报（属性名全小写，模板占位符全大写）
        (re.compile(r'(?<![a-z])PLACEHOLDER(?![a-z])'), 'PLACEHOLDER（独立词，非属性）'),
        (re.compile(r'\bTODO\b[\s:]'), 'TODO'),
        (re.compile(r'待填写|待补充|待替换'), '中文占位符'),
        (re.compile(r'\bYOUR_DESCRIPTION_HERE\b|\bYOUR_TITLE_HERE\b'), '英文占位符'),
        (re.compile(r'\{\{.*?\}\}'), 'Mustache模板语法'),
    ]
    findings = []  # (file, pattern_name, line_preview)
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        for pat, name in patterns:
            for m in pat.finditer(content):
                line_start = content.rfind('\n', 0, m.start()) + 1
                line_end = content.find('\n', m.end())
                line = content[line_start:line_end].strip()[:100]
                findings.append((os.path.basename(fpath), name, line))

    return findings


def check_chinese_quotes(articles):
    """维度11: 中文引号规范性（标题/H1 中含英文双引号）"""
    violations = []
    # 检查 title 标签和 H1 中的英文引号
    title_pat = re.compile(r'<title>([^<]+)</title>')
    h1_pat = re.compile(r'<h1[^>]*>([^<]+)</h1>')

    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        tm = title_pat.search(content)
        hm = h1_pat.search(content)

        issues = []
        if tm:
            t = tm.group(1)
            if '"' in t or '"' in t or '&quot;' in t or '&#x22;' in t:
                issues.append(f'title="{t[:60]}"')
        if hm:
            h = hm.group(1)
            if '"' in h or '"' in h or '&quot;' in h or '&#x22;' in h:
                issues.append(f'h1="{h[:60]}"')

        if issues:
            violations.append((os.path.basename(fpath), issues))

    return violations


def check_title_length(articles):
    """维度12: 标题 >28 字"""
    too_long = []
    title_pat = re.compile(r'<title>([^<]+)</title>')
    for fpath in articles:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        tm = title_pat.search(content)
        if tm:
            t = tm.group(1).strip()
            # 去掉站点后缀
            t_clean = re.sub(r'\s*[|\-]\s*AIHR.*$', '', t).strip()
            if len(t_clean) > 28:
                too_long.append((os.path.basename(fpath), t_clean, len(t_clean)))
    return too_long


def check_redirects_conflict():
    """维度13: redirects.json 源路径在磁盘存在（矛盾——排除桩页）"""
    rp = os.path.join(SITE_ROOT, 'redirects.json')
    if not os.path.exists(rp):
        return ['redirects.json 不存在']
    with open(rp, 'r', encoding='utf-8') as f:
        redirects = json.load(f)

    conflicts = []
    for src in redirects:
        rel = src.lstrip('/')
        abs_path = os.path.join(SITE_ROOT, rel)
        if os.path.exists(abs_path):
            # 检查是否为重定向桩页（canonical + refresh + replace）
            with open(abs_path, 'r', encoding='utf-8') as fh:
                head = fh.read(2000)
            is_stub = 'window.location.replace' in head or 'http-equiv="refresh"' in head
            if not is_stub:
                conflicts.append(f'{src} → 非桩页文件仍在磁盘！')
    return conflicts


def check_sitemap_vs_disk():
    """维度14: sitemap URL 对应磁盘文件"""
    sp = os.path.join(SITE_ROOT, 'sitemap.xml')
    with open(sp, 'r', encoding='utf-8') as f:
        content = f.read()

    urls = re.findall(r'<loc>(https://www\.aihrlab\.online/[^<]+)</loc>', content)
    missing = []
    for url in urls:
        rel = url.replace('https://www.aihrlab.online/', '')
        abs_path = os.path.join(SITE_ROOT, rel)
        if rel.endswith('/'):
            abs_path = os.path.join(abs_path, 'index.html')
        elif not rel.endswith('.html'):
            abs_path += '.html'
        if not os.path.exists(abs_path):
            missing.append(rel)

    return missing


def check_article_index_validity():
    """维度15: article-index.json slug 有效性"""
    # 可能位于 assets/js/ 或根目录
    aip = os.path.join(SITE_ROOT, 'assets', 'js', 'article-index.json')
    if not os.path.exists(aip):
        aip = os.path.join(SITE_ROOT, 'article-index.json')
    with open(aip, 'r', encoding='utf-8') as f:
        data = json.load(f)

    invalid = []
    # article-index.json 是列表格式，每项有 url 字段
    items = data if isinstance(data, list) else data.get('articles', [])
    for item in items:
        url = item.get('url', '') or item.get('slug', '')
        # url 是 /articles/some-slug.html 格式
        slug = url.lstrip('/').split('/')[-1] if url else ''
        if not slug:
            continue
        # 如果 slug 没有 .html 后缀，补上
        if not slug.endswith('.html'):
            slug += '.html'
        fpath = os.path.join(ARTICLES_DIR, slug)
        if not os.path.exists(fpath):
            invalid.append(slug)
    return invalid


def check_internal_links_broken(articles):
    """维度16: 内链断裂（排除解析到站点外的合法根路径链接）"""
    disk_files = set()
    for root, dirs, files in os.walk(SITE_ROOT):
        for fn in files:
            if fn.endswith('.html'):
                disk_files.add(os.path.relpath(os.path.join(root, fn), SITE_ROOT))

    broken = []
    link_pat = re.compile(r'href=["\']([^"\']*\.html[^"\']*)["\']')

    for fpath in articles:
        rel_src = os.path.relpath(fpath, SITE_ROOT)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        for m in link_pat.finditer(content):
            href = m.group(1)
            # 跳过外部链接、锚点、协议链接
            if href.startswith(('http://', 'https://', '#', 'mailto:', 'tel:')):
                continue
            # 去掉查询参数和锚点后再检查文件
            href_clean = re.sub(r'[?#].*$', '', href)
            # 解析相对路径
            source_dir = os.path.dirname(fpath)
            target_abs = os.path.normpath(os.path.join(source_dir, href_clean))
            # 跳过解析到站点之外的路径（如 ../../../../../index.html → 合法的根页面导航）
            if not target_abs.startswith(SITE_ROOT):
                continue
            target_rel = os.path.relpath(target_abs, SITE_ROOT)

            if target_rel not in disk_files and not os.path.exists(target_abs):
                broken.append(f'[{rel_src}] → {target_rel}')

    return broken


# ============================================================
# 主流程
# ============================================================

def main():
    print('=' * 70)
    print('全站债务扫描 v2 — 全维度历史债务清查')
    print(f'站点根目录: {SITE_ROOT}')
    print('=' * 70)

    articles = get_all_articles()
    total = len(articles)
    print(f'\n文章总数（排除模板/桩页/功能页）: {total}')
    print('-' * 70)

    all_clear = True

    # --- 维度 1: GA4 ---
    print('\n[维度 1] GA4 脚本覆盖率 (G-BWLGRVRRGN)')
    miss = check_ga4(articles)
    if miss:
        print(f'  FAIL: {len(miss)}/{total} 缺失 GA4')
        for m in miss[:5]:
            print(f'    - {m}')
        if len(miss) > 5:
            print(f'    ... 还有 {len(miss)-5} 篇')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 全部包含 GA4')

    # --- 维度 2: 百度统计 ---
    print('\n[维度 2] 百度统计覆盖率 (b53ffd05...)')
    miss = check_baidu_tongji(articles)
    if miss:
        print(f'  FAIL: {len(miss)}/{total} 缺失百度统计')
        for m in miss[:5]:
            print(f'    - {m}')
        if len(miss) > 5:
            print(f'    ... 还有 {len(miss)-5} 篇')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 全部包含百度统计')

    # --- 维度 3: Bing 统计 ---
    print('\n[维度 3] Bing 统计覆盖率 (EFE6B97...)')
    miss = check_bing_tongji(articles)
    if miss:
        print(f'  FAIL: {len(miss)}/{total} 缺失 Bing 统计')
        for m in miss[:5]:
            print(f'    - {m}')
        if len(miss) > 5:
            print(f'    ... 还有 {len(miss)-5} 篇')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 全部包含 Bing 统计')

    # --- 维度 4: GEO 元数据 ---
    print('\n[维度 4] GEO 元数据完整度')
    miss_af, miss_sa = check_geo_metadata(articles)
    if miss_af or miss_sa:
        print(f'  FAIL:')
        if miss_af:
            print(f'    answer-for 缺失: {len(miss_af)}/{total}')
            for m in miss_af[:5]: print(f'      - {m}')
            if len(miss_af) > 5: print(f'      ... +{len(miss_af)-5}')
        if miss_sa:
            print(f'    short-answer 缺失: {len(miss_sa)}/{total}')
            for m in miss_sa[:5]: print(f'      - {m}')
            if len(miss_sa) > 5: print(f'      +{len(miss_sa)-5}')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} GEO 元数据完整')

    # --- 维度 5: inline-related ---
    print('\n[维度 5] .inline-related 内链覆盖率')
    miss = check_inline_related(articles)
    if miss:
        print(f'  FAIL: {len(miss)}/{total} 缺少内联延伸阅读')
        for m in miss[:10]:
            print(f'    - {m}')
        if len(miss) > 10:
            print(f'    ... 还有 {len(miss)-10} 篇')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 全部包含 inline-related')

    # --- 维度 6: QR 码 ---
    print('\n[维度 6] QR 码覆盖率 (article-footer-qr)')
    miss = check_qr_code(articles)
    if miss:
        print(f'  FAIL: {len(miss)}/{total} 缺少二维码')
        for m in miss[:10]:
            print(f'    - {m}')
        if len(miss) > 10:
            print(f'    ... 还有 {len(miss)-10} 篇')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 全部包含 QR 码')

    # --- 维度 7: canonical ---
    print('\n[维度 7] canonical 链接完整性')
    miss, wrong = check_canonical(articles)
    if miss:
        print(f'  FAIL: {len(miss)}/{total} 缺少 canonical')
        for m in miss[:5]: print(f'    - {m}')
        all_clear = False
    elif wrong:
        print(f'  WARN: {len(wrong)} 篇 canonical 指向非 aihrlab.online 域名')
        for w in wrong[:3]: print(f'    - {w[0]} → {w[1]}')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} canonical 正确')

    # --- 维度 8: OG 标签 ---
    print('\n[维度 8: OG 标签完整性 (og:title + og:description)]')
    mt, md = check_og_tags(articles)
    if mt or md:
        print(f'  FAIL:')
        if mt: print(f'    og:title 缺失: {len(mt)}')
        if md: print(f'    og:description 缺失: {len(md)}')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} OG 标签完整')

    # --- 维度 9: JSON-LD ---
    print('\n[维度 9] JSON-LD 结构化数据 (application/ld+json)')
    miss = check_json_ld(articles)
    if miss:
        print(f'  FAIL: {len(miss)}/{total} 缺少结构化数据')
        for m in miss[:10]:
            print(f'    - {m}')
        if len(miss) > 10:
            print(f'    ... 还有 {len(miss)-10} 篇')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 全部包含 JSON-LD')

    # --- 维度 10: 占位符残留 ---
    print('\n[维度 10] 模板占位符残留 (PLACEHOLDER/TODO/待填写)')
    finds = check_placeholder_residual(articles)
    if finds:
        print(f'  FAIL: 发现 {len(finds)} 处残留')
        for f, name, preview in finds[:15]:
            print(f'    [{name}] {f}: {preview}')
        if len(finds) > 15:
            print(f'    ... 还有 {len(finds)-15} 处')
        all_clear = False
    else:
        print(f'  PASS: 无占位符残留')

    # --- 维度 11: 中文引号 ---
    print('\n[维度 11] 中文引号规范 (title/h1 含英文引号)')
    viol = check_chinese_quotes(articles)
    if viol:
        print(f'  FAIL: {len(viol)}/{total} 违规')
        for f, issues in viol[:10]:
            print(f'    - {f}: {issues[0]}')
        if len(viol) > 10:
            print(f'    ... 还有 {len(viol)-10} 篇')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 引号规范')

    # --- 维度 12: 标题长度 ---
    print('\n[维度 12] 标题长度 (>28 字)')
    long_titles = check_title_length(articles)
    if long_titles:
        print(f'  FAIL: {len(long_titles)}/{total} 超长')
        for f, t, l in long_titles:
            print(f'    - {f} ({l}字): {t}')
        all_clear = False
    else:
        print(f'  PASS: {total}/{total} 标题长度合格')

    # --- 维度 13-16: 全局一致性 ---
    print('\n--- 全局索引一致性 ---')

    conf = check_redirects_conflict()
    print(f'[维度 13] redirects.json 矛盾（源路径在磁盘存在）')
    if conf:
        print(f'  FAIL: {len(conf)} 处矛盾')
        for c in conf: print(f'    - {c}')
        all_clear = False
    else:
        print(f'  PASS: 无矛盾')

    sm = check_sitemap_vs_disk()
    print(f'[维度 14] sitemap→磁盘对应')
    if sm:
        print(f'  FAIL: {len(sm)} 个 sitemap URL 无对应文件')
        for s in sm: print(f'    - {s}')
        all_clear = False
    else:
        print(f'  PASS: {sm.__len__()} 个URL全部对应')

    ai = check_article_index_validity()
    print(f'[维度 15] article-index.json slug 有效性')
    if ai:
        print(f'  FAIL: {len(ai)} 个无效 slug')
        for a in ai: print(f'    - {a}')
        all_clear = False
    else:
        print(f'  PASS: 全部有效')

    bl = check_internal_links_broken(articles)
    print(f'[维度 16] 内链断裂（全文 href→磁盘）')
    if bl:
        print(f'  FAIL: {len(bl)} 处断裂')
        for b in bl[:20]: print(f'    - {b}')
        if len(bl) > 20:
            print(f'    ... 还有 {len(bl)-20} 处')
        all_clear = False
    else:
        print(f'  PASS: 全部内链有效')

    # --- 总结 ---
    print('\n' + '=' * 70)
    if all_clear:
        print('结果: 16/16 维度全部通过 ✓')
    else:
        print('结果: 存在未清债务 ✗ —— 以上 FAIL/WARN 项须逐项修复后再推广')
    print('=' * 70)

    sys.exit(0 if all_clear else 1)


if __name__ == '__main__':
    main()
