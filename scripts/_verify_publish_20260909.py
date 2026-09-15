#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Authoritative remote verification of the published commit (api.github.com, ?ref=sha)."""
import os, sys, json, base64, re, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_atomic as ga

TOKEN = ga.TOKEN
CONTENTS = ga.CONTENTS
BRANCH = ga.BRANCH
COMMIT = "ee7a776ccfd96849458c7d1a71b8d76c71c3f38a"
SLUG = "strategic-workforce-planning-ai-2026"
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"


def get(rel, ref=COMMIT, tries=4):
    u = f"{CONTENTS}/{rel}?ref={ref}"
    for a in range(1, tries + 1):
        try:
            req = urllib.request.Request(u)
            req.add_header("Authorization", f"Bearer {TOKEN}")
            req.add_header("User-Agent", "aihr-sync")
            req.add_header("Accept", "application/vnd.github+json")
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            if "content" in d:
                return base64.b64decode(d["content"]).decode("utf-8", "ignore")
            if "download_url" in d and d.get("size", 0) > 900000:
                with urllib.request.urlopen(d["download_url"], timeout=120) as r2:
                    return r2.read().decode("utf-8", "ignore")
            # image / binary: return raw bytes marker
            return "__BINARY__:" + str(d.get("size"))
        except Exception as e:
            print(f"  [warn] get {rel} attempt {a}: {e}")
            import time; time.sleep(2)
    return None


def main():
    print(f"=== Remote verify @ commit {COMMIT[:10]} ===")
    ok = True

    # HEAD check
    head = ga._req("GET", f"refs/heads/{BRANCH}")["object"]["sha"]
    print(f"  remote HEAD = {head[:10]}  (== published? {head == COMMIT})")
    if head != COMMIT:
        ok = False

    # 1. article
    art = get(f"articles/{SLUG}.html")
    assert art and art.startswith("<"), "article fetch failed"
    print(f"  [article] len={len(art)} em-dash={art.count('—')} nodeid={'data-page-node-id' in art}")
    for mod in ("geo-answer-capsule", "geo-stats", "geo-quote"):
        if mod not in art:
            print(f"    ✗ MISSING {mod}"); ok = False
    lds = [b for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', art, re.S)]
    types = []
    faq_n = 0
    cit_n = 0
    for b in lds:
        o = json.loads(b); types.append(o.get("@type"))
        if o.get("@type") == "FAQPage":
            q = o["mainEntity"]["questions"] if isinstance(o["mainEntity"], dict) else o["mainEntity"]
            faq_n = len(q)
        if o.get("@type") == "Article":
            cit_n = len(o.get("citation", []))
    print(f"  [article] JSON-LD types={types} FAQ={faq_n} citations={cit_n}")
    if faq_n != 6 or cit_n != 6 or "BreadcrumbList" not in types:
        print("    ✗ JSON-LD structure mismatch"); ok = False
    # internal links resolve on remote
    links = sorted(set(re.findall(r'href="/articles/([^"]+)\.html"', art)))
    print(f"  [article] internal links={len(links)}")
    for l in links:
        txt = get(f"articles/{l}.html")
        if not txt or not txt.startswith("<"):
            print(f"    ✗ broken internal link: {l}"); ok = False
    print(f"  [article] all {len(links)} internal links resolve: {'YES' if ok else 'NO'}")

    # 2. index json
    idx = json.loads(get("assets/js/article-index.json"))
    print(f"  [index json] entries={len(idx)} new present={any(e['url']==SLUG for e in idx)}")
    if len(idx) != 259 or not any(e["url"] == SLUG for e in idx):
        ok = False

    # 3. index html
    html = get("articles/index.html")
    cards = re.findall(r'<article class="article-card"', html)
    print(f"  [index html] cards={len(cards)}")
    for blk in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try: d = json.loads(blk.group(1))
        except: continue
        if isinstance(d, dict) and d.get("@type") == "CollectionPage":
            its = d["mainEntity"]["itemListElement"]
            p1 = its[0]
            print(f"  [index html] ItemList={len(its)} pos1={p1['name'][:18]} -> {p1['url'].split('/')[-1]}")
            if len(its) != 259 or p1["url"] != URL:
                ok = False
            break
    if len(cards) != 259:
        ok = False

    # 4. sitemap
    sm = get("sitemap.xml")
    locs = re.findall(r"<loc>(.*?)</loc>", sm)
    nonascii = [l for l in locs if any(ord(c) > 127 for c in l)]
    print(f"  [sitemap] locs={len(locs)} new present={URL in locs} non-ascii={len(nonascii)}")
    if URL not in locs or len(nonascii) > 0:
        ok = False

    # 5. llms
    ll = get("llms-full.txt")
    print(f"  [llms] ### 167 present={'### 167.' in ll} new url present={URL in ll}")
    if "### 167." not in ll or URL not in ll:
        ok = False

    # 6. images
    for img in [f"assets/images/banners/{SLUG}.webp",
                f"assets/og-covers/og-{SLUG}.jpg",
                f"assets/og-covers/og-{SLUG}.webp"]:
        r = get(img)
        print(f"  [img] {img}: {'OK' if r and r.startswith('__BINARY__') else 'MISSING'}")
        if not (r and r.startswith("__BINARY__")):
            ok = False

    print("\n=== REMOTE VERIFY:", "ALL GREEN ✅" if ok else "FAILURES ❌", "===")


if __name__ == "__main__":
    main()
