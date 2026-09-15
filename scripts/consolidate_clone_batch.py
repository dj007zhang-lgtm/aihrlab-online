#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二批：合并剩余 24 篇「模板克隆」文章 + 同步改指站内引用。

依据（2026-09-15 全站段落指纹扫描）：
  25 篇文章共用同一套正文（14 个段落原文相同），每篇仅把首句换成自己的标题，
  属规模化模板内容（scaled content abuse）。保留正文母题页
  ai-as-transformative-agent-2026，其余 24 篇转为 noindex 迁移桩，
  并按各自标题语义路由到可信落点（真文 / 主题枢纽 / 资源卡），
  而不是像旧桩页那样统一丢到 /articles/ 列表页。

同时把站内仍在指向它们的引用直接改写到落点，避免二次跳转漏斗。
幂等。
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KEEP = "ai-as-transformative-agent-2026.html"  # 正文母题，保留

ROUTE = {
    "agent-era-org-structure-2026.html": "/hub/ai-native-org.html",
    "ai-collaboration-tools-matrix-2026.html": "/resources/hr-ai-use-case-prioritization.html",
    "ai-ethics-governance-enterprise-2026.html": "/articles/ai-governance-framework-2026.html",
    "ai-leadership-development-2026.html": "/hub/talent-development-hub.html",
    "ai-leverage-org-transformation-2026.html": "/hub/ai-org-transformation.html",
    "ai-native-org-forms-2026.html": "/hub/ai-native-org.html",
    "ai-native-org-practice-2026.html": "/hub/ai-native-org.html",
    "ai-native-recruitment-2026.html": "/hub/ai-talent-recruiting.html",
    "ai-performance-revolution-2026.html": "/hub/performance-management-hub.html",
    "ai-product-release-rhythm-2026.html": "/hub/big-tech-cases-hub.html",
    "ai-talent-war-2026.html": "/articles/talent-pricing-logic-2026.html",
    "ai-transformation-failures-2026.html": "/hub/ai-landing-playbook.html",
    "algorithm-fairness-audit-hr-2026.html": "/articles/eu-ai-act-recruitment-compliance-2026.html",
    "bigtech-ai-org-lessons-2026.html": "/hub/big-tech-cases-hub.html",
    "bigtech-ai-product-race-2026.html": "/hub/big-tech-cases-hub.html",
    "chro-ai-transformation-role-2026.html": "/hub/ai-org-transformation.html",
    "digital-employee-management-guide-2026.html": "/articles/hr-digital-employee-2026.html",
    "enterprise-ai-governance-framework-2026.html": "/articles/ai-governance-framework-2026.html",
    "hr-agent-practical-guide-2026.html": "/articles/hr-agent-landing-guide-2026.html",
    "hr-agent-roi-reality-2026.html": "/articles/hr-agent-landing-guide-2026.html",
    "hr-ai-transition-roadmap-2026.html": "/hub/ai-landing-playbook.html",
    "human-ai-boundary-2026.html": "/resources/human-ai-task-matrix.html",
    "human-ai-collaboration-models-2026.html": "/resources/human-ai-task-matrix.html",
    "hybrid-work-ai-enablement-2026.html": "/articles/remote-work-ai-era-2026.html",
}

STUB = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{target}">
<title>{title}</title>
</head>
<body>
<p>本文已合并，主题内容请见：<a href="{target}">{anchor}</a></p>
<script>location.href="{target}";</script>
</body>
</html>
"""

SKIP_DIRS = {"reports", ".git", "__pycache__", "node_modules"}
SKIP_FILES = {"redirects.json", "publish-manifest.json"}
SKIP_SUFFIX = ("_push_log.json", ".md")


def main():
    # 1) 落点校验
    bad = [t for t in ROUTE.values() if not os.path.exists(os.path.join(ROOT, t.lstrip("/")))]
    if bad:
        print("ABORT：以下落点不存在，请修正后再跑：")
        for b in bad:
            print("   ", b)
        return 1

    # 2) 转为迁移桩
    merged = skipped = 0
    for fn, target in ROUTE.items():
        p = os.path.join(ROOT, "articles", fn)
        if not os.path.exists(p):
            print("  MISSING  ", fn)
            continue
        cur = open(p, encoding="utf-8").read()
        if 'http-equiv="refresh"' in cur:
            skipped += 1
            print("  SKIP(已迁移)", fn)
            continue
        m = re.search(r"<title>(.*?)</title>", cur, re.S)
        title = (m.group(1).strip() if m else "页面已迁移").replace(" | AIHR数智引擎", "")
        open(p, "w", encoding="utf-8").write(
            STUB.format(target=target, title=f"{title}（内容已合并） | AIHR数智引擎",
                        anchor="合并后的主题内容")
        )
        merged += 1
        print(f"  MERGED  {fn}  ->  {target}")

    # 3) 站内引用改指
    pats = {k: re.compile(re.escape("/articles/" + k)) for k in ROUTE}
    changed = total = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn2 in filenames:
            if not fn2.endswith((".html", ".json", ".txt")):
                continue
            if fn2 in SKIP_FILES or fn2.endswith(SKIP_SUFFIX):
                continue
            if fn2 in ROUTE:
                continue
            path = os.path.join(dirpath, fn2)
            try:
                s = open(path, encoding="utf-8").read()
            except Exception:
                continue
            o = s
            for stub, rx in pats.items():
                s, n = rx.subn(ROUTE[stub], s)
                total += n
            if s != o:
                open(path, "w", encoding="utf-8").write(s)
                changed += 1
                print("  REPOINTED ", os.path.relpath(path, ROOT))

    print(f"\nSummary: merged={merged} skipped={skipped} | 引用改写 {total} 处 / {changed} 文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
