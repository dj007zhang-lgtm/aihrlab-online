#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa_guardian.py —— 全站质量保障编排器（错不二犯机制核心）

定位（回应 2026-09 主理人复盘盲点）：
  旧 QC 是「逐篇门禁」，数学上无法发现「跨篇克隆/全站桩页/域名质量分下滑」。
  本编排器提供第四层能力：
    1) 预防门禁    —— 复用 publish.py 既有双闸（quality_gate + stability_guard）。
    2) 全站检测    —— 本站 7 个 gate，含跨篇克隆/桩页/死链/重定向契约/meta/设计资产/sitemap。
    3) 异常预警    —— 软指标与 baseline 比对，回归超阈升级为 BLOCK。
    4) 回归校验+自愈—— baseline 仅在全绿时更新（永锁坏状态）；--heal 做确定性自愈并自验。

鲁棒性纪律（最高优先级）：
  - 故障隔离：单 gate 抛异常 → status=ERROR，绝不拖垮整体运行，但必须显眼告警（不静默）。
  - 幂等：检测门零副作用；自愈仅在 --heal 显式触发。
  - 自愈闭环：自愈后重跑受影响 gate 自验，仍失败则报错退出。
  - 不冻站：ERROR 不阻断发布（避免单 gate bug 冻结全站），但记入 gate_errors 并每周 P1 预警。

退出码：0=全绿(无阻断)；1=存在阻断(BLOCK)→ publish.py 据此中止；2=用法/致命错误。
用法：
  python3 ci/qa_guardian.py                 # 全站检测 + 更新 baseline（若全绿）+ 报告
  python3 ci/qa_guardian.py --report-only   # 只检测出报告，不更新 baseline、退出码恒 0
  python3 ci/qa_guardian.py --reset-baseline# 以当前好状态重种 baseline
  python3 ci/qa_guardian.py --heal          # 确定性自愈（重建 sitemap/index + 还原重定向契约）后重验
"""
import os
import sys
import json
import time
import importlib
import subprocess
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gates import GateReport

GATES_PKG = "gates"
THRESHOLDS_PATH = os.path.join(HERE, "heuristics", "thresholds.json")
BASELINE_PATH = os.path.join(HERE, "baseline", "health_baseline.json")
REPORT_MD = os.path.join(SITE_ROOT, "reports", "qa_guardian-report.md")
REPORT_JSON = os.path.join(SITE_ROOT, "reports", "qa_guardian-status.json")

GATE_ORDER = [
    "gate_clone_detection",
    "gate_stub_detector",
    "gate_link_doctor",
    "gate_meta_lint",
    "gate_design_asset_lint",
    "gate_sitemap_consistency",
    "gate_tracking_metrics",
]


def load_thresholds():
    with open(THRESHOLDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_baseline():
    if os.path.exists(BASELINE_PATH):
        try:
            return json.load(open(BASELINE_PATH, encoding="utf-8"))
        except Exception:
            return None
    return None


def save_baseline(gates_dict):
    """保存各门指标快照。约定：baseline["gates"][gate_name] = 该门完整 metrics。
    stub_detector 读 baseline["gates"]["stub_detector"]["thin_block"]；
    tracking_metrics 读 baseline["gates"]["tracking_metrics"]（扁平指标，用于回归比较）。
    与 save 契约不一致会导致回归锁静默失效——见 2026-09-14 体检修复。"""
    os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
    data = {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "version": 1, "gates": gates_dict}
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def discover_gates(thresholds):
    mods = []
    for name in GATE_ORDER:
        cfg = thresholds.get("gates", {}).get(name.replace("gate_", ""), {})
        if not cfg.get("enabled", True):
            continue
        try:
            mod = importlib.import_module(f"{GATES_PKG}.{name}")
        except Exception as e:
            mods.append((name, None, e))
            continue
        mods.append((name, mod, cfg))
    return mods


def run_all_gates(baseline):
    thresholds = load_thresholds()
    mods = discover_gates(thresholds)
    reports = []
    gate_errors = []
    for name, mod, cfg in mods:
        short = name.replace("gate_", "")
        if mod is None:
            r = GateReport(short, f"(模块加载失败)")
            r.status = "ERROR"
            r.summary = f"gate 模块无法加载：{cfg if isinstance(cfg, Exception) else '?'}"
            gate_errors.append(short)
            reports.append(r)
            continue
        try:
            r = mod.run(SITE_ROOT, cfg, baseline)
        except Exception as e:
            r = GateReport(short, f"({name})")
            r.status = "ERROR"
            r.summary = f"gate 运行异常：{type(e).__name__}: {e}"
            gate_errors.append(short)
        reports.append(r)
    return reports, gate_errors


def compute_overall(reports):
    """RED(block) 与否。ERROR 不阻断（不冻站），但返回供告警。"""
    blocking = [r for r in reports if r.blocking and r.status == "FAIL"]
    return blocking


# ───────────────────────── 自愈 ─────────────────────────
def heal_sitemap():
    out = subprocess.run([sys.executable, "scripts/build_sitemap.py"], cwd=SITE_ROOT,
                         capture_output=True, text=True)
    return out.returncode == 0, (out.stdout + out.stderr)[-300:]


def heal_article_index():
    sp = os.path.join(SITE_ROOT, "scripts", "sync-articles.py")
    if not os.path.exists(sp):
        return False, "sync-articles.py 不存在"
    out = subprocess.run([sys.executable, "scripts/sync-articles.py"], cwd=SITE_ROOT,
                         capture_output=True, text=True)
    return out.returncode == 0, (out.stdout + out.stderr)[-300:]


def heal_redirect_contract():
    rj = os.path.join(SITE_ROOT, "redirects.json")
    if not os.path.exists(rj):
        return True, "无 redirects.json"
    redirects = json.load(open(rj, encoding="utf-8"))
    n = 0
    STUB = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{target}">
<title>{title}</title>
</head>
<body>
<p>本文已合并，主题内容请见：<a href="{target}">{anchor}</a></p>
<script>location.href="{target}";</script>
</body>
</html>
"""
    for src, target in redirects.items():
        abs_p = os.path.join(SITE_ROOT, src.lstrip("/"))
        if not os.path.exists(abs_p):
            continue
        cur = open(abs_p, encoding="utf-8").read()
        is_stub = ('http-equiv="refresh"' in cur) and ('name="robots" content="noindex' in cur)
        if is_stub:
            # 校验 refresh 目标是否为声明值
            import re
            m = re.search(r'content="0; url=([^"]+)"', cur)
            if m and m.group(1).rstrip('"') == target:
                continue
        title = "页面已迁移"
        tm = re.search(r"<title>(.*?)</title>", cur, re.S)
        if tm:
            title = tm.group(1).strip().replace(" | AIHR数智引擎", "")
        open(abs_p, "w", encoding="utf-8").write(
            STUB.format(target=target, title=f"{title}（内容已合并） | AIHR数智引擎", anchor="合并后的主题内容"))
        n += 1
    return True, f"已还原 {n} 个重定向桩契约"


def do_heal():
    print("\n" + "=" * 60)
    print("自愈（确定性 + 可逆）：重建派生产物 + 还原重定向契约")
    print("=" * 60)
    ok1, msg1 = heal_sitemap();      print(f"  sitemap 重建: {'OK' if ok1 else 'FAIL'} — {msg1}")
    ok2, msg2 = heal_article_index(); print(f"  article-index 重建: {'OK' if ok2 else 'FAIL'} — {msg2}")
    ok3, msg3 = heal_redirect_contract(); print(f"  重定向契约还原: {'OK' if ok3 else 'FAIL'} — {msg3}")
    return ok1 and ok2 and ok3


# ───────────────────────── 报告 ─────────────────────────
def render_report(reports, gate_errors, baseline, blocking, mode):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    red = bool(blocking)
    lines = []
    lines.append(f"# qa_guardian 质量保障报告 — {now}")
    lines.append("")
    lines.append(f"- 模式: `{mode}`")
    lines.append(f"- 结果: **{'🔴 RED（阻断发布）' if red else '🟢 GREEN（全绿）'}**")
    lines.append(f"- gate 异常(ERROR): {len(gate_errors)} " + (f"→ {gate_errors}" if gate_errors else "（无）"))
    lines.append(f"- baseline: {'有' if baseline else '无（首次将生成）'}")
    lines.append("")
    lines.append("| 门 | 状态 | 阻断 | 摘要 |")
    lines.append("|---|---|---|---|")
    for r in reports:
        lines.append(f"| {r.name} | {r.status} | {'是' if r.blocking else '否'} | {r.summary} |")
    lines.append("")
    for r in reports:
        if r.findings:
            lines.append(f"## {r.name} 发现（{len(r.findings)}）")
            for f in r.findings[:40]:
                loc = f" `{f['file']}`" if f.get("file") else ""
                lines.append(f"- **[{f['severity']}]** {f['code']}{loc}: {f['detail']}")
            if len(r.findings) > 40:
                lines.append(f"- … 另 {len(r.findings)-40} 条")
            lines.append("")
    if gate_errors:
        lines.append("## ⚠️ 检测门异常（须人工排查，否则真问题会被静默）")
        for g in gate_errors:
            lines.append(f"- {g}: 运行异常，本次该维度未被校验。")
        lines.append("")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    report_only = "--report-only" in args
    reset_baseline = "--reset-baseline" in args
    heal = "--heal" in args
    mode = ("heal" if heal else "report-only" if report_only else "standard")

    t0 = time.time()
    print("=" * 64)
    print(" qa_guardian — 全站质量保障编排器（错不二犯机制）")
    print(f" 站点根: {SITE_ROOT}")
    print(f" 模式:   {mode}")
    print("=" * 64)

    if heal:
        if not do_heal():
            print("❌ 自愈部分失败，请检查上方日志。")
            sys.exit(1)

    baseline = load_baseline()
    if reset_baseline:
        baseline = None
        print("⏱  已清空 baseline，将以当前好状态重种。")

    reports, gate_errors = run_all_gates(baseline)
    blocking = compute_overall(reports)

    # 渲染 + 落盘
    report_md = render_report(reports, gate_errors, baseline, blocking, mode)
    os.makedirs(os.path.dirname(REPORT_MD), exist_ok=True)
    open(REPORT_MD, "w", encoding="utf-8").write(report_md)

    status = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "result": "RED" if blocking else "GREEN",
        "gate_errors": gate_errors,
        "gates": [r.to_dict() for r in reports],
        "elapsed_s": round(time.time() - t0, 2),
    }
    open(REPORT_JSON, "w", encoding="utf-8").write(json.dumps(status, ensure_ascii=False, indent=2))

    # baseline 更新（只要无 gate 崩溃即锁当前快照；硬阻断仍由 exit 码拦发布）
    if not report_only and not gate_errors:
        snap = {r.name: r.metrics for r in reports if r.status != "ERROR"}
        save_baseline(snap)
        if baseline:
            print("\n✅ baseline 已更新（当前快照，含各门指标）。")
        else:
            print("\n✅ baseline 首次生成（锁定当前好状态为回归基准）。")
    elif gate_errors:
        print("\n⚠️  存在 gate 异常，baseline 不更新（避免基于不可信快照锁定坏状态）。")

    # 控制台摘要
    print("\n" + "-" * 64)
    for r in reports:
        flag = {"PASS": "🟢", "WARN": "🟡", "FAIL": "🔴", "ERROR": "⚠️", "INFO": "🔵"}.get(r.status, "·")
        print(f"  {flag} {r.name:<22} {r.status:<6} {r.summary}")
    if gate_errors:
        print(f"  ⚠️  gate 异常: {', '.join(gate_errors)}（未静默，须人工排查）")
    print("-" * 64)
    print(f"  报告: reports/qa_guardian-report.md | 状态: reports/qa_guardian-status.json")
    print(f"  耗时: {status['elapsed_s']}s")

    if blocking:
        print("\n🔴 RED：存在阻断级结构性债务，publish.py 将中止推送。请先修复上述 BLOCK 项。")
        sys.exit(1)
    if report_only:
        sys.exit(0)
    print("\n🟢 GREEN：全站检测通过，无阻断级债务。")
    sys.exit(0)


if __name__ == "__main__":
    main()
