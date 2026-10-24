#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AIHRlab（网站）· 外部数据口径校验器（失效模式 F3）。

体系归属：AIHRlab 网站。本文件只管「数据读数是否可信」，不管内容、不管版式。

为什么存在：历史上多次策略失误不是算错，是**读错口径**——
  · 把 Citation Share 当成「占本站引用量的比例」，实为「本站在该 query 上
    相对全网被引站点的份额」（反算 57/57 不符才暴露，且误读会翻转结论方向）；
  · 两份同名导出（PageTrafficReport 与 PageTrafficReport(1)）其实是不同窗口，
    被当同一窗口同框比较（曝光覆盖率 304%，结论全错）；
  · clicks > impressions 的异常行未修正就合计，点击被高估 11.5%。

五条断言（对应项目「外部数据读数铁律」）：
  A1 粒度判定    —— 有没有 page/URL 字段；说「page 级明细」必须实测确认
  A2 比率自洽    —— CTR 等比率字段必须能用 分子/分母 回算复现
  A3 异常行修正  —— clicks > impressions 必须标出并按上限修正后再合计
  A4 覆盖率对账  —— 明细合计 ÷ 基准表合计；<60% = 限量导出禁用于绝对量；
                    >105% = 疑似不同窗口，禁止同框比较
  A5 同名副本窗口判定 —— 两份同名/同类表逐页比值若为非常数倍 → 不同窗口

退出码：0 = 可用于结论；1 = 有 WARN（可用于相对比较，绝对量须标注）；
        2 = 有 BLOCK（存在口径错误，禁止据此下结论）。
用法：
    python3 scripts/verify_kpi_caliber.py 表1.csv [表2.csv ...]
    python3 scripts/verify_kpi_caliber.py 目录/*.csv --baseline DeviceReport.csv
"""
import csv, os, sys, re, glob, math, statistics as st
from collections import Counter

# ── 列名识别（大小写/空格不敏感）────────────────────────────
COL = {
    "page":     ("page", "url", "landing", "target", "网页", "页面"),
    "query":    ("keyword", "query", "grounding query", "关键词", "查询"),
    "date":     ("date", "日期"),
    "impr":     ("impressions", "展示", "曝光"),
    "clicks":   ("clicks", "点击"),
    "ctr":      ("ctr", "点击率"),
    "pos":      ("avg. position", "position", "排名", "位次"),
    "cit":      ("citations", "引用"),
    "share":    ("citation share", "share", "份额"),
    "device":   ("device", "设备"),
}


def canon(name):
    return (name or "").strip().lower()


def col_role(name):
    c = canon(name)
    for role, keys in COL.items():
        for k in keys:
            if c == k or k in c:
                return role
    return None


def num(s):
    s = (s or "").strip().replace("%", "").replace(",", "")
    if s in ("", "-", "—", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def profile(path):
    """单表画像：列、角色映射、粒度、关键合计。"""
    rows = read(path)
    if not rows:
        return None
    cols = list(rows[0].keys())
    roles = {}
    for c in cols:
        r = col_role(c)
        if r:
            roles[r] = c
    tot = {}
    for r in roles:
        if r in ("impr", "clicks", "cit"):
            tot[r] = sum(num(x[roles[r]]) or 0 for x in rows)
    return {"path": path, "name": os.path.basename(path), "rows": rows,
            "cols": cols, "roles": roles, "tot": tot}


def check_granularity(p):
    """A1 粒度判定。"""
    has_page = "page" in p["roles"]
    has_query = "query" in p["roles"]
    has_date = "date" in p["roles"]
    if has_page:
        g = "page 级"
    elif has_query:
        g = "query 级"
    elif has_date:
        g = "日级"
    else:
        g = "未知"
    return g, has_page, has_query


def check_ratio(p, findings):
    """A2 比率字段自洽：CTR = clicks/impressions。"""
    r = p["roles"]
    if "ctr" not in r or "impr" not in r or "clicks" not in r:
        return
    bad = 0
    tot_i = tot_c = 0
    for x in p["rows"]:
        i = num(x[r["impr"]]); c = num(x[r["clicks"]]); v = num(x[r["ctr"]])
        if i is None or c is None or v is None:
            continue
        tot_i += i; tot_c += c
        if i > 0 and abs(v - c / i * 100) > 0.6:
            bad += 1
    if bad:
        findings.append(("BLOCK", "A2", p["name"],
                         f"CTR 与 clicks/impressions 不自洽 {bad} 行 —— 该字段不是「点击/曝光」，"
                         f"禁止按 CTR 解读，须先确认真实口径"))
    else:
        findings.append(("OK", "A2", p["name"],
                         f"CTR 自洽（0 行不符；合计 {tot_c:.0f}/{tot_i:.0f} = "
                         f"{tot_c/tot_i*100 if tot_i else 0:.2f}%）"))
    # 份额类字段：两种候选口径都试，报告哪个成立
    if "share" in r and "cit" in r:
        tc = sum(num(x[r["cit"]]) or 0 for x in p["rows"])
        a_bad = sum(1 for x in p["rows"]
                    if num(x[r["share"]]) is not None and num(x[r["cit"]])
                    and abs(num(x[r["share"]]) - num(x[r["cit"]]) / tc * 100) > 0.6)
        if a_bad == 0:
            findings.append(("OK", "A2", p["name"],
                             "份额字段 = 占本表合计的比例（回算 0 行不符）"))
        else:
            # 候选 B：本站 / 全网（分母 = cit / share）
            b_bad = sum(1 for x in p["rows"]
                        if num(x[r["share"]]) and num(x[r["cit"]])
                        and (num(x[r["cit"]]) / (num(x[r["share"]]) / 100)) < num(x[r["cit"]]))
            if b_bad == 0:
                findings.append(("BLOCK", "A2", p["name"],
                                 f"份额字段 **不是**占本表合计（{a_bad}/{len(p['rows'])} 行不符），"
                                 f"而是「本站在该 query 上相对全网被引站点的份额」。"
                                 f"按前者解读会翻转结论方向。"))
            else:
                findings.append(("BLOCK", "A2", p["name"],
                                 f"份额字段两种候选口径都不成立（A:{a_bad} / B:{b_bad} 行不符）——"
                                 f"口径未明，禁止解读该字段"))


def check_anomaly(p, findings):
    """A3 clicks > impressions 异常行。"""
    r = p["roles"]
    if "impr" not in r or "clicks" not in r:
        return
    over = [x for x in p["rows"]
            if (num(x[r["impr"]]) or 0) > 0
            and (num(x[r["clicks"]]) or 0) > num(x[r["impr"]])]
    if not over:
        return
    raw = sum(num(x[r["clicks"]]) or 0 for x in p["rows"])
    fixed = sum(min(num(x[r["clicks"]]) or 0, num(x[r["impr"]]) or 0) for x in p["rows"])
    tot_i = sum(num(x[r["impr"]]) or 0 for x in p["rows"])
    findings.append(("BLOCK", "A3", p["name"],
                     f"{len(over)} 行 clicks > impressions（数据异常）。"
                     f"原合计 {raw:.0f} → 按曝光上限修正 {fixed:.0f}（高估 "
                     f"{(raw-fixed)/fixed*100 if fixed else 0:.1f}%）；"
                     f"CTR {raw/tot_i*100 if tot_i else 0:.2f}% → "
                     f"{fixed/tot_i*100 if tot_i else 0:.2f}%。"
                     f"样例：" + "、".join(
                         f"{x[r['query']][:18] if 'query' in r else x[r.get('page','')][:18]}"
                         f"({num(x[r['clicks']]):.0f}/{num(x[r['impr']]):.0f})"
                         for x in over[:3])))


def check_coverage(profiles, baseline_name, findings):
    """A4 覆盖率对账：明细表 ÷ 基准表。"""
    base = None
    for p in profiles:
        if baseline_name.lower() in p["name"].lower():
            base = p
            break
    if base is None:
        # 以含 date 的日表为默认基准
        cands = [p for p in profiles if "date" in p["roles"]]
        base = cands[0] if cands else None
    if base is None:
        findings.append(("WARN", "A4", "-",
                         "未指定基准表且无日表，覆盖率无法对账 —— 绝对量一律标注「未对账」"))
        return
    for p in profiles:
        if p is base:
            continue
        for metric in ("impr", "clicks", "cit"):
            if metric not in p["tot"] or metric not in base["tot"]:
                continue
            b = base["tot"][metric]
            if not b:
                continue
            cov = p["tot"][metric] / b * 100
            if cov > 105:
                findings.append(("BLOCK", "A4", p["name"],
                                 f"{metric} 合计 {p['tot'][metric]:.0f} 是基准表（{base['name']}，"
                                 f"{b:.0f}）的 {cov:.1f}% —— 疑似**不同统计窗口**，"
                                 f"禁止与基准表同框比较绝对量"))
            elif cov < 60:
                findings.append(("WARN", "A4", p["name"],
                                 f"{metric} 覆盖率仅 {cov:.1f}% —— 限量导出，"
                                 f"**禁止用于绝对量**，只能做表内相对排名"))
            else:
                findings.append(("OK", "A4", p["name"],
                                 f"{metric} 覆盖率 {cov:.1f}%（基准 {base['name']}）"))


def check_window_pair(profiles, findings):
    """A5 同名副本窗口判定：逐页比值若非常数倍 → 不同窗口。"""
    bystem = {}
    for p in profiles:
        if "page" not in p["roles"]:
            continue
        # 同名副本：去掉 " (1)" 这类副本标记与扩展名后再归并
        stem = re.sub(r"\.csv$", "", p["name"], flags=re.I)
        stem = re.sub(r"\s*\(\d+\)\s*$", "", stem).strip()
        bystem.setdefault(stem, []).append(p)
    for stem, group in bystem.items():
        if len(group) < 2:
            continue
        a, b = group[0], group[1]
        def pagekey(u):
            """URL 归一化：去域名 / 去 .html / 去末尾斜杠 / index 等价。
            不归一化的话，同一页在两份导出里可能写成 /a.html 与 /a，导致共同页匹配失败。"""
            u = (u or "").strip().lower()
            for host in ("https://www.aihrlab.online", "http://www.aihrlab.online",
                         "https://aihrlab.online", "http://aihrlab.online"):
                u = u.replace(host, "")
            u = u.rstrip("/")
            if u.endswith(".html"):
                u = u[:-5]
            if u.endswith("/index"):
                u = u[:-6]
            return u.lstrip("/")

        ma = {pagekey(x[a["roles"]["page"]]): num(x[a["roles"]["impr"]])
              for x in a["rows"] if "impr" in a["roles"]}
        mb = {pagekey(x[b["roles"]["page"]]): num(x[b["roles"]["impr"]])
              for x in b["rows"] if "impr" in b["roles"]}
        ratios = []
        for k, va in ma.items():
            if k in mb and va and mb[k]:
                ratios.append(mb[k] / va)
        if len(ratios) < 5:
            continue
        cv = st.pstdev(ratios) / st.mean(ratios)
        findings.append(("BLOCK" if cv > 0.25 else "OK", "A5", stem,
                         f"同名副本 {len(ratios)} 个共同页，比值 "
                         f"{min(ratios):.2f}–{max(ratios):.2f}（中位 {st.median(ratios):.2f}，"
                         f"变异系数 {cv:.3f}）"
                         + (" —— **非常数倍 = 不同统计窗口**，禁止同框比较；"
                            "跨表联合只能用各表内相对排名"
                            if cv > 0.25 else " —— 近似常数倍，可视作同窗口")))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    baseline = ""
    if "--baseline" in sys.argv:
        i = sys.argv.index("--baseline")
        baseline = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""

    paths = []
    for a in args:
        if os.path.isdir(a):
            paths += sorted(glob.glob(os.path.join(a, "*.csv")))
        else:
            paths += sorted(glob.glob(a))
    if not paths:
        print("用法: python3 scripts/verify_kpi_caliber.py 表1.csv [表2.csv ...] [--baseline X.csv]")
        return 2

    profiles = []
    for p in paths:
        try:
            pr = profile(p)
            if pr:
                profiles.append(pr)
        except Exception as e:
            print(f"  ⚠ 读取失败 {os.path.basename(p)}: {e}")

    print("=" * 84)
    print(f"F3 数据口径校验 · {len(profiles)} 份表")
    print("=" * 84)

    findings = []
    for p in profiles:
        g, has_page, has_query = check_granularity(p)
        cols = ", ".join(canon(c) for c in p["cols"])
        print(f"\n[{p['name']}]  {len(p['rows'])} 行 · {g}")
        print(f"   列: {cols}")
        if has_query and not has_page:
            findings.append(("WARN", "A1", p["name"],
                             "无 page/URL 字段 —— 不是 page 级明细，"
                             "无法做「哪篇文章贡献了多少」的归因"))
        elif has_page:
            findings.append(("OK", "A1", p["name"], "含 page 字段，可 page 级归因"))
        check_ratio(p, findings)
        check_anomaly(p, findings)

    check_coverage(profiles, baseline, findings)
    check_window_pair(profiles, findings)

    print("\n" + "=" * 84)
    print("判定")
    print("=" * 84)
    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]
    oks = [f for f in findings if f[0] == "OK"]
    for lvl in ("BLOCK", "WARN"):
        lst = [f for f in findings if f[0] == lvl]
        if not lst:
            continue
        print(f"\n【{lvl}】{len(lst)} 条")
        for lvl_, code, name, msg in lst:
            print(f"  [{code}] {name}: {msg}")
    print(f"\nOK {len(oks)} / WARN {len(warns)} / BLOCK {len(blocks)}")

    if blocks:
        print("\n🔴 存在口径错误：禁止据此下结论，先修正读法或换表。")
        return 2
    if warns:
        print("\n🟠 有口径限制：可用于相对比较，绝对量必须标注覆盖率/粒度限制。")
        return 1
    print("\n✅ 口径自洽，可用于结论。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
