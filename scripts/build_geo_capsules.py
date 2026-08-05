#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_geo_capsules.py — GEO 胶囊去集中化批量注入（Task #419）

目标：向 52 个「缺 GEO 胶囊」文件中的 36 个真实文章注入 geo-answer-capsule，
降低 big-tech-ai-org-2026 独占 85.8% 页级 AI 引用的集中风险。

纪律：
- 胶囊文案（核心结论）严格取自该文自身 BLUF / 结论，零编造、不夸大。
- 仅注入真实文章；重定向桩页（http-equiv=refresh / window.location.replace）
  无 <header class="article-header">，脚本自动跳过。
- 注入位置：<article> 内 </header> 之后，与 big-tech-ai-org-2026 范式一致。
- 已含胶囊的文件跳过（幂等）。
"""
import os, re

ART = "articles"
SITE_ROOT = os.path.dirname(os.path.abspath("."))

# slug -> 核心结论（BLUF，40~70 字，严格取自原文自身结论）
CAPS = {
    "agent-interviewer-boundary-2026.html":
        "AI 面试的真正边界不在技术能力，而在责任归属：凡可标准化、留痕的环节（初筛、结构化初面、客观测评）AI 胜任；依赖隐性判断、情境权衡、伦理终审的环节必须留给人。",
    "ai-change-hr-heart.html":
        "AI 变革推不动，根源是没安住人心：算法、模型、方案再精准，也推不动一场真正的变革；过不了「安人心」这关，再好的技术都是纸老虎。",
    "ai-era-high-roi-4-things.html":
        "当大模型把执行门槛降到极低，「熟练」本身在贬值；真正带来长周期超额回报的，是建立局部语料库、沉淀体感、做那些难被一键生成的事。",
    "ai-hr-landing-3-high-roi-plays.html":
        "德勤 2026 覆盖 314 家企业的调研显示：85% 将 AI 列为 HR 核心驱动力，仅 6% 跑通端到端场景；AI 招聘（周期 -70%）与员工服务（事务量 -60%）是验证过的最高 ROI 切入点。",
    "ai-native-org-paradigm-map-2026.html":
        "AI 原生组织变革不是加一个 AI 部门，而是沿「增强→重构→删除→原生」四级上行；杠杆最高、也最少人做的是「删除」——删掉被智能体接管的协调层。",
    "ai-org-two-models-compare-2026.html":
        "两种组织的差别不在用多少 AI，而在组织网络的基本单元里谁坐在节点上：传统层级组织的节点只有人，AI 原生组织的节点上坐着人与智能体。",
    "ai-silent-org-signals.html":
        "越依赖 AI 做管理与汇报，组织信号通道越易被切断：真话层层过滤、只剩迎合；AI 的平滑化本能正在抹杀组织的痛觉与纠偏能力。",
    "ai-talent-profile-reconstruction-2026.html":
        "AI 没有让「人」变不重要，而是让「岗位」变不可靠；人才画像重构的本质，是把锚点从稳定岗位移到任务流与可验证技能（WEF 预测 2030 年 39% 核心技能将变化）。",
    "ant-group-ai-org-restructuring-2026.html":
        "2026 年 7 月蚂蚁收缩通用 AI 助手灵光、把筹码压给健康 AI 阿福，是一场 CFO 出身的 CEO 用 AI 重新分配组织资源的实验：通用赛道没水花，垂类更健康。",
    "bigtech-ai-reorg-2026.html":
        "大厂 AI 组织重构分真假：阿里通义 + 未来生活实验室合并打通研发布局，美团 AI Transformation 成一级部门——真做者是技术与场景同频，跟风者只换架构图。",
    "bytedance-7000-interns.html":
        "字节用 7000 名应届生批量生产可直接上岗的替代者：同样薪酬包宁愿招两个高潜应届生、不留干了 8 年的「熟练工」，大厂 HR 正在系统性「去经验化」。",
    "bytedance-performance-review-2026.html":
        "字节 2026 年 7 月绩效通知改了两件事：顶尖人才拿更大股权绑定、所有人按「业务产出 + 管理理念落地」双轴评估，绩效从算分奖金变成重布线人才利益分配。",
    "deepmind-no-kpi-talent-management.html":
        "DeepMind 以 1100 人冲上 9000 亿估值却不用传统 KPI，靠「科学领导力」——以研究影响力代替 KPI、以同行评议代替考核，是 AI 时代知识型组织的未来模板。",
    "deloitte-2026.html":
        "德勤 2026 报告覆盖 15 国 3000+ 企业 HR 高管：85% 认为组织适应能力至关重要，仅 7% 真正做到；差距不是能力问题，是结构性「知道但做不到」。",
    "digital-org-chart-2026.html":
        "静态架构图记录的是「谁该向谁汇报」的官方快照而非真实协作；数字化组织的真正形态，是一套不靠人画、靠系统流出的实时组织操作系统。",
    "disc-style-test-2026.html":
        "DISC 不是性格测验，而是「人在组织里如何推动事情」的行为地图；当协作网络的节点从清一色的人变成人与 AI，DISC 的价值在于重画人与智能体的分工边界。",
    "dri-kaifu-lisa-su.html":
        "李开复将 AI 进化分为工具→协作者→代理者三阶段，指出多数企业停留在「表演式 AI」；真正的分水岭是 AI 从帮人做事跨越到替人决策，支点角色是 DRI（直接责任人）。",
    "fat-donglai-you-cant-learn.html":
        "胖东来把近 40 亿资产利润全员分配、创始人持股降至 5%，用极致利益共同体清空管理内耗；「视人为人」不是文化口号，是对监控式 KPI 的暴力清零。",
    "global-tech-hr-ai-disruption-2026.html":
        "2026 年微软、Uber、IBM、Meta、谷歌集体重构 HR 部门：IBM 的 AskHR 已接管 200 个常规岗位、四年人力成本降 40%——AI 正成为 HR 的替代者而非工具。",
    "hr-bigfive-recruitment-screening.html":
        "大五人格（OCEAN）是招聘初筛中性价比最高、证据最充分的性格框架，但边界明确：它是早期信号而非终裁门槛，尽责性是跨岗位预测绩效最稳健的单一维度。",
    "hr-digital-employee-2026.html":
        "HR 数字员工不是又一块仪表盘，而是工作流执行权从「人操作软件」转移到「软件替人办事」；已在邀约、排面、合规合同等场景跑通，落地要跨过几道关。",
    "hr-handle-boss-ai-fever.html":
        "面对老板的 AI 狂热，HR 的破局不是硬顶也不是盲从，而是把强制 AI 指标翻译成可验证的业务场景、用试点数据替代口号，把焦虑接回组织真实能力。",
    "huawei-hr-leaders-history.html":
        "华为的核心竞争力不是产品技术，而是组织能力与人力资源体系；梳理 1987—2026 年历任 HR 一号位，最值得 AI 时代反复读的样本是「以岗定级、易岗易薪」的硬核工具。",
    "huoshui-plan-2026.html":
        "活水不是员工福利，是 AI 时代组织重新定价人才的一道闸门：能流向 AI 业务的筹码被保留、流不动的被 N+1 清出，开多大取决于公司对 AI 的渴求与冗余容忍度。",
    "karpathy-ai-replacement-test.html":
        "Karpathy 把 BLS 近 1.43 亿岗位扔给大模型做替代测试：被屏幕框住的「脑力劳动」（开发、分析、财务、编辑）最危险，安全区反而是当年不被看好的现场工作。",
    "mckinsey-2026-org-report-deep-dive.html":
        "麦肯锡《2026 组织状况报告》指出 86% 领导者承认组织未准备好将 AI 嵌入日常、约 2/3 认为组织过于复杂；破局要把「变革本身」作为永久运营模式。",
    "mckinsey-6-percent-trust-architecture.html":
        "麦肯锡 2025 研究：88% 企业已在用 AI、仅 6% 规模化落地，落差指向结构性判断——多数组织在用旧架构运行新能力；解法是把信任基线从「默认信人」迁到「默认先评估 AI」。",
    "meta-ai-code-75-percent.html":
        "Meta 在 2026 年 Q1 财报披露新代码 AI 生成占比达 75%，工程师集体转型为「AI 产品经理」——不再写代码，而是设计 AI 如何写代码，这是现在不是未来。",
    "sme-ai-hr-2026.html":
        "中小企业 AI+HR 的真实漏斗：97.4% 听说过、53.2% 试过、仅 33% 还在用；问题不在能力，在缺乏把试用变成日常的正式政策与场景化落地路径。",
    "tencent-319b-ali-3800b.html":
        "腾讯 319 亿、阿里 3800 亿的 AI 资本开支，买的是组织节点密度而非人头；HR 一号位的考卷，是把 Token 预算从执行层成本思维升级为战略层人才与算力配置思维。",
    "tencent-ai-lab-disbanded.html":
        "腾讯撤销近十年的独立 AI Lab、整体并入大模型体系，标志 AI 研发从「养士式离体研究」转向「实战式集中工程」；大模型不是算法突破，是工程的暴力。",
    "tencent-teg-cadre-activation.html":
        "腾讯组织变阵的核心不是裁员而是「干部激活」：2019 年裁撤约 10% 中干、2022 年绩效三档制、TEG 撤销 AI Lab 重组成大模型部，用组织手术刀应对 AI 时代。",
    "token-kpi-new-corporate-metrics.html":
        "「你今天消耗多少 Token」正成为大厂新问候语：微软将 AI 使用纳入绩效、阿里腾讯划定月度 Token 额度未达标扣绩效——AI 原生的工作方式靠强制指标而非自觉养成。",
    "unitree-flat-org-trap.html":
        "宇树以创始人兼 CEO/CTO 的极致扁平著称，但团队从百人迈向千人后「人多了效率更低」；硬科技创业公司的组织演进，需在扁平与必要层级间找到新平衡点。",
    "wangxing-meituan-management-talk.html":
        "王兴在美团 2000 人管理会上「暴力去熵」：要求别叫「兴哥」、用第一性原理拆穿精英幻觉，把几万人的组织从情感缓冲带改写成对着逻辑与数据开炮的专业零件。",
    "wwdc-2026-hr-insights.html":
        "WWDC 2026 的 Apple Intelligence 2.0 不是功能升级，而是管理范式迁移：当 AI Agent 能自主跨应用执行复杂任务，「管理」本身的意义正被重新定义，中间层首当其冲。",
    "ai-rebuild-training-coach-2026.html":
        "AI 重构培训，是把培训单元从「课程」拆成「在任务流中按需发生的教练时刻」——由 AI 据每人技能缺口实时生成、推送、陪练，而不是把旧课件塞进聊天框。",
    "ai-evaluation-split-2026.html":
        "AI 把评估拆成两半：一边验证 AI 能力（75% 招聘到 2027 年将测 AI 熟练度），一边保护独立人类判断（50% 组织到 2026 年底要求「无 AI」评估）；大多数企业连要测的能力都命名不清，真正的稀缺资产是组织判断权。",
}


CAPS_RE = re.compile(r'\n?\s*<div class="geo-answer-capsule">.*?</div>\n?', re.S)


def strip_existing(h):
    return CAPS_RE.sub("", h)


def inject(path, text):
    h = open(path, encoding="utf-8").read()
    if 'http-equiv="refresh"' in h or "window.location.replace" in h:
        return "stub"
    # 幂等：先清除任何位置的旧胶囊（含首版误置于站点 header 之外的），
    # 再注入正确位置。
    h = strip_existing(h)
    cap = (
        '    <div class="geo-answer-capsule">\n'
        '      <p class="geo-answer-capsule__label">核心结论</p>\n'
        f'      <p class="geo-answer-capsule__text">{text}</p>\n'
        '    </div>'
    )
    ai = h.find("<article")
    # 主锚点：文章自身的 <header class="article-header"> 闭合标签
    ah = h.find('<header class="article-header">')
    if ah >= 0:
        idx = h.find("</header>", ah)
        if idx >= 0:
            insert_at = idx + len("</header>")
            new = h[:insert_at] + "\n" + cap + h[insert_at:]
            open(path, "w", encoding="utf-8").write(new)
            return "injected"
    # 兜底锚点 A：首个 <figure class="article-banner"> 之前（覆盖裸 <header>/
    # <div class="article-header">/无 header 三类变体）
    bpos = h.find('<figure class="article-banner">', ai if ai >= 0 else 0)
    if bpos >= 0:
        new = h[:bpos] + cap + "\n" + h[bpos:]
        open(path, "w", encoding="utf-8").write(new)
        return "injected_before_banner"
    # 兜底锚点 B：</h1> 之后
    h1e = h.find("</h1>", ai if ai >= 0 else 0)
    if h1e >= 0:
        insert_at = h1e + len("</h1>")
        new = h[:insert_at] + "\n" + cap + h[insert_at:]
        open(path, "w", encoding="utf-8").write(new)
        return "injected_after_h1"
    return "no_anchor"


def main():
    done, skip = [], []
    for slug, text in CAPS.items():
        p = os.path.join(ART, slug)
        if not os.path.exists(p):
            print("MISSING FILE:", slug)
            continue
        r = inject(p, text)
        if r.startswith("injected"):
            done.append(slug)
            print("INJECTED", slug, "->", r)
        else:
            skip.append((slug, r))
            print("SKIP", slug, "->", r)
    print(f"\nDONE={len(done)} SKIP={len(skip)}")
    if skip:
        print("Skipped:", skip)


if __name__ == "__main__":
    main()
