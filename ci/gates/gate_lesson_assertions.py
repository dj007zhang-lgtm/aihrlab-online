# -*- coding: utf-8 -*-
"""
gate_lesson_assertions —— 历史教训断言门（错不二犯机制·反应式全站体检）

核心纠偏（回应 2026-09-27 主理人复盘）：
  旧 qa_guardian 只查「可量化结构债」（JSON-LD/克隆/死链…），根本查不到
  「被否决的设计意图」——改名一个 class 就全盲，导致首页计数带 9/5 从死 CSS 复活。
  本门把 ci/regression_rules.json 里登记的每条历史教训变成全站断言：
    计数带 / 旧 QR v0 导流号召 / 被墙第三方资源 / 编辑器工件。
  任一 BLOCK 命中 → 门 FAIL + blocking → publish.py 中止。

鲁棒性：复用 gates 基础设施；抛异常由编排器捕获为 ERROR，绝不拖垮整体。
"""
import os
import time
from . import (walk_html, read, is_indexable, rel, GateReport, Finding)
from .regression_rules import load_rules, scan_file


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    rules = load_rules()
    rep = GateReport(
        "lesson_assertions",
        "历史教训断言（防概念性重复犯错：计数带 / 旧QR-CTA / 被墙资源 / 编辑器工件）",
    )
    rep.metrics = {"rules": len(rules), "scanned": 0, "violations": 0}

    for f in walk_html(site_root):
        html = read(f)
        if not is_indexable(html):
            continue
        relf = rel(site_root, f)
        for fd in scan_file(relf, html, rules, scope_filter="site"):
            rep.add(Finding(fd["severity"], fd["code"], file=fd["file"], detail=fd["detail"]))
            rep.metrics["violations"] += 1
        rep.metrics["scanned"] += 1

    if rep.metrics["violations"] == 0:
        rep.status = "PASS"
        rep.summary = f"全站扫描 {rep.metrics['scanned']} 页 / {len(rules)} 条历史教训断言，零违例。"
    else:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = (f"命中 {rep.metrics['violations']} 处已被主理人否决的设计模式"
                       f"（概念性重复犯错），须清除后再发布。")
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
