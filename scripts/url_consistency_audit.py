#!/usr/bin/env python3
"""
URL 一致性全面体检（URL Consistency Health Check）
扫描 6 大维度：sitemap/磁盘/redirects/索引/内链/重复

用法:
  python3 scripts/url_consistency_audit.py

输出结构化报告，标注所有不一致项。
"""

import os
import re
import json
import sys
from urllib.parse import urlparse
from collections import Counter

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(SITE_ROOT, "articles")

# ============================================================
# 工具函数
# ============================================================

def get_disk_html_files():
    """获取磁盘上所有 .html 文件（排除 .git 等）"""
    results = set()
    for root, dirs, files in os.walk(SITE_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        for f in files:
            if f.endswith('.html'):
                results.add(os.path.join(root, f))
    return results


def get_sitemap_urls():
    """从 sitemap.xml 提取所有 loc URL"""
    sitemap_path = os.path.join(SITE_ROOT, "sitemap.xml")
    if not os.path.exists(sitemap_path):
        return []
    with open(sitemap_path, 'r', encoding='utf-8') as f:
        content = f.read()
    urls = re.findall(r'<loc>([^<]+)</loc>', content)
    return urls


def url_to_relpath(url):
    """将完整 URL 转为相对于 SITE_ROOT 的路径"""
    parsed = urlparse(url)
    path = parsed.path  # e.g., /articles/foo.html
    # 去掉开头的 /
    if path.startswith('/'):
        path = path[1:]
    return path


def relpath_to_abs(rel):
    """相对路径转绝对路径"""
    return os.path.join(SITE_ROOT, rel)


def file_exists_on_disk(relpath):
    """检查文件是否在磁盘存在"""
    abs_path = relpath_to_abs(relpath) if not os.path.isabs(relpath) else relpath
    return os.path.exists(abs_path)


def is_redirect_page(fpath):
    """判断是否为重定向桩页"""
    try:
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(2048)
        return 'http-equiv="refresh"' in content or 'window.location.replace' in content
    except:
        return False


def load_redirects():
    """加载 redirects.json"""
    rp = os.path.join(SITE_ROOT, "redirects.json")
    if not os.path.exists(rp):
        return {}
    with open(rp, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_article_index():
    """加载 article-index.json"""
    aip = os.path.join(SITE_ROOT, "assets", "js", "article-index.json")
    if not os.path.exists(aip):
        return []
    with open(aip, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_internal_links(fpath):
    """提取一个 HTML 文件中所有指向站内 .html 的 href"""
    try:
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return []

    links = []
    # 匹配 href="..." 或 href='...' 中指向 .html 的链接（排除 http/https/mailto/javascript/#）
    for m in re.findall(r'''href=["']([^"']+)["']''', content):
        href = m.strip()
        if (href.endswith('.html') and 
            not href.startswith('http://') and 
            not href.startswith('https://') and
            not href.startswith('mailto:') and
            not href.startswith('javascript:')):
            links.append(href)
    return links


# ============================================================
# 体检维度
# ============================================================

def check_1_sitemap_vs_disk():
    """维度1: sitemap URL 是否全部对应磁盘上的真实文件"""
    issues = []
    sitemap_urls = get_sitemap_urls()
    for url in sitemap_urls:
        rel = url_to_relpath(url)
        if not rel or rel == '':
            # 根路径特殊处理
            if not file_exists_on_disk('index.html'):
                issues.append(f"sitemap 含根路径 / 但 index.html 不存在")
            continue

        if not file_exists_on_disk(rel):
            issues.append(f"sitemap URL 指向不存在文件: {rel}")
    return issues


def check_2_disk_vs_sitemap():
    """维度2: 磁盘上的文章页是否都在 sitemap 中（遗漏检测）"""
    issues = []
    sitemap_urls = get_sitemap_urls()
    sitemap_rels = set()
    for url in sitemap_urls:
        rel = url_to_relpath(url)
        if rel:
            sitemap_rels.add(rel)

    # 只检查 articles/ 目录下的 .html（排除 index.html 和重定向桩）
    disk_files = get_disk_html_files()
    for fpath in sorted(disk_files):
        rel = os.path.relpath(fpath, SITE_ROOT)

        # 排除非内容页
        if not rel.startswith('articles/') or rel.endswith('index.html'):
            continue
        # 排除重定向桩页
        if is_redirect_page(fpath):
            continue

        basename = os.path.basename(fpath)
        if rel not in sitemap_rels:
            issues.append(f"磁盘文件未收入 sitemap: {rel}")

    return issues


def check_3_redirects_integrity():
    """维度3: redirects.json 完整性
       - source（旧 slug）不应在磁盘有非重定向文件
       - target（新 slug）必须在磁盘存在
    """
    issues = []
    redirects = load_redirects()

    for src, tgt in redirects.items():
        # source 应该是旧 URL，不应在磁盘有正常文件（可以有重定向桩）
        if file_exists_on_disk(src.lstrip('/')):
            abs_src = relpath_to_abs(src.lstrip('/'))
            if not is_redirect_page(abs_src):
                issues.append(f"redirects.json 源路径仍存在非桩文件: {src} → 需改为重定向桩或删除")

        # target 必须存在
        tgt_rel = tgt.lstrip('/')
        if not file_exists_on_disk(tgt_rel):
            issues.append(f"redirects.json 目标路径不存在: {tgt} ← 来自源 {src}")

    return issues


def check_4_article_index_integrity():
    """维度4: article-index.json 的 slug 是否全部对应磁盘文件"""
    issues = []
    articles = load_article_index()

    for entry in articles:
        url_or_slug = entry.get('url', '')
        title = entry.get('title', '(无标题)')

        # 处理两种格式：/articles/slug 或纯 slug
        if url_or_slug.startswith('/'):
            slug = url_or_slug.lstrip('/')
        else:
            slug = f"articles/{url_or_slug}.html"

        if not file_exists_on_disk(slug):
            issues.append(f"article-index.json 条目指向不存在文件: [{title}] → {slug}")

    return issues


def resolve_href(fpath, href):
    """将 href 解析为绝对路径（处理根相对 / 和相对路径）"""
    if href.startswith('/'):
        # 根相对路径：/articles/foo.html → SITE_ROOT/articles/foo.html
        return os.path.normpath(os.path.join(SITE_ROOT, href.lstrip('/')))
    else:
        # 相对路径：相对于文件所在目录
        source_dir = os.path.dirname(fpath)
        return os.path.normpath(os.path.join(source_dir, href))


def check_5_broken_internal_links():
    """维度5: 全站内链断裂扫描（所有 HTML 文件中的内部 .html 链接）"""
    issues = []
    disk_files = get_disk_html_files()

    for fpath in sorted(disk_files):
        # 跳过重定向桩页
        if is_redirect_page(fpath):
            continue
        # 跳过模板文件（含 PLACEHOLDER 占位符）
        if '/templates/' in fpath:
            continue

        rel_source = os.path.relpath(fpath, SITE_ROOT)
        links = extract_internal_links(fpath)

        for href in links:
            target_abs = resolve_href(fpath, href)

            # 转为相对路径以便显示
            try:
                target_rel = os.path.relpath(target_abs, SITE_ROOT)
            except ValueError:
                target_rel = target_abs

            if not os.path.exists(target_abs):
                issues.append(f"[{rel_source}] 内链断裂 → {target_rel} (原始 href={href})")

    return issues


def check_6_duplicates_and_anomalies():
    """维度6: 重复条目与异常检测
       - sitemap 重复 URL
       - 磁盘上有重定向桩但 redirects.json 无记录
       - 磁盘上有多个同名/近似文件
    """
    issues = []

    # 6a: sitemap 重复
    sitemap_urls = get_sitemap_urls()
    url_counts = Counter(sitemap_urls)
    for url, count in url_counts.items():
        if count > 1:
            issues.append(f"sitemap 重复 URL ({count}次): {url}")

    # 6b: 磁盘上的重定向桩是否全在 redirects.json 中
    # 排除功能性页面（自定义404、section index 等，非旧slug重定向）
    FUNCTIONAL_STUBS = {'404.html', 'resources.html', 'articles.html'}
    redirects = load_redirects()
    redirect_sources = set(redirects.keys())
    disk_files = get_disk_html_files()
    for fpath in disk_files:
        if is_redirect_page(fpath):
            rel = os.path.relpath(fpath, SITE_ROOT)
            basename = os.path.basename(fpath)
            # 跳过功能性重定向页（非旧URL重定向）
            if basename in FUNCTIONAL_STUBS:
                continue
            # 转为 redirects.json 格式（以 / 开头）
            key = '/' + rel
            if key not in redirect_sources:
                issues.append(f"重定向桩页未记入 redirects.json: {rel}")

    # 6c: article-index.json 中是否有重复 slug
    articles = load_article_index()
    slugs = []
    for entry in articles:
        url_or_slug = entry.get('url', '')
        if url_or_slug.startswith('/'):
            slugs.append(url_or_slug)
        else:
            slugs.append(f"/articles/{url_or_slug}.html")
    slug_counts = Counter(slugs)
    for slug, count in slug_counts.items():
        if count > 1:
            issues.append(f"article-index.json 重复 slug ({count}次): {slug}")

    return issues


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 70)
    print("  URL 一致性全面体检 (URL Consistency Health Check)")
    print("=" * 70)

    all_issues = {}

    checks = [
        ("1-sitemap→磁盘", check_1_sitemap_vs_disk,
         "sitemap 中的 URL 在磁盘上是否都有对应文件"),
        ("2-磁盘→sitemap", check_2_disk_vs_sitemap,
         "磁盘上的文章是否都已被 sitemap 收录"),
        ("3-redirects完整性", check_3_redirects_integrity,
         "redirects.json 源/目标路径有效性"),
        ("4-article-index完整性", check_4_article_index_integrity,
         "article-index.json 条目指向的文件是否存在"),
        ("5-内链断裂扫描", check_5_broken_internal_links,
         "全站所有内联 .html 链接目标是否存在"),
        ("6-重复与异常", check_6_duplicates_and_anomalies,
         "sitemap重复/孤立重定向桩/index重复slug"),
    ]

    total_issues = 0
    for name, fn, desc in checks:
        print(f"\n▶ {name}: {desc}")
        issues = fn()
        all_issues[name] = issues
        if issues:
            print(f"  ❌ 发现 {len(issues)} 个问题:")
            for issue in issues:
                print(f"    • {issue}")
            total_issues += len(issues)
        else:
            print(f"  ✅ 无问题")

    # 汇总
    print("\n" + "=" * 70)
    if total_issues == 0:
        print("  🟢 全面体检通过 — 所有 URL 引用一致，无断裂/遗漏/重复")
    else:
        print(f"  🔴 共发现 {total_issues} 个问题，需修复:")
        for name, issues in all_issues.items():
            if issues:
                print(f"    [{name}]: {len(issues)} 个")
    print("=" * 70)

    return total_issues


if __name__ == "__main__":
    sys.exit(main())
