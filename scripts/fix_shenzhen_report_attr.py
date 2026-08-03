# -*- coding: utf-8 -*-
"""
修复站内「深圳报告」的归因缺失与一处虚构报告名。

问题诊断（2026-08-03 核验）：
1. articles/ai-layoff-to-rebuild-hr-stand-firm.html 引用
   "2026年4月发布的《2026企业人力资源AI应用白皮书》" —— 查无此报告，
   且无出版方。同文另有 5 处"深圳报告"指向真实存在的另一份报告。→ 虚构报告名。
2. 两篇文章通篇以"深圳报告"代称，从未点明正式名称与发布方，读者无法核验。→ 可核验性缺失。

真实信源（已四源交叉核验）：
  《AI时代人力资源发展报告（2026）》
  发布方：深圳市人力资源管理协会
  发布时间：2026年5月23日，深圳人才园
  主编：宋照礼（新加坡国立大学商学院副教授）
  编委会主任：曾晓华（协会会长）
  学术顾问：魏立群（香港浸会大学商学院）、陈晓（美国宾夕法尼亚州立大学劳动与雇佣关系学院）、
            贺前华（华南理工大学电子与信息学院）
  报告引用数据：全球约60%—70%的工作具备自动化潜力；约80%的职业中至少10%的任务
                可被大语言模型加速；含12大趋势判断。
  来源：深圳市人力资源管理协会官网 szhrma.com；深圳都市报 dutenews.com
"""
import io
import sys

REPORT = "《AI时代人力资源发展报告（2026）》"
missing = []


def fix(path, pairs, refs=None):
    s = io.open(path, encoding="utf-8").read()
    n0 = len(s)
    for old, new, label in pairs:
        if old not in s:
            missing.append("%s :: %s" % (path, label))
            continue
        s = s.replace(old, new, 1)
    if refs:
        anchor = '<div class="article-footer-qr">'
        if "参考来源" in s:
            missing.append("%s :: 参考来源(已存在,跳过)" % path)
        elif anchor in s:
            s = s.replace(anchor, refs + anchor, 1)
        else:
            missing.append("%s :: 参考来源锚点缺失" % path)
    io.open(path, "w", encoding="utf-8").write(s)
    print("  %s  %d -> %d bytes" % (path, n0, len(s)))
    return s


# ==================== 文件 1：ai-layoff-to-rebuild-hr-stand-firm ====================
F1 = "articles/ai-layoff-to-rebuild-hr-stand-firm.html"
REFS1 = (
    '<p style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--line); '
    'color: var(--text-muted); font-size: 0.95rem;"><strong>参考来源：</strong>'
    "深圳市人力资源管理协会，《AI时代人力资源发展报告（2026）》"
    "（主编：新加坡国立大学商学院宋照礼；2026年5月23日发布于深圳人才园）；"
    "北京大学国家发展研究院、智联招聘，"
    "《新质驱动·组织向新——2026年人力资源管理趋势报告》（2100余家企业调研，2026年4月21日）；"
    "OpenAI，《AI就业转型框架》（2026年4月）</p>"
)

pairs1 = [
    # 虚构报告名 → 真实报告
    (
        '2026年4月发布的《2026企业人力资源AI应用白皮书》显示，'
        '"多数企业完成HR系统线上布局，但AI深度渗透比例偏低"',
        "深圳市人力资源管理协会《AI时代人力资源发展报告（2026）》的判断是，"
        "当前多数企业的AI应用还停留在文档生成、数据分析这类浅层场景，"
        "真正完成组织设计、动态人才配置、能力图谱等组织级转型的并不多",
        "F1-虚构白皮书",
    ),
    # 首次出现的"深圳报告"补全正式名称与发布方
    (
        "<p>深圳报告还指出一个更底层的概念转变",
        "<p>这份由深圳市人力资源管理协会在2026年5月发布、"
        "新加坡国立大学商学院宋照礼教授主编的" + REPORT + "（下称「深圳报告」），"
        "还指出一个更底层的概念转变",
        "F1-深圳报告首现补名",
    ),
]

# ==================== 文件 2：ai-hr-2026-midyear-three-signals ====================
F2 = "articles/ai-hr-2026-midyear-three-signals.html"
REFS2 = (
    '<p style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--line); '
    'color: var(--text-muted); font-size: 0.95rem;"><strong>参考来源：</strong>'
    "深圳市人力资源管理协会，《AI时代人力资源发展报告（2026）》"
    "（主编：新加坡国立大学商学院宋照礼；2026年5月23日发布于深圳人才园）；"
    "InfoQ（极客邦科技），《2026年中国企业AI人才与组织发展报告》（1035份有效样本）；"
    "SHRM，《State of AI in HR 2026》（1908名HR专业人员调研，2026年3月）</p>"
)

pairs2 = [
    # 补样本量，增强可核验性
    (
        "InfoQ在《2026年中国企业AI人才与组织发展报告》中提出了"
        '"超级员工"的概念。',
        "InfoQ（极客邦科技）在基于1035份有效样本的"
        "《2026年中国企业AI人才与组织发展报告》中提出了"
        '"超级员工"的概念。',
        "F2-InfoQ补样本量",
    ),
    # 首现"深圳报告"补全正式名称与发布方
    (
        "<p>深圳报告还指出一个更底层的概念转变",
        "<p>深圳市人力资源管理协会2026年5月发布的" + REPORT
        + "（下称「深圳报告」，主编为新加坡国立大学商学院宋照礼教授）"
        "还指出一个更底层的概念转变",
        "F2-深圳报告首现补名",
    ),
    # 宋照礼职称精确化（副教授，非"教授"泛称）
    (
        "深圳报告主编、新加坡国立大学教授宋照礼在发布会上说",
        "深圳报告主编、新加坡国立大学商学院副教授宋照礼在发布会上说",
        "F2-宋照礼职称",
    ),
]

print("--- applying ---")
s1 = fix(F1, pairs1, REFS1)
s2 = fix(F2, pairs2, REFS2)

print("\nmissing anchors:", missing if missing else "NONE (all hit)")

print("\n--- residual scan ---")
bad_hit = False
for path, s in ((F1, s1), (F2, s2)):
    for b in ["2026企业人力资源AI应用白皮书", "新加坡国立大学教授宋照礼"]:
        n = s.count(b)
        print(("  DIRTY " if n else "  clean ") + "%-46s %s" % (b, path))
        if n:
            bad_hit = True

sys.exit(1 if (missing or bad_hit) else 0)
