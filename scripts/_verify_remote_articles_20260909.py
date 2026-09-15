#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List real remote main articles/ dir and compare slug sets with local disk."""
import os, json, urllib.request, time
import git_atomic as ga

ROOT = ga.ROOT
TOKEN = ga.TOKEN
CONTENTS = ga.CONTENTS
BRANCH = ga.BRANCH
NEW_SLUG = "strategic-workforce-planning-ai-2026"

EXPECT_NONASCII = "AI裁员7飙到40你的公司在做减法还是乘法"


def list_remote_articles(ref):
    url = f"{CONTENTS}/articles?ref={ref}&per_page=1000"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", "aihr-sync")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    return {e["name"][:-5] for e in d
            if e["name"].endswith(".html") and e["name"] != "index.html"}


def local_slugs():
    adir = os.path.join(ROOT, "articles")
    return {f[:-5] for f in os.listdir(adir)
            if f.endswith(".html") and f != "index.html"}


def main():
    head = ga._req("GET", f"refs/heads/{BRANCH}")["object"]["sha"]
    print(f"remote HEAD = {head}")
    remote = list_remote_articles(head)
    local = local_slugs()
    print(f"remote articles/ count = {len(remote)}")
    print(f"local  articles/ count = {len(local)}")
    missing_locally = remote - local
    extra_local = local - remote
    print(f"\nremote-only (on main, NOT on disk) = {len(missing_locally)}")
    for s in sorted(missing_locally):
        print(f"  - {s}")
    print(f"\nlocal-only (on disk, NOT on main) = {len(extra_local)}")
    for s in sorted(extra_local):
        flag = "  <-- NON-ASCII" if any(ord(c) > 127 for c in s) else ""
        print(f"  - {s}{flag}")
    # Check the suspicious chinese-slug file specifically
    print(f"\nSuspicious {EXPECT_NONASCII}.html exists on disk? "
          f"{os.path.exists(os.path.join(ROOT,'articles',EXPECT_NONASCII+'.html'))}")
    print(f"Suspicious file on remote main? {EXPECT_NONASCII in remote}")


if __name__ == "__main__":
    main()
