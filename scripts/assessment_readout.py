#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assessment_readout.py — 测评完成数据读数（2026-11-05）

把百度统计「访问分析 → 事件分析」导出 CSV，读成「完成次数 + 匿名类型分布」。
口径全文见 reports/assessment-data-readout.md。

用法：
    python3 scripts/assessment_readout.py <事件分析CSV> [--out <报告.md>] [--window <窗口说明>]
    python3 scripts/assessment_readout.py --self-test

设计红线：
  1. 只统计 action == assessment_complete 的行；没有事件名称列时，必须显式声明
     整表就是该事件的 label 明细（--assume-complete），否则拒绝推断。
  2. 识别不出列名时打印真实表头并退出 2，绝不靠位置猜数字。
  3. 数值解析失败的行计入「无法解析」并逐行报出，不静默丢弃。
  4. 不推算「完成人数」「完成率」：分母（访问人数 / 测评开始数）不在此导出中。
  5. 不合并不同窗口的导出；一次只吃一个文件。
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict

LABEL_KEYS = ["事件标签", "标签", "label", "Label", "event_label", "事件 label"]
COUNT_KEYS = ["事件数", "触发次数", "事件次数", "次数", "数量", "PV", "浏览量", "count", "value"]
ACTION_KEYS = ["事件名称", "事件", "action", "Action", "event", "事件 action"]

ENCODINGS = ["utf-8-sig", "gbk", "utf-8"]
LABEL_RE = re.compile(r"^([A-Za-z0-9_-]+):(.+)$")


def read_rows(path):
    raw = open(path, "rb").read()
    text = None
    used = None
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            used = enc
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise SystemExit("FAIL 无法解码 CSV（试过 %s）" % ", ".join(ENCODINGS))
    # GA4 / 百度统计导出常带 # 注释头，跳过后再找表头
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise SystemExit("FAIL CSV 无有效数据行")
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    rows = list(reader)
    return rows, list(reader.fieldnames or []), used


def pick(fieldnames, candidates, what):
    for c in candidates:
        for f in fieldnames:
            if f.strip() == c:
                return f
    # 退一步：包含匹配，但仍要求唯一
    hits = [f for f in fieldnames for c in candidates if c in f.strip()]
    if len(set(hits)) == 1:
        return hits[0]
    raise SystemExit(
        "FAIL 识别不出「%s」列。真实表头：%s\n"
        "     请用 --label-col / --count-col / --action-col 显式指定，不要靠猜。"
        % (what, fieldnames)
    )


def parse_count(v):
    s = str(v if v is not None else "").strip().replace(",", "").replace("，", "")
    s = s.replace("%", "").strip()
    if not s:
        return None
    try:
        n = int(round(float(s)))
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None


def analyze(path, args):
    rows, fields, enc = read_rows(path)
    label_col = args.label_col or pick(fields, LABEL_KEYS, "事件标签 / label")
    count_col = args.count_col or pick(fields, COUNT_KEYS, "事件数 / 次数")

    action_col = args.action_col
    if action_col is None and not args.assume_complete:
        try:
            action_col = pick(fields, ACTION_KEYS, "事件名称 / action")
        except SystemExit:
            raise SystemExit(
                "FAIL 表里没有事件名称列，无法确认哪些行是 assessment_complete。\n"
                "     若整个 CSV 已按该事件筛选，请加 --assume-complete 显式声明。"
            )

    by_id = defaultdict(Counter)
    other_events = 0
    unparsed = []
    malformed = []
    total = 0

    for i, r in enumerate(rows, start=2):
        action = (r.get(action_col) or "").strip() if action_col else "assessment_complete"
        if action != "assessment_complete":
            other_events += 1
            continue
        label = (r.get(label_col) or "").strip()
        n = parse_count(r.get(count_col))
        if n is None:
            unparsed.append((i, label, r.get(count_col)))
            continue
        m = LABEL_RE.match(label)
        if not m:
            malformed.append((i, label, n))
            continue
        by_id[m.group(1)][m.group(2)] += n
        total += n

    return {
        "path": path, "enc": enc, "fields": fields,
        "label_col": label_col, "count_col": count_col, "action_col": action_col,
        "rows": len(rows), "total": total, "by_id": by_id,
        "other_events": other_events, "unparsed": unparsed, "malformed": malformed,
    }


def render(res, window):
    L = []
    L.append("# 测评完成数据读数")
    L.append("")
    L.append("- 数据源：`%s`（编码 %s）" % (res["path"], res["enc"]))
    L.append("- 统计窗口：%s" % (window or "**未提供，须从导出文件名 / 百度统计后台确认后再对外引用**"))
    L.append("- 口径：**事件数（次）**，不是人数，也不是完成率。前端已按「测评 ID + runKey」做会话内去重。")
    L.append("- 识别列：label=`%s`，次数=`%s`，事件名=`%s`" % (
        res["label_col"], res["count_col"], res["action_col"] or "整表假定为 assessment_complete"))
    L.append("")
    L.append("## 总览")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 完成次数合计 | %d |" % res["total"])
    L.append("| 涉及测评 | %d 套 |" % len(res["by_id"]))
    L.append("| 其他事件行（已忽略） | %d |" % res["other_events"])
    L.append("| 格式不符 label 行 | %d |" % len(res["malformed"]))
    L.append("| 次数无法解析行 | %d |" % len(res["unparsed"]))
    L.append("| 扫描数据行 | %d |" % res["rows"])
    L.append("")
    L.append("## 按测评拆分")
    L.append("")
    if not res["by_id"]:
        L.append("> 无有效 assessment_complete 记录。可能原因：埋点刚上线尚未产生数据、导出窗口不对、导出的是别的事件。")
    for aid in sorted(res["by_id"]):
        cats = res["by_id"][aid]
        sub = sum(cats.values())
        L.append("### `%s`（%d 次）" % (aid, sub))
        L.append("")
        L.append("| 结果类别 | 次数 | 占该测评 |")
        L.append("|---|---:|---:|")
        for cat, n in cats.most_common():
            L.append("| %s | %d | %.1f%% |" % (cat, n, (n / sub * 100) if sub else 0.0))
        L.append("")
        if "completed" in cats:
            L.append("> `%s` 无天然结果类别，`completed` 只贡献完成次数，**不参与类型分布解读**。" % aid)
            L.append("")
    if res["malformed"]:
        L.append("## 格式不符的 label（不静默丢弃）")
        L.append("")
        for i, label, n in res["malformed"][:30]:
            L.append("- 第 %d 行：`%s`（%d 次）" % (i, label, n))
        L.append("")
    if res["unparsed"]:
        L.append("## 次数无法解析（不静默丢弃）")
        L.append("")
        for i, label, v in res["unparsed"][:30]:
            L.append("- 第 %d 行：label=`%s`，次数原值=`%s`" % (i, label, v))
        L.append("")
    L.append("## 不可据此得出的结论")
    L.append("")
    L.append("- **不能说「多少用户做完了测评」**：事件数是「次」，未去重到人；分母不在此导出中。")
    L.append("- **不能算完成率**：`assessment_start` 是站内点击数，与完成事件不同粒度，禁止相除。")
    L.append("- **不能与 GA4 旧窗口页面浏览量同框**：两者渠道部分重叠、窗口不同，见 `reports/kpi-read-2026-10-22-query-detail.md` 第 5 节。")
    L.append("- **样本量小不谈分布**：任一测评完成次数 < 30 时，类型占比只作定性观察，不写进结论。")
    L.append("- **历史完成数无法回溯**：埋点上线前的完成行为从未上报，任何导出都不会包含。")
    L.append("")
    return "\n".join(L) + "\n"


def self_test():
    sample = (
        "事件名称,事件标签,事件数\n"
        "assessment_complete,disc:D,12\n"
        "assessment_complete,disc:I,8\n"
        "assessment_complete,mbti:INTJ,5\n"
        "assessment_complete,tarot:completed,7\n"
        "gate_view,/articles/x.html,99\n"
        "assessment_complete,bad-label-no-colon,3\n"
        "assessment_complete,holland:RIA,abc\n"
    )
    fd, p = tempfile.mkstemp(suffix=".csv")
    os.write(fd, sample.encode("utf-8-sig")); os.close(fd)
    try:
        class A:  # 模拟默认参数
            label_col = count_col = action_col = None
            assume_complete = False
        r = analyze(p, A())
        assert r["total"] == 32, ("total", r["total"])
        assert r["by_id"]["disc"] == Counter({"D": 12, "I": 8}), r["by_id"]["disc"]
        assert r["by_id"]["tarot"] == Counter({"completed": 7})
        assert r["other_events"] == 1, r["other_events"]
        assert len(r["malformed"]) == 1 and len(r["unparsed"]) == 1
        txt = render(r, "self-test")
        assert "完成次数合计 | 32" in txt and "不参与类型分布解读" in txt
        # 反例：缺事件名列时不得静默推断
        sample2 = "事件标签,事件数\ndisc:D,12\n"
        fd2, p2 = tempfile.mkstemp(suffix=".csv")
        os.write(fd2, sample2.encode("utf-8-sig")); os.close(fd2)
        try:
            try:
                analyze(p2, A())
                print("FAIL self-test: 缺事件名列时未拒绝推断"); return 1
            except SystemExit:
                pass
        finally:
            os.unlink(p2)
        print("PASS self-test：正常统计 / 其他事件忽略 / 坏 label 报出 / 坏数值报出 / 缺列拒绝推断")
        return 0
    finally:
        os.unlink(p)


def main():
    ap = argparse.ArgumentParser(description="测评完成事件读数（百度统计事件分析导出）")
    ap.add_argument("csv", nargs="?", help="百度统计事件分析 CSV")
    ap.add_argument("--out", help="输出 Markdown 报告路径")
    ap.add_argument("--window", help="统计窗口说明，如 2026-11-05~2026-11-12")
    ap.add_argument("--assume-complete", action="store_true", help="整表已是 assessment_complete 的 label 明细")
    ap.add_argument("--label-col"), ap.add_argument("--count-col"), ap.add_argument("--action-col")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.csv:
        print("用法：python3 scripts/assessment_readout.py <事件分析CSV> [--out 报告.md] [--window 窗口]")
        return 2
    if not os.path.exists(args.csv):
        print("FAIL 文件不存在：%s" % args.csv)
        return 2

    res = analyze(args.csv, args)
    txt = render(res, args.window)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(txt)
        print("报告已写：%s" % args.out)
    print("完成次数合计 %d 次，涉及 %d 套测评；格式不符 %d 行，次数无法解析 %d 行，其他事件 %d 行"
          % (res["total"], len(res["by_id"]), len(res["malformed"]),
             len(res["unparsed"]), res["other_events"]))
    for aid in sorted(res["by_id"]):
        print("  %-12s %4d 次  %s" % (aid, sum(res["by_id"][aid].values()),
              ", ".join("%s=%d" % (k, v) for k, v in res["by_id"][aid].most_common())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
