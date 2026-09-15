#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify local disk == real remote main (strict superset of remote + new article).

Fetches the authoritative remote main versions of the four sync targets and
compares the article set against local disk, so we never push local drift that
would drop or revert remote-only articles.
"""
import os, sys, json, base64, urllib.request, urllib.error, time
import git_atomic as ga

REPO = ga.REPO
BRANCH = ga.BRANCH
ROOT = ga.ROOT
TOKEN = ga.TOKEN
CONTENTS = ga.CONTENTS

NEW_SLUG = "strategic-workforce-planning-ai-2026"


def fetch_remote(rel, ref=None, tries=3):
    """Fetch a file from the real remote main. Returns decoded text or None."""
    url = f"{CONTENTS}/{rel}" + (f"?ref={ref}" if ref else "")
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {TOKEN}")
            req.add_header("User-Agent", "aihr-sync")
            req.add_header("Accept", "application/vnd.github+json")
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            if "content" in d:
                return base64.b64decode(d["content"]).decode("utf-8", "ignore")
            if "download_url" in d and d.get("size", 0) > 1000000:
                du = d["download_url"]
                req2 = urllib.request.Request(du)
                req2.add_header("Authorization", f"Bearer {TOKEN}")
                with urllib.request.urlopen(req2, timeout=120) as r2:
                    return r2.read().decode("utf-8", "ignore")
            return None
        except Exception as e:
            print(f"  [warn] fetch {rel} attempt {attempt}: {e}")
            time.sleep(2)
    return None


def get_head_sha():
    ref = ga._req("GET", f"refs/heads/{BRANCH}")
    return ref["object"]["sha"]


def local_article_slugs():
    adir = os.path.join(ROOT, "articles")
    return {f[:-5] for f in os.listdir(adir)
            if f.endswith(".html") and f != "index.html"}


def main():
    print("=== Baseline verification (real remote main authoritative) ===")
    head = get_head_sha()
    print(f"  remote HEAD = {head}")

    # Remote article-index.json
    idx_remote = fetch_remote("assets/js/article-index.json", ref=head)
    if idx_remote is None:
        print("  ERROR: cannot fetch remote article-index.json")
        sys.exit(2)
    remote_entries = json.loads(idx_remote)
    remote_slugs = {e["url"] for e in remote_entries}
    print(f"  remote article-index.json entries = {len(remote_entries)}")

    # Local disk article slugs
    local_slugs = local_article_slugs()
    print(f"  local disk article slugs      = {len(local_slugs)}")

    # The new article must be on disk but NOT in remote yet
    if NEW_SLUG not in local_slugs:
        print(f"  ERROR: new article {NEW_SLUG} NOT on local disk")
        sys.exit(2)
    if NEW_SLUG in remote_slugs:
        print(f"  WARN: new article {NEW_SLUG} already in remote (already published?)")
    else:
        print(f"  ok: new article {NEW_SLUG} on disk, not yet in remote")

    # Remote slugs must be a subset of local slugs (local is strict superset)
    missing_locally = remote_slugs - local_slugs
    if missing_locally:
        print(f"  ERROR: {len(missing_locally)} remote articles MISSING locally:")
        for s in sorted(missing_locally)[:20]:
            print(f"    - {s}")
        sys.exit(2)
    else:
        print(f"  ok: all {len(remote_slugs)} remote articles present locally (local is strict superset)")

    extra_local = local_slugs - remote_slugs
    print(f"  local-only slugs (should be just new article) = {sorted(extra_local)}")

    # sitemap + llms remote sanity
    sm = fetch_remote("sitemap.xml", ref=head)
    if sm:
        import re
        locs = re.findall(r"<loc>(.*?)</loc>", sm)
        print(f"  remote sitemap.xml <loc> count = {len(locs)}")
        new_url = f"https://www.aihrlab.online/articles/{NEW_SLUG}.html"
        print(f"  new url in remote sitemap? {new_url in locs}")
        nonascii = [l for l in locs if any(ord(c) > 127 for c in l)]
        print(f"  remote sitemap non-ASCII urls = {len(nonascii)}")
    else:
        print("  WARN: could not fetch remote sitemap.xml")

    print("=== Verification done ===")


if __name__ == "__main__":
    main()
