#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主题集群闭环：给每根 spoke 注入「回到枢纽」的回链，让权威汇聚到 pillar。

背景：枢纽页（hub）与文章（spoke）之间若只有单向链接，权威是外泄的——
  hub → spokes 只是导航，spokes → hub 才是权重回流的通道。
2026-09-14 大厂案例库闭环时，27 篇 spoke 里有 0 篇回链，集群一直是敞口的。

本脚本按集群配置注入回链，幂等（已含该枢纽链接的文件自动跳过）。
新增集群只需往 CLUSTERS 里加一段。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "articles")

CLUSTERS = [
    {
        "hub": "/hub/big-tech-cases-hub.html",
        "name": "大厂 AI 组织变革案例全景",
        "note": "27 篇深度案例横向对比",
        "spokes": [
            "bytedance-160b-ai-org.html",
            "bytedance-doubao-org-engine-2026.html",
            "bytedance-ai-native-org-case-2026.html",
            "bytedance-performance-reform-2026.html",
            "bytedance-campus-7000.html",
            "tencent-319b-ali-3800b.html",
            "tencent-huoshui-internal-mobility.html",
            "tencent-ai-org-huoshui-case-2026.html",
            "tencent-vs-bytedance-flat-2026.html",
            "tencent-ai-lab-disbanded.html",
            "tencent-teg-cadre-activation.html",
            "tencent-huawei-hr-rotation-mechanism-2026.html",
            "alibaba-ai-org-restructuring-2026.html",
            "alibaba-1-6-n-ai-restructure-2026.html",
            "alibaba-ai-midplatform-org-case-2026.html",
            "china-ai-org-three-routes.html",
            "baidu-tp-reform.html",
            "huawei-hr-leaders-history.html",
            "jd-pinduoduo-ai-org-2026.html",
            "wangxing-meituan-management-talk.html",
            "xiaomi-2026-org-evolution.html",
            "big-tech-ai-org-2026.html",
            "mckinsey-2026-organization-report.html",
            "mckinsey-2026-org-report-deep-dive.html",
            "anthropic-best-ai-company.html",
            "anthropic-engineer-three-stages.html",
            "microsoft-anthropic-ai-org-restructure.html",
        ],
    },
    {
        "hub": "/hub/talent-development-hub.html",
        "name": "AI 时代人才发展体系重构全景",
        "note": "16 篇按阶段编排的深度长文",
        "spokes": [
            "talent-development-framework-2026.html",
            "ai-native-talent-density-2026.html",
            "skills-graph-2026.html",
            "hr-skill-graph-2026.html",
            "skills-based-organization-2026.html",
            "ai-skills-based-org-2026.html",
            "talent-pricing-logic-2026.html",
            "ai-era-skill-rebuild-judgment-2026.html",
            "ai-cognitive-offloading-deskilling-2026.html",
            "ai-rebuild-training-coach-2026.html",
            "ai-organizational-learning-2026.html",
            "ai-succession-planning-2026.html",
            "ai-talent-profile-reconstruction-2026.html",
            "ai-talent-review-ninebox-2026.html",
            "ai-employee-retention-strategy-2026.html",
            "ai-era-employee-retention-2026.html",
        ],
    },
]


def make_block(hub, name, note):
    return (
        '<div style="margin:2rem 0;padding:0.9rem 1.1rem;border-left:3px solid #5C8A2C;'
        'background:rgba(92,138,44,0.06);border-radius:6px;font-size:0.98rem;">'
        f'📚 本文收录于 <a href="{hub}" style="color:#3F6212;font-weight:600;">{name}</a>'
        f'（{note}）</div>'
    )


def main():
    total_injected = 0
    for cl in CLUSTERS:
        hub, name, note = cl["hub"], cl["name"], cl["note"]
        block = make_block(hub, name, note)
        injected = skipped = missing = no_anchor = stub = 0
        for fn in cl["spokes"]:
            path = os.path.join(ART, fn)
            if not os.path.exists(path):
                missing += 1
                print("  MISSING  ", fn)
                continue
            html = open(path, encoding="utf-8").read()
            if 'http-equiv="refresh"' in html:
                stub += 1
                print("  SKIP(已合并为迁移桩)", fn)
                continue
            if hub in html:
                skipped += 1
                continue
            if '<div class="article-footer-qr">' in html:
                html = html.replace('<div class="article-footer-qr">',
                                     block + '\n<div class="article-footer-qr">', 1)
            elif '</article>' in html:
                html = html.replace('</article>', block + '\n</article>', 1)
            else:
                no_anchor += 1
                print("  NO_ANCHOR", fn)
                continue
            open(path, "w", encoding="utf-8").write(html)
            injected += 1
            print("  INJECTED", fn)
        print(f"\n[{name}] injected={injected} skipped={skipped} stub={stub} missing={missing} no_anchor={no_anchor}")
        total_injected += injected
    print(f"\n总注入: {total_injected} 篇")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
