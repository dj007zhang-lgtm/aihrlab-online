#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atomic publish for cross-cultural-team-management-2026 (overseas series #3)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_atomic

FILES = [
    "articles/cross-cultural-team-management-2026.html",
    "assets/images/banners/cross-cultural-team-management-2026.webp",
    "assets/js/article-index.json",
    "articles/index.html",
    "sitemap.xml",
    "llms-full.txt",
]

sha = git_atomic.atomic_commit(
    FILES,
    "publish: 跨文化团队：权力距离不靠翻译解决 (overseas #3)",
)
print("PUBLISHED COMMIT:", sha)
