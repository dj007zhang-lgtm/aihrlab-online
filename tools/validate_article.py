#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前主理人自检（非阻塞，质量保障用）。

检查项：
  1. GA4 gtag 统计代码存在（googletagmanager.com/gtag/js + gtag('config'）
  2. <meta charset> 声明存在且为 utf-8（防乱码）
  3. Schema JSON-LD 合法（可解析为 dict，含 @context/@type）
  4. meta description 无 CMS 残留（搜索首页/文章/阅读N/来源）
  5. 文末二维码区块 article-footer-qr 在位
  6. main.js 已加载（追踪脚本配对）
  7. 标题 ≤ 28 字
用法：python3 tools/validate_article.py [file_or_dir]
"""
import sys, os, re, json, glob

EXCLUDE = ('articles-backup', '/.git', 'google', 'baidu_verify')

def check_file(path):
    c = open(path, encoding='utf-8').read()
    issues = []

    # 0. CSS 样式表（缺则整页无样式，肉眼可见排版崩）
    if 'rel="stylesheet"' not in c:
        issues.append('缺 CSS 样式表 link（整页无样式）')

    # 1. GA4 gtag
    if 'googletagmanager.com/gtag/js' not in c or not re.search(r"gtag\('config'", c):
        issues.append('缺 GA4 gtag 统计代码')

    # 2. charset
    m = re.search(r'<meta[^>]+charset=["\']?([\w-]+)', c, re.I)
    if not m or m.group(1).lower() != 'utf-8':
        issues.append('缺/非 utf-8 charset 声明（可能乱码）')

    # 3. Schema JSON-LD
    for sm in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', c, re.S):
        raw = sm.group(1).strip()
        try:
            d = json.loads(raw)
            if not d.get('@context') or not d.get('@type'):
                issues.append('Schema 缺 @context/@type')
        except Exception as e:
            issues.append(f'Schema JSON-LD 非法: {e}')

    # 4. meta description CMS 残留
    for dm in re.finditer(r'<meta[^>]+name="description"[^>]*content="([^"]*)"', c, re.I):
        desc = dm.group(1)
        if any(k in desc for k in ['搜索首页', '文章/', '阅读', '来源：', '读完本文你将获得']):
            issues.append(f'meta description CMS 残留: {desc[:30]}...')
            break

    # 5. footer-qr（仅对含二维码区块约定的页面）
    has_qr_hook = any(k in c for k in ['article-footer-qr', 'article-qrcode', 'oaQr'])
    if has_qr_hook and 'qrcode-wechat.webp' not in c and 'qrcode_oa.jpg' not in c:
        issues.append('二维码区块存在但缺图片引用')

    # 6. main.js 配对
    if has_qr_hook and 'assets/js/main.js' not in c:
        issues.append('含二维码钩子但未加载 main.js（追踪失效）')

    # 7. 标题长度
    tm = re.search(r'<title>(.*?)</title>', c, re.S)
    if tm:
        title = re.sub(r'\s*[|｜\|].*$', '', tm.group(1)).strip()
        if len(title) > 28:
            issues.append(f'标题超 28 字 ({len(title)}): {title}')

    return issues

def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ['.']
    files = []
    for t in targets:
        if os.path.isdir(t):
            for dp, _, fns in os.walk(t):
                if any(x in dp for x in EXCLUDE):
                    continue
                for f in fns:
                    if f.endswith('.html'):
                        files.append(os.path.join(dp, f))
        else:
            files.append(t)

    bad = 0
    for f in sorted(set(files)):
        if any(x in f for x in EXCLUDE):
            continue
        issues = check_file(f)
        if issues:
            bad += 1
            print(f'✗ {f}')
            for i in issues:
                print(f'    - {i}')
    if bad == 0:
        print(f'✓ 全部通过（{len(files)} 个文件，无基础问题）')
    else:
        print(f'\n共 {bad} 个文件有问题')
        sys.exit(1)

if __name__ == '__main__':
    main()
