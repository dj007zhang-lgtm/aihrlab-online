# -*- coding: utf-8 -*-
"""
外科手术式修复 articles/ai-native-org-hr-2026.html 的信源层级伪装 + 张冠李戴。

问题诊断（2026-08-03 核验）：
1. 《全球AI Native组织全景报告》—— 逐字命中 siryzhang.github.io 个人 GitHub Pages
   页面（真名《全球 AI Native 组织全维度调研与全景报告》），是个人作品，
   站内却包装成"2026年4月发布的报告"，读者会误认为是机构研究。→ 信源层级伪装。
2. 腾讯云开发者社区《AI原生组织研究报告》—— 实为社区 UGC 文章
   《AI原生组织（AI-Native Organization）》(cloud.tencent.cn/developer/article/2670401)，
   其自身洞察还转引自 FT 中文网。站内升格为"研究报告"并称"两个独立来源交叉印证"。→ 伪装 + 伪交叉验证。
3. jimo.studio 发布《2026年中国企业AI人才与组织发展报告》—— 该报告实为
   InfoQ（极客邦科技）发布，1035 份有效样本。站内另一篇 ai-hr-2026-midyear-three-signals.html
   归因正确，两处打架。→ 张冠李戴。

替换信源（均已核验为真）：
- 中国信息通信研究院人工智能研究所 + 北京小米移动软件有限公司，《智能原生研究报告（2026年）》，2026年4月
  https://www.caict.ac.cn/kxyj/qwfb/ztbg/202604/P020260429600282400440.pdf
- 腾讯研究院历时一年对腾讯 CodeBuddy、月之暗面、出门问问、Anthropic、Block 等十余家团队的调研
  （公式：组织竞争力 = 人才密度 × AI杠杆 / 组织摩擦）
- InfoQ（极客邦科技），《2026年中国企业AI人才与组织发展报告》，1035 份有效样本
"""
import io
import sys

F = "articles/ai-native-org-hr-2026.html"
s = io.open(F, encoding="utf-8").read()
orig_len = len(s)
missing = []


def rep(old, new, label):
    global s
    if old not in s:
        missing.append(label)
        return
    s = s.replace(old, new, 1)


# ---------- 1. 第一性原理段：换掉个人 GitHub 页面，改挂信通院 ----------
rep(
    "<p>2026年4月发布的《全球AI Native组织全景报告》给出了一句判断："
    "真正的AI Native组织遵循着完全不同的第一性原理——它们直接围绕"
    "「人机协同（Human-AI Collaboration）」重构其业务逻辑、底层架构、"
    "核心人才梯队、激励机制与决策链路。报告把2025—2026的技术演进定义为"
    "全球AI「正式跨越基础模型阶段，全面迈入Agentic组织重构新纪元」。</p>",
    "<p>中国信息通信研究院人工智能研究所与北京小米移动软件有限公司在2026年4月"
    "联合发布的《智能原生研究报告（2026年）》给了一个定义：智能原生（AI-Native）是"
    "「以人工智能为根本驱动力的系统性范式革命，即从设计之初就以人工智能为核心驱动力"
    "构建的产品、企业或系统」。报告在结论处强调，这「不是技术工具的简单叠加，而是"
    "产业逻辑、发展范式与竞争生态的全方位跃迁」。</p>",
    "1-第一性原理段",
)

# ---------- 2. 腾讯云 UGC 段：换成信通院章节机制 + 腾讯研究院真实调研 ----------
rep(
    "<p>腾讯云开发者社区2026年5月的《AI原生组织研究报告》也持同一立场："
    "AI原生组织是「从基因层面重构企业架构，以AI为底座而非补丁」。"
    "两个独立来源在同一季度给出一致结论，说明这已不是概念炒作，"
    "而是开始有方法论沉淀的趋势。</p>",
    "<p>值得注意的是，信通院把「紧密人机协同：重塑协作网络与价值创造逻辑」"
    "单列为智能原生的核心机制之一。措辞是<strong>重塑协作网络</strong>，"
    "不是在旧协作网络上挂一个AI助手。</p>"
    "<p>腾讯研究院历时一年对腾讯CodeBuddy、月之暗面、出门问问、Anthropic、Block等"
    "十余家团队的深度调研，给出了一个更适合HR记住的表达式："
    "<strong>组织竞争力 = 人才密度 × AI杠杆 ÷ 组织摩擦</strong>。"
    "这个式子的残酷之处在分母——AI杠杆再大，只要审批链、部门墙、信息衰减这些"
    "摩擦项不动，放大出来的仍然接近于零。多数企业买工具是在动分子，"
    "而真正卡住他们的是分母，那恰好是HR的地盘。</p>",
    "2-腾讯云段",
)

# ---------- 3. 三大特征引导句：去掉"腾讯云报告提炼" ----------
rep(
    "<p>把「基因层面重构」落到可观察的组织特征上，腾讯云报告提炼出三条，"
    "它们互为支撑：</p>",
    "<p>把「范式革命」这种大词落到可观察的组织特征上，可以收敛成三条互为支撑的"
    "基因特征——它们分别重写了决策方式、效能公式和数据机制：</p>",
    "3-三特征引导句",
)

# ---------- 4. jimo.studio → InfoQ（极客邦科技） ----------
rep(
    "jimo.studio发布的《2026年中国企业AI人才与组织发展报告》基于1035份有效调研样本指出",
    "InfoQ（极客邦科技）发布的《2026年中国企业AI人才与组织发展报告》"
    "基于1035份有效调研样本指出",
    "4-jimo归因",
)

# ---------- 5. 特征三补信通院数据飞轮机制 ----------
rep(
    "这意味着HR设计流程时，要预留「可被数据修正」的接口，而不是追求一次性的完美SOP。</p>",
    "这意味着HR设计流程时，要预留「可被数据修正」的接口，而不是追求一次性的完美SOP。</p>"
    "<p>信通院报告给这个机制起的名字是「高效数据飞轮」——构建模型、数据、场景之间的"
    "自增强闭环。落到HR语言里：每一次员工纠正agent的动作，都应该是一次组织知识的沉淀，"
    "而不是一次被浪费的抱怨。</p>",
    "5-特征三补数据飞轮",
)

# ---------- 6. FAQ JSON-LD 中的假报告名 ----------
rep(
    "根据腾讯云开发者社区2026年《AI原生组织研究报告》，核心特征有三条：",
    "AI原生组织的核心特征可收敛为三条：",
    "6-FAQ归因",
)

# ---------- 7. 补参考来源区块 ----------
REFS = (
    '<p style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--line); '
    'color: var(--text-muted); font-size: 0.95rem;"><strong>参考来源：</strong>'
    "中国信息通信研究院人工智能研究所、北京小米移动软件有限公司，"
    "《智能原生研究报告（2026年）》，2026年4月；"
    "腾讯研究院关于AI原生团队的年度调研（覆盖腾讯CodeBuddy、月之暗面、出门问问、"
    "Anthropic、Block等十余家团队）；"
    "InfoQ（极客邦科技），《2026年中国企业AI人才与组织发展报告》（1035份有效样本）</p>"
)
ANCHOR = '<div class="article-footer-qr">'
if "参考来源" in s:
    missing.append("7-参考来源(已存在,跳过)")
elif ANCHOR in s:
    s = s.replace(ANCHOR, REFS + ANCHOR, 1)
else:
    missing.append("7-参考来源锚点缺失")

# ---------- 落盘 ----------
io.open(F, "w", encoding="utf-8").write(s)
print("file: %s  %d -> %d bytes" % (F, orig_len, len(s)))
print("missing anchors:", missing if missing else "NONE (all hit)")

# ---------- 残留自检 ----------
BAD = [
    "全球AI Native组织全景报告",
    "jimo.studio",
    "腾讯云开发者社区",
    "腾讯云报告",
    "《AI原生组织研究报告》",
    "两个独立来源",
]
print("\n--- residual scan ---")
bad_hit = False
for b in BAD:
    n = s.count(b)
    print(("  DIRTY " if n else "  clean ") + b + (" x%d" % n if n else ""))
    if n:
        bad_hit = True
sys.exit(1 if (missing or bad_hit) else 0)
