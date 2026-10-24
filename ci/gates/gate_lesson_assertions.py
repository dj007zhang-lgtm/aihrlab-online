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
from .regression_rules import (
    load_rules, scan_file, build_meta_corpus, load_allowlists,
)


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    rules = load_rules()
    rep = GateReport(
        "lesson_assertions",
        "历史教训断言（防概念性重复犯错：计数带 / 旧QR-CTA / 被墙资源 / 编辑器工件 / "
        "meta 跨页污染 / og:title-h1 同源）",
    )
    rep.metrics = {"rules": len(rules), "scanned": 0, "violations": 0}

    # 计算型判据（meta_cross_page / meta_field_equals）需要全站语料与存量登记册。
    # 2026-10-23：此前两个消费者都未传 corpus，导致该类规则**静默跳过**
    # ——规则登记了却不生效，正是治理审计要根治的「装饰性门禁」。
    all_html = sorted(rel(site_root, f) for f in walk_html(site_root))
    corpus = build_meta_corpus(site_root, all_html)
    allowlists = load_allowlists(os.path.join(site_root, "ci"))

    for f in walk_html(site_root):
        html = read(f)
        if not is_indexable(html):
            continue
        relf = rel(site_root, f)
        for fd in scan_file(relf, html, rules, scope_filter="site",
                            corpus=corpus, allowlists=allowlists):
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
