#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atomic publish for ai-hr-three-pillar-model-2026 (6 files, one commit)."""
import git_atomic

FILES = [
    "articles/ai-hr-three-pillar-model-2026.html",
    "assets/images/banners/ai-hr-three-pillar-model-2026.webp",
    "assets/js/article-index.json",
    "articles/index.html",
    "sitemap.xml",
    "llms-full.txt",
]

MSG = "publish: AI 重排 HR 三支柱：事务瘦身，专家升维 (HR three-pillar model reweighted by AI)"

if __name__ == "__main__":
    sha = git_atomic.atomic_commit(FILES, MSG, dry_run=False, verbose=True)
    print("PUBLISHED_COMMIT", sha)
