#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atomic publish for strategic-workforce-planning-ai-2026 (8 site files)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_atomic as ga

FILES = [
    "articles/strategic-workforce-planning-ai-2026.html",
    "assets/images/banners/strategic-workforce-planning-ai-2026.webp",
    "assets/og-covers/og-strategic-workforce-planning-ai-2026.jpg",
    "assets/og-covers/og-strategic-workforce-planning-ai-2026.webp",
    "assets/js/article-index.json",
    "articles/index.html",
    "sitemap.xml",
    "llms-full.txt",
]

MSG = "publish: 战略人力规划失效：不是算不准，是算错对象 (SWP in agent era)"


def main():
    # sanity: all files exist on disk
    for f in FILES:
        p = os.path.join(ga.ROOT, f)
        assert os.path.exists(p), f"MISSING {f}"
        print(f"  ok {f} ({os.path.getsize(p)} bytes)")

    print("\n[dry-run] building objects without ref update...")
    sha = ga.atomic_commit(FILES, MSG, dry_run=True, verbose=False)
    print(f"[dry-run] orphan commit {sha[:12]} built OK")

    print("\n[real] atomic commit + PATCH refs/heads/main ...")
    sha = ga.atomic_commit(FILES, MSG, dry_run=False, verbose=True)
    print(f"\n=== PUBLISHED commit {sha} ===")


if __name__ == "__main__":
    main()
