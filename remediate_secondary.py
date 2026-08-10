#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Secondary remediation from全站体检 (audit):
   C3 dead anchors, C2 dup ids, A9 noopener, A6 alt, A8 lazy, D5 localStorage.
   Read-only safe: reversible via git. No gate-bypass; run quality+stability after.
"""
import os, re, glob, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

def read(p):
    return open(p, encoding='utf-8').read()
def write(p, s):
    open(p, 'w', encoding='utf-8').write(s)

report = []

# ---------------- C3 dead anchors: add missing id to heading ----------------
C3 = {
    "articles/ai-change-hr-heart.html": [
        ('<h2>AI变革的终极底气，是人心安，而非算法精</h2>',
         '<h2 id="ai变革的终极底气是人心安而非算法精">AI变革的终极底气，是人心安，而非算法精</h2>'),
    ],
    "articles/jimeng-organization-logic.html": [
        ('<h2>即梦Seedance 2.0：工程化暴力美学的组织样本</h2>',
         '<h2 id="即梦seedance-20工程化暴力美学的组织样本">即梦Seedance 2.0：工程化暴力美学的组织样本</h2>'),
    ],
}
for f, subs in C3.items():
    p = os.path.join(ROOT, f)
    if not os.path.exists(p):
        report.append(f"[C3] MISSING FILE {f}"); continue
    html = read(p); n = 0
    for a, b in subs:
        if a in html and b not in html:
            html = html.replace(a, b, 1); n += 1
        elif a not in html:
            report.append(f"[C3] {f}: anchor source heading not found -> {a[:30]}")
    if n:
        write(p, html); report.append(f"[C3] {f}: fixed {n} dead anchor target")

# ---------------- C2 dup ids: drop h2's duplicate id when section shares it ----------------
def fix_dup_id(path):
    html = read(path)
    section_ids = set(re.findall(r'<section[^>]*\bid="(s\d+)"', html))
    if not section_ids:
        return 0
    def repl(m):
        pre, n = m.group(1), m.group(2)
        if n in section_ids:
            return pre  # drop the duplicate id on the h2
        return m.group(0)
    new_html, k = re.subn(r'(<h2[^>]*?)\bid="(s\d+)"', repl, html)
    if k:
        write(path, new_html)
    return k

dup_files = []
for f in glob.glob(os.path.join(ROOT, "articles", "*.html")):
    h = read(f)
    sec = set(re.findall(r'<section[^>]*\bid="(s\d+)"', h))
    h2 = set(re.findall(r'<h2[^>]*\bid="(s\d+)"', h))
    if sec & h2:
        dup_files.append(f)
total = 0
for f in dup_files:
    k = fix_dup_id(f)
    total += k
if dup_files:
    report.append(f"[C2] removed {total} duplicate h2 ids across {len(dup_files)} files")

# ---------------- A9 noopener: add rel=noopener to target=_blank lacking it ----------------
def fix_noopener(path):
    html = read(path)
    def repl(m):
        tag = m.group(0)
        if 'rel=' not in tag:
            return tag[:tag.rfind('>')] + ' rel="noopener"' + tag[tag.rfind('>'):]
        if 'noopener' not in tag:
            return re.sub(r'(rel="[^"]*)"', r'\1 noopener"', tag, count=1)
        return tag
    new_html, k = re.subn(r'<a\b[^>]*\btarget="_blank"[^>]*>', repl, html)
    if k:
        write(path, new_html)
    return k

A9 = ["articles/ai-layoff-7-to-40.html"]
for f in A9:
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        k = fix_noopener(p)
        if k:
            report.append(f"[A9] {f}: added rel=noopener to {k} link(s)")

# ---------------- A6 alt: add alt="" to imgs missing it ----------------
def fix_alt(path):
    html = read(path)
    def repl(m):
        tag = m.group(0)
        if 'alt=' in tag:
            return tag
        return tag[:tag.rfind('>')] + ' alt=""' + tag[tag.rfind('>'):]
    new_html, k = re.subn(r'<img\b[^>]*>', repl, html)
    if k:
        write(path, new_html)
    return k

A6 = ["articles/ai-layoff-7-to-40.html"]
for f in A6:
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        k = fix_alt(p)
        if k:
            report.append(f"[A6] {f}: added alt to {k} image(s)")

# ---------------- A8 lazy: add loading=lazy to body imgs missing it (skip logo/hero) ----------------
def fix_lazy(path):
    html = read(path)
    def repl(m):
        tag = m.group(0)
        if 'loading=' in tag:
            return tag
        low = tag.lower()
        # skip above-the-fold / critical assets to protect LCP
        if 'logo-icon' in low or 'fetchpriority' in low or 'class="hero' in low or 'hero-' in low:
            return tag
        return tag[:tag.rfind('>')] + ' loading="lazy"' + tag[tag.rfind('>'):]
    new_html, k = re.subn(r'<img\b[^>]*>', repl, html)
    if k:
        write(path, new_html)
    return k

A8 = [
    "articles/microsoft-hr-system-overhaul.html",
    "articles/microsoft-hr-transformation-ai-thinking.html",
    "articles/musk-2026-ai-interview.html",
    "articles/musk-2026-ai-recursive-evolution.html",
]
for f in A8:
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        k = fix_lazy(p)
        if k:
            report.append(f"[A8] {f}: added loading=lazy to {k} image(s)")

# ---------------- D5 localStorage: safe wrapper in main.js ----------------
MP = os.path.join(ROOT, "assets/js/main.js")
if os.path.exists(MP):
    js = read(MP)
    wrapper = ('var safeLS=(function(){try{var s=window.localStorage;'
               'return{getItem:function(k){try{return s.getItem(k);}catch(e){return null;}},'
               'setItem:function(k,v){try{s.setItem(k,v);}catch(e){}},'
               'removeItem:function(k){try{s.removeItem(k);}catch(e){}}};}'
               'catch(e){return{getItem:function(){return null;},setItem:function(){},removeItem:function(){}};}})();\n')
    # replace all `localStorage.` / `localStorage[` with safeLS (wrapper uses window.localStorage internally, untouched)
    new_js = re.sub(r'\blocalStorage(\.|\])', r'safeLS\1', js)
    if new_js != js:
        # prepend wrapper at very top
        new_js = wrapper + new_js
        write(MP, new_js)
        report.append("[D5] main.js: wrapped localStorage in safeLS (Safari private-mode robust)")
    else:
        report.append("[D5] main.js: no raw localStorage usage found (already safe)")

print("\n".join(report) if report else "No changes made.")
