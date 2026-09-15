#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect the 17-article index gap and remote index json schema."""
import os, json, base64, urllib.request
import git_atomic as ga

ROOT = ga.ROOT
TOKEN = ga.TOKEN
CONTENTS = ga.CONTENTS
BRANCH = ga.BRANCH


def fetch(rel, ref):
    url = f"{CONTENTS}/{rel}?ref={ref}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", "aihr-sync")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    return base64.b64decode(d["content"]).decode("utf-8", "ignore")


def list_remote_articles(ref):
    url = f"{CONTENTS}/articles?ref={ref}&per_page=1000"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", "aihr-sync")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    return {e["name"][:-5] for e in d
            if e["name"].endswith(".html") and e["name"] != "index.html"}


def main():
    head = ga._req("GET", f"refs/heads/{BRANCH}")["object"]["sha"]
    idx_txt = fetch("assets/js/article-index.json", head)
    idx = json.loads(idx_txt)
    idx_slugs = {e["url"] for e in idx}
    print(f"remote index json entries = {len(idx)}")
    print(f"sample entry schema: {json.dumps(idx[0], ensure_ascii=False)}")
    print(f"entries have 'tags'? {all('tags' in e for e in idx)}")
    print(f"categories present: {sorted({e['category'] for e in idx})}")

    remote_articles = list_remote_articles(head)
    gap = sorted(remote_articles - idx_slugs)
    print(f"\n17 gap: {len(gap)} articles on main but NOT in index json:")
    for s in gap:
        print(f"  - {s}")

    # Does sitemap include these 17?
    sm = fetch("sitemap.xml", head)
    import re
    locs = set(re.findall(r"<loc>(.*?)</loc>", sm))
    in_sm = [s for s in gap if f"/articles/{s}.html" in locs]
    print(f"\n  of these, in sitemap: {len(in_sm)} / {len(gap)}")
    print(f"  sitemap total <loc> = {len(locs)}")


if __name__ == "__main__":
    main()
