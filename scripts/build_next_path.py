#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_next_path.py — 新访客转化路径模块「读完这篇，下一步」（P0-2，2026-09-21）

问题（来自 2026-09-21 渠道复盘）：
  新访客占 91.65%、跳出 92.89%、平均访问页数 1.2。文章页读完之后的全部出口只有两样：
  一个「本文收录于 XX 枢纽」的链接 + 一个公众号二维码。读者要么走、要么扫码，
  站内没有第二条路 —— 这是「单页消费」的直接成因。

做什么：
  为每篇部署文章静态注入一个四段式路径模块（真实内链，可被抓取、可被点击度量）：
    1) 同主题专题枢纽（优先取文章自带的「本文收录于」链接，无则按关键词回退映射）
    2) 2 篇同簇长文（同分类优先 + 标签重合度排序，排除自身，结果确定可重跑）
    3) 1 个在线自测（按主题关键词映射）
    4) 站内 AI 问答（/ask/，端点已在 qa-config.js 配置且实测可用）
  链接文字逐字取目标页 H1（守 Gate10 铁律）；不编造数字、不写营销腔文案。
  每个链接带 data-track="next_path_click" data-target-type="hub|article|assessment|copilot"，
  由 analytics-loader.js 统一采集 → 百度统计事件，用于回答「流量有没有转化」。

纪律：
  - 幂等：以 <!--NEXT_PATH_START--> / <!--NEXT_PATH_END--> 为界，重跑即替换，不叠加。
  - 只处理 sitemap 内的文章页（线上真实存在），孤儿页不动。
  - 只追加原子化事实注脚（分类/标签/工具类型），不做价值判断、不写号召语。

用法：
  python3 scripts/build_next_path.py --dry-run
  python3 scripts/build_next_path.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(BASE_DIR, "assets", "js", "article-index.json")
SITEMAP = os.path.join(BASE_DIR, "sitemap.xml")

START = "<!--NEXT_PATH_START-->"
END = "<!--NEXT_PATH_END-->"

# 主题 → 专题枢纽（仅在文章自身没有「本文收录于」链接时回退）
HUB_FALLBACK = [
    (("裁员", "重组", "人员优化"), "/hub/ai-layoff-restructuring.html"),
    (("大厂", "案例", "实践"), "/hub/big-tech-cases-hub.html"),
    (("人才", "发展", "培训", "学习", "继任"), "/hub/talent-development-hub.html"),
    (("招聘", "选才", "候选人", "面试"), "/hub/ai-talent-recruiting.html"),
    (("出海", "海外", "跨国"), "/hub/overseas-hr-hub.html"),
    (("绩效", "考核", "目标"), "/hub/performance-management-hub.html"),
    (("诊断", "盘点", "组织健康"), "/hub/org-diagnosis-hub.html"),
    (("ai 原生", "ai native", "原生组织"), "/hub/ai-native-org.html"),
    (("落地", "实施", "推行"), "/hub/ai-landing-playbook.html"),
]
DEFAULT_HUB = "/hub/ai-org-transformation.html"

# 主题 → 在线自测
ASSESS_FALLBACK = [
    (("替代", "风险", "岗位消失", "被 ai"), "/tools/ai-risk-test/index.html"),
    (("行为风格", "沟通", "团队协作", "disc"), "/tools/disc-test/index.html"),
    (("职业", "兴趣", "岗位匹配", "招聘"), "/tools/holland/index.html"),
    (("人格", "领导力", "性格"), "/tools/bigfive/index.html"),
    (("成熟度", "就绪", "诊断", "数字化"), "/tools/dri-self-assessment.html"),
    (("合规", "用工", "出海", "风险清单"), "/tools/compliance-dashboard.html"),
]
DEFAULT_ASSESS = "/tools/ai-risk-test/index.html"

COPILOT = "/ask/"


def h1_of(rel_path: str) -> str:
    """取目标页 H1 纯文本（链接文字必须与目标 H1 逐字一致）。"""
    full = os.path.join(BASE_DIR, rel_path.lstrip("/"))
    if not os.path.exists(full):
        return ""
    s = open(full, encoding="utf-8").read()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    if not m:
        return ""
    t = re.sub(r"<[^>]+>", "", m.group(1))
    return html.unescape(t).strip()


def deployed_articles() -> list:
    xml = open(SITEMAP, encoding="utf-8").read()
    out = []
    for loc in re.findall(r"<loc>(.*?)</loc>", xml, re.S):
        path = re.sub(r"^https?://[^/]+", "", loc.strip()).lstrip("/")
        if not path.startswith("articles/"):
            continue
        if os.path.exists(os.path.join(BASE_DIR, path)):
            out.append(path)
    return sorted(set(out))


def pick_hub(slug: str, meta: dict, body: str) -> str:
    m = re.search(r"本文收录于.{0,400}?href=\"(/hub/[^\"]+)\"", body, re.S)
    if m:
        return m.group(1)
    text = (meta.get("title", "") + " " + meta.get("category", "") + " " + " ".join(meta.get("tags", []))).lower()
    for keys, hub in HUB_FALLBACK:
        for k in keys:
            if k in text:
                return hub
    return DEFAULT_HUB


def pick_assess(meta: dict) -> str:
    text = (meta.get("title", "") + " " + meta.get("category", "") + " " + " ".join(meta.get("tags", []))).lower()
    for keys, tool in ASSESS_FALLBACK:
        for k in keys:
            if k in text:
                return tool
    return DEFAULT_ASSESS


def same_cluster(meta: dict, index: list, self_url: str, n: int = 2) -> list:
    """同分类优先，再按标签重合度排序；结果确定（可重跑复现）。"""
    tags = set(meta.get("tags", []) or [])
    cat = meta.get("category", "")
    scored = []
    for a in index:
        u = a.get("url", "")
        if u == self_url:
            continue
        a_tags = set(a.get("tags", []) or [])
        score = len(tags & a_tags) * 2
        if a.get("category", "") == cat:
            score += 3
        if not score:
            continue
        scored.append((-score, u, sorted(tags & a_tags), a))
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[:n]


def build_block(slug: str, meta: dict, body: str, index: list) -> str:
    hub = pick_hub(slug, meta, body)
    tool = pick_assess(meta)
    hub_h1 = h1_of(hub) or "专题枢纽"
    tool_h1 = h1_of(tool) or "在线自测"
    ask_h1 = h1_of("ask/index.html") or "站内问答"

    items = []
    items.append(
        '    <li class="next-path__item"><a class="next-path__link" href="%s" data-track="next_path_click" '
        'data-target-type="hub">%s</a><span class="next-path__note">专题枢纽 · 同主题深度长文聚合</span></li>'
        % (hub, html.escape(hub_h1))
    )
    for neg, u, shared, a in same_cluster(meta, index, slug):
        f = "articles/%s.html" % u
        if not os.path.exists(os.path.join(BASE_DIR, f)):
            continue
        title = h1_of(f) or a.get("title", "")
        note = "同主题长文" + (" · 共同标签：" + "、".join(shared[:2]) if shared else "")
        items.append(
            '    <li class="next-path__item"><a class="next-path__link" href="/articles/%s.html" '
            'data-track="next_path_click" data-target-type="article">%s</a>'
            '<span class="next-path__note">%s</span></li>' % (u, html.escape(title), html.escape(note))
        )
    items.append(
        '    <li class="next-path__item"><a class="next-path__link" href="%s" data-track="next_path_click" '
        'data-target-type="assessment">%s</a><span class="next-path__note">在线自测 · 免注册，结果本地计算</span></li>'
        % (tool, html.escape(tool_h1))
    )
    items.append(
        '    <li class="next-path__item"><a class="next-path__link" href="%s" data-track="next_path_click" '
        'data-target-type="copilot">%s</a><span class="next-path__note">站内 AI 问答 · 基于本站文章作答并附来源</span></li>'
        % (COPILOT, html.escape(ask_h1))
    )

    return (
        "%s\n"
        '<section class="next-path" aria-label="读完这篇之后的路径">\n'
        '  <h2 class="next-path__title">读完这篇，下一步</h2>\n'
        '  <ol class="next-path__list">\n%s\n  </ol>\n'
        "</section>\n%s" % (START, "\n".join(items), END)
    )


def inject(path: str, block: str, dry: bool) -> bool:
    full = os.path.join(BASE_DIR, path)
    s = open(full, encoding="utf-8").read()
    if START in s and END in s:
        a, b = s.index(START), s.index(END) + len(END)
        new = s[:a] + block + s[b:]
    else:
        anchor = s.find('<div class="article-footer-qr"')
        if anchor == -1:
            anchor = s.find("</article>")
        if anchor == -1:
            return False
        new = s[:anchor] + block + "\n" + s[anchor:]
    if new == s:
        return False
    if not dry:
        open(full, "w", encoding="utf-8").write(new)
    return True


def main():
    dry = "--dry-run" in sys.argv
    index = json.load(open(INDEX, encoding="utf-8"))
    by_url = {a.get("url"): a for a in index}
    pages = deployed_articles()
    changed, skipped = [], []
    for p in pages:
        slug = os.path.basename(p)[:-5]
        meta = by_url.get(slug)
        if not meta:
            skipped.append(p)
            continue
        body = open(os.path.join(BASE_DIR, p), encoding="utf-8").read()
        block = build_block(slug, meta, body, index)
        if inject(p, block, dry):
            changed.append(p)
    print(f"部署文章页：{len(pages)} | 注入/更新：{len(changed)} | 无索引元数据跳过：{len(skipped)} | dry-run={dry}")
    if skipped[:5]:
        print("  跳过示例：", skipped[:5])
    if not dry:
        with open(os.path.join(BASE_DIR, ".next_path_files.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(changed) + "\n")
    # 核验：链接文字是否等于目标 H1
    bad = 0
    for p in changed[:40]:
        s = open(os.path.join(BASE_DIR, p), encoding="utf-8").read()
        blk = s[s.index(START): s.index(END)] if START in s else ""
        for href, text in re.findall(r'href="([^"]+)"[^>]*>([^<]+)</a>', blk):
            tgt = href.lstrip("/") or "index.html"
            if tgt.endswith("/"):
                tgt += "index.html"
            th = h1_of(tgt)
            if th and html.escape(th) != text.strip():
                bad += 1
                print(f"  ⚠ 链接文字≠目标H1：{p} → {href} | '{text.strip()}' vs '{th}'")
    print(f"抽样 40 篇链接文字 vs 目标 H1 不一致：{bad}")


if __name__ == "__main__":
    main()
