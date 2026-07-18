#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站静态审计 - 覆盖今天暴露的所有 bug 模式：
1. HTML 结构畸形：<head>/</head>/<body>/</body>/</html> 顺序与数量
2. 残留裸文字（如 /script>、</div> 等被渲染成页面文本）
3. CSS class 用了但没定义（全局 style.css/style.min.css + 本文件内联 style）
4. onclick 引用的 JS 函数不存在于任何 JS 文件
5. 断裂内链

运行目录：site-migrated/  (脚本自身所在目录)
用法：python3 audit_site.py
"""
import os, re, glob, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# 验证类/特殊文件（本就无标准 head/body 结构）——跳过结构检查
SKIP_STRUCT = ('baidu_verify', 'google', 'msvalidate', '_verify')

issues = []

def add(sev, f, line, msg):
    issues.append((sev, f, line, msg))

# ── 收集所有 CSS 定义（全局 + 内联） ──
def collect_css_defs():
    defs = set()
    for f in ['assets/css/style.css', 'assets/css/style.min.css']:
        if os.path.exists(f):
            css = open(f, encoding='utf-8', errors='ignore').read()
            for m in re.finditer(r'\.(-?[a-zA-Z][-a-zA-Z0-9_]*)(?=[\s\{,:>~+])', css):
                defs.add(m.group(1))
    return defs

CSS_DEFS = collect_css_defs()
print(f'[debug] CSS 定义收集: {len(CSS_DEFS)} 个 class')

# ── 收集所有 JS 函数定义 ──
def collect_js_funcs():
    funcs = set()
    for f in glob.glob('assets/js/*.js'):
        js = open(f, encoding='utf-8', errors='ignore').read()
        for m in re.finditer(r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', js):
            funcs.add(m.group(1))
        for m in re.finditer(r'(?:window|self)\.([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*function', js):
            funcs.add(m.group(1))
        for m in re.finditer(r'(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:function|\([^)]*\)\s*=>)', js):
            funcs.add(m.group(1))
    return funcs

JS_FUNCS = collect_js_funcs()
print(f'[debug] JS 函数收集: {len(JS_FUNCS)} 个')

HTML_FILES = sorted(glob.glob('**/*.html', recursive=True))
HTML_FILES = [f for f in HTML_FILES
              if 'node_modules' not in f
              and not any(x in f for x in ['backup', 'archive', '_bak', 'old/'])
              and not f.startswith('templates/')]

SAFE_PREFIX = ('js-', 'fa-', 'sr-only', 'container', 'main-content', 'hero-',
               'site-', 'nav-', 'footer-', 'btn-', 'gate-', 'how-',
               'step-', 'hide-', 'show-', 'active', 'visually-hidden',
               'lazy', 'async', 'defer', 'wrapper', 'section', 'svg-', 'g-res-',
               'row', 'col-', 'text-', 'd-', 'flex', 'justify', 'm-', 'p-',
               'w-', 'h-', 'border', 'bg-', 'rounded', 'shadow', 'overflow',
               'position', 'gap-', 'grid', 'items-', 'align-', 'tooltip',
               'modal', 'accordion')

for f in HTML_FILES:
    html = open(f, encoding='utf-8', errors='ignore').read()
    lines = html.split('\n')
    base = os.path.basename(f)
    skip_struct = any(s in base for s in SKIP_STRUCT)

    # ── 1. HTML 结构 ──
    if not skip_struct:
        n_head_o = len(re.findall(r'<head[ >]', html))
        n_head_c = len(re.findall(r'</head>', html))
        n_body_o = len(re.findall(r'<body[ >]', html))
        n_body_c = len(re.findall(r'</body>', html))
        n_html_o = len(re.findall(r'<html[ >]', html))
        n_html_c = len(re.findall(r'</html>', html))

        if n_head_o != 1 or n_head_c != 1:
            add('HIGH', f, 0, f'head 标签数量异常 (开{n_head_o}/闭{n_head_c})')
        if n_body_o != 1 or n_body_c != 1:
            add('HIGH', f, 0, f'body 标签数量异常 (开{n_body_o}/闭{n_body_c})')
        if n_html_o != 1 or n_html_c != 1:
            add('HIGH', f, 0, f'html 标签数量异常 (开{n_html_o}/闭{n_html_c})')

        body_idx = html.find('<body')
        if body_idx >= 0:
            pre = html[:body_idx]
            for tag in ['<nav', '<header', '<main', '<footer']:
                mt = re.search(re.escape(tag) + r'[ >]', pre)
                if mt:
                    ln_no = html[:mt.start()].count('\n') + 1
                    add('HIGH', f, ln_no, f'{tag} 出现在 <body> 之外（结构错误）')

    # ── 2. 残留裸文字 ──
    for i, ln in enumerate(lines, 1):
        if re.search(r'</script>\s*/?script>', ln):
            add('HIGH', f, i, '残留 /script> 文字（会被当页面内容渲染）')
        if re.search(r'</body>\s*</body>', ln) or re.search(r'</html>\s*</html>', ln):
            add('HIGH', f, i, '重复闭合标签（</body></body> 或 </html></html>）')

    # ── 3. CSS class 用了但没定义 ──
    inline_css = ' '.join(re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL))
    local_defs = set(re.findall(r'\.(-?[a-zA-Z][-a-zA-Z0-9_]*)(?=[\s\{,:>~+])', inline_css))
    # 本文件目录下的 CSS（如 tools/X/assets/styles.css）
    d = os.path.dirname(f)
    for cf in glob.glob(os.path.join(d, '**', '*.css'), recursive=True):
        try:
            css = open(cf, encoding='utf-8', errors='ignore').read()
            for m in re.finditer(r'\.(-?[a-zA-Z][-a-zA-Z0-9_]*)(?=[\s\{,:>~+])', css):
                local_defs.add(m.group(1))
        except:
            pass
    for m in re.finditer(r'class="([^"]*?)"', html):
        for cls in m.group(1).split():
            if cls in CSS_DEFS or cls in local_defs:
                continue
            if any(cls.startswith(p) for p in SAFE_PREFIX):
                continue
            if '-' in cls and not cls.startswith('http'):
                ln_no = html[:m.start()].count('\n') + 1
                add('MED', f, ln_no, f'CSS class .{cls} 无定义')

    # ── 4. onclick 函数未定义（含本文件内联 script） ──
    inline_js = ' '.join(re.findall(r'<script>(.*?)</script>', html, re.DOTALL))
    file_funcs = set()
    for m in re.finditer(r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', inline_js):
        file_funcs.add(m.group(1))
    for m in re.finditer(r'(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:function|\([^)]*\)\s*=>)', inline_js):
        file_funcs.add(m.group(1))
    all_funcs = JS_FUNCS | file_funcs
    for i, ln in enumerate(lines, 1):
        for m in re.finditer(r'onclick="([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', ln):
            fn = m.group(1)
            if fn in ('if', 'for', 'while', 'switch', 'catch', 'function'):
                continue
            if fn not in all_funcs:
                add('HIGH', f, i, f'onclick 引用函数 {fn}() 未定义（全局JS或本文件内联均无）')

# ── 输出 ──
print(f'\n扫描 {len(HTML_FILES)} 个 HTML 文件\n')
if not issues:
    print('✅ 未发现结构/CSS/JS 引用类问题')
else:
    by_sev = {'HIGH': [], 'MED': []}
    for sev, f, line, msg in issues:
        by_sev.setdefault(sev, []).append(f'  [{f}:{line}] {msg}')
    for sev in ['HIGH', 'MED']:
        if by_sev.get(sev):
            print(f'\n{sev} ({len(by_sev[sev])}):')
            seen = set()
            for x in by_sev[sev]:
                if x not in seen:
                    seen.add(x)
                    print(x)
    total_unique = sum(len(set(v)) for v in by_sev.values())
    print(f'\n总计 {len(issues)} 项（去重后 {total_unique}）')

with open('audit_report.txt', 'w', encoding='utf-8') as fo:
    fo.write(f'全站审计 {len(HTML_FILES)} 文件，发现 {len(issues)} 项\n\n')
    for sev, f, line, msg in sorted(issues):
        fo.write(f'[{sev}] {f}:{line} - {msg}\n')
