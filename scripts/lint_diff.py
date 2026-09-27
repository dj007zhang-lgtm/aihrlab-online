#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_diff.py —— 发布前 diff 级红线预检（防重复犯错·预防式）

为什么需要它（回应 2026-09-27 主理人复盘 RC-B）：
  旧机制全是「发布时才全站体检」的反应式——错误早已落盘，只能回滚。
  本脚本对「本次将要发布的文件」跑历史教训断言，错误在推送前就被拦在门外：
  把『不二犯』从「事后发现」变成「动笔即拦」。

与 qa_guardian.gate_lesson_assertions 的关系：
  共用单一真相源 ci/regression_rules.json（教训登记册），但消费者不同——
  qa_guardian 扫全站（兜底），lint_diff 只扫本次改动（预防）。两者互补。

用法：
  python3 scripts/lint_diff.py file1.html file2.html ...   # 显式文件清单
  python3 scripts/lint_diff.py --git                       # 取 git diff HEAD 改动文件
  python3 scripts/lint_diff.py --stdin                     # 从 stdin 读文件清单（每行一个）
仅检查 .html 文件（CSS/JS 不承载这些设计模式文本，且已被 design_asset_lint 覆盖）。
退出码：0=通过；1=命中被否决设计模式（阻断发布）。
"""
import sys
import os
import subprocess

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SITE_ROOT, "ci", "gates"))
from regression_rules import load_rules, scan_file


def collect_files(args):
    files = [a for a in args if not a.startswith("--")]
    if "--git" in args:
        out = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=SITE_ROOT, capture_output=True, text=True,
        )
        files += [l.strip() for l in out.stdout.splitlines() if l.strip()]
    if "--stdin" in args:
        data = sys.stdin.read()
        files += [l.strip() for l in data.splitlines() if l.strip()]
    seen = set()
    res = []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        if not f.endswith(".html"):
            continue
        p = os.path.join(SITE_ROOT, f)
        if os.path.exists(p):
            res.append((f, p))
    return res


def main():
    args = sys.argv[1:]
    targets = collect_files(args)
    rules = load_rules()
    violations = []
    for relf, p in targets:
        try:
            html = open(p, encoding="utf-8").read()
        except Exception:
            continue
        for fd in scan_file(relf, html, rules):
            violations.append(fd)

    if violations:
        print("🔴 lint_diff 命中已被主理人否决的设计模式（阻断发布）：")
        for v in violations:
            print(f"  [{v['code']}] {v['file']}: {v['detail']}")
        sys.exit(1)
    print(f"✅ lint_diff：{len(targets)} 个 HTML 文件通过历史教训断言预检，无可否决设计模式。")
    sys.exit(0)


if __name__ == "__main__":
    main()
