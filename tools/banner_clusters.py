# -*- coding: utf-8 -*-
"""
文章 banner 主题母题聚类映射 + 幂等插入引擎。
- 18 个主题簇，每簇 1 张母题 banner（assets/images/banners/<cluster>.png）
- 95 篇真实内容文章按主题归入对应簇（已排除 8 重定向桩页、3 试点、1 文章库列表页）
- 幂等：重复运行不会重复插入 <figure class="article-banner">
"""

# 簇 key -> (簇中文名, banner 文件名, [文章 slug 列表])
CLUSTERS = {
    "c01-china-bigtech-org": ("中国大厂AI组织重构", "c01-china-bigtech-org.png", [
        "alibaba-ai-org-restructuring-2026",
        "bigtech-ai-reorg-2026",
        "bytedance-160b-ai-org",
        "bytedance-doubao-org-engine-2026",
        "china-ai-org-three-routes",
        "jd-pinduoduo-ai-org-2026",
        "tencent-319b-ali-3800b",
        "tencent-ai-lab-disbanded",
        "xiaomi-2026-org-evolution",
        "unitree-flat-org-trap",
        "unitree-ipo-org-analysis",
        "wangxing-meituan-management-talk",
        "jimeng-organization-logic",
        "keling-ai-innovation-path",
    ]),
    "c02-talent-mobility-rotation": ("人才流动与轮岗机制", "c02-talent-mobility-rotation.png", [
        "huawei-hr-leaders-history",
        "tencent-huawei-hr-rotation-mechanism-2026",
        "tencent-huoshui-internal-mobility",
        "tencent-teg-cadre-activation",
        "bigtech-hr-rotation-2026",
        "didi-three-hr-leaders",
        "dingtalk-ceo-change-control-vs-empowerment",
    ]),
    "c03-bytedance-campus-context": ("字节校招与情境管理", "c03-bytedance-campus-context.png", [
        "bytedance-7000-interns",
        "bytedance-campus-7000",
        "bytedance-context-management-ai-agent",
    ]),
    "c04-ai-native-org": ("AI原生组织范式", "c04-ai-native-org.png", [
        "ai-native-org-hr-2026",
        "ai-native-org-paradigm-map-2026",
        "from-company-to-intelligent-organization",
        "anthropic-best-ai-company",
        "anthropic-danger-signals",
        "anthropic-engineer-three-stages",
        "openclaw-ai-agent-management",
        "kpi-failure-ai-org-restructure",
    ]),
    "c05-microsoft-decoupling": ("微软组织解耦与HR爆改", "c05-microsoft-decoupling.png", [
        "microsoft-ai-decoupling",
        "microsoft-anthropic-ai-org-restructure",
        "microsoft-cisco-ai-restructuring-2026",
        "microsoft-decoupling-openai-strategy",
        "microsoft-hr-system-overhaul",
        "microsoft-hr-transformation-ai-thinking",
    ]),
    "c06-meta-restructure": ("Meta组织重构与中层优化", "c06-meta-restructure.png", [
        "meta-300b-ai-layoff",
        "meta-ai-code-75-percent",
        "meta-ai-optimizes-middle-managers",
        "meta-layoffs-middle-managers",
        "meta-pod-structure",
    ]),
    "c07-ai-layoff": ("AI裁员与组织收缩", "c07-ai-layoff.png", [
        "AI裁员7飙到40你的公司在做减法还是乘法",
        "ai-layoff-2026-mid-year-review",
        "ai-layoff-230k-regret",
        "ai-layoff-manager-redefine",
        "ai-layoff-regret",
        "ai-layoff-to-rebuild-hr-stand-firm",
    ]),
    "c08-ai-governance-compliance": ("AI治理·合规·伦理", "c08-ai-governance-compliance.png", [
        "ai-governance-gap-hr-2026",
        "ai-hiring-fairness-compliance-2026",
        "ai-recruitment-bias-compliance-2026",
        "agent-interviewer-boundary-2026",
        "ai-bounded-rationality",
    ]),
    "c09-ai-recruitment-selection": ("AI招聘与选才", "c09-ai-recruitment-selection.png", [
        "ai-hr-jobs",
        "ai-recruitment-selection-guide-2026",
        "recruitment-ai-fullstack",
        "hr-bigfive-recruitment-screening",
    ]),
    "c10-mckinsey-report": ("麦肯锡组织报告解读", "c10-mckinsey-report.png", [
        "mckinsey-2026-org-report-deep-dive",
        "mckinsey-2026-organization-report",
        "mckinsey-2026-training-vs-screening",
        "mckinsey-6-percent-trust-architecture",
        "mckinsey-6pct-trust",
        "mckinsey-hidden-deadlock",
        "mckinsey-human-ai-orchestration",
    ]),
    "c11-consulting-reports": ("德勤·美世·IDC·德鲁克", "c11-consulting-reports.png", [
        "deloitte-2026",
        "mercer-2026",
        "idc-2026-hr-ai-agent-guide",
        "drucker-ai-era-answer",
    ]),
    "c12-ai-landing-change": ("AI落地失败与变革阻力", "c12-ai-landing-change.png", [
        "ai-landing-fails-org-not-changed",
        "ai-era-org-rigidity",
        "ai-change-hr-heart",
        "ai-silent-org-signals",
        "hr-handle-boss-ai-fever",
        "ai-era-hr-5-misalignments",
        "ai-hr-org-cluster",
    ]),
    "c13-hr-transformation-architect": ("HR转型与架构师角色", "c13-hr-transformation-architect.png", [
        "2026-hr-transformation-chief-architect",
        "ai-hr-2026-midyear-three-signals",
        "ai-hr-report-2026-context-management",
        "ai-hr-landing-3-high-roi-plays",
        "ai-era-high-roi-4-things",
        "human-ai-equation",
    ]),
    "c14-compute-infra-org": ("算力基建与组织演进", "c14-compute-infra-org.png", [
        "gtc2026-ai-infrastructure-org-evolution",
        "gtc2026-org-evolution",
        "wwdc-2026-hr-insights",
        "token-kpi-new-corporate-metrics",
    ]),
    "c15-musk-recursive": ("马斯克与递归进化", "c15-musk-recursive.png", [
        "musk-2026-ai-interview",
        "musk-2026-ai-recursive-evolution",
    ]),
    "c16-leadership-dri": ("领导力范式·DRI·天才团队", "c16-leadership-dri.png", [
        "dri-kaifu-lisa-su",
        "deepmind-no-kpi-talent-management",
        "fat-donglai-you-cant-learn",
        "karpathy-ai-replacement-test",
    ]),
    "c17-ai-tools-efficiency": ("AI工具与效能", "c17-ai-tools-efficiency.png", [
        "hr-ai-prompt-toolbox-21",
        "ai-coding-efficiency-org-evolution",
    ]),
    "c18-baidu-jobgrade": ("百度职级改革", "c18-baidu-jobgrade.png", [
        "baidu-tp-reform",
    ]),
}

# 反向索引：slug -> (簇key, banner文件名)
SLUG_TO_BANNER = {}
for key, (name, fname, slugs) in CLUSTERS.items():
    for s in slugs:
        SLUG_TO_BANNER[s] = (key, fname)

# 试点 3 篇（已上线，跳过；此处仅备案）
PILOT = {
    "big-tech-ai-org-2026": "big-tech-ai-org-2026.png",
    "ai-talent-profile-reconstruction-2026": "ai-talent-profile-reconstruction-2026.png",
    "ai-flatten-org-middle-managers-2026": "ai-flatten-org-middle-managers-2026.png",
}

# 排除：重定向桩页（无 H1 + http-equiv refresh）
EXCLUDE_STUBS = [
    "ai-layoff-subtraction-vs-multiplication",
    "ai-layoff-subtraction",
    "dingtalk-ceo-change",
    "kpi-failure",
    "meta-ai-layoffs-middle-managers",
    "microsoft-anthropic-org-restructuring-ai-era",
    "microsoft-openai-decoupling",
    "unitree-ipo-org-design",
]

# 排除：文章库列表页（自有英雄插画）
EXCLUDE_LISTING = ["index"]


def banner_for_slug(slug):
    """返回 (簇key, banner文件名) 或 None。"""
    return SLUG_TO_BANNER.get(slug)


if __name__ == "__main__":
    total = sum(len(v[2]) for v in CLUSTERS.values())
    print(f"簇数: {len(CLUSTERS)}")
    print(f"覆盖文章数: {total}")
    print(f"反向索引条目: {len(SLUG_TO_BANNER)}")
    all_slugs = [s for v in CLUSTERS.values() for s in v[2]]
    assert len(all_slugs) == len(set(all_slugs)), "存在重复 slug！"
    print("✓ 无重复 slug")
    for k, (n, f, sl) in CLUSTERS.items():
        print(f"  {k}: {n}  ({len(sl)}篇)")
