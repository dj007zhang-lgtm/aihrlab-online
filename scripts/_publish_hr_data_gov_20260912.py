#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step [5]: atomic publish of hr-data-governance-2026 + 4-source sync.
Single commit, no intermediate state. Then Step [6] remote verify via api.github.com.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import git_atomic

FILES = [
    "articles/hr-data-governance-2026.html",
    "assets/images/banners/hr-data-governance-2026.webp",
    "assets/js/article-index.json",
    "articles/index.html",
    "sitemap.xml",
    "llms-full.txt",
]

MSG = "publish: HR data governance new function (hr-data-governance-2026) + four-source sync"

if __name__ == "__main__":
    sha = git_atomic.atomic_commit(FILES, MSG)
    print("COMMIT SHA:", sha)
    # Step [6] remote verify (authoritative, api.github.com)
    checks = {
        "articles/hr-data-governance-2026.html": "geo-answer-capsule",
        "assets/js/article-index.json": "hr-data-governance-2026",
        "articles/index.html": "hr-data-governance-2026",
        "sitemap.xml": "hr-data-governance-2026",
        "llms-full.txt": "hr-data-governance-2026",
        "assets/images/banners/hr-data-governance-2026.webp": None,
    }
    print("--- remote verify ---")
    for f, needle in checks.items():
        ok = git_atomic.verify_remote([f], needle=needle)
        print(f"  {f}: {ok[f]}")
    # Also confirm no non-ASCII (Chinese) URL residue in sitemap
    sm = git_atomic.verify_remote(["sitemap.xml"], needle=None)["sitemap.xml"]
    import base64, json, urllib.request
    # fetch raw to scan for non-ascii in <loc>
    req = urllib.request.Request(f"{git_atomic.CONTENTS}/sitemap.xml?ref={git_atomic.BRANCH}")
    req.add_header("Authorization", f"Bearer {git_atomic.TOKEN}")
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = base64.b64decode(json.loads(r.read())["content"]).decode("utf-8", "ignore")
    import re
    locs = re.findall(r"<loc>(.*?)</loc>", raw)
    nonascii = [l for l in locs if any(ord(c) > 127 for c in l)]
    print("  sitemap <loc> count:", len(locs), "| non-ASCII locs:", len(nonascii))
    print("PUBLISH + VERIFY DONE; commit", sha)
