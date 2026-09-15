#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 10 篇「标题不同、正文逐字相同」的 doorway pages。

事实依据（2026-09-15 全站正文指纹扫描）：
  这 10 个文件的正文完全相同（各 1386 汉字），标题却各不相同，
  属于典型的 doorway / duplicate doorway page：对搜索引擎是明确的低质信号，
  会稀释域名整体评价，并吃掉本应用于真文的抓取预算。

处置：
  保留正文真正的母题 owning page（ai-as-transformative-agent-2026），
  其余 9 篇转为 noindex 迁移桩，并将 301/refresh 指向语义最近的可信落点
  （真文或主题枢纽），而不是像旧桩页那样统一丢到 /articles/ 列表页。

幂等：已迁移的页面会被识别并跳过。
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = "ai-as-transformative-agent-2026.html"  # 正文母题保留页

# 待合并页 -> 语义最近的可信落点
CONSOLIDATE = {
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

STUB_TEMPLATE = """<!DOCTYPE html>
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

ANCHORS = {
    "/hub/ai-org-transformation.html": "AI 组织变革：大厂范式拆解（主题枢纽）",
    "/hub/big-tech-cases-hub.html": "大厂 AI 组织变革案例全景（案例库）",
    "/hub/ai-native-org.html": "AI 原生组织范式与组织设计",
    "/articles/organizational-culture-diagnosis-2026.html": "组织文化诊断",
    "/articles/skills-based-organization-2026.html": "技能本位组织：岗位制失灵后怎么重搭",
    "/articles/ai-talent-review-ninebox-2026.html": "人才盘点：从能力建模到九宫格自动化",
    "/articles/talent-pricing-logic-2026.html": "人才定价逻辑：一个人值多少钱，岗位就怎么设计",
}


def main():
    # 落点必须真实存在，否则拒绝
    bad = [t for t in CONSOLIDATE.values() if not os.path.exists(os.path.join(ROOT, t.lstrip("/")))]
    if bad:
        print("ABORT：落点不存在：")
        for b in bad:
            print("   ", b)
        return 1

    done = skipped = 0
    for fn, target in CONSOLIDATE.items():
        p = os.path.join(ROOT, "articles", fn)
        if not os.path.exists(p):
            print("  MISSING  ", fn)
            continue
        cur = open(p, encoding="utf-8").read()
        if 'http-equiv="refresh"' in cur:
            skipped += 1
            print("  SKIP(已迁移)", fn)
            continue
        # 保留原标题用于迁移页 title，避免割裂外部引用
        m = re.search(r"<title>(.*?)</title>", cur, re.S)
        old_title = (m.group(1).strip() if m else "页面已迁移").replace(" | AIHR数智引擎", "")
        t = STUB_TEMPLATE.format(
            target=target,
            title=f"{old_title}（内容已合并） | AIHR数智引擎",
            anchor=ANCHORS.get(target, "合并后的主题页"),
        )
        open(p, "w", encoding="utf-8").write(t)
        done += 1
        print(f"  MERGED  {fn}  ->  {target}")

    print(f"\nSummary: merged={done} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
