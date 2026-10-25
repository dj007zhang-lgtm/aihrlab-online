#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
close_all_clusters.py — 全站主题集群闭环（M1 供给加速器的内链工程）

目标：把每篇文章归位到唯一主枢纽，并注入「本文收录于 …」回链块。
集群闭环是主题权威能否累积的前提：spoke 不回链 pillar，权威就一直外泄。

纪律：
  - 幂等：已有回链的文章不重复注入；重复执行不产生副作用。
  - 零虚构：回链文案只用枢纽真实 h1 的简短别名 + 动态篇数，不编造。
  - 不碰桩页（noindex meta refresh 迁移页）、不碰 index.html。
  - 一篇文章最多归属 1 个主枢纽，避免权威稀释。

用法：
    python3 scripts/close_all_clusters.py           # 预览（dry-run）
    python3 scripts/close_all_clusters.py --apply   # 实际写入
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "articles")
HUB = os.path.join(ROOT, "hub")

APPLY = "--apply" in sys.argv

# ---------------------------------------------------------------- 枢纽定义
# key: hub 文件名(无扩展)   name: 注入文案用的简短别名   kw: 主题关键词（小写）
# 匹配优先级按 PRIORITY 顺序，越靠前越优先命中。
HUBS = {
    "big-tech-cases-hub": {
        "name": "大厂组织变革案例库",
        # 注意：勿用 "jd-"（会误伤 ai-jd-writing，JD=职位描述）与
        # "ant-"（会误伤 consultant 类词）；用完整专名替代。
        "kw": ["tencent", "alibaba", "ali-", "bytedance", "byte-", "baidu",
               "huawei", "jd-pinduoduo", "jingdong", "xiaomi", "meituan",
               "wangxing", "pinduoduo", "microsoft", "anthropic", "google",
               "meta-", "openai", "deepseek", "unitree", "didi", "kuaishou",
               "nvidia", "apple", "amazon", "netflix", "uber", "ant-group",
               "蚂蚁", "滴滴", "快手", "宇树", "英伟达"],
    },
    "ai-talent-recruiting": {
        "name": "AI 人才与招聘重构",
        "kw": ["recruit", "hiring", "interview", "selection", "sourcing",
               "校招", "招聘", "面试", "选才", "人才画像", "雇主品牌",
               "bigfive", "screening"],
    },
    "performance-management-hub": {
        "name": "绩效管理范式跃迁",
        "kw": ["performance", "kpi", "okr", "appraisal", "ninebox", "nine-box",
               "绩效", "考核", "评估", "九宫格", "职级", "薪酬", "compensation",
               "晋升", "激励"],
    },
    "talent-development-hub": {
        "name": "AI 时代人才发展体系",
        "kw": ["talent-development", "talent-develop", "competency", "learning",
               "succession", "leadership", "retention", "onboarding", "coach",
               "人才发展", "能力", "学习", "继任", "领导力", "保留", "培养",
               "培训", "胜任力", "技能", "skill"],
    },
    "org-diagnosis-hub": {
        "name": "组织诊断方法论",
        "kw": ["diagnosis", "ona", "network-analysis", "culture-debt",
               "组织诊断", "组织文化", "组织债务", "网络分析", "组织设计",
               "organizational-design", "agility"],
    },
    "ai-layoff-restructuring": {
        "name": "AI 裁员与组织减法",
        "kw": ["layoff", "flatten", "downsizing", "裁员", "扁平", "中层",
               "减法", "restructur"],
    },
    "ai-landing-playbook": {
        "name": "AI 落地实战手册",
        "kw": ["landing", "pilot", "digital-employee", "agent", "workflow",
               "toolbox", "prompt", "落地", "试点", "数字员工", "工作流",
               "工具", "提示词"],
    },
    "ai-native-org": {
        "name": "AI 原生组织范式",
        "kw": ["ai-native", "native-org", "intelligent-organization",
               "原生组织", "智能组织", "组织范式"],
    },
    "ai-org-transformation": {
        "name": "AI 组织变革全景",
        "kw": ["transformation", "change", "org-change", "transit",
               "组织变革", "转型", "变革", "adkar"],
    },
}

# 优先级：公司名优先（大厂案例库），否则按主题
PRIORITY = [
    "big-tech-cases-hub",
    "ai-talent-recruiting",
    "performance-management-hub",
    "talent-development-hub",
    "org-diagnosis-hub",
    "ai-layoff-restructuring",
    "ai-landing-playbook",
    "ai-native-org",
    "ai-org-transformation",
]

ANCHOR = "<!-- ★ 公众号二维码（CTA 固定文案）★ -->"

# 文案刻意不带具体篇数：枢纽页的 spoke 列表与本脚本的归位集合并不完全重合，
# 写死数字会与实际不符（违反零虚构纪律），且同枢纽不同文章会显示不同数字。
BLOCK = (
    '<div style="margin:2rem 0;padding:0.9rem 1.1rem;'
    'border-left:3px solid #5C8A2C;background:rgba(92,138,44,0.06);'
    'border-radius:6px;font-size:0.98rem;">'
    '📚 本文收录于 <a href="/hub/{slug}.html" '
    'style="color:#3F6212;font-weight:600;">{name}</a>'
    '（专题枢纽 · 同主题深度长文聚合）</div>\n'
)


def is_stub(html):
    """noindex + meta refresh 迁移桩页：不注入。"""
    return 'http-equiv="refresh"' in html or 'name="robots" content="noindex' in html


def match_text(path, html):
    """拼接文件名 + h1 作为匹配文本（小写）。

    刻意不纳入 meta description：描述里常顺带提及公司名/概念
    （如「敏捷HR实践」的摘要提到腾讯字节），会造成大范围误命中。
    实测纳入 description 时 big-tech 误收 43 篇中的大量非案例文章。
    """
    base = os.path.basename(path)
    m = re.search(r"<h1>(.*?)</h1>", html, re.S)
    h1 = re.sub(r"<[^>]+>", "", m.group(1)) if m else ""
    return (base + " " + h1).lower()


def hub_spoke_count(slug):
    """统计枢纽当前收录的真实文章数（用于回链文案的篇数）。"""
    p = os.path.join(HUB, slug + ".html")
    if not os.path.exists(p):
        return 0
    h = open(p, encoding="utf-8").read()
    return len(set(re.findall(r"/articles/([a-z0-9\-]+)\.html", h)))


def already_linked(html):
    """是否已有指向任意枢纽的回链块。"""
    return "📚 本文收录于" in html


def main():
    counts = {k: hub_spoke_count(k) for k in HUBS}
    files = sorted(f for f in os.listdir(ART)
                   if f.endswith(".html") and f != "index.html")
    assigned, skipped, matched = [], [], {}
    unresolved = []

    for f in files:
        path = os.path.join(ART, f)
        html = open(path, encoding="utf-8").read()
        if is_stub(html):
            continue
        if already_linked(html):
            skipped.append(f)
            continue
        text = match_text(path, html)
        fname = os.path.basename(path).lower()
        hit = None
        for slug in PRIORITY:
            # 大厂案例库极严：只在文件名命中公司名时收录，
            # 否则「敏捷HR实践」这类文章会因 h1 提及公司名被误收。
            src = fname if slug == "big-tech-cases-hub" else text
            if any(k in src for k in HUBS[slug]["kw"]):
                hit = slug
                break
        if not hit:
            unresolved.append(f)
            continue
        matched.setdefault(hit, []).append(f)

    # 先按归属结果更新篇数（注入后枢纽实际文章数）
    proj = {k: counts[k] + len(v) for k, v in matched.items()}
    for k in counts:
        proj.setdefault(k, counts[k])

    print("=== 集群归位预览 ===")
    for slug in PRIORITY:
        n = len(matched.get(slug, []))
        print(f"  {slug:<30} 现有回链 {counts[slug]:>3} → 新增 {n:>3} "
              f"(归位后 {proj[slug]:>3} 篇)")
    print(f"\n  已有回链跳过: {len(skipped)} 篇")
    print(f"  无关键词命中（待人工归位）: {len(unresolved)} 篇")
    for f in unresolved[:20]:
        print(f"      - {f}")
    if len(unresolved) > 20:
        print(f"      … 另 {len(unresolved)-20} 篇")

    if not APPLY:
        print("\n[dry-run] 未写入。加 --apply 执行。")
        return

    written = 0
    for slug in PRIORITY:
        for f in matched.get(slug, []):
            path = os.path.join(ART, f)
            html = open(path, encoding="utf-8").read()
            block = BLOCK.format(slug=slug, name=HUBS[slug]["name"])
            if ANCHOR in html:
                html = html.replace(ANCHOR, block + ANCHOR, 1)
            elif '<div class="article-footer-qr">' in html:
                html = html.replace('<div class="article-footer-qr">',
                                    block + '<div class="article-footer-qr">', 1)
            else:
                html = html.replace("</article>", block + "</article>", 1)
            open(path, "w", encoding="utf-8").write(html)
            written += 1
    print(f"\n✅ 已注入回链: {written} 篇")


if __name__ == "__main__":
    main()
