#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vitals_monitor.py —— 搜索生命体征主动监控器（主理人红线机制）

背景（2026-08 致命事故）：
  GSC 有效页 90→3 暴跌，曝光/点击归零数周才被用户截图发现。这是主理人行为
  失职——发布后从不主动跟进搜索生命体征。本脚本把"主动监控"从口号变成机制：
  每周由 automation 触发，对比近 7 日 vs 前 7 日 GSC 曝光/点击，归零/骤降即告警。

判定（GSC 有 ~3 天延迟，pull_gsc 已处理）：
  - 归零（近期曝光/点击 == 0 且前期 > 0）        → P0 致命
  - 骤降 > 60%                                   → P1 告警
  - 在线不可达且仓库无快照 → BLOCKED（显式请用户本地补拉）
  - 有快照但过期 > 9 天   → STALE（显式请用户补拉）

为什么分 online / offline：
  沙箱无 Google 出口（oauth2.googleapis.com 超时）是已知限制，但这不构成
  "不监控"的借口。真实设计：
    - 用户在本地跑 `tools/metrics_pull.py --gsc --days 30`，把生成的
      `tools/metrics_<date>.json` 提交到仓库；
    - automation 在沙箱跑本脚本的 offline 模式，读已提交快照分析；
    - 若快照过期/缺失，脚本写 BLOCKED/STALE 报告——这是主理人"显式请你补位
      + 我下轮必跟进"的凭据，而不是沉默。
  所以：环境限制让"在线拉取"失败，但"分析 + 告警 + 请补位"始终发生。

用法：
  python tools/vitals_monitor.py            # auto：在线优先，失败回退离线快照
  python tools/vitals_monitor.py --online   # 本地有网出口时完整跑 GSC
  python tools/vitals_monitor.py --offline  # 只读 tools/metrics_*.json 快照分析

退出码（供 automation 判定升级）：
  0 = 健康；2 = P1；3 = P0；4 = BLOCKED / STALE
"""
import os
import sys
import json
import glob
import argparse
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORTS = os.path.join(ROOT, "reports")
os.makedirs(REPORTS, exist_ok=True)

DROP_THRESHOLD = 0.60      # 骤降阈值
RECENT_DAYS = 7            # 近 7 日
PRIOR_DAYS = 7             # 前 7 日
SNAPSHOT_STALE_DAYS = 9    # 快照超过此天数视为过期

DATE = datetime.now().strftime("%Y-%m-%d")
ALERT_PATH = os.path.join(REPORTS, f"vitals-alert-{DATE}.md")


def _latest_snapshot():
    """返回最新的「带日期」快照 tools/metrics_YYYYMMDD.json。

    只认 metrics_8位日期.json 这种格式，忽略其他命名（如临时 metrics_test.json），
    避免 glob 把非日期文件误当最新快照导致日期解析崩。
    """
    import re as _re
    cand = []
    for p in glob.glob(os.path.join(HERE, "metrics_*.json")):
        m = _re.match(r"metrics_(\d{8})\.json$", os.path.basename(p))
        if m:
            cand.append((m.group(1), p))
    if not cand:
        return None
    cand.sort(key=lambda x: x[0])
    return cand[-1][1]


def _snapshot_date(snap_path):
    """从文件名解析快照日期；解析失败返回 None（视为超旧）。"""
    import re as _re
    m = _re.match(r"metrics_(\d{8})\.json$", os.path.basename(snap_path))
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d")
    except Exception:
        return None


def _load_gsc_online(days):
    """在线拉 GSC；任何失败向上抛。复用 metrics_pull.pull_gsc。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "metrics_pull", os.path.join(HERE, "metrics_pull.py"))
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    return mp.pull_gsc(days)


def _window_totals(daily, recent_n, prior_n):
    """daily 按日期升序；取近 N 日、前 N 日汇总。"""
    n = len(daily)
    prior = daily[max(0, n - recent_n - prior_n):n - recent_n]
    recent = daily[max(0, n - recent_n):]

    def agg(rows):
        return (
            sum(r.get("impressions") or 0 for r in rows),
            sum(r.get("clicks") or 0 for r in rows),
        )
    return agg(recent), agg(prior), recent, prior


def _analyze(gsc):
    """返回 (result_dict, level, error_str)。"""
    daily = gsc.get("daily", [])
    if not daily:
        return None, None, "GSC 返回的 daily 为空：可能站点未被收录，或凭据站点不匹配。"
    (r_imp, r_clk), (p_imp, p_clk), recent, prior = _window_totals(daily, RECENT_DAYS, PRIOR_DAYS)
    findings = []
    level = "OK"
    if p_imp > 0 and r_imp == 0:
        level = "P0"
        findings.append(f"曝光归零：前 7 日 {p_imp} 次 → 近 7 日 0 次。站点搜索可见性已死亡，立即排查。")
    elif p_imp > 0 and (p_imp - r_imp) / p_imp > DROP_THRESHOLD:
        level = "P1"
        findings.append(f"曝光骤降 {(p_imp - r_imp) / p_imp * 100:.0f}%：前 7 日 {p_imp} → 近 7 日 {r_imp}。")
    if p_clk > 0 and r_clk == 0:
        if level != "P0":
            level = "P0"
        findings.append(f"点击归零：前 7 日 {p_clk} → 近 7 日 0。")
    elif p_clk > 0 and (p_clk - r_clk) / p_clk > DROP_THRESHOLD:
        if level == "OK":
            level = "P1"
        findings.append(f"点击骤降 {(p_clk - r_clk) / p_clk * 100:.0f}%：前 7 日 {p_clk} → 近 7 日 {r_clk}。")
    res = {
        "recent_imp": r_imp, "recent_clk": r_clk,
        "prior_imp": p_imp, "prior_clk": p_clk,
        "recent_days": len(recent), "prior_days": len(prior),
        "window": gsc.get("window"), "level": level, "findings": findings,
    }
    return res, level, None


def _write_report(status, body):
    L = [
        f"# 搜索生命体征监控 {DATE}", "",
        f"- 状态：**{status}**",
        f"- 生成：{datetime.now():%Y-%m-%d %H:%M}",
        f"- 模式：{body.get('mode', 'auto')}",
        f"- 数据窗口：{body.get('window', '—')}", "",
    ]
    if status in ("P0", "P1"):
        L += ["## 告警", ""]
        for f in body.get("findings", []):
            L.append(f"- {f}")
        L += ["", "## 立即行动（先于一切其他工作）",
              "- 登录 GSC 查「有效页面 / 覆盖率」与 sitemap 状态；",
              "- 若本次发布导致（sitemap 收录骤减 / 软 404），回滚或按 reports/retro-gsc-deindex-2026-08-13.md 流程处理；",
              "- 向用户同步根因与恢复 ETA（1–4 周）。"]
    elif status == "BLOCKED":
        L += ["## MONITOR BLOCKED（主理人未能取到实时数据）", "",
              body.get("reason", ""),
              "", "## 须用户在本地补位（主理人下轮必跟进，不得视 BLOCKED 为已监控）",
              "- 本地运行：`python tools/metrics_pull.py --gsc --days 30`",
              "- 将生成的 `tools/metrics_<date>.json` 提交到仓库；",
              "- 主理人下轮跑 `python tools/vitals_monitor.py --offline` 复核。"]
    elif status == "STALE":
        L += ["## STALE（快照过期）", "",
              body.get("reason", ""),
              "", "## 须用户在本地补位",
              "- 同上：本地拉新快照并提交，使 offline 分析基于新鲜数据。"]
    else:
        L += ["## 健康", "",
              f"近 7 日曝光 {body.get('recent_imp')} / 点击 {body.get('recent_clk')}；"
              f"前 7 日曝光 {body.get('prior_imp')} / 点击 {body.get('prior_clk')}。无归零或骤降。"]
    txt = "\n".join(L) + "\n"
    with open(ALERT_PATH, "w") as f:
        f.write(txt)
    return txt


def _exit(level):
    return {"P0": 3, "P1": 2, "OK": 0}.get(level, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "online", "offline"], default="auto")
    args = ap.parse_args()

    # ---- offline 模式 ----
    if args.mode == "offline":
        snap = _latest_snapshot()
        if not snap:
            _write_report("BLOCKED", {"mode": "offline",
                          "reason": "离线模式但仓库内无 tools/metrics_*.json 快照。请先在本地产出并提交。"})
            print("STATUS=BLOCKED (no snapshot)")
            sys.exit(4)
        data = json.load(open(snap, encoding="utf-8"))
        gsc = data.get("gsc")
        if not gsc:
            _write_report("BLOCKED", {"mode": "offline",
                          "reason": f"快照 {os.path.basename(snap)} 无 gsc 数据。"})
            sys.exit(4)
        res, level, err = _analyze(gsc)
        if err:
            _write_report("BLOCKED", {"mode": "offline", "reason": err})
            sys.exit(4)
        sdate = _snapshot_date(snap)
        age = (datetime.now() - sdate).days if sdate else 999
        if age > SNAPSHOT_STALE_DAYS:
            _write_report("STALE", {**res, "mode": "offline",
                         "reason": f"最近快照 {os.path.basename(snap)} 距今天 {age} 天（> {SNAPSHOT_STALE_DAYS}）。"})
            print(f"STATUS=STALE (snapshot {age}d old)")
            sys.exit(4)
        print(_write_report(level, {**res, "mode": "offline"}))
        sys.exit(_exit(level))

    # ---- online / auto ----
    try:
        gsc = _load_gsc_online(30)
        snap_path = os.path.join(HERE, f"metrics_{datetime.now():%Y%m%d}.json")
        json.dump({"gsc": gsc}, open(snap_path, "w"), ensure_ascii=False, indent=2)
        res, level, err = _analyze(gsc)
        if err:
            _write_report("BLOCKED", {"mode": "online", "reason": err})
            sys.exit(4)
        print(_write_report(level, {**res, "mode": "online"}))
        sys.exit(_exit(level))
    except Exception as e:
        if args.mode == "online":
            _write_report("BLOCKED", {"mode": "online", "reason": f"在线拉取失败：{e}"})
            print(f"STATUS=BLOCKED: {e}")
            sys.exit(4)
        # auto：回退离线快照
        snap = _latest_snapshot()
        if not snap:
            reason = (f"在线拉取失败（{e}），且仓库内无 tools/metrics_*.json 快照可离线分析。"
                      "沙箱无 Google 出口是已知限制，但主理人不得视其为不监控的借口——"
                      "须显式请用户在本地跑 metrics_pull 并提交快照，下轮必跟进。")
            _write_report("BLOCKED", {"mode": "auto", "reason": reason})
            print("STATUS=BLOCKED (online failed, no snapshot)")
            sys.exit(4)
        sdate = _snapshot_date(snap)
        age = (datetime.now() - sdate).days if sdate else 999
        data = json.load(open(snap, encoding="utf-8"))
        gsc = data.get("gsc")
        if not gsc:
            _write_report("BLOCKED", {"mode": "auto",
                          "reason": f"快照 {os.path.basename(snap)} 无 gsc 数据。"})
            sys.exit(4)
        res, level, err = _analyze(gsc)
        if err:
            _write_report("BLOCKED", {"mode": "auto", "reason": err})
            sys.exit(4)
        if age > SNAPSHOT_STALE_DAYS:
            _write_report("STALE", {**res, "mode": "auto",
                         "reason": f"最近快照 {os.path.basename(snap)} 距今天 {age} 天（> {SNAPSHOT_STALE_DAYS}），请用户在本地补拉新快照。"})
            print(f"STATUS=STALE (snapshot {age}d old)")
            sys.exit(4)
        print(_write_report(level, {**res, "mode": "auto-offline"}))
        sys.exit(_exit(level))


if __name__ == "__main__":
    main()
