#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R1 P2：为全站所有 HTML 页面注入防 FOUC 深色模式引导脚本。
- 脚本置于 <head> 紧随其后（在阻塞样式表之前同步执行），渲染前设 data-theme，杜绝先浅后暗闪。
- 幂等：文件已含 'aihr_theme'（即已注入）则跳过，可安全重跑。
- 仅当存在 '<head>' 时注入；无 head 的页跳过并报告。
"""
import os, sys

ROOT = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
SCRIPT = ('<script>(function(){try{var t=localStorage.getItem(\'aihr_theme\');'
          'if(!t){t=(window.matchMedia&&window.matchMedia(\'(prefers-color-scheme: dark)\').matches)?\'dark\':\'light\';}'
          'document.documentElement.setAttribute(\'data-theme\',t);}'
          'catch(e){document.documentElement.setAttribute(\'data-theme\',\'light\');}})();</script>')

def walk_html(root):
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith('.html'):
                yield os.path.join(dirpath, f)

def main():
    total=injected=skipped_done=skipped_nohead=0
    for path in walk_html(ROOT):
        total += 1
        try:
            txt = open(path, encoding='utf-8').read()
        except Exception as e:
            print(f"✗ 读取失败 {path}: {e}", file=sys.stderr); continue
        if 'aihr_theme' in txt:
            skipped_done += 1; continue
        if '<head>' not in txt:
            skipped_nohead += 1; continue
        # 在首个 <head> 之后插入引导脚本（同步、在样式表之前执行）
        new = txt.replace('<head>', '<head>\n' + SCRIPT + '\n', 1)
        if new == txt:
            skipped_nohead += 1; continue
        open(path, 'w', encoding='utf-8').write(new)
        injected += 1
        print(f"✓ 注入 {os.path.relpath(path, ROOT)}")
    print(f"\n总计扫描 {total} 个 HTML | 新注入 {injected} | 已存在跳过 {skipped_done} | 无<head>跳过 {skipped_nohead}")

if __name__ == '__main__':
    main()
