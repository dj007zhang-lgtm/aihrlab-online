#!/usr/bin/env python3
"""Scan articles/ for content articles missing a reference block.
Excludes: redirect stubs, the list page, and files already containing a references block.
"""
import os, re, json, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "articles")

# Load redirects.json to identify stubs
redirects = {}
rj = os.path.join(ROOT, "redirects.json")
if os.path.exists(rj):
    with open(rj, encoding="utf-8") as f:
        redirects = json.load(f)

stub_slugs = set(os.path.splitext(k.lstrip("/").split("/")[-1])[0] for k in redirects.keys() if k.startswith("/articles/"))

ref_re = re.compile(r'class="references"|参考来源')
h1_re = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
title_re = re.compile(r"<title>(.*?)</title>", re.S)

missing = []
already = []
for fn in sorted(os.listdir(ART)):
    if not fn.endswith(".html"):
        continue
    slug = fn[:-5]
    path = os.path.join(ART, fn)
    with open(path, encoding="utf-8") as f:
        c = f.read()
    if slug in stub_slugs:
        continue
    if fn == "index.html":
        continue
    # detect stub via http-equiv refresh
    if "http-equiv" in c and "refresh" in c and "articles/" in c:
        continue
    h1 = h1_re.search(c)
    h1 = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else ""
    if ref_re.search(c):
        already.append((slug, h1))
    else:
        missing.append((slug, h1))

print(f"TOTAL content articles (non-stub, non-index): {len(missing)+len(already)}")
print(f"ALREADY has references: {len(already)}")
print(f"MISSING references: {len(missing)}")
print("\n===== MISSING (slug | H1) =====")
for slug, h1 in missing:
    print(f"{slug}\t{h1}")
