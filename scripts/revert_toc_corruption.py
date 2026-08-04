#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回滚 build_toc_rail.py 的破坏性注入：从远程 main 还原所有含 toc-rail 的本地文章文件。
远程 main 含有全部历史原子推送（GEO 胶囊/内链等），不含本次损坏的 TOC，故还原只移除损坏。
"""
import os
import base64
import time
import urllib.request
import json

import git_atomic as ga

ROOT = ga.ROOT
ART = os.path.join(ROOT, "articles")


def fetch_remote(rel):
    req = urllib.request.Request(f"{ga.CONTENTS}/{rel}?ref={ga.BRANCH}")
    req.add_header("Authorization", f"Bearer {ga.TOKEN}")
    req.add_header("User-Agent", "aihr-sync")
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    return base64.b64decode(d["content"]).decode("utf-8")


def main():
    files = sorted(f for f in os.listdir(ART) if f.endswith(".html"))
    reverted = 0
    for fn in files:
        p = os.path.join(ART, fn)
        t = open(p, encoding="utf-8").read()
        if "toc-rail" not in t:
            continue
        remote = fetch_remote(f"articles/{fn}")
        open(p, "w", encoding="utf-8").write(remote)
        reverted += 1
        if reverted % 20 == 0:
            print(f"  reverted {reverted}...")
        time.sleep(0.3)
    print(f"✓ 已还原 {reverted} 个损坏文章文件（来自远程 main）")


if __name__ == "__main__":
    main()
