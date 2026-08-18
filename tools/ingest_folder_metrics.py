#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIHR 数据收件箱 -> 统一快照 解析器
==================================
把用户每周下载到 aihr-data-inbox/ 的 Bing / GSC / 百度统计 原始文件，
解析成 `tools/metrics_<date>.json` 快照（兼容 vitals_monitor.py 的 gsc/bing 结构），
并额外产出 bing_ai(C1 引用) 与 baidu(D 跳出率/来源/入口页) 用于周复盘。

输入（用户每周一放置，沙箱可见路径）：
  <inbox>/AIHR网站数据/
    bing/   SearchPerformanceOverview_All_*.csv, AIPerformanceOverviewStats_*.csv, ...
    GA:GSC/ <site>_-Performance-on-Search-<date>/图表.csv
    百度统计/ 全部来源_*.pdf, 入口页面_*.pdf, 新老访客_*.pdf, ...

输出：
  <site-migrated>/tools/metrics_<YYYYMMDD>.json
  stdout 打印九轴可算部分的周汇总 + 环比。

用法：
  python tools/ingest_folder_metrics.py [--inbox <path>] [--out <site-migrated/tools>]

铁律：周值 = 最近 7 日(截至数据最新日)合计÷7天；环比 = 对比前 7 日。
      跳出率取区间均值（率非合计）；GSC/Bing 曝光点击取日合计。
"""
import argparse, csv, json, os, re, sys, glob
from datetime import datetime, date, timedelta

INBOX_DEFAULT = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/aihr-data-inbox/AIHR网站数据"
OUT_DEFAULT = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/tools"


def _parse_date(s):
    s = (s or "").strip().strip('"')
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _num(x):
    x = (x or "").strip().strip('%').replace(",", "")
    try:
        return float(x)
    except ValueError:
        return 0.0


def _read_csv_rows(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def parse_bing_search(inbox):
    """SearchPerformanceOverview_All_*.csv -> daily[{date,impressions,clicks,position?}] + totals"""
    pat = os.path.join(inbox, "bing", "www.aihrlab.online_SearchPerformanceOverview_All_*.csv")
    fs = sorted(glob.glob(pat))
    if not fs:
        return None
    rows = _read_csv_rows(fs[-1])
    daily = []
    for r in rows[1:]:
        if len(r) < 3:
            continue
        d = _parse_date(r[0])
        if not d:
            continue
        daily.append({"date": d.isoformat(), "impressions": int(_num(r[2])),
                      "clicks": int(_num(r[1]))})
    daily.sort(key=lambda x: x["date"])
    tot_imp = sum(x["impressions"] for x in daily)
    tot_clk = sum(x["clicks"] for x in daily)
    return {"daily": daily, "totals": {"impressions": tot_imp, "clicks": tot_clk},
            "window": f"{daily[0]['date']}~{daily[-1]['date']}" if daily else ""}


def parse_bing_ai(inbox):
    """AIPerformanceOverviewStats_*.csv -> daily[{date,citations,cited_pages}]"""
    pat = os.path.join(inbox, "bing", "www.aihrlab.online_AIPerformanceOverviewStats_*.csv")
    fs = sorted(glob.glob(pat))
    if not fs:
        return None
    rows = _read_csv_rows(fs[-1])
    daily = []
    for r in rows[1:]:
        if len(r) < 3:
            continue
        d = _parse_date(r[0])
        if not d:
            continue
        daily.append({"date": d.isoformat(), "citations": int(_num(r[1])),
                      "cited_pages": int(_num(r[2]))})
    daily.sort(key=lambda x: x["date"])
    return {"daily": daily, "totals": {"citations": sum(x["citations"] for x in daily)},
            "window": f"{daily[0]['date']}~{daily[-1]['date']}" if daily else ""}


def parse_gsc(inbox):
    """GA:GSC/<site>_-Performance-on-Search-<date>/图表.csv -> daily[{date,impressions,clicks,ctr,position}]"""
    base = os.path.join(inbox, "GA:GSC")
    if not os.path.isdir(base):
        return None
    cand = []
    for root, _, files in os.walk(base):
        for fn in files:
            if fn == "图表.csv":
                cand.append(os.path.join(root, fn))
    if not cand:
        return None
    rows = _read_csv_rows(cand[0])
    # header: 日期,点击次数,展示,点击率,排名
    daily = []
    for r in rows[1:]:
        if len(r) < 3:
            continue
        d = _parse_date(r[0])
        if not d:
            continue
        daily.append({"date": d.isoformat(), "impressions": int(_num(r[2])),
                      "clicks": int(_num(r[1])),
                      "position": _num(r[4]) if len(r) > 4 else None})
    daily.sort(key=lambda x: x["date"])
    return {"daily": daily, "totals": {"impressions": sum(x["impressions"] for x in daily),
                                       "clicks": sum(x["clicks"] for x in daily)},
            "window": f"{daily[0]['date']}~{daily[-1]['date']}" if daily else ""}


def parse_baidu(inbox):
    """百度统计 PDF -> {avg_bounceRatio, pv, uv, by_source, top_entry_pages, new_vs_return}"""
    try:
        import pdfplumber
    except ImportError:
        print("[warn] pdfplumber 不可用，跳过百度统计解析", file=sys.stderr)
        return None
    folder = os.path.join(inbox, "百度统计")
    if not os.path.isdir(folder):
        return None
    text_all = ""
    for f in sorted(glob.glob(os.path.join(folder, "*.pdf"))):
        try:
            with pdfplumber.open(f) as pdf:
                for p in pdf.pages:
                    text_all += (p.extract_text() or "") + "\n"
        except Exception as e:
            print(f"[warn] PDF 解析失败 {os.path.basename(f)}: {e}", file=sys.stderr)

    out = {}
    # 全站跳出率（全部来源 当页汇总）
    m = re.search(r"当页汇总\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d{2}:\d{2}:\d{2})", text_all)
    if m:
        out["pv"] = int(m.group(1))
        out["uv"] = int(m.group(2))
        out["avg_bounceRatio"] = float(m.group(4)) / 100.0
        out["avg_duration"] = m.group(5)
    # 来源类型
    out["by_source"] = []
    for sm in re.finditer(r"^(外部链接|直接访问|百度自然搜索|其他搜索引擎|自定义来源)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d{2}:\d{2}:\d{2})", text_all, re.M):
        out["by_source"].append({"source": sm.group(1), "pv": int(sm.group(2)),
                                  "uv": int(sm.group(3)), "bounceRatio": float(sm.group(5)) / 100.0})
    # 入口页 TOP（big-tech 等）
    out["top_entry_pages"] = []
    for em in re.finditer(r"(https?://[^\s]+?aihrlab\.online[^\s]*)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d{2}:\d{2}:\d{2})", text_all):
        out["top_entry_pages"].append({"page": em.group(1), "pv": int(em.group(2)),
                                        "uv": int(em.group(3)), "bounceRatio": float(em.group(5)) / 100.0})
    out["top_entry_pages"].sort(key=lambda x: x["pv"], reverse=True)
    out["top_entry_pages"] = out["top_entry_pages"][:5]
    # 新老访客
    nm = re.search(r"新访客\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%", text_all)
    rm = re.search(r"老访客\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%", text_all)
    if nm and rm:
        out["new_vs_return"] = {
            "new": {"pv": int(nm.group(2)), "uv": int(nm.group(3)), "bounceRatio": float(nm.group(4)) / 100.0},
            "return": {"pv": int(rm.group(2)), "uv": int(rm.group(3)), "bounceRatio": float(rm.group(4)) / 100.0},
        }
    # 给 vitals_monitor 一个聚合日点（百度统计 PDF 仅 30 日聚合，无日序列；
    # 单一聚合点不会触发"上升"误判，仅按绝对地板 0.85 判 P1）
    if out.get("avg_bounceRatio") is not None:
        out["daily"] = [{"date": date.today().isoformat(), "bounceRatio": out["avg_bounceRatio"]}]
    return out


def load_gsc_override(out_dir):
    """GSC 导出 CSV 不含有效页数（deindex 真指标），此值由用户在 GSC 仪表盘读取后
    写入 tools/gsc_meta_override.json。每周 ingest 自动合并进 gsc 快照，使监控能精判恢复。"""
    p = os.path.join(out_dir, "gsc_meta_override.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def weekly_bins(daily, days=7):
    """返回 (recent7, prior7) 两个日期区间的合计；recent 截至数据最新日。"""
    if not daily:
        return None, None
    dates = [datetime.fromisoformat(x["date"]).date() for x in daily]
    maxd = max(dates)
    recent_start = maxd - timedelta(days=days - 1)
    prior_start = recent_start - timedelta(days=days)
    prior_end = recent_start - timedelta(days=1)

    def tot(s, e):
        imp = clk = cit = 0
        for x in daily:
            d = datetime.fromisoformat(x["date"]).date()
            if s <= d <= e:
                imp += x.get("impressions", 0)
                clk += x.get("clicks", 0)
                cit += x.get("citations", 0)
        return imp, clk, cit

    r_imp, r_clk, r_cit = tot(recent_start, maxd)
    p_imp, p_clk, p_cit = tot(prior_start, prior_end)
    return (recent_start, maxd, r_imp, r_clk, r_cit), (prior_start, prior_end, p_imp, p_clk, p_cit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=INBOX_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    today = date.today().strftime("%Y%m%d")
    snap = {"generated": datetime.now().isoformat(timespec="seconds"),
            "source": "user-folder-ingest",
            "caliber": "trailing-30d, daily grain, ingested weekly"}

    bing = parse_bing_search(args.inbox)
    bing_ai = parse_bing_ai(args.inbox)
    gsc = parse_gsc(args.inbox)
    baidu = parse_baidu(args.inbox)

    if bing: snap["bing"] = bing
    if bing_ai: snap["bing_ai"] = bing_ai
    if gsc: snap["gsc"] = gsc
    if baidu: snap["baidu"] = baidu

    # GSC 有效页数覆盖（deindex 真指标，CSV 不含）：合并进 gsc 快照
    ov = load_gsc_override(args.out)
    if gsc and ov and ov.get("valid_pages") is not None:
        gsc["valid_pages"] = int(ov["valid_pages"])
        gsc["valid_pages_reported_on"] = ov.get("reported_on")
        gsc["valid_pages_source"] = ov.get("source")
        print(f"[over] GSC 有效页数={ov['valid_pages']}（来源：{ov.get('source')}，报告日 {ov.get('reported_on')}）")

    out_path = os.path.join(args.out, f"metrics_{today}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f"[ok] snapshot -> {out_path}")

    # ---- 周汇总打印 ----
    print("\n================ 周汇总（口径：最近7日 vs 前7日） ================")
    if bing:
        rc, pc = weekly_bins(bing["daily"])
        if rc and pc:
            print(f"[Bing 搜索] 窗口 {bing['window']}")
            print(f"  最近7日 {rc[0]}~{rc[1]}: 曝光 {rc[2]} / 点击 {rc[3]}  | 前7日 {pc[0]}~{pc[1]}: 曝光 {pc[2]} / 点击 {pc[3]}")
            if pc[2]:
                print(f"  曝光环比 { (rc[2]-pc[2])/pc[2]*100:+.0f}%  | 点击环比 { (rc[3]-pc[3])/pc[3]*100:+.0f}%")
            print(f"  30日合计: 曝光 {bing['totals']['impressions']} / 点击 {bing['totals']['clicks']}")
    if bing_ai:
        rc, pc = weekly_bins(bing_ai["daily"])
        if rc and pc:
            print(f"[Bing AI 引用 C1] 窗口 {bing_ai['window']}")
            print(f"  最近7日: 引用 {rc[4]}  | 前7日: 引用 {pc[4]}  | 环比 { (rc[4]-pc[4])/pc[4]*100:+.0f}%" if pc[4] else f"  最近7日: 引用 {rc[4]}")
            print(f"  30日合计: 引用 {bing_ai['totals']['citations']}")
    if gsc:
        rc, pc = weekly_bins(gsc["daily"])
        if rc and pc:
            print(f"[GSC] 窗口 {gsc['window']}")
            print(f"  最近7日 {rc[0]}~{rc[1]}: 展示 {rc[2]} / 点击 {rc[3]}  | 前7日 {pc[0]}~{pc[1]}: 展示 {pc[2]} / 点击 {pc[3]}")
            print(f"  30日合计: 展示 {gsc['totals']['impressions']} / 点击 {gsc['totals']['clicks']}")
    if baidu:
        print(f"[百度统计 D 跳出率] 全站 30日: 跳出率 {baidu.get('avg_bounceRatio',0)*100:.2f}% | PV {baidu.get('pv')} | UV {baidu.get('uv')}")
        if baidu.get("new_vs_return"):
            nv, rv = baidu["new_vs_return"]["new"], baidu["new_vs_return"]["return"]
            print(f"  新访客跳出率 {nv['bounceRatio']*100:.1f}% (PV {nv['pv']}) / 老访客 {rv['bounceRatio']*100:.1f}% (PV {rv['pv']})")
        print("  入口页 TOP:")
        for p in baidu.get("top_entry_pages", [])[:3]:
            print(f"    {p['page'][:60]}... PV {p['pv']} 跳出率 {p['bounceRatio']*100:.1f}%")


if __name__ == "__main__":
    main()
