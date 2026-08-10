#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站体检（只读，不改任何文件）
维度：
  A 排版与阅读体验  B 可访问性与对比度  C 资源与链接完整性
  D JS/代码健壮性    E 响应式与暗色一致性

用法: python3 scripts/site_health_audit.py [--json]
"""
import os, re, sys, json, glob, subprocess
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 桩页/非正文页豁免
STUB_HINT = re.compile(r'http-equiv=["\']refresh["\']', re.I)
SKIP_FILES = {
    '404.html', 'seo-monitor.html', 'baidu_verify_codeva-e9RlNB7KYx.html',
    'googlecbc66c5d343f6aed.html',
}

findings = defaultdict(list)          # severity -> [ (code, page, detail) ]
stats = Counter()

def add(sev, code, page, detail):
    findings[sev].append((code, page, detail))
    stats[code] += 1

def rel(p):
    return os.path.relpath(p, ROOT)

def collect_pages():
    pages = []
    for pat in ('*.html', 'articles/*.html', 'categories/**/*.html',
                'tags/**/*.html', 'hub/**/*.html', 'glossary/**/*.html',
                'compare/**/*.html', 'products/**/*.html', 'resources/**/*.html',
                'bridge/**/*.html', 'assessments/**/*.html'):
        pages += glob.glob(os.path.join(ROOT, pat), recursive=True)
    return sorted(set(pages))

# ---------------------------------------------------------------- 主循环
def audit_pages():
    pages = collect_pages()
    real_pages = []
    for p in pages:
        name = os.path.basename(p)
        if name in SKIP_FILES:
            continue
        try:
            html = open(p, encoding='utf-8').read()
        except Exception as e:
            add('BLOCKER', 'READ_FAIL', rel(p), str(e)); continue
        if STUB_HINT.search(html) and len(html) < 4000:
            stats['_stub'] += 1
            continue
        real_pages.append((p, html))
    stats['_pages'] = len(real_pages)

    for p, html in real_pages:
        r = rel(p)
        is_article = '/articles/' in p.replace('\\', '/')

        # ---------- A 排版与阅读体验 ----------
        # A1 viewport
        m = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*>', html, re.I)
        if not m:
            add('MAJOR', 'A1_NO_VIEWPORT', r, '缺 viewport meta，移动端会按 980px 缩放')
        else:
            vp = m.group(0)
            if 'user-scalable=no' in vp or re.search(r'maximum-scale\s*=\s*1', vp):
                add('MAJOR', 'A2_ZOOM_BLOCKED', r, '禁止用户缩放，违反 WCAG 1.4.4')

        # A3 lang
        if not re.search(r'<html[^>]+lang=["\']zh', html, re.I):
            add('MINOR', 'A3_NO_LANG', r, '<html> 缺 lang="zh-CN"')

        # A4 H1 唯一性
        h1s = re.findall(r'<h1[^>]*>', html, re.I)
        if len(h1s) == 0:
            add('MAJOR', 'A4_NO_H1', r, '无 H1')
        elif len(h1s) > 1:
            add('MAJOR', 'A4_MULTI_H1', r, f'{len(h1s)} 个 H1')

        # A5 标题跳级（只看正文流；排除组件容器/footer 内标题）
        art = re.search(r'<article[^>]*>(.*?)</article>', html, re.S | re.I)
        body_scope = art.group(1) if art else html
        COMPONENT = re.compile(
            r'class="[^"]*(key-insight|note-box|callout|toc-rail|toc|'
            r'related-reading|sidebar|article-footer|verified-sources|'
            r'geo-stats|continue-reading-card|analogy-box|alert|error-navigation|'
            r'model-box|comparison-box|formula-box|steps-box|cta-box|table-note|setup-step|comparision-box|case-box|asset-card|breadcrumb|'
            r'response-card|geo-answer-capsule|article-banner|inline-related|'
            r'next-path)[^"]*"', re.I)
        levels = []
        in_footer = False
        in_component = 0
        for tag in re.finditer(r'<(/?)([a-zA-Z0-9]+)\b([^>]*)>', body_scope):
            closing, name, attrs = tag.group(1), tag.group(2).lower(), tag.group(3)
            if name == 'footer' and not closing:
                in_footer = True
            elif name == 'footer' and closing:
                in_footer = False
            elif not closing and name in ('div', 'section', 'aside', 'nav') and COMPONENT.search(attrs):
                in_component += 1
            elif closing and name in ('div', 'section', 'aside', 'nav') and in_component > 0:
                in_component -= 1
            elif name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') and not closing:
                if not in_footer and in_component == 0:
                    # 排除功能性标题（如 TOC「目录」），非正文层级流
                    end = body_scope.find('</' + name + '>', tag.end())
                    txt = body_scope[tag.end():end] if end > tag.end() else ''
                    txt = re.sub(r'<[^>]+>', '', txt).strip()
                    if txt in ('目录', '相关阅读', '延伸阅读', '参考来源', '参考信源'):
                        continue
                    levels.append(int(name[1]))
        prev = None
        for lv in levels:
            if prev is not None and lv > prev + 1:
                add('MINOR', 'A5_HEADING_SKIP', r, f'H{prev} → H{lv} 跳级')
                break
            prev = lv

        # A6 图片缺 alt
        imgs = re.findall(r'<img\b[^>]*>', html, re.I)
        no_alt = [i for i in imgs if not re.search(r'\balt\s*=', i, re.I)]
        if no_alt:
            add('MAJOR', 'A6_IMG_NO_ALT', r, f'{len(no_alt)} 张图缺 alt')

        # A7 图片缺 width/height → CLS（属性或 style 内联尺寸均可防 CLS，均认可）
        def _has_dim(tag):
            if re.search(r'\bwidth\s*=', tag, re.I) and re.search(r'\bheight\s*=', tag, re.I):
                return True
            return False
        no_dim = [i for i in imgs
                  if not _has_dim(i)
                  and not re.search(r'style=["\'][^"\']*\bwidth\s*:[^"\']*', i, re.I)
                  and 'data:image' not in i]
        if no_dim:
            add('MAJOR', 'A7_IMG_NO_DIM', r, f'{len(no_dim)} 张图缺 width/height（CLS 风险）')

        # A8 首屏以下图片缺 loading=lazy（LCP 关键资源不扣分：logo / hero / fetchpriority）
        no_lazy = [i for i in imgs
                   if 'loading=' not in i.lower()
                   and 'data:image' not in i
                   and 'logo-icon' not in i.lower()
                   and 'fetchpriority' not in i.lower()
                   and 'hero' not in i.lower()]
        if len(no_lazy) >= 3:
            add('MINOR', 'A8_IMG_NO_LAZY', r, f'{len(no_lazy)} 张图未声明 loading')

        # A9 target=_blank 缺 rel=noopener
        for a in re.findall(r'<a\b[^>]*target=["\']_blank["\'][^>]*>', html, re.I):
            if 'noopener' not in a.lower():
                add('MINOR', 'A9_BLANK_NO_NOOPENER', r, '有 target=_blank 缺 rel=noopener')
                break

        # A10 内联 style 中的小字号
        for sz in re.findall(r'font-size\s*:\s*([\d.]+)px', html, re.I):
            if float(sz) < 12:
                add('MINOR', 'A10_TINY_FONT', r, f'内联 font-size:{sz}px < 12px')
                break

        # ---------- C 资源与链接 ----------
        # C1 本地资源存在性
        for attr in re.findall(r'(?:src|href)=["\'](/[^"\'#?]+)["\']', html):
            if attr.startswith('//'):
                continue
            ext = os.path.splitext(attr)[1].lower()
            if ext not in ('.css', '.js', '.png', '.jpg', '.jpeg', '.webp',
                           '.svg', '.ico', '.json', '.xml', '.txt', '.pdf'):
                continue
            target = os.path.join(ROOT, attr.lstrip('/'))
            if not os.path.exists(target):
                add('BLOCKER', 'C1_ASSET_404', r, f'资源不存在: {attr}')

        # C2 重复 id
        ids = re.findall(r'\sid=["\']([^"\']+)["\']', html)
        dup = [k for k, v in Counter(ids).items() if v > 1]
        if dup:
            add('MAJOR', 'C2_DUP_ID', r, f'重复 id: {", ".join(dup[:5])}')

        # C3 锚点目标缺失
        idset = set(ids)
        for href in set(re.findall(r'href=["\']#([^"\']+)["\']', html)):
            if href and href not in idset and not re.search(
                    r'name=["\']%s["\']' % re.escape(href), html):
                add('MINOR', 'C3_DEAD_ANCHOR', r, f'锚点 #{href} 无对应元素')
                break

        # ---------- D 代码健壮性 ----------
        # D1 内联 script 语法（交由 Gate18 兜底，这里只查明显单行 // 残留）
        for sc in re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S | re.I):
            if 'application/ld+json' in sc[:0]:
                continue
            lines = [l for l in sc.split('\n') if l.strip()]
            if len(lines) == 1 and re.search(r'(?<!:)//(?!/)', lines[0]) and len(lines[0]) > 200:
                add('BLOCKER', 'D1_INLINE_JS_SWALLOW', r, '单行内联 script 含 // 注释（后续代码被吞）')
                break

        # D2 JSON-LD 可解析
        for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
            try:
                json.loads(blk.strip())
            except Exception as e:
                add('MAJOR', 'D2_BAD_JSONLD', r, f'JSON-LD 解析失败: {e}')
                break

        # ---------- E 暗色一致性 ----------
        # E1 内联硬编码浅色背景（深色模式下会亮块浮暗底）
        hard = re.findall(r'style=["\'][^"\']*background(?:-color)?\s*:\s*(#[Ff][0-9A-Fa-f]{5}|#[Ff][0-9A-Fa-f]{2}\b|white|#fff\b|#ffffff\b)', html)
        if len(hard) >= 3:
            add('MINOR', 'E1_HARDCODED_LIGHT_BG', r, f'{len(hard)} 处内联硬编码浅色背景')

        # E2 文章页缺 scroll-margin 保护（sticky header 遮挡锚点）
        if is_article and re.search(r'href=["\']#', html):
            if 'scroll-margin' not in html:
                stats['_no_scroll_margin_inline'] += 1

    return real_pages

# ---------------------------------------------------------------- CSS
def audit_css():
    p = os.path.join(ROOT, 'assets/css/style.css')
    css = open(p, encoding='utf-8').read()
    r = 'assets/css/style.css'

    if 'prefers-reduced-motion' not in css:
        add('MAJOR', 'E3_NO_REDUCED_MOTION', r,
            '无 prefers-reduced-motion 支持（前庭障碍用户无法关闭动画）')
    if 'scroll-margin' not in css:
        add('MAJOR', 'A11_NO_SCROLL_MARGIN', r,
            '标题无 scroll-margin-top，sticky header 会遮挡锚点跳转目标')
    if not re.search(r':focus-visible', css):
        add('MAJOR', 'B1_NO_FOCUS_VISIBLE', r,
            '无 :focus-visible 样式，键盘用户看不到焦点')
    if 'outline:none' in css.replace(' ', '') or 'outline:0' in css.replace(' ', ''):
        n = len(re.findall(r'outline\s*:\s*(?:none|0)', css))
        add('MINOR', 'B2_OUTLINE_REMOVED', r, f'{n} 处移除 outline')
    if '@media print' not in css:
        add('MINOR', 'A12_NO_PRINT', r, '无打印样式')
    # 断点
    bps = sorted(set(int(x) for x in re.findall(r'max-width\s*:\s*(\d+)px', css)))
    stats['_breakpoints'] = len(bps)
    # 行宽
    m = re.search(r'--article-width\s*:\s*(\d+)px', css)
    if m:
        stats['_article_width'] = int(m.group(1))
    m = re.search(r'html\{font-size:(\d+)px', css)
    if m:
        stats['_root_font'] = int(m.group(1))
    return bps

# ---------------------------------------------------------------- JS
def audit_js():
    node = '/Users/andyzhang/.workbuddy/binaries/node/versions/22.22.2/bin/node'
    for f in sorted(glob.glob(os.path.join(ROOT, 'assets/js/*.js'))):
        r = rel(f)
        try:
            out = subprocess.run([node, '--check', f], capture_output=True, text=True, timeout=30)
            if out.returncode != 0:
                add('BLOCKER', 'D3_JS_SYNTAX', r, out.stderr.strip().split('\n')[0])
        except Exception as e:
            add('MAJOR', 'D3_JS_CHECK_FAIL', r, str(e))
        src = open(f, encoding='utf-8').read()
        # 全局 error 监听
        if os.path.basename(f) == 'main.js' and "addEventListener('error'" not in src:
            add('MAJOR', 'D4_NO_GLOBAL_ERR', r, '缺全局 error 监听')
        # localStorage 裸用（无 try/catch）→ 隐私模式崩
        for mm in re.finditer(r'localStorage\.(getItem|setItem|removeItem)', src):
            seg = src[max(0, mm.start() - 220):mm.start()]
            if 'try{' not in seg and 'try {' not in seg:
                add('MINOR', 'D5_RAW_LOCALSTORAGE', r,
                    'localStorage 调用未包 try/catch（Safari 无痕模式抛异常）')
                break

# ---------------------------------------------------------------- 对比度
def srgb(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def lum(hexs):
    hexs = hexs.lstrip('#')
    if len(hexs) == 3:
        hexs = ''.join(ch * 2 for ch in hexs)
    r, g, b = (int(hexs[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)

def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def audit_contrast():
    pairs_light = [
        ('正文 text/bg', '#1a1a1a', '#F1EFE9', 4.5),
        ('次要 text-secondary/bg', '#6b6b6b', '#F1EFE9', 4.5),
        ('弱化 text-muted/bg', '#6b6b6b', '#F1EFE9', 4.5),  # 体检修复 2026-08-09（原 #9a9a9a 仅 2.45:1）
        ('链接 text-link/bg', '#365314', '#F1EFE9', 4.5),
        ('强调 accent/bg', '#3F6212', '#F1EFE9', 4.5),
        ('正文 text/surface白', '#1a1a1a', '#FFFFFF', 4.5),
        ('次要 text-secondary/surface', '#6b6b6b', '#FFFFFF', 4.5),
        ('弱化 text-muted/surface', '#6b6b6b', '#FFFFFF', 4.5),
    ]
    pairs_dark = [
        ('暗-正文 text/bg', '#ECEAE4', '#0B0C0E', 4.5),
        ('暗-次要 text-secondary/bg', '#A6ADB8', '#0B0C0E', 4.5),
        ('暗-弱化 text-muted/bg', '#7E8896', '#0B0C0E', 4.5),  # 体检修复 2026-08-09/10（原 #6B7280 仅 4.05:1）
        ('暗-链接 text-link/bg', '#9CC06A', '#0B0C0E', 4.5),
        ('暗-正文 text/surface', '#ECEAE4', '#16191D', 4.5),
        ('暗-次要 text-secondary/surface', '#A6ADB8', '#16191D', 4.5),
        ('暗-弱化 text-muted/surface', '#7E8896', '#16191D', 4.5),
    ]
    rows = []
    for name, fg, bg, need in pairs_light + pairs_dark:
        rr = ratio(fg, bg)
        ok = rr >= need
        rows.append((name, fg, bg, rr, ok))
        if not ok:
            sev = 'MAJOR' if rr < 3.0 else 'MINOR'
            add(sev, 'B3_CONTRAST', 'design-token',
                f'{name} = {rr:.2f}:1 < {need}（WCAG AA 未过）')
    return rows

# ---------------------------------------------------------------- main
def main():
    audit_pages()
    bps = audit_css()
    audit_js()
    rows = audit_contrast()

    print('=' * 78)
    print('全站体检报告 · 代码健壮性 / 阅读体验 / 排版 / 可访问性')
    print('=' * 78)
    print(f"扫描正文页 {stats['_pages']} 个（跳过重定向桩页 {stats['_stub']} 个）")
    print(f"根字号 {stats.get('_root_font')}px · 正文栏宽 {stats.get('_article_width')}px "
          f"· 响应式断点 {stats.get('_breakpoints')} 个 {bps}")
    print()
    print('--- 对比度实测（WCAG AA 需 ≥4.5:1）---')
    for name, fg, bg, rr, ok in rows:
        print(f"  {'PASS' if ok else 'FAIL'}  {rr:6.2f}:1  {name:34s} {fg} on {bg}")
    print()
    order = ['BLOCKER', 'MAJOR', 'MINOR']
    for sev in order:
        items = findings.get(sev, [])
        if not items:
            continue
        by_code = defaultdict(list)
        for code, page, detail in items:
            by_code[code].append((page, detail))
        print(f'--- {sev} ({len(items)} 项) ---')
        for code, lst in sorted(by_code.items(), key=lambda x: -len(x[1])):
            print(f'  [{code}] × {len(lst)}')
            for page, detail in lst[:5]:
                print(f'      {page}: {detail}')
            if len(lst) > 5:
                print(f'      … 另 {len(lst)-5} 处')
        print()
    print('=' * 78)
    print(f"合计 BLOCKER {len(findings.get('BLOCKER',[]))} · "
          f"MAJOR {len(findings.get('MAJOR',[]))} · "
          f"MINOR {len(findings.get('MINOR',[]))}")

if __name__ == '__main__':
    main()
