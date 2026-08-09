#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_references.py — 生成 references.json (slug -> [已核验信源])

数据源: reports/facts-ledger.md §6 已核验为真、且有真实 canonical URL 的报告。
映射: 按文章 category / tags 主题匹配, 只挂「议题相关」的已核验一手资料。
幂等: 可重跑, 覆盖式写出; 只输出命中 >=1 篇文章的 slug。

零虚构红线: 仅收录 WebSearch 核验过真实 URL 的报告;
Microsoft 纳德拉「私有评估集」无单一官方 URL, 已排除。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "assets", "js", "article-index.json")
OUT = os.path.join(ROOT, "assets", "js", "references.json")

# 12 条已核验报告 (Microsoft 纳德拉无官方 URL, 已排除)。
# topics 使用 article-index.json 中的精确 tag / category 字符串。
REPORTS = [
    {
        "key": "mckinsey-state-of-orgs-2026",
        "title": "The State of Organizations 2026",
        "publisher": "McKinsey & Company",
        "year": 2026,
        "url": "https://www.mckinsey.com/fi/our-insights/the-state-of-organizations",
        "topics": ["组织变革", "领导力", "组织扁平化", "敏捷组织"],
    },
    {
        "key": "mckinsey-hr-monitor-2026",
        "title": "HR Monitor 2026",
        "publisher": "McKinsey & Company",
        "year": 2026,
        "url": "https://www.mckinsey.com/tr/our-insights/hr-monitor",
        "topics": ["HR转型", "人才战略", "员工体验"],
    },
    {
        "key": "hr-partner-smb-ai-hr-2026",
        "title": "The State of AI in Small Business HR 2026",
        "publisher": "HR Partner",
        "year": 2026,
        "url": "https://hrpartner.io/state-of-ai-in-small-business-hr-2026",
        "topics": ["HR转型", "AI转型", "人才战略"],
    },
    {
        "key": "caict-xiaomi-ai-native-2026",
        "title": "智能原生研究报告（2026年）",
        "publisher": "中国信通院人工智能研究所 + 北京小米移动软件",
        "year": 2026,
        "url": "https://www.caict.ac.cn/kxyj/qwfb/ztbg/202604/P020260429600282400440.pdf",
        "topics": ["AI原生组织", "AI转型", "数字化转型"],
    },
    {
        "key": "pku-zhaopin-hr-trends-2026",
        "title": "新质驱动·组织向新——2026年人力资源管理趋势报告",
        "publisher": "北京大学国家发展研究院 + 智联招聘",
        "year": 2026,
        "url": "https://nsd.pku.edu.cn/sylm/xw/ee7d63a8784143eaa0d0bf3e79a93398.htm",
        "topics": ["HR转型", "人才战略", "员工体验", "技能优先"],
    },
    {
        "key": "szhrma-ai-hr-2026",
        "title": "AI时代人力资源发展报告（2026）",
        "publisher": "深圳市人力资源管理协会",
        "year": 2026,
        "url": "https://www.szhrma.com/renli888/vip_doc/30984267.html",
        "topics": ["HR转型", "AI转型", "人才战略"],
    },
    {
        "key": "infoq-ai-talent-org-2026",
        "title": "2026年中国企业AI人才与组织发展报告",
        "publisher": "InfoQ（极客邦科技）",
        "year": 2026,
        "url": "https://www.infoq.cn/article/UZTN39WZ81MhFteW9uDW",
        "topics": ["人才战略", "AI转型", "技能优先", "组织变革"],
    },
    {
        "key": "shrm-talent-trends-2026",
        "title": "2026 Talent Trends Report",
        "publisher": "SHRM",
        "year": 2026,
        "url": "https://www.shrm.org/in/about/press-room/shrm-unveils-2026-talent-trends-report--data-driven-insights-for",
        "topics": ["人才战略", "员工体验", "技能优先"],
    },
    {
        "key": "deloitte-hct-2026",
        "title": "2026 Global Human Capital Trends",
        "publisher": "Deloitte（与 Oxford Economics 合作）",
        "year": 2026,
        "url": "https://www.deloitte.com/us/en/about/press-room/deloitte-report-winning-organizations-will-build-the-human-advantage.html",
        "topics": ["人才战略", "HR转型", "员工体验", "组织变革"],
    },
    {
        "key": "wef-future-of-jobs-2025",
        "title": "Future of Jobs Report 2025",
        "publisher": "World Economic Forum",
        "year": 2025,
        "url": "https://www.weforum.org/publications/the-future-of-jobs-report-2025/",
        "topics": ["技能优先", "人才战略", "AI转型"],
    },
    {
        "key": "stanford-ai-index-2026",
        "title": "The 2026 AI Index Report",
        "publisher": "Stanford HAI",
        "year": 2026,
        "url": "https://aiindex.stanford.edu/",
        "topics": ["AI转型", "治理与伦理", "智能体", "大厂实践"],
    },
    {
        "key": "ccid-wangshang-micro-2026",
        "title": "AI时代小微经营者观察",
        "publisher": "赛迪智库中小企业研究所 + 网商银行",
        "year": 2026,
        "url": "https://h.xinhuaxmt.com/vh512/share/13169827",
        "topics": ["AI转型", "数字化转型"],
    },
]


# 每篇文章最多挂载的信源数 (相关性降序取前 N, 避免块过长显得 spam 且保诚实)
CAP = 6


def match_article(article):
    """返回该文章命中的报告列表 (按相关度降序取前 CAP 条)。

    相关度 = 报告 topics 与文章 tags/category 的重合数; 同分按 REPORTS 列表序
    (即人工设定的报告优先级) 升序。这样最贴合议题的报告优先入选,
    泛泛相关的报告 (如小微经营者观察) 在窄议题文章里自然落选。
    """
    tags = set(article.get("tags", []))
    if article.get("category"):
        tags.add(article["category"])
    scored = []
    for idx, r in enumerate(REPORTS):
        overlap = sum(1 for t in r["topics"] if t in tags)
        if overlap > 0:
            scored.append((overlap, idx, r))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [r for _, _, r in scored[:CAP]]


def main():
    if not os.path.exists(INDEX):
        print(f"[ERR] 找不到 {INDEX}", file=sys.stderr)
        sys.exit(1)
    with open(INDEX, encoding="utf-8") as f:
        articles = json.load(f)

    out = {}
    for a in articles:
        slug = a.get("url", "")
        if not slug:
            continue
        hits = match_article(a)
        if hits:
            out[slug] = [
                {
                    "title": r["title"],
                    "publisher": r["publisher"],
                    "year": r["year"],
                    "url": r["url"],
                }
                for r in hits
            ]

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    total_refs = sum(len(v) for v in out.values())
    print(f"[OK] 生成 {OUT}")
    print(f"     文章总数={len(articles)}  命中文章={len(out)}  信源挂载总数={total_refs}")
    # 每个报告的命中分布
    dist = {r["key"]: 0 for r in REPORTS}
    for v in out.values():
        keys = {x["url"] for x in v}
        for r in REPORTS:
            if r["url"] in keys:
                dist[r["key"]] += 1
    print("     报告命中分布:")
    for r in REPORTS:
        print(f"       - {r['title'][:34]:34s} -> {dist[r['key']]} 篇")


if __name__ == "__main__":
    main()
