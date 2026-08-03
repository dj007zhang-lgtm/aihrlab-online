# -*- coding: utf-8 -*-
"""
一次性修复：articles/ai-governance-gap-hr-2026.html 的信源张冠李戴。

问题：80% 用 AI / 仅 23% 立政策 这组数据被归给「深蓝君管理咨询《2026 AI+HR趋势观察报告》」，
      该机构与报告查无实据；站内 sme-ai-hr-2026.html 对同一组数据的归因才是正确的
      —— HR Partner《The State of AI in Small Business HR 2026》（英美澳 20–500 人中小企业）。
      同一组数字站内两处说法打架，属事实诚信硬伤。

已核验为真、无需改动的引用：
  - Littler 2026年4月雇主调查（54%/84%/68%/79% 等）
  - McKinsey《HR Monitor 2026》（中国 43% / 英国 39% / 美国 37% / 欧洲大陆 23%；
    10国、1303名HR专业人士、5501名员工，数据采集 2026年1月，2026年6月发布）
  - 麦肯锡 10-20-70 法则
  - 欧盟《AI 法案》Regulation 2024/1689
"""
import io
import sys

P = 'articles/ai-governance-gap-hr-2026.html'
h = io.open(P, encoding='utf-8').read()
orig_len = len(h)

missing = []


def rep(old, new, tag):
    global h
    if old not in h:
        print("  MISS[%s]" % tag)
        missing.append(tag)
        return
    h = h.replace(old, new)
    print("  ok  %s" % tag)


# ---- 1. 关键数据小标题：换掉虚构机构，补上真实信源 ----
rep('<h3>关键数据（据 Littler / 麦肯锡 / 深蓝君报告，2026）</h3>',
    '<h3>关键数据（据 HR Partner / Littler / 麦肯锡，2026）</h3>', 'kd-h3')

rep('<li><strong>80%</strong> 的 HR 团队已使用 AI 工具，仅 <strong>23%</strong> 制定了正式政策规范。</li>',
    '<li><strong>80%</strong> 的 HR 团队已使用 AI 工具，仅 <strong>23%</strong> 制定了正式政策规范'
    '（HR Partner 调研，样本为英美澳 20–500 人中小企业）。</li>', 'kd-li')

# ---- 2. 正文首段归因 ----
rep('这不是某家公司的个案。深蓝君管理咨询发布的《2026 AI+HR趋势观察报告》给出了一个警示性判断：'
    '<strong>80%的HR团队已在工作中使用AI工具，但仅有23%的企业制定了正式的政策规范。</strong>',
    '这不是某家公司的个案。HR Partner 发布的《The State of AI in Small Business HR 2026》'
    '调研了英美澳 20–500 人的中小企业，给出了一个警示性判断：'
    '<strong>80%的HR团队已在工作中使用AI工具，但仅有23%的企业制定了正式的政策规范。</strong>',
    'body-attr')

# ---- 3. 数据清单条目归因 ----
rep('<li><strong>深蓝君《2026 AI+HR趋势观察报告》：</strong>80%的HR团队在用AI，仅23%企业有正式政策。</li>',
    '<li><strong>HR Partner《The State of AI in Small Business HR 2026》'
    '（英美澳 20–500 人中小企业）：</strong>80%的HR团队在用AI，仅23%企业有正式政策。</li>', 'list-attr')

# ---- 4. 给 HR Monitor 条目补样本口径（真实数据，补齐可核验性） ----
rep('<li><strong>麦肯锡《HR Monitor 2026》：</strong>中国以43%的运营级AI采用率领先全球'
    '（英国39%、美国37%、欧洲大陆平均23%）。采用率高，但治理框架的成熟度未必同步。</li>',
    '<li><strong>麦肯锡《HR Monitor 2026》（10国、1303名HR专业人士与5501名员工，数据采集于2026年1月）：'
    '</strong>中国以43%的运营级AI采用率领先全球（英国39%、美国37%、欧洲大陆平均23%）；'
    '全球范围内仅28%的HR流程部署了可运营的AI方案，37%仍停留在试点。采用率高，但治理框架的成熟度未必同步。</li>',
    'hrmonitor-scope')

# ---- 5. meta / og / twitter：给 80% 加上归因，避免无限外推 ----
rep('<meta name="description" content="关键摘要：2026年，80%的HR团队已在工作中使用AI，'
    '但仅23%的企业制定了正式AI政策。这种「治理鸿沟」正在成为合规风险的核心来源。'
    '本文拆解鸿沟成因、2026全球监管时间表，并给出企业AI-HR治理的实操框架。">',
    '<meta name="description" content="关键摘要：据 HR Partner 2026 年调研，80%的HR团队已在工作中使用AI，'
    '但仅23%的企业制定了正式AI政策。这种「治理鸿沟」正在成为合规风险的核心来源。'
    '本文拆解鸿沟成因、2026全球监管时间表，并给出企业AI-HR治理的实操框架。">', 'meta-desc')

rep('<meta content="2026年，80%的HR团队已在工作中使用AI，但仅23%的企业制定了正式AI政策。'
    '这道57%的鸿沟正成为合规风险核心来源。" name="short-answer"/>',
    '<meta content="据 HR Partner 2026 年调研，80%的HR团队已在工作中使用AI，'
    '但仅23%的企业制定了正式AI政策。这道57个百分点的鸿沟正成为合规风险核心来源。" name="short-answer"/>',
    'short-answer')

# ---- 6. 补参考来源 ----
REFS = ('<p style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--line); '
        'color: var(--text-muted); font-size: 0.95rem;">'
        '<strong>参考来源：</strong>HR Partner,《The State of AI in Small Business HR 2026》；'
        'Littler,《2026 Annual Employer Survey》（2026年4月）；'
        'McKinsey &amp; Company,《HR Monitor 2026: A turning point for the people function》；'
        '欧盟《人工智能法案》(Regulation (EU) 2024/1689)</p>')

anchor = '<!-- 相关阅读 -->'
if anchor in h and '参考来源' not in h:
    h = h.replace(anchor, REFS + anchor, 1)
    print("  ok  refs")
else:
    print("  MISS[refs]")
    missing.append('refs')

if missing:
    print("\nFAILED, missing anchors: %s" % missing)
    sys.exit(1)

io.open(P, 'w', encoding='utf-8').write(h)
print("\nWROTE %s  (%d -> %d bytes)" % (P, orig_len, len(h)))

print("\n虚构信源残留自检：")
for token in ['深蓝君', '2026 AI+HR趋势观察报告']:
    n = h.count(token)
    print("  %-24s %s" % (token, ("RESIDUE x%d" % n) if n else "clean"))
