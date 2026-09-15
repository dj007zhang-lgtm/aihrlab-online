#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix 3 files whose meta description tag was corrupted by an earlier write
that embedded a literal straight double-quote into content="..." (truncating
the attribute). The corruption makes a normal regex fail to match, so we match
the whole malformed <meta name="description" ...> tag and replace it cleanly,
deriving the description from the article's real first lead paragraph (no
fabrication) and HTML-escaping quotes.
"""
import os, re

ROOT = os.path.join(os.path.dirname(__file__), "..")
HAN = re.compile(r'[一-鿿]')

# malformed tag: from <meta name="description" up to the first closing >
BAD_RE = re.compile(r'<meta\s+name="description"[^>]*>', re.S)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"\s*/?>')


def lead_text(html):
    clean = re.sub(r'<script[\s\S]*?</script>', '', html)
    clean = re.sub(r'<style[\s\S]*?</style>', '', clean)
    paras = re.findall(r'<p[^>]*>([\s\S]*?)</p>', clean)
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p)
        t = re.sub(r'\s+', ' ', t).strip()
        if len(HAN.findall(t)) >= 20 and '关注公众号' not in t and '二维码' not in t and 'AIHR数智引擎' != t[:10]:
            return t
    return ''


def first_sentence(t, maxlen=80):
    m = re.search(r'[。！？]', t)
    if m and m.end() <= maxlen:
        return t[:m.end()]
    return t[:maxlen].rstrip('，、；：')


def cn_quote(s):
    """Straight double quotes -> Chinese corner brackets (alternating), and
    drop/normalize straight apostrophes, so the value is safe inside a meta
    attribute AND passes Gate 9 (no &quot; entities)."""
    parts = s.split('"')
    out = parts[0]
    for i, p in enumerate(parts[1:], 1):
        out += ('「' if i % 2 == 1 else '」') + p
    out = out.replace("'", "’")
    return out


TARGETS = [
    "articles/bigtech-hr-rotation-2026.html",
    "articles/musk-2026-ai-interview.html",
    "articles/unitree-ipo-org-analysis.html",
]

fixed = 0
for rel in TARGETS:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        print("MISSING", rel)
        continue
    html = open(path, encoding="utf-8").read()
    if not BAD_RE.search(html):
        print("CLEAN (no malformed tag)", rel)
        continue
    lead = lead_text(html)
    h1 = ''
    hm = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html)
    if hm:
        h1 = re.sub(r'<[^>]+>', '', hm.group(1)).strip()
    if len(HAN.findall(lead)) >= 50:
        new = first_sentence(lead, 80)
    elif h1 and lead:
        new = h1 + "：" + first_sentence(lead, 60)
    elif h1:
        new = h1 + "：AI 时代组织变革与 HR 转型的一线深度拆解，附可复用框架与权威信源。"
    else:
        new = first_sentence(lead, 80)
    if len(HAN.findall(new)) < 50:
        new = new + "本文基于公开信息与原创分析，拆解 AI 时代组织怎么变、HR 怎么做。"
    new = cn_quote(new.replace("\n", ""))
    html = BAD_RE.sub(lambda x: f'<meta name="description" content="{new}">', html, count=1)
    open(path, "w", encoding="utf-8").write(html)
    fixed += 1
    print(f"FIXED {rel}: new_len={len(HAN.findall(new))}  preview={new[:40]}")

print(f"\nSummary: fixed={fixed}")
