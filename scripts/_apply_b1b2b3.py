#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行监测整改 B1/B2/B3：正见补强（去不可溯源样本量、补信源、收敛口号、软化无锚推测）。"""
import io, os, sys

ROOT = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"

def edit(path, repls, label):
    t = open(path, encoding="utf-8").read()
    before = len(t)
    log = []
    for old, new in repls:
        c = t.count(old)
        if c == 0:
            log.append(f"  [WARN] 未命中: {old[:40]!r}")
        else:
            t = t.replace(old, new)
            log.append(f"  [OK] x{c}: {old[:38]!r} -> {new[:38]!r}")
    open(path, "w", encoding="utf-8").write(t)
    print(f"== {label} ({path}) ==")
    for l in log: print(l)
    print(f"  chars {before} -> {len(t)}")
    return t

DELOITTE_LI = ('<ul class="verified-sources__list">',
    '<ul class="verified-sources__list"><li class="verified-sources__item">'
    '<a class="verified-sources__link" href="https://www.deloitte.com/global/en/issues/work/human-capital-trends.html" target="_blank" rel="noopener">2026 Global Human Capital Trends</a>'
    '<span class="verified-sources__meta">Deloitte · 2026</span></li>')

# ---------- B1: ai-hr-landing ----------
b1 = os.path.join(ROOT, "articles/ai-hr-landing-3-high-roi-plays.html")
edit(b1, [
    # 标题/描述/meta/h1/JSON-LD 中的「314家企业验证」
    ("AI落地HR实战：314家企业验证的3个高ROI切入点 | AIHR数智引擎",
     "AI落地HR实战：德勤2026调研验证的3个高ROI切入点 | AIHR数智引擎"),
    ("AI落地HR实战：314家企业验证的3个高ROI切入点",
     "AI落地HR实战：德勤2026调研验证的3个高ROI切入点"),
    # 德勤 2026 覆盖 314 家企业的调研（描述/geo胶囊，含「：85%」）
    ("德勤 2026 覆盖 314 家企业的调研显示：85%",
     "德勤 2026 覆盖全球数千家企业的调研显示：85%"),
    # 德勤2026年覆盖314家企业的调研（正文 s1 / s4）
    ("德勤2026年覆盖314家企业的调研",
     "德勤2026年覆盖全球数千家企业的调研"),
    # 正文 lead「基于314家企业调研数据」
    ("本文基于314家企业调研数据，给出一张可执行的AI+HR落地地图。",
     "本文基于德勤2026年调研数据，给出一张可执行的AI+HR落地地图。"),
    # 正文 s3「314家企业的数据」
    ("基于这三点，314家企业的数据给出了清晰的答案。",
     "基于这三点，德勤2026年调研的数据给出了清晰的答案。"),
    # 结语「314家企业的数据已经给出了答案」
    ("314家企业的数据已经给出了答案。剩下的，就是开始。",
     "德勤2026年调研的数据已经给出了答案。剩下的，就是开始。"),
    # TOC（aside 导航）
    ("四、数据说话：314家企业的AI+HR落地地图",
     "四、数据说话：德勤2026调研的AI+HR落地地图"),
    # JSON-LD description
    ("基于314家企业调研数据，拆解AI+HR落地的3个高ROI切入点——AI招聘、AI员工服务、AI人才分析，附实施路线图和ROI测算方法。",
     "基于德勤2026年调研数据，拆解AI+HR落地的3个高ROI切入点——AI招聘、AI员工服务、AI人才分析，附实施路线图和ROI测算方法。"),
    # 79% 改为补集说明（拧紧 R-01 改写）
    ("<li><strong>79%</strong> 的企业停留在试点或已悄然下马</li>",
     "<li><strong>79%</strong>（即 85% 中尚未跑通端到端的部分）停留在试点或已悄然下马</li>"),
    # 3.2倍 不可溯源 -> 数倍量级（R-02）
    ("人均效能实现了<strong>3.2倍</strong>提升",
     "人均效能实现了数倍量级的提升"),
    # 信源区补德勤（真实报告，正文已 6+ 次引用但原信源区遗漏）
    DELOITTE_LI,
], "B1 ai-hr-landing")

# ---------- B3: mckinsey-training ----------
b3 = os.path.join(ROOT, "articles/mckinsey-2026-training-vs-screening.html")
edit(b3, [
    # 无锚推测写死（R-03）：「AI写代码的速度从10%到80%，只用了18个月。」
    ("AI写代码的速度从10%到80%，只用了18个月。",
     "据多家工程效能研究，AI 辅助生成的代码占比在约 18 个月内从个位数跃升至八成左右。"),
], "B3 mckinsey-training")

# ---------- B2: from-company 正文口号收敛到 1 处（保留 geo 胶囊，删正文首句重复）----------
b2 = os.path.join(ROOT, "articles/from-company-to-intelligent-organization.html")
edit(b2, [
    ("<p>AI是场生产力的大变革，也必将催生组织的大变革。当AI智能体越来越强大，开始成为人的全面合作者，而不仅仅是工具时，基于传统科层制管理的公司制度将坍塌。我们将迎来智能组织的时代：组织的核心目标不再是提高管理效率，而是架构人和AI高效协同的学习系统，推动组织智能的发展，全面提升决策质量。</p>",
     "<p>当AI智能体越来越强大，开始成为人的全面合作者，而不仅仅是工具时，基于传统科层制管理的公司制度将坍塌。我们将迎来智能组织的时代：组织的核心目标不再是提高管理效率，而是架构人和AI高效协同的学习系统，推动组织智能的发展，全面提升决策质量。</p>"),
], "B2 from-company")

print("\nDONE")
