#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按「数据溯源三级标准」清理非文章页的无信源硬数字。

口径（项目既有铁律，不自创）：
  A 级 具名一手机构＋报告名＋日期且可验证 → 保留数字 + 补信源
  B 级 具名机构但数值无法验证           → 保留机构归属，删数字
  C 级 二手转引 / 无主聚合（"数据显示"） → 删除数字，改结构性论述

本批处理到的判决：
  · compare/* 与 brief/* 已有可见可点的逐条来源行（co-src / src），属审计误报，不改页面。
  · hub/ai-org-transformation 与 hub/performance-management-hub 保留公司公开披露的资本开支
    数字，并补标准信源块；删掉我们自己算的倍数对比（无公开基数可比）。
  · 其余页面数字皆为无归属转引或自家工具的估算占位，一律降级为非数值表述。

幂等：每处替换都带期望次数断言，重复运行不会再改。
usage: python3 scripts/fix_unsourced_numbers.py [--apply]
"""

import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY = "--apply" in sys.argv

SRC_BLOCK = (
    '<section class="verified-sources" aria-label="参考信源">'
    '<h2 class="verified-sources__title">参考信源</h2>'
    '<ul class="verified-sources__list">'
    '<li class="verified-sources__item"><span class="verified-sources__link">'
    '字节跳动、阿里巴巴对外披露的资本开支口径</span>'
    '<span class="verified-sources__meta">公司公告与财报电话会 · 2025</span></li>'
    '<li class="verified-sources__item"><span class="verified-sources__link">'
    '百度职级体系调整：废除 T/P/E 字母序列，改为数字单通道</span>'
    '<span class="verified-sources__meta">公开报道 · 2026 年 5 月</span></li>'
    '<li class="verified-sources__item"><span class="verified-sources__link">'
    '腾讯、华为、Anthropic 的组织调整公开动作</span>'
    '<span class="verified-sources__meta">公开披露 · 2025—2026</span></li>'
    '</ul></section>\n'
)

# (file, old, new, expect)
PATCHES = [
    # --- 冰山模型：自家工具的概念占比，不作外部事实陈述 ---
    ("assets/iceberg-model.html",
     "仅占真实成本的 ≈10%",
     "只占真实成本的一小部分", 1),
    # 同一张图里的教学用数字也是自家估算：去掉伪精度，保留洞察本身
    ("assets/iceberg-model.html",
     "⚡ HC减少20% ≠ 成本减少20%（隐性成本占比60%+）",
     "⚡ HC 减少的比例 ≠ 成本减少的比例（隐性成本占大头）", 1),
    ("products/iceberg-manual.html",
     "只盯薪资会漏掉 50%+ 的真实成本。",
     "只盯薪资会漏掉大部分真实成本。", 1),

    # --- MBTI：世界百强 89% 属无出处的行业传说（C 级），删数字 ---
    ("tools/mbti/index.html",
     "MBTI 在全球被广泛应用于招聘选拔、人岗匹配与团队建设（世界百强企业约 89% 曾引入）。",
     "MBTI 在全球被广泛应用于招聘选拔、人岗匹配与团队建设。", 1),

    # --- 术语词典：C 级改结构 / B 级留归属去数字 ---
    ("glossary/index.html",
     "数据显示多数企业在用AI却少立规矩（约80%在用、仅约23%立规），HR是AI伦理边界的守门人；",
     "多数组织已经在用 AI，但立下内部规矩的是少数，HR是AI伦理边界的守门人；", 1),
    ("glossary/index.html",
     "数据显示多数企业在用AI却少立规矩（约80%在用、仅约23%立规）；HR是AI伦理边界的守门人。",
     "多数组织已经在用 AI，但立下内部规矩的是少数；HR是AI伦理边界的守门人。", 1),
    ("glossary/index.html",
     "Deloitte 2026 显示 71% 员工已在做职责外工作、仅 24% 与同岗同做，岗位制已失灵；"
     "SBO 用技能图谱把人才系统转向动态能力。",
     "Deloitte 2026 的劳动力数据显示员工做职责外工作已成常态、同岗同做的比例很低，岗位制已失灵；"
     "SBO 用技能图谱把人才系统转向动态能力。", 1),
    ("glossary/index.html",
     "Deloitte 2026 显示 71% 员工已在做职责外工作、仅 24% 与同岗同做，岗位制已失灵；"
     "SBO 用技能图谱把人才系统从静态职衔转向动态能力，招聘与晋升不再被职衔绑架。",
     "Deloitte 2026 的劳动力数据显示员工做职责外工作已成常态、同岗同做的比例很低，岗位制已失灵；"
     "SBO 用技能图谱把人才系统从静态职衔转向动态能力，招聘与晋升不再被职衔绑架。", 1),
    ("glossary/index.html",
     "微软 Work Trend Index 2026 称组织因素贡献 AI 影响达 67%；HR 要定义人机职责边界",
     "微软 Work Trend Index 2026 称组织因素是决定 AI 影响大小的主要变量；HR 要定义人机职责边界", 1),
    ("glossary/index.html",
     "Mercer 2026 称完全落地的仅 1%——关键在共享分类法、技能映射与持续验证三件套，"
     "而非挂个技能本位招牌。",
     "Mercer 2026 称真正完全落地的仍是极少数，关键在共享分类法、技能映射与持续验证三件套，"
     "而非挂个技能本位招牌。", 1),

    # --- 专题枢纽：倍数对比是我们自己算的，去掉；75% 无托管方，降级 ---
    ("hub/ai-org-transformation.html",
     "字节2025年资本开支超1600亿元（约为同期百度的4倍、腾讯的2.5倍），",
     "字节2025年资本开支超1600亿元，", 1),
    ("hub/performance-management-hub.html",
     "字节2025年资本开支超1600亿元（约为同期百度的4倍、腾讯的2.5倍），",
     "字节2025年资本开支超1600亿元，", 1),
    ("hub/ai-org-transformation.html",
     "Meta用Pod结构（工程师创业式小团队）运转，AI代码占比已达约75%；",
     "Meta用Pod结构（工程师创业式小团队）运转，AI 已参与相当比例的代码产出；", 1),
    ("hub/performance-management-hub.html",
     "Meta用Pod结构（工程师创业式小团队）运转，AI代码占比已达约75%；",
     "Meta用Pod结构（工程师创业式小团队）运转，AI 已参与相当比例的代码产出；", 1),
    ("hub/ai-org-transformation.html",
     '<footer class="site-footer">',
     SRC_BLOCK + '<footer class="site-footer">', 1),
    ("hub/performance-management-hub.html",
     '<footer class="site-footer">',
     SRC_BLOCK + '<footer class="site-footer">', 1),

    # --- 原生组织枢纽：75% 无托管方 ---
    ("hub/ai-native-org.html",
     "当 AI 代码占比冲到 75%、当 Agent 被当作数字同事普遍配给",
     "当 AI 生成的代码占到新增代码的多数、当 Agent 被当作数字同事普遍配给", 1),

    # --- 大厂案例枢纽：86% 的具体口径归在具体文章里，此处只留机构判断 ---
    ("hub/big-tech-cases-hub.html",
     "麦肯锡把组织进化定义为永久运营模式（86% 企业 AI 准备不足）",
     "麦肯锡把组织进化定义为永久运营模式，并判断多数企业的 AI 准备度不足", 1),

    # --- 主题地图：能力地图的两个百分比无出处 ---
    ("hub/index.html",
     "人才发展的问题不在培训预算，而在能力地图缺位：仅 38% 组织有统一技能库、11% 建成技能架构。",
     "人才发展的问题不在培训预算，而在能力地图缺位：多数组织没有统一的技能库，"
     "建成完整技能架构的是少数。", 1),
]


def main():
    by_file = {}
    for f, old, new, exp in PATCHES:
        by_file.setdefault(f, []).append((old, new, exp))

    ok = fail = 0
    for f, items in by_file.items():
        path = os.path.join(ROOT, f)
        t = open(path, encoding="utf-8").read()
        before = t
        msgs = []
        for old, new, exp in items:
            # 幂等守卫：插入型改动（信源块）一旦已存在就必须跳过，
            # 否则重跑会在同一个 <footer> 前反复堆同一种区块。
            if old.startswith("<footer") and "verified-sources__list" in t:
                msgs.append("⤼ 跳过（信源块已存在，幂等守卫生效）")
                continue
            n = t.count(old)
            if n == exp:
                t = t.replace(old, new)
                ok += 1
                msgs.append("✓ %s… 命中 %d" % (old[:26], n))
            else:
                fail += 1
                msgs.append("✗ 期望 %d 命中却得到 %d：%s…" % (exp, n, old[:34]))
        print("### %s" % f)
        for m in msgs:
            print("    " + m)
        if APPLY and t != before:
            open(path, "w", encoding="utf-8").write(t)
            bytes_delta = len(t) - len(before)
            print("    已写入（%s%d 字节）" % ("+" if bytes_delta >= 0 else "", bytes_delta))

    print("-" * 60)
    print("替换成功 %d 处 / 失败 %d 处" % (ok, fail))
    print("模式：%s" % ("已写盘" if APPLY else "DRY-RUN（加 --apply 落盘）"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
