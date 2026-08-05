#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标题修复脚本（一次性清理历史债，配合 check_title_consistency.py）
==============================================================
策略（围绕目标：SERP 标题必须完整、≤28 字、且保留原意，禁止物理截断）：
  1. 词中截断标题：title_core 改为 H1 全文（若 H1 ≤ 28 字，零语义损失）；
     若 H1 > 28 字，用 CRAFTED 字典里的【重写】版本（保留核心钩子，非砍半句）。
  2. 所有 articles/ 页面：og:title 对齐到 title_core（消除 title/og 偏离 WARN）。
  3. 引号清洗：title_core / og:title 中的英文双引号 " 转为「」。

实现：仅做精确字符串替换（整段 <title>...</title> 与 og:title content），
不解析、不重写 HTML 结构，避免结构性损坏。改完请用 validate_article.py 复核。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_title_consistency as tc

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(SITE_ROOT, "articles")

# H1 > 28 字的文件：人工重写的完整标题（≤28，保留核心钩子，非截断）
CRAFTED = {
    "didi-three-hr-leaders.html": "滴滴三任HR负责人：从战争到长期主义",
    "jimeng-organization-logic.html": "拆解即梦Seedance：可复制的组织力",
    "mckinsey-6pct-trust.html": "麦肯锡6%落地率：AI-First信任架构怎么搭",
    "microsoft-ai-decoupling.html": "微软的暗线：1370亿刻意避开OpenAI",
    "2026-hr-transformation-chief-architect.html": "2026HR转型：活成组织的首席架构师",
    "ai-layoff-manager-redefine.html": "AI裁员：管理者不会被AI替代，但「管理」正在被重新定义",
    "anthropic-danger-signals.html": "Anthropic实录：用6个危险信号拆掉冗余流程",
    "bigtech-ai-reorg-2026.html": "大厂AI重构：4巨头挥刀向内，谁在真做",
    "deepmind-no-kpi-talent-management.html": "DeepMind答案：没有KPI如何管天才团队",
    "mckinsey-hidden-deadlock.html": "麦肯锡隐藏死局：AI转型需底层制度授权",
    "meta-ai-code-75-percent.html": "Meta组织变脸：AI代码占比75%工程师变AI产品经理",
    "musk-2026-ai-interview.html": "马斯克访谈：当AI进入递归进化，HR物理边界",
    "musk-2026-ai-recursive-evolution.html": "马斯克2026访谈：AI递归进化与HR物理边界",
}


def clean_quotes(s):
    """英文双引号成对转「」；奇数则整体包「」。"""
    if '"' not in s:
        return s
    parts = s.split('"')
    if len(parts) % 2 == 0:
        # 偶数段 = 奇数个引号？split 后段数 = 引号数 + 1。引号成对 => 段数为奇数。
        pass
    # 段数 = 引号数 + 1。成对引号 => 段数奇数。
    res = parts[0]
    for i in range(1, len(parts)):
        q = "「" if i % 2 == 1 else "」"
        res += q + parts[i]
    return res


def main():
    changed = []
    for fn in sorted(os.listdir(ARTICLES)):
        if not fn.endswith(".html"):
            continue
        fp = os.path.join(ARTICLES, fn)
        with open(fp, "r", encoding="utf-8") as fh:
            content = fh.read()
        if 'http-equiv="refresh"' in content:
            continue

        tm = tc.TITLE_RE.search(content)
        if not tm:
            continue
        old_title_full = tm.group(1).strip()
        old_core = tc._strip_brand(old_title_full)
        h1 = tc._extract_h1(content)
        ogm = tc.OG_TITLE_RE.search(content)
        og_core = tc._strip_brand(ogm.group(2).strip()) if ogm else ""

        # 完整标题来源 = H1 与 og:title 中较长者（兼容 og 属性顺序不同的旧文）
        full_source = h1 if (h1 and len(h1) >= len(og_core)) else og_core

        # 决定新 core
        if (h1 and tc._is_midword_chop(old_core, h1)) or \
           (og_core and tc._is_midword_chop(old_core, og_core)):
            if fn in CRAFTED:
                new_core = CRAFTED[fn]
            elif full_source and len(full_source) <= 28:
                new_core = full_source
            else:
                # 兜底：不应发生（CRAFTED 已覆盖所有超长 H1）
                new_core = old_core
        else:
            new_core = old_core

        new_core = clean_quotes(new_core)

        # 替换 <title>
        new_title_full = f"{new_core} | AIHR数智引擎"
        new_title_tag = f"<title>{new_title_full}</title>"
        content2 = content.replace(f"<title>{old_title_full}</title>", new_title_tag, 1)

        # 对齐 og:title
        ogm = tc.OG_TITLE_RE.search(content2)
        if ogm:
            old_og = ogm.group(0)  # 整段 <meta ...>
            attr_q = ogm.group(1)
            new_og = old_og.replace(ogm.group(2), new_core, 1)
            content2 = content2.replace(old_og, new_og, 1)

        if content2 != content:
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(content2)
            changed.append((fn, old_core, new_core, len(new_core)))

    print(f"修复标题 {len(changed)} 个：\n")
    for fn, old, new, ln in changed:
        flag = "✓≤28" if ln <= 28 else f"✗{ln}超长"
        print(f"  {fn}")
        print(f"    旧({len(old)}): {old}")
        print(f"    新({ln}): {new}  [{flag}]")
    print(f"\n共 {len(changed)} 个文件已写入。")


if __name__ == "__main__":
    main()
