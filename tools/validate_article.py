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
  8. HTML 结构完整性（<style>/<script> 开闭平衡 + </body>/</html> 闭合，防白屏）
  9. og:image / twitter:image 引用的本地文件真实存在（防社交卡片图裂，信任信号）
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

    # 8. HTML 结构完整性（防白屏 / 浏览器把 body 当 CSS 吞掉）
    #    2026-07-13 教训：head 里未闭合 <style> 导致 hero 页白屏，旧校验未拦住
    n_style_open = len(re.findall(r'<style\b', c, re.I))
    n_style_close = len(re.findall(r'</style>', c, re.I))
    if n_style_open != n_style_close:
        issues.append(f'<style> 未闭合（{n_style_open} 开 / {n_style_close} 闭）— 会把 body 当 CSS 吞掉致白屏')
    if re.search(r'<style>\s*<', c):
        issues.append('空 <style> 后紧跟标签（吞 body 白屏高风险）')
    n_script_open = len(re.findall(r'<script\b', c, re.I))
    n_script_close = len(re.findall(r'</script>', c, re.I))
    if n_script_open != n_script_close:
        issues.append(f'<script> 未闭合（{n_script_open} 开 / {n_script_close} 闭）')
    if '<body' in c and '</body>' not in c:
        issues.append('缺 </body> 闭合标签（结构不完整）')
    if '<html' in c and '</html>' not in c:
        issues.append('缺 </html> 闭合标签（结构不完整）')

    # 9. og:image / twitter:image 本地文件存在性（防社交卡片图裂，静默伤信任）
    #    2026-07-13 教训：阿里文 og:image 指向不存在的 .webp，社交分享卡片图裂
    site_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    og_imgs = []
    for mm in re.finditer(r'<meta\b([^>]*)/?>', c, re.I):
        attrs = mm.group(1)
        pm = re.search(r'property=["\']([^"\']+)["\']', attrs, re.I)
        nm = re.search(r'name=["\']([^"\']+)["\']', attrs, re.I)
        cm = re.search(r'content=["\']([^"\']+)["\']', attrs, re.I)
        if not cm:
            continue
        prop = (pm.group(1) if pm else '') + '|' + (nm.group(1) if nm else '')
        # 精确匹配，避免 og:image:width / og:image:height 被子串误判为 og:image
        if prop in ('og:image|', '|twitter:image'):
            og_imgs.append(cm.group(1))
    missing = []
    for src in og_imgs:
        if src.startswith('https://www.aihrlab.online/'):
            rel = src[len('https://www.aihrlab.online/'):]
        elif src.startswith(('http://', 'https://')):
            continue  # 外部图，跳过
        elif src.startswith('/'):
            rel = src[1:]
        else:
            rel = src
        if not os.path.exists(os.path.join(site_root, rel)):
            missing.append(src)
    if missing:
        issues.append('og:image/twitter:image 引用文件不存在: ' + '；'.join(missing[:3]))

    # 10. <head> 结构完整性 + 正则残留 ">/>  artifact（防社交卡片/SEO 静默伤）
    #     2026-07-14 教训：dingtalk 文缺 <head> 开始标签 + 双 </head> 致白屏/怪异渲染，
    #     批量 og:image 替换遗留 ">/ 残骸（多一个斜杠），浏览器虽忽略但属结构污染。
    n_head_open = len(re.findall(r'<head[ >]', c))
    n_head_close = len(re.findall(r'</head>', c))
    if n_head_open == 0:
        issues.append('缺 <head> 开始标签（结构不完整，浏览器进入怪异模式）')
    elif n_head_open > 1:
        issues.append(f'<head> 开始标签重复（{n_head_open} 个）')
    if n_head_close == 0:
        issues.append('缺 </head> 闭合标签（结构不完整）')
    elif n_head_close > 1:
        issues.append(f'</head> 闭合标签重复（{n_head_close} 个）')
    if re.search(r'">\s*/>', c):
        issues.append('存在 ">/ 正则残留残骸（meta 标签后多一个斜杠）')

    # 11. void 元素未闭合（<link>/<meta>/<img>/<input> 等自闭合标签必须有 >）
    #     2026-07-14 教训：preconnect 标签重建时漏写结尾 >，导致标签粘连成非法结构，
    #     浏览器静默解析异常。判定：开标签后若在下个 > 之前先遇到 < 或文末仍无 >，则畸形。
    #     （允许 void 元素跨多行，只要最终以 > 闭合即可）
    for m in re.finditer(r'<(link|meta|img|input|br|hr|source)\b(.*?)(?=<|>|$)', c, re.S):
        # m 的结尾后一个字符决定：是 '>'（正常闭合）还是 '<' / 文末（畸形）
        end = m.end()
        next_ch = c[end] if end < len(c) else ''
        if next_ch != '>':
            issues.append(f'存在未闭合的 <{m.group(1)}> 标签（畸形 void 元素，结构解析将异常）')
            break

    # 12. style.min.css 与 style.css 同步（防压缩漂移：min 缺源中类=线上缺样式）
    #     改 CSS 后须跑 tools/build_css.py 重生 min。
    css_src = os.path.join(site_root, 'assets', 'css', 'style.css')
    css_min = os.path.join(site_root, 'assets', 'css', 'style.min.css')
    if os.path.exists(css_src) and os.path.exists(css_min):
        def _cls(p):
            return set(re.findall(r'\.([a-zA-Z][a-zA-Z0-9_-]*)', open(p, encoding='utf-8').read()))
        sc, sm = _cls(css_src), _cls(css_min)
        missing = sc - sm
        if missing:
            issues.append(f'style.min.css 缺失源中 {len(missing)} 个类（漂移，须跑 build_css.py 重生）')

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
