#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_jsonld_20260927.py —— 修复 29 篇可索引文章残缺/缺失的 JSON-LD 结构化数据。

背景（2026-09-27 发布 QR Block v2 时被 qa_guardian 抓出）：
  - gate_tracking_metrics 报 JSON-LD 覆盖率从 baseline 100% 降到 88.4%（降 11.6pp）→ RED 阻断发布。
  - 实测确认：29 篇可索引文章含一段「裸 JSON 尾巴」（author/publisher/datePublished/
    mainEntityOfPage），但缺 @context 与 @type:Article 头部，且包裹它的 <script> 无
    application/ld+json 类型——搜索引擎不解析，等于无结构化数据。
  - 头部被剥疑为早前「清理 data-page-node-id 工件 / 去 Google Fonts」的连带损伤（与
    2026-09-09 commit 721d1390 同源）。

修复策略（确定性、零虚构）：
  1) 删除残缺片段：移除含 "datePublished" 且不含 application/ld+json 的 <script> 块。
  2) 注入完整合法 Article schema 到 <head>（在 </head> 前）：
     headline=og:title / description=meta description / image=og:image /
     datePublished=dateModified=<time datetime> / author+publisher=AIHR数智引擎 /
     mainEntityOfPage=canonical / isPartOf=站点 / inLanguage=zh-CN。
     不编 citation/keywords/articleSection（文章专属，避免虚构），minimal 合法 schema 即可满足 SEO/GEO。

幂等：若文件已含 application/ld+json 则跳过（不应发生，29 篇均不含）。
仅改 articles/ 下指定 29 篇，不碰其他文件。
"""
import re
import os
import sys
import json

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(SITE_ROOT, "articles")

TARGETS = """agent-interviewer-boundary-2026 agile-hr-practices-2026 ai-candidate-outreach-playbook-2026 ai-interview-arms-race-2026 ai-jd-writing-playbook-2026 ai-native-organizational-design-2026 ai-recruiting-analytics-playbook-2026 ai-recruitment-bias-compliance-2026 ai-resume-screening-playbook-2026 ai-structured-interview-playbook-2026 change-management-methodology-2026 change-resistance-diagnosis-2026 daily-tech-ai-2026-08 digital-transformation-org-capability-2026 employee-experience-design-2026 eu-ai-act-recruitment-compliance-2026 future-of-work-hr-2026 leadership-development-ai-era-2026 org-diagnosis-framework-2026 organizational-culture-debt-2026 organizational-culture-diagnosis-2026 organizational-design-agility-2026 organizational-network-analysis-ona-2026 performance-management-system-2026 recruitment-ai-fullstack remote-team-management-challenges-2026 talent-acquisition-strategy-2026 talent-development-framework-2026 team-effectiveness-framework-2026""".split()

NAMESPACE = "https://www.aihrlab.online"


def strip_broken(html):
    """移除含 datePublished 且非 application/ld+json 的 <script> 块（残缺 JSON 尾巴）。"""
    scripts = list(re.finditer(r'<script\b[^>]*>(.*?)</script>', html, re.S | re.I))
    out = html
    removed = 0
    for m in scripts:
        tag = m.group(0)
        inner = m.group(1)
        is_ldjson = bool(re.search(r'application/ld\+json', m.group(1), re.I)) or \
                   bool(re.search(r'type="application/ld\+json"', m.group(0), re.I))
        if is_ldjson:
            continue
        if '"datePublished"' in inner and '"mainEntityOfPage"' in inner:
            out = out.replace(tag, "")
            removed += 1
    return out, removed


def build_ld(headline, desc, img, date, canonical):
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": desc,
        "image": {
            "@type": "ImageObject",
            "url": img,
            "width": 1200,
            "height": 630,
        },
        "author": {
            "@type": "Organization",
            "name": "AIHR数智引擎",
            "url": f"{NAMESPACE}/about.html",
            "jobTitle": "AI时代组织变革研究者",
            "worksFor": {"@type": "Organization", "name": "AIHR数智引擎"},
        },
        "publisher": {
            "@type": "Organization",
            "name": "AIHR数智引擎",
            "logo": {
                "@type": "ImageObject",
                "url": img,
                "width": 512,
                "height": 512,
            },
        },
        "datePublished": date,
        "dateModified": date,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "isPartOf": {"@type": "WebSite", "name": "AIHR数智引擎", "url": f"{NAMESPACE}/"},
        "inLanguage": "zh-CN",
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def main():
    log = []
    for base in TARGETS:
        f = os.path.join(ARTICLES, f"{base}.html")
        if not os.path.exists(f):
            log.append(f"[SKIP] 不存在: {f}")
            continue
        html = open(f, encoding="utf-8").read()
        if re.search(r'application/ld\+json', html, re.I):
            log.append(f"[SKIP] 已含合法 JSON-LD: {base}")
            continue
        ogt = re.search(r'property="og:title"\s+content="([^"]+)"', html, re.I)
        desc = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html, re.I)
        ogimg = re.search(r'property="og:image"\s+content="([^"]+)"', html, re.I)
        tm = re.search(r'<time[^>]*datetime="([^"]+)"', html)
        canon = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html, re.I)
        if not (ogt and desc and ogimg and tm and canon):
            log.append(f"[SKIP] 缺必填字段: {base}")
            continue
        cleaned, removed = strip_broken(html)
        block = ('\n<script type="application/ld+json">' +
                 build_ld(ogt.group(1), desc.group(1), ogimg.group(1), tm.group(1), canon.group(1)) +
                 '</script>\n')
        if '</head>' in cleaned:
            cleaned = cleaned.replace('</head>', block + '</head>', 1)
        else:
            cleaned = cleaned.replace('</body>', block + '</body>', 1)
        open(f, "w", encoding="utf-8").write(cleaned)
        log.append(f"[OK] {base}: 删除残缺片段={removed}, 注入 JSON-LD")
    print("\n".join(log))
    print(f"\n处理文件数: {len(TARGETS)}")


if __name__ == "__main__":
    main()
