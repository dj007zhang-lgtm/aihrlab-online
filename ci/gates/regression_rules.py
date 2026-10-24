# -*- coding: utf-8 -*-
"""
regression_rules.py —— 历史教训断言引擎（防概念性重复犯错的核心可复用件）

被 qa_guardian 的 gate_lesson_assertions（全站事后体检）与 scripts/lint_diff.py
（发布前 diff 预防式预检）共同复用。单一真相源：ci/regression_rules.json。

设计要点（回应主理人复盘）：
  - 教训不再是散文笔记，而是一条条可被机器断言的禁用模式。
  - match=within_class 支持上下文限定（如「关注公众号」仅在文章尾页 QR 块内才禁，
    不误伤测评解锁流），避免把合法内容也拦掉。

2026-10-23 引擎扩展（治理审计直接产物）：
  原引擎只支持字面量子串匹配（any / within_class），因此「A 是否等于 B」
  「本页字段是否混入他页标题」这类需要跨字段/跨文件计算的不变量，
  处于**结构性零覆盖**状态。实证：og:title 被两条标题拼接损坏、
  description 被注入他篇标题，305 页 × 10 次合规巡检全部存活；
  且把历史损坏值原样喂回门禁 9，判定为 0 FAIL / 0 WARN 完全放行。
  故新增计算型 match：
    meta_field_equals   两字段必须相等（h1 == og:title）
    meta_cross_page     指定 meta 字段不得包含其他页面的标题（拼接 / 注入污染）
"""
import os
import re
import json
from html import unescape as html_unescape

HERE = os.path.dirname(os.path.abspath(__file__))
# 登记册放在 ci/ 一级（gates 的父目录），与 gate 模块解耦，便于 lint_diff 等外部消费者复用。
RULES_PATH = os.path.join(os.path.dirname(HERE), "regression_rules.json")


def load_rules():
    with open(RULES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("rules", [])


def load_allowlists(root_ci):
    """加载 {rule_id: set(rel_path)} —— 存量例外登记册。

    设计原则（2026-10-23）：不容忍静默偏差。存量偏差必须**显式登记**才降级为
    WARN，任何未登记的新偏差一律 BLOCK。登记册本身可审计（条目只减不增）。
    """
    out = {}
    for rule in load_rules():
        fn = rule.get("allowlist")
        if not fn:
            continue
        p = os.path.join(root_ci, fn)
        if not os.path.exists(p):
            out[rule["id"]] = set()
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("entries", data) if isinstance(data, dict) else data
            out[rule["id"]] = set(i["file"] if isinstance(i, dict) else i for i in items)
        except Exception:
            out[rule["id"]] = set()
    return out


def _extract_blocks(html, class_name, window=5000):
    """提取所有 class 含 class_name 的元素后续文本（到 window 字符为止，QR 块不会更长）。"""
    out = []
    pat = re.compile(
        r'<[a-zA-Z][^>]*class="[^"]*' + re.escape(class_name) + r'[^"]*"[^>]*>',
        re.S | re.I,
    )
    for m in pat.finditer(html):
        start = m.end()
        out.append(html[start:start + window])
    return out


# ---------------------------------------------------------------------------
# 计算型判据所需：页面字段提取 + 语料构建
# ---------------------------------------------------------------------------
def _meta_value(html, field):
    """提取页面字段：h1 / title / og:title / twitter:title / description。"""
    if field == "h1":
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
        if not m:
            return None
        v = re.sub(r"<[^>]+>", "", m.group(1))
        return re.sub(r"\s+", " ", html_unescape(v)).strip() or None
    if field == "title":
        m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        return re.sub(r"\s+", " ", html_unescape(m.group(1))).strip() if m else None
    for m in re.finditer(r"<meta\s+([^>]*?)/?>", html, re.S | re.I):
        attrs = m.group(1)
        k = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
        v = re.search(r'content\s*=\s*["\']([^"\']*)["\']', attrs, re.I)
        if k and v and k.group(1).lower() == field.lower():
            return re.sub(r"\s+", " ", html_unescape(v.group(1))).strip()
    return None


def build_meta_corpus(root, html_files):
    """构建 {rel_path: {field: value}}，供 meta_cross_page 判据使用。

    只收录可索引页：noindex 跳转壳的标题是目标页副本，会制造大量假阳性。
    """
    corpus = {}
    for rel in html_files:
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                html = f.read()
        except Exception:
            continue
        if re.search(r'name=["\']robots["\'][^>]*noindex', html, re.I):
            continue
        entry = {}
        for fld in ("h1", "title", "og:title", "twitter:title", "description"):
            entry[fld] = _meta_value(html, fld)
        if entry.get("h1") or entry.get("title"):
            corpus[rel] = entry
    return corpus


def scan_file(rel_path, html, rules, scope_filter=None, corpus=None, allowlists=None):
    """对单文件跑全部规则，返回 findings 列表（dict: severity/code/file/detail）。

    scope_filter: 若非 None，仅检查 rule["scope"]==scope_filter 的规则；
                  传 None 表示检查全部（lint_diff 用）。
    corpus:       build_meta_corpus() 产物，计算型规则需要（可选，无则跳过）。
    allowlists:   load_allowlists() 产物，命中登记册的存量偏差降级为 WARN。
    """
    findings = []
    allowlists = allowlists or {}
    for rule in rules:
        if scope_filter and rule.get("scope") != scope_filter:
            continue
        sev = rule.get("severity", "BLOCK")
        code = rule["id"]
        name = rule.get("name", code)
        mt = rule.get("match", "any")

        # ---- 计算型判据 1：字段必须相等 ----
        if mt == "meta_field_equals":
            fa, fb = rule["fields"][0], rule["fields"][1]
            va, vb = _meta_value(html, fa), _meta_value(html, fb)
            if va and vb and va != vb:
                if rel_path in allowlists.get(code, set()):
                    findings.append({
                        "severity": "WARN", "code": code, "file": rel_path,
                        "detail": (f"[{name}] {fa} 与 {fb} 不一致（存量已登记，"
                                   f"待裁决统一口径）: 「{va}」 vs 「{vb}」"),
                    })
                else:
                    findings.append({
                        "severity": sev, "code": code, "file": rel_path,
                        "detail": f"[{name}] {fa} 与 {fb} 必须一致: 「{va}」 vs 「{vb}」",
                    })
            continue

        # ---- 计算型判据 2：meta 字段不得混入他页标题 ----
        if mt == "meta_cross_page":
            if corpus:
                minlen = rule.get("min_len", 14)
                excl = set(rule.get("exclude", []))
                against = rule.get("against", ("h1", "title"))
                for fld in rule.get("fields", []):
                    val = _meta_value(html, fld) or ""
                    if not val:
                        continue
                    for other, entry in corpus.items():
                        if other == rel_path or other in excl or rel_path in excl:
                            continue
                        for srcf in against:
                            cand = (entry.get(srcf) or "").replace("| AIHR数智引擎", "").strip()
                            if len(cand) >= minlen and cand in val:
                                findings.append({
                                    "severity": sev, "code": code, "file": rel_path,
                                    "detail": (f"[{name}] {fld} 混入了 {other} 的标题"
                                               f"（拼接损坏 / 注入污染）: 「{cand}」"),
                                })
                                # 同一来源页命中一次即止，避免 h1/title 双源重复上报
                                break
            continue

        # ---- 原有字面量判据 ----
        if mt == "within_class":
            cls = rule.get("block_class", "")
            blocks = _extract_blocks(html, cls)
            for b in blocks:
                for pat in rule.get("patterns", []):
                    if pat in b:
                        findings.append({
                            "severity": sev, "code": code, "file": rel_path,
                            "detail": f"[{name}] 块 .{cls} 内含禁用文本「{pat}」",
                        })
        else:
            for pat in rule.get("patterns", []):
                if pat in html:
                    findings.append({
                        "severity": sev, "code": code, "file": rel_path,
                        "detail": f"[{name}] 命中禁用模式「{pat}」",
                    })
    return findings
