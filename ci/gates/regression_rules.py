# -*- coding: utf-8 -*-
"""
regression_rules.py —— 历史教训断言引擎（防概念性重复犯错的核心可复用件）

被 qa_guardian 的 gate_lesson_assertions（全站事后体检）与 scripts/lint_diff.py
（发布前 diff 预防式预检）共同复用。单一真相源：ci/regression_rules.json。

设计要点（回应主理人复盘）：
  - 教训不再是散文笔记，而是一条条可被机器断言的禁用模式。
  - match=within_class 支持上下文限定（如「关注公众号」仅在文章尾页 QR 块内才禁，
    不误伤测评解锁流），避免把合法内容也拦掉。
"""
import os
import re
import json

HERE = os.path.dirname(os.path.abspath(__file__))
# 登记册放在 ci/ 一级（gates 的父目录），与 gate 模块解耦，便于 lint_diff 等外部消费者复用。
RULES_PATH = os.path.join(os.path.dirname(HERE), "regression_rules.json")


def load_rules():
    with open(RULES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("rules", [])


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


def scan_file(rel_path, html, rules, scope_filter=None):
    """对单文件跑全部规则，返回 findings 列表（dict: severity/code/file/detail）。

    scope_filter: 若非 None，仅检查 rule["scope"]==scope_filter 的规则；
                  传 None 表示检查全部（lint_diff 用）。
    """
    findings = []
    for rule in rules:
        if scope_filter and rule.get("scope") != scope_filter:
            continue
        sev = rule.get("severity", "BLOCK")
        code = rule["id"]
        name = rule.get("name", code)
        if rule.get("match") == "within_class":
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
