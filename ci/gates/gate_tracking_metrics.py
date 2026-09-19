# -*- coding: utf-8 -*-
"""
gate_tracking_metrics —— 软指标基线回归锁定（错不二犯核心）

日常 QC 只看表层卫生，从不为"整站质量分"设基线。本门把 2026-09 整改后的好状态
固化为 baseline，任何向坏方向的回归都升级为阻断：
  - 可索引页中位数正文数跌超 median_words_pct%  → BLOCK
  - GEO 元数据覆盖率掉超 geo_cov_pp 个百分点    → BLOCK
  - OG 图覆盖率掉超 og_cov_pp 个百分点          → BLOCK
  - JSON-LD 覆盖率掉超 jsonld_cov_pp 个百分点    → BLOCK
其他软指标仅 WARN 进报告。

baseline 仅在「全站无 BLOCK 级发现」时由编排器更新，确保永不锁定坏状态。
"""
import re
import time
from . import (walk_html, read, is_indexable, clean_text, count_cjk,
               extract_article_body, GateReport, Finding)

GEO_AF = re.compile(r'name=["\']answer-for["\']', re.I)
GEO_SA = re.compile(r'name=["\'](?:twitter|short-answer)["\']', re.I)
OG_PAT = re.compile(r'property=["\']og:image["\']', re.I)
JSONLD = re.compile(r'application/ld\+json')
QR_PAT = re.compile(r'article-footer-qr|footer-qr')
INLINE = re.compile(r'class=["\'][^"\']*inline-related')


def _compute(site_root):
    files = [f for f in walk_html(site_root, ["articles"]) if is_indexable(read(f))]
    total = len(files)
    counts = []
    cov = {"geo": 0, "og": 0, "jsonld": 0, "qr": 0, "inline": 0}
    for f in files:
        html = read(f)
        counts.append(count_cjk(clean_text(extract_article_body(html))))
        if GEO_AF.search(html) and GEO_SA.search(html):
            cov["geo"] += 1
        if OG_PAT.search(html):
            cov["og"] += 1
        if JSONLD.search(html):
            cov["jsonld"] += 1
        if QR_PAT.search(html):
            cov["qr"] += 1
        if INLINE.search(html):
            cov["inline"] += 1
    counts.sort()
    median = counts[len(counts) // 2] if counts else 0
    def pct(k):
        return round(100.0 * cov[k] / total, 1) if total else 0.0
    return {
        "indexable_articles": total,
        "median_words": median,
        "geo_cov": pct("geo"),
        "og_cov": pct("og"),
        "jsonld_cov": pct("jsonld"),
        "qr_cov": pct("qr"),
        "inline_cov": pct("inline"),
    }


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    p = cfg.get("params", {})
    lock = p.get("regression_lock", {})
    cur = _compute(site_root)
    rep = GateReport("tracking_metrics", "软指标基线回归锁定")
    rep.metrics = cur

    base = (baseline or {}).get("gates", {}).get("tracking_metrics", {})
    if not base:
        rep.status = "INFO"
        rep.summary = f"首次运行无 baseline；当前快照已记录（中位数 {cur['median_words']} 字）。"
        rep.elapsed_s = round(time.time() - t0, 2)
        return rep

    escalations = []
    # 中位数字数回归
    mwp = lock.get("median_words_pct", 30)
    if cur["median_words"] < base.get("median_words", 0) * (1 - mwp / 100.0):
        escalations.append(f"中位数正文 {cur['median_words']} < baseline {base['median_words']}×(1-{mwp}%)")
        rep.add(Finding("BLOCK", "REGRESS-MEDIAN-WORDS",
                        detail=f"正文深度回归超 {mwp}%：{cur['median_words']} vs {base['median_words']}"))
    # 覆盖率回归（百分点）
    for key, pp_key, label in [("geo_cov", "geo_cov_pp", "GEO"),
                               ("og_cov", "og_cov_pp", "OG图"),
                               ("jsonld_cov", "jsonld_cov_pp", "JSON-LD")]:
        pp = lock.get(pp_key, 10)
        drop = base.get(key, 0) - cur[key]
        if drop >= pp:
            escalations.append(f"{label}覆盖率降 {drop}pp")
            rep.add(Finding("BLOCK", f"REGRESS-{label.upper()}-COV",
                            detail=f"{label}覆盖率 {cur[key]}% 较 baseline {base.get(key,0)}% 降 {drop}pp（≥{pp}）"))

    if escalations:
        rep.status = "FAIL"
        rep.blocking = True
        rep.summary = "基线回归锁定触发（阻断）：" + "；".join(escalations)
    else:
        rep.status = "PASS"
        deltas = {k: round(cur[k] - base.get(k, 0), 1) for k in cur}
        rep.summary = f"相对 baseline 无回归（中位数 {cur['median_words']}字，GEO {cur['geo_cov']}%，OG {cur['og_cov']}%）。"
        rep.metrics["_deltas_vs_baseline"] = deltas
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
