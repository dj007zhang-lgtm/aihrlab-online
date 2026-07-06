#!/usr/bin/env python3
"""AIHR 文章发布合规检查器

检查项：
  1. 二维码铁律：仅 1 个 article-footer-qr，无 article-qrcode / footer QR
  2. JSON-LD：合法且含 Article + FAQPage + BreadcrumbList
  3. Article headline 长度 <= 28 字
  4. meta description 存在且非空
  5. 相关阅读内链 3-5 篇

用法：
    python3 tools/publish_check.py                # 全站扫描
    python3 tools/publish_check.py articles/foo.html   # 单篇
退出码：0=全部合规，1=有不合規
"""
import re
import json
import sys
import os
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(ROOT, "articles")


def is_article_page(html, types):
    """真文章页判定：含 Article JSON-LD，或正文带 article-body/article-content 类。
    主题簇/列表/枢纽页（无 Article、无 article-body）不视为文章，跳过二维码与内链强校验。"""
    return ("Article" in types) or ("article-body" in html) or ("article-content" in html)


def check_file(path):
    html = open(path, encoding="utf-8").read()
    issues = []

    # 2) JSON-LD + headline（先解析，供 is_article 判定）
    blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S
    )
    types = set()
    headline = None
    for b in blocks:
        try:
            obj = json.loads(b)
            t = obj.get("@type")
            tlist = t if isinstance(t, list) else [t]
            for tt in tlist:
                if tt:
                    types.add(tt)
            if "Article" in tlist and obj.get("headline"):
                headline = obj["headline"]
        except Exception as e:
            issues.append(f"JSON-LD 解析失败: {e}")

    real_article = is_article_page(html, types)

    # 文章页专属校验：二维码铁律 / 必需 JSON-LD 类型 / 标题长度 / 相关阅读内链
    if real_article:
        # 1) 二维码铁律
        n_footer = html.count("article-footer-qr")
        if n_footer != 1:
            issues.append(f"二维码 article-footer-qr 数量={n_footer}（应为1）")
        if "article-qrcode" in html:
            issues.append("存在 article-qrcode（应清除）")
        # 必需 JSON-LD 类型
        for need in ("Article", "FAQPage", "BreadcrumbList"):
            if need not in types:
                issues.append(f"缺少 JSON-LD 类型 {need}")
        # 3) headline 长度
        if headline is None:
            issues.append("缺少 Article headline")
        elif len(headline) > 28:
            issues.append(f"标题过长: {len(headline)}字 > 28（'{headline}'）")
        # 5) 相关阅读内链 3-5
        rr = re.search(
            r'<section[^>]*class="[^"]*related-reading[^"]*"[^>]*>(.*?)</section>', html, re.S
        )
        if rr:
            links = re.findall(r'href="(/articles/[^"]+\.html)"', rr.group(1))
        else:
            self_slug = os.path.basename(path)
            links = [
                l
                for l in re.findall(r'href="(/articles/[^"]+\.html)"', html)
                if os.path.basename(l) != self_slug
            ]
        n_links = len(set(links))
        if n_links < 3:
            issues.append(f"相关阅读内链仅 {n_links} 条（建议 3-5）")
    else:
        # 枢纽/列表页：仅当含 JSON-LD 却缺类型时提示（不含 Article 属正常）
        for need in ("FAQPage", "BreadcrumbList"):
            if need not in types and types:
                issues.append(f"缺少 JSON-LD 类型 {need}")

    # 4) meta description（所有页面）
    m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html, re.I)
    if not m or not m.group(1).strip():
        issues.append("缺少/空 meta description")

    return issues


def main():
    args = [a for a in sys.argv[1:] if a.endswith(".html")]
    files = args if args else sorted(glob.glob(os.path.join(ARTICLES, "*.html")))
    total = len(files)
    bad = 0
    for f in files:
        issues = check_file(f)
        name = os.path.relpath(f, ROOT)
        if issues:
            bad += 1
            print(f"[✗] {name}")
            for i in issues:
                print(f"      - {i}")
        else:
            print(f"[✓] {name}")
    print(f"\n扫描 {total} 个文件，不合规 {bad} 个。")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
