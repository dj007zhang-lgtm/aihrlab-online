#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把站内指向「已合并页面」的引用，直接改写到各自的合并落点。

配合 consolidate_duplicate_pages.py 使用：合并脚本负责把页面本身变成迁移桩，
本脚本负责把站内还在指向它的链接改成直连真文，避免再出现一次跳转漏斗。

覆盖：HTML（任意深度）、assets/js JSON、llms*.txt、sitemap 之外的纯文本索引。
幂等。
"""
import os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REPOINT = {
    "ai-ceo-new-responsibility-2026.html": "/hub/ai-org-transformation.html",
    "ai-skill-rebuild-paradigm-2026.html": "/articles/skills-based-organization-2026.html",
    "ai-talent-assessment-revolution-2026.html": "/articles/ai-talent-review-ninebox-2026.html",
    "google-ai-org-experiment-2026.html": "/hub/big-tech-cases-hub.html",
    "google-ai-talent-strategy-2026.html": "/articles/talent-pricing-logic-2026.html",
    "org-resilience-ai-era-2026.html": "/hub/ai-native-org.html",
    "org-resilience-culture-compare-2026.html": "/articles/organizational-culture-diagnosis-2026.html",
    "org-transformation-cost-roi-2026.html": "/hub/ai-org-transformation.html",
    "skill-based-org-ai-pricing-2026.html": "/articles/skills-based-organization-2026.html",
}

# 不作为改写对象：历史留痕与内部台账，保留原始 URL 以免审计线索丢失
SKIP_DIRS = {"reports", ".git", "__pycache__", "node_modules"}
SKIP_SUFFIX = (".md", "_push_log.json", "publish-manifest.json", "redirects.json")


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith((".html", ".json", ".txt", ".xml")):
                continue
            if fn.endswith(SKIP_SUFFIX):
                continue
            yield os.path.join(dirpath, fn)


def main():
    pats = {k: re.compile(re.escape("/articles/" + k)) for k in REPOINT}
    changed, total = 0, 0
    per = {k: 0 for k in REPOINT}
    for path in walk(ROOT):
        base = os.path.basename(path)
        if base in REPOINT:
            continue  # 被合并页自身不动
        try:
            s = open(path, encoding="utf-8").read()
        except Exception:
            continue
        o = s
        for stub, rx in pats.items():
            s, n = rx.subn(REPOINT[stub], s)
            if n:
                per[stub] += n
                total += n
        if s != o:
            open(path, "w", encoding="utf-8").write(s)
            changed += 1
            print("  REPOINTED ", os.path.relpath(path, ROOT))
    print(f"\n引用改写：{total} 处，涉及 {changed} 个文件")
    print("\n=== 每个已合并页的引用收敛 ===")
    for k, v in per.items():
        print(f"  {v:>3} 处  {k}  ->  {REPOINT[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
