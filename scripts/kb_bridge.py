#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIHRlab 站点 <-> UncleJ-wiki 知识库 桥接（只读，零侵入）

设计原则（最低影响面）：
- 本文件只新增，不修改站点任何既有脚本。
- 只做「读取 + 解析 + 生成引用片段」，不复制知识库内容到站点。
- 站点文章引用硬数字时写 `（DATA-002：89% ...）`，数字唯一真相源仍在 wiki 台账。

用法：
  python3 scripts/kb_bridge.py list [--cluster ai] [--project aihrlab] [--tier 1]
  python3 scripts/kb_bridge.py cite DATA-002 [--format md|html]
  python3 scripts/kb_bridge.py brief --topic "中层管理者 AI 转型"
  python3 scripts/kb_bridge.py stats
"""
import argparse
import os
import re
import sys

# ── 唯一需要维护的常量：知识库根 ────────────────────────────────────────
KB_ROOT = "/Users/andyzhang/WorkBuddy/2026-08-31-10-48-58/.workbuddy/wiki"
DATA_SOURCES = os.path.join(KB_ROOT, "assets", "data_sources.md")
GLOSSARY = os.path.join(KB_ROOT, "assets", "glossary.md")
TOPICS = os.path.join(KB_ROOT, "assets", "topics_ledger.md")
CASES = os.path.join(KB_ROOT, "assets", "cases")

# 站点侧口径：AIHRlab 主用 cluster（结构/定义/常青）
AIHRLAB_CLUSTERS = ("benchmark", "recruit", "talent", "perf", "consult")


def _read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_ledger():
    """解析 data_sources.md 的台账表格，返回 dict[id] = row。"""
    txt = _read(DATA_SOURCES)
    rows, header = [], None
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        rows.append(dict(zip(header, cells)))
    return {r.get("ID", ""): r for r in rows if r.get("ID", "").startswith("DATA-")}


def parse_glossary():
    """返回 [(term, definition)]。兼容 `| 术语 | 释义 |` 与 `- **术语**：释义`。"""
    terms = []
    for line in _read(GLOSSARY).splitlines():
        line = line.strip()
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if m and not set(m.group(1)) <= set("-: "):
            terms.append((m.group(1), m.group(2)))
            continue
        m = re.match(r"^[-*]\s*\*\*(.+?)\*\*[：:]\s*(.+)$", line)
        if m:
            terms.append((m.group(1), m.group(2)))
    return terms


def cite(row, fmt="md"):
    """生成一条可粘贴的引用片段。"""
    sid = row.get("ID", "")
    org = row.get("机构 / 报告", "")
    year = row.get("年", "")
    n = row.get("样本 n", "")
    nums = row.get("关键数字（可引用）", "")
    tier = row.get("tier", "")
    warn = ""
    if tier.strip() == "3":
        warn = " [待核·禁止作主论据]"
    if fmt == "html":
        return ('<span class="kb-cite" data-kb="%s">（%s：%s，%s %s，n=%s%s）</span>'
                % (sid, sid, nums, org, year, n, warn))
    return "（%s：%s｜%s %s，n=%s%s）" % (sid, nums, org, year, n, warn)


def cmd_list(a):
    rows = parse_ledger()
    out = []
    for sid, r in sorted(rows.items()):
        clus = r.get("适用簇", "")
        proj = r.get("project", "")
        tier = r.get("tier", "").strip()
        if a.cluster and a.cluster not in clus:
            continue
        if a.project and proj not in ("both", a.project):
            continue
        if a.tier and tier != str(a.tier):
            continue
        out.append("%-9s tier%s | %s" % (sid, tier, r.get("机构 / 报告", "")[:52]))
    print("命中 %d 条" % len(out))
    print("\n".join(out))


def cmd_cite(a):
    rows = parse_ledger()
    ids = [i.strip().upper() for i in a.ids.split(",")]
    for sid in ids:
        r = rows.get(sid)
        if not r:
            print("!! 未找到 %s（台账无此 ID，禁止裸写数字）" % sid)
            continue
        print(cite(r, a.format))
        if r.get("tier", "").strip() == "3":
            print("   ↳ 纪律：tier3 待核，须先一手核验再作主论据。")


def cmd_brief(a):
    """站点侧轻量选题简报：只给台账 + 术语 + 案例，不读 patterns 全文。"""
    rows = parse_ledger()
    kw = [w for w in re.split(r"[\s,，、]+", a.topic) if w]
    hit = []
    for sid, r in rows.items():
        blob = " ".join(r.values())
        score = sum(blob.count(w) for w in kw)
        if score:
            hit.append((score, sid, r))
    hit.sort(reverse=True)
    print("=== 知识库选题简报（站点口径）===")
    print("主题：%s" % a.topic)
    print("\n[数据源] 命中 %d 条" % len(hit))
    for score, sid, r in hit[:8]:
        print("  %-9s tier%s | %s" % (sid, r.get("tier", "").strip(), r.get("机构 / 报告", "")[:50]))
    tier3 = [sid for _, sid, r in hit if r.get("tier", "").strip() == "3"]
    if tier3:
        print("\n[纪律告警] tier3 待核源 %s —— 禁止作主论据，须先核验。" % ", ".join(tier3))
    terms = [(t, d) for t, d in parse_glossary() if any(w in t or w in d for w in kw)]
    if terms:
        print("\n[术语] 命中 %d 条" % len(terms))
        for t, d in terms[:5]:
            print("  %s：%s" % (t, d[:60]))
    cases = []
    if os.path.isdir(CASES):
        for fn in sorted(os.listdir(CASES)):
            if not fn.endswith(".md") or fn == "README.md":
                continue
            body = _read(os.path.join(CASES, fn))
            if any(w in body for w in kw):
                cases.append(fn)
    if cases:
        print("\n[案例卡] 命中 %d 张：%s" % (len(cases), ", ".join(cases)))
    if not hit and not terms and not cases:
        print("\n!! 知识库无命中：本选题目前无台账数字支撑，须先补数据源入库或改为判断型论证。")


def cmd_stats(a):
    rows = parse_ledger()
    from collections import Counter
    tiers = Counter(r.get("tier", "").strip() for r in rows.values())
    projs = Counter(r.get("project", "") for r in rows.values())
    print("台账总数：%d" % len(rows))
    print("tier 分布：%s" % dict(tiers))
    print("project 分布：%s" % dict(projs))
    print("术语条数：%d" % len(parse_glossary()))


def main():
    p = argparse.ArgumentParser(description="AIHRlab <-> UncleJ-wiki 桥接（只读）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="列出可用数据源")
    s.add_argument("--cluster"); s.add_argument("--project"); s.add_argument("--tier")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("cite", help="生成引用片段")
    s.add_argument("ids", help="逗号分隔，如 DATA-002,DATA-005")
    s.add_argument("--format", default="md", choices=["md", "html"])
    s.set_defaults(func=cmd_cite)

    s = sub.add_parser("brief", help="站点侧选题简报")
    s.add_argument("--topic", required=True)
    s.set_defaults(func=cmd_brief)

    s = sub.add_parser("stats", help="知识库资产统计")
    s.set_defaults(func=cmd_stats)

    a = p.parse_args()
    if not os.path.isdir(KB_ROOT):
        sys.exit("!! KB_ROOT 不存在：%s" % KB_ROOT)
    a.func(a)


if __name__ == "__main__":
    main()
