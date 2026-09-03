#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unify_titles.py — 全站标题统一脚本（第二步：批量）

⚠️  状态：已冻结（2026-09-03）
2026-09-03 用户校准：页面展示标题（h1/og:title/twitter:title）必须干净，但 <title> 允许保留
「 | AIHR数智引擎」品牌后缀。本脚本会批量 stripping 所有字段的后缀，与现行纪律冲突，
除非明确决定恢复「四字段全干净」旧口径，否则不应再执行 --apply。

历史规则（留档）：
1. 所有文章四字段 —— <title> / <h1> / og:title / twitter:title —— 统一为「无后缀规范标题」。
2. 不追加「｜AIHR数智引擎」等品牌后缀。
3. 规范标题来源（长度按 SEO/GEO 健康区间，单一真相源 scripts/title_standards.py）：
   - H1(去后缀) ≤ 40 字（TITLE_WARN，健康上限）→ 直接用 H1。
   - H1 > 40 字 → 用 LONG_TITLE_MAP 中人工重写、保留原意、≤40 字的版本（严禁物理截断）。
4. 重定向桩页（标题含「页面已迁移」或含 http-equiv=refresh）跳过。
5. 非文章页（首页/列表页/hub）仅清除 <title> 里的品牌后缀并统一已有 og/twitter，不插入新 meta。

如需仅修复「页面展示标题意外带后缀」的个案，建议用 sed/perl 针对 h1/og/twitter 局部处理，
不要运行本脚本的全字段 strip。

用法（仅保留 dry-run 供审计）：
  python3 scripts/unify_titles.py            # dry-run，显示会改动哪些文件
  python3 scripts/unify_titles.py --apply    # ❌ 已不建议执行
"""
import re
import sys
import json
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(ROOT, "articles")
INDEX_JSON = os.path.join(ROOT, "assets", "js", "article-index.json")

SUFFIX_PATTERNS = ["｜AIHR数智引擎", "| AIHR数智引擎", "｜ AIHR数智引擎", " | AIHR数智引擎"]

# H1 > 40 字 → 人工重写（保留钩子/原意，≤40 字，无破折号/英文冒号做 spine）
LONG_TITLE_MAP = {
    "2026-hr-transformation-chief-architect": "2026HR转型：成为组织的首席架构师",
    "ai-bounded-rationality": "真正危险的不是AI，是你的有限理性",
    "ai-governance-gap-hr-2026": "AI治理鸿沟：80%用AI，仅23%立规矩",
    "anthropic-danger-signals": "Anthropic实录：6个危险信号拆冗余流程",
    "anthropic-engineer-three-stages": "Anthropic报告：AI时代工程师三阶跃迁",
    "bytedance-7000-interns": "字节校招7000人：大厂HR去经验化",
    "deepmind-no-kpi-talent-management": "无KPI管天才团队：DeepMind的科学领导力",
    "didi-three-hr-leaders": "滴滴三任HR一号位：从战争到长期主义",
    "idc-2026-hr-ai-agent-guide": "IDC 2026：HR AI Agent选型指南",
    "jimeng-organization-logic": "拆解即梦Seedance：AI时代组织重构逻辑",
    "mckinsey-2026-org-report-deep-dive": "麦肯锡2026组织报告：AI时代组织进化论",
    "mckinsey-2026-training-vs-screening": "麦肯锡2026：HR必须从培训转向筛选",
    "mckinsey-6-percent-trust-architecture": "麦肯锡6%落地率：AI-First信任架构怎么搭",
    "mckinsey-6pct-trust": "麦肯锡6%落地率：AI-First信任架构怎么搭",
    "mckinsey-hidden-deadlock": "麦肯锡死局：无制度授权，AI转型是行为艺术",
    "meta-ai-code-75-percent": "Meta变脸：AI代码75%，工程师成AI产品经理",
    "microsoft-ai-decoupling": "微软暗线：1370亿避开OpenAI的组织解耦",
    "microsoft-anthropic-ai-org-restructure": "微软砸架构Anthropic灭中层：组织底层代码重构",
    "microsoft-cisco-ai-restructuring-2026": "微软裁4800思科裁4000：AI重构非替代",
    "musk-2026-ai-interview": "马斯克2026访谈：AI递归进化，HR边界消失？",
    "openclaw-ai-agent-management": "OpenClaw走红：HR如何管隐形AI员工",
    "tencent-319b-ali-3800b": "腾讯319亿阿里3800亿：HR一号位的终极考卷",
    "tencent-ai-lab-disbanded": "腾讯AI Lab落幕：大模型时代的组织巷战",
    "wangxing-meituan-management-talk": "王兴美团2000人管理会：经验的清算",
    "wwdc-2026-hr-insights": "WWDC2026：Apple智能给HR的启示",
    "big-tech-ai-org-2026": "2026大厂AI组织变革全景图：五大厂谁跑最快",
    "bigtech-ai-reorg-2026": "大厂AI组织重构：谁在真做谁在跟风",
    "china-ai-org-three-routes": "2026中国AI组织三条路线",
    "gtc2026-ai-infrastructure-org-evolution": "GTC2026：算力基建时代的组织演进",
    "musk-2026-ai-recursive-evolution": "马斯克2026：当AI递归进化，HR边界消失？",
}


def strip_suffix(s):
    s = (s or "").strip()
    for p in SUFFIX_PATTERNS:
        if s.endswith(p):
            s = s[: len(s) - len(p)].strip()
    return s


def is_stub(html):
    return ("页面已迁移" in html) or ('http-equiv="refresh"' in html.lower())


def set_title_tag(html, canonical):
    return re.sub(r"<title>[^<]*</title>", f"<title>{canonical}</title>", html, count=1)


def set_h1(html, canonical):
    """统一 H1 文本。
    - 若当前 H1 文本（剥标签后）已等于 canonical，保留原结构（含 <br> 视觉换行）。
    - 否则整体替换为 canonical（去掉 <br> 等内联标签）。
    """
    def repl(m):
        cur = re.sub(r"<[^>]+>", "", m.group(0)).strip()
        if cur == canonical:
            return m.group(0)
        # 注意：group(3) 才是闭合 </h1>，绝不能用 group(2)（旧内容）
        return m.group(1) + canonical + m.group(3)
    return re.sub(r"(<h1[^>]*>)(.*?)(</h1>)", repl, html, count=1, flags=re.DOTALL)


def set_meta(html, prop, canonical, anchor_prop, insert=True):
    """统一某 prop 的 meta 标签值。
    insert=True（文章页）：删除全部该 prop 标签（连前导换行/缩进），再插入一枚规范标签（去重+补缺，幂等）。
    insert=False（非文章页）：仅替换已有标签的 content 值，不插入新标签、不删除。
    """
    tag = ('<meta content="%s" property="%s"/>' % (canonical, prop)) if prop.startswith("og:") \
        else ('<meta content="%s" name="%s"/>' % (canonical, prop))
    pat = re.compile(r'<meta[^>]*\b' + re.escape(prop) + r'\b[^>]*?/?>', re.DOTALL)
    if not insert:
        # 仅替换已有标签的 content 值
        return pat.sub(lambda m: re.sub(r'content="[^"]*"', 'content="%s"' % canonical, m.group(0)), html)
    # 删除：连前导 \n\s* 一起吃掉，避免重复运行累积空白
    html = re.sub(r'\n\s*' + pat.pattern, '', html)
    html = pat.sub('', html)
    anch = re.search(r'<meta[^>]*\b' + re.escape(anchor_prop) + r'\b[^>]*?/?>', html)
    if anch:
        idx = anch.end()
        return html[:idx] + tag + html[idx:]
    vp = re.search(r'<meta[^>]*name="viewport"[^>]*>', html)
    if vp:
        idx = vp.end()
        return html[:idx] + tag + html[idx:]
    return html.replace("</head>", tag + "\n</head>", 1)


def main():
    apply = "--apply" in sys.argv
    dry = not apply
    print(f"MODE: {'APPLY' if apply else 'DRY-RUN (no writes)'}\n")

    # 非文章页集合（须在文章循环前计算，列表页不参与文章四字段统一）
    non_article = set()
    for pat in ["index.html", "articles/index.html", "articles.html", "resources.html"]:
        fp = os.path.join(ROOT, pat)
        if os.path.exists(fp):
            non_article.add(fp)
    for fp in glob.glob(os.path.join(ROOT, "hub", "*.html")):
        non_article.add(fp)
    for fp in glob.glob(os.path.join(ROOT, "*.html")):
        if os.path.basename(fp) != "index.html":
            non_article.add(fp)

    rows = []
    skipped_stubs = []
    skipped_no_h1 = []
    changed = 0

    with open(INDEX_JSON, encoding="utf-8") as f:
        index_data = json.load(f)
    index_titles = {e.get("url"): e for e in index_data}

    for fpath in sorted(glob.glob(os.path.join(ARTICLES_DIR, "*.html"))):
        if fpath in non_article:
            continue
        slug = os.path.basename(fpath).replace(".html", "")
        with open(fpath, encoding="utf-8") as f:
            html = f.read()
        if is_stub(html):
            skipped_stubs.append(slug)
            continue

        # 兼容 H1 内联标签（<br>/<span> 等）：剥标签后取纯文本，再 strip
        h1m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        h1 = re.sub(r"<[^>]+>", "", h1m.group(1)).strip() if h1m else ""
        if not h1m:
            skipped_no_h1.append(slug)
            print(f"  [SKIP] 无 H1: {slug}")
            continue

        canonical = LONG_TITLE_MAP.get(slug) or strip_suffix(h1)
        if not canonical:
            print(f"  [SKIP] 空 canonical: {slug}")
            continue
        if len(canonical) > 40 and slug not in LONG_TITLE_MAP:
            print(f"  [WARN] canonical >40 [{len(canonical)}] 且不在 LONG_TITLE_MAP: {slug} -> {canonical}")

        new_html = html
        new_html = set_title_tag(new_html, canonical)
        new_html = set_h1(new_html, canonical)
        new_html = set_meta(new_html, "og:title", canonical, "og:type", insert=True)
        new_html = set_meta(new_html, "twitter:title", canonical, "og:title", insert=True)

        html_changed = new_html != html

        idx_changed = False
        if slug in index_titles and index_titles[slug].get("title") != canonical:
            index_titles[slug]["title"] = canonical
            idx_changed = True

        if html_changed or idx_changed:
            changed += 1
            rows.append({"slug": slug, "canonical": canonical, "html_changed": html_changed, "idx_changed": idx_changed})
            if dry:
                flags = []
                if html_changed:
                    flags.append("html")
                if idx_changed:
                    flags.append("index")
                print(f"  [{'/'.join(flags)}] {slug} -> {canonical}")
            else:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(new_html)

    index_written = False
    if any(r["idx_changed"] for r in rows):
        if not dry:
            with open(INDEX_JSON, "w", encoding="utf-8") as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            index_written = True
        else:
            print(f"  (index.json 将有 {sum(1 for r in rows if r['idx_changed'])} 条 title 更新)")

    # 非文章页：仅去 <title> 后缀 + 统一已有 og/twitter（不插入新 meta）
    non_changes = 0
    for fp in sorted(non_article):
        with open(fp, encoding="utf-8") as f:
            html = f.read()
        tm = re.search(r"<title>([^<]+)</title>", html)
        if not tm:
            continue
        canonical = strip_suffix(tm.group(1).strip())
        if canonical == tm.group(1).strip():
            continue
        non_changes += 1
        if dry:
            print(f"  [非文章页] {os.path.relpath(fp, ROOT)}: {tm.group(1).strip()} -> {canonical}")
        else:
            h2 = set_title_tag(html, canonical)
            h2 = set_meta(h2, "og:title", canonical, "og:type", insert=False)
            h2 = set_meta(h2, "twitter:title", canonical, "og:title", insert=False)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(h2)

    print(f"\n=== 汇总 ===")
    print(f"跳过桩页: {len(skipped_stubs)}")
    if skipped_stubs:
        for s in skipped_stubs:
            print(f"   - {s}")
    print(f"跳过无H1页: {len(skipped_no_h1)}")
    if skipped_no_h1:
        for s in skipped_no_h1:
            print(f"   - {s}")
    print(f"文章改动数: {changed}")
    print(f"非文章页 title 后缀清理: {non_changes}")
    if not dry:
        print("已写入文件。")
    else:
        print("DRY-RUN 完成，未写入。")


if __name__ == "__main__":
    main()
