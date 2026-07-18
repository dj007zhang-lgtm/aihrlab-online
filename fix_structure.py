#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站 HTML 结构一次性修复：
1. 删除残留的 /script> 裸文字（如 search.js 行末多出的 /script>）
2. 将 <body> 移到 </head> 之后，纠正 nav/header/script 在 body 之外的系统性结构错误
每个文件修改后即时做基础结构校验。
"""
import re, glob, os

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

SKIP = ('backup', 'node_modules', 'template')
VERIFY = ('baidu_verify', 'google', 'msvalidate', '_verify')

files = [f for f in glob.glob('**/*.html', recursive=True)
         if not any(x in f for x in SKIP)
         and not os.path.basename(f).startswith(tuple(VERIFY))]

fixed = []

for f in files:
    html = open(f, encoding='utf-8', errors='ignore').read()
    original = html
    changed = False

    # ── 修复 1：残留 /script> 裸文字 ──
    new = re.sub(r'(</script>)\s*/script>', r'\1', html)
    if new != html:
        html = new
        changed = True

    # ── 修复 2：body 位置规范化 ──
    head_close = html.find('</head>')
    body_open = html.find('<body')
    if head_close >= 0 and body_open > head_close:
        # 检查 head 和 body 之间是否有非空白内容（nav/header/script）
        between = html[head_close + len('</head>'):body_open]
        if between.strip():
            body_match = re.search(r'<body[^>]*>', html)
            if body_match:
                body_tag = body_match.group(0)
                # 删除原 body 标签
                html = html[:body_match.start()] + html[body_match.end():]
                # 在 </head> 后插入
                ins = head_close + len('</head>')
                html = html[:ins] + '\n' + body_tag + html[ins:]
                changed = True

    if changed:
        # 基础校验：tag 平衡
        n_body_o = len(re.findall(r'<body[ >]', html))
        n_body_c = len(re.findall(r'</body>', html))
        n_html_o = len(re.findall(r'<html[ >]', html))
        n_html_c = len(re.findall(r'</html>', html))
        if n_body_o != 1 or n_body_c != 1 or n_html_o != 1 or n_html_c != 1:
            print(f'  ⚠️  {f} 校验失败（标签不平衡），已跳过写入')
            continue
        open(f, 'w', encoding='utf-8').write(html)
        fixed.append(f)
        print(f'FIXED: {f}')

print(f'\n共修复 {len(fixed)} 个文件')
