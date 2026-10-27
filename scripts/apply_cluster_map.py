#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_cluster_map.py — 把 ci/cluster-map.json 的归属写进文章页。

与 close_all_clusters.py 的分工：
  close_all_clusters.py 是「关键词猜测 + 优先级命中」，命中不了就跳过，
  正因为如此才留下 88 篇孤儿。本脚本不做任何猜测——它只消费已经人工
  策展判定过的 cluster-map，把结果落到文章页。
  猜测归猜测（可废弃），判定归判定（是真相源）。

纪律：
  - 幂等：已有归属声明的页面不重写，重复执行零副作用。
  - 零虚构：枢纽显示名取自枢纽页真实 h1 的既定别名，取不到就不注入并报错，
    绝不编造名字。
  - 精确字面量替换 + 计数断言 + 字节对账，不用贪婪正则。
  - hub 为 null 的成员（刻意不归枢纽的页）跳过并记录，不算失败。
"""
import os
import re
import sys
import json
import subprocess

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip() or \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "ci", "cluster-map.json")
ART = os.path.join(ROOT, "articles")
HUB = os.path.join(ROOT, "hub")

# 枢纽 slug → 注入文案用的显示名。取自各枢纽页既用的别名，
# 与 close_all_clusters.HUBS 保持同名，避免同一枢纽出现两个叫法。
HUB_NAMES = {
    "big-tech-cases-hub": "大厂组织变革案例库",
    "ai-talent-recruiting": "AI 人才与招聘重构",
    "performance-management-hub": "绩效管理范式跃迁",
    "talent-development-hub": "AI 时代人才发展体系",
    "org-diagnosis-hub": "组织诊断方法论",
    "ai-layoff-restructuring": "AI 裁员与组织减法",
    "ai-landing-playbook": "AI 落地实战手册",
    "ai-native-org": "AI 原生组织范式",
    "ai-org-transformation": "AI 组织变革全景",
    "overseas-hr-hub": "出海 HR 与全球用工",
    "employee-experience-hub": "AI 时代的员工：体验、权利与劳动关系",
}

ANCHOR = "<!-- ★ 公众号二维码（CTA 固定文案）★ -->"
DECL_RE = re.compile(r'本文收录于.{0,400}?href="/hub/([^"]+?)\.html"', re.S)

BLOCK = (
    '<div style="margin:2rem 0;padding:0.9rem 1.1rem;'
    'border-left:3px solid #5C8A2C;background:rgba(92,138,44,0.06);'
    'border-radius:6px;font-size:0.98rem;">'
    '📚 本文收录于 <a href="/hub/{slug}.html" '
    'style="color:#3F6212;font-weight:600;">{name}</a>'
    '（专题枢纽 · 同主题深度长文聚合）</div>\n'
)


def inject(html, block):
    """返回 (新 html, 命中方式)。找不到任何锚点返回 (None, None)。"""
    if ANCHOR in html:
        return html.replace(ANCHOR, block + ANCHOR, 1), "qr-anchor"
    if '<div class="article-footer-qr">' in html:
        return html.replace('<div class="article-footer-qr">',
                            block + '<div class="article-footer-qr">', 1), "footer-qr"
    if "</article>" in html:
        return html.replace("</article>", block + "</article>", 1), "end-article"
    return None, None


def main():
    data = json.load(open(MAP, encoding="utf-8"))
    members = data["members"]
    unknown = set(v["hub"] for v in members.values() if v["hub"]) - set(HUB_NAMES)
    if unknown:
        print("❌ 以下枢纽在 HUB_NAMES 中没有登记，拒绝用编造的名字注入：")
        for u in sorted(unknown):
            print("   ", u)
        sys.exit(2)

    apply = "--apply" in sys.argv
    stats = {"already": 0, "injected": 0, "skipped_null": 0,
             "missing_page": 0, "no_anchor": 0, "changed": 0}
    no_anchor, changed = [], []

    for slug in sorted(members):
        entry = members[slug]
        hub = entry["hub"]
        path = os.path.join(ART, slug + ".html")
        if not os.path.exists(path):
            stats["missing_page"] += 1
            continue
        if hub is None:
            stats["skipped_null"] += 1
            continue

        html = open(path, encoding="utf-8").read()
        cur = DECL_RE.search(html)
        if cur:
            if cur.group(1) == hub:
                stats["already"] += 1
                continue
            # 现状与真相源冲突：记录但不擅自改（可能是历史有意决策）
            changed.append((slug, cur.group(1), hub))
            continue

        block = BLOCK.format(slug=hub, name=HUB_NAMES[hub])
        new, how = inject(html, block)
        if new is None:
            stats["no_anchor"] += 1
            no_anchor.append(slug)
            continue

        # 计数断言：必须恰好多出一个归属块
        if new.count("📚 本文收录于") != html.count("📚 本文收录于") + 1:
            print(f"❌ 计数断言失败（未恰好 +1 块）: {slug}")
            sys.exit(2)
        if len(new) != len(html) + len(block):
            print(f"❌ 字节对账失败: {slug}")
            sys.exit(2)

        if apply:
            open(path, "w", encoding="utf-8").write(new)
        stats["injected"] += 1

    print("=== 簇归属落盘 ===")
    print(f"  已有归属且一致（跳过）  : {stats['already']}")
    print(f"  本轮新注入              : {stats['injected']}")
    print(f"  刻意不归枢纽（跳过）    : {stats['skipped_null']}")
    print(f"  页面缺失                : {stats['missing_page']}")
    print(f"  找不到插入锚点          : {stats['no_anchor']}")
    print(f"  现状与真相源冲突（未改）: {len(changed)}")
    for s, old, new in changed:
        print(f"      {s}: 现状 {old} → 真相源 {new}")
    for s in no_anchor[:10]:
        print(f"      [无锚点] {s}")

    if not apply:
        print("\n[dry-run] 未写入。加 --apply 落盘。")


if __name__ == "__main__":
    main()
