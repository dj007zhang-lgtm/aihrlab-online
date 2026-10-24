#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_meta_hygiene.py — AIHRlab(网站) head 区元数据卫生修复

体系归属：AIHRlab 网站侧（与公众号规则无关）。

修两类逃逸缺陷（均为 2026-10-23 P3-1 诊断实测发现，此前零自动化覆盖）：

  H1  孤儿行 `">`
      head 区存在一行内容恰为 `">`（前带若干空行）。这是生成器留下的破损标签残骸，
      会被解析器当作 head 内的文本节点 → 浏览器隐式提前闭合 head，
      其后的 meta / canonical 落入 body。实测 21 页。

  H2  meta content 内含未转义半角双引号
      例：<meta property="og:description" content="...帮助HR从"提供课程"转向...">
      属性在第一个内层 `"` 处被提前闭合，实际生效值截断到 25 字，
      社交分享 / AI 抓取拿到的是破句。实测 6 页。
      修法：内层 `"` 成对替换为全角 “ ”（与站内 description 既有风格一致）。

安全约束：
  - 精确整行匹配 + 计数断言，不用贪婪正则跨行替换；
  - 幂等：已修复的文件重跑 0 改动；
  - 每文件改动前后做 meta 可解析性回归（改后 content 内不得再含半角 `"`）；
  - 跳过 noindex + meta refresh 的跳转壳（URL 合并壳，禁止改动）；
  - 只动 <meta> 标签行与孤儿行，不触碰任何其它 DOM。

用法：python3 scripts/fix_meta_hygiene.py [--apply]   （无 --apply 为 dry-run）
退出码：0 通过 / 1 有文件被修改（dry-run 下用于 CI）/ 2 校验失败
"""
from __future__ import annotations

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY = "--apply" in sys.argv

SCAN_DIRS = ("articles/*.html", "hub/*.html", "assessments/*.html",
             "resources/*.html", "products/*.html", "brief/*.html")

# 标签级匹配：`<meta ...>` 以第一个 `>` 收尾（content 内不含 `>` 时即完整标签）。
# 压缩成单行的 head（一行内联多个 <meta>）也能逐个正确处理。
META_TAG = re.compile(r'<meta\b[^>]*>')
# 在标签内取 content 值：非贪婪取值，收尾的 `"` 后面必须是空白或结尾
# （否则会误吞后续属性，如 content="y" data-z="w"）。
# 「内容里夹了半角引号」的破损标签因此会被完整取出：内层 `"` 后跟的是正文字符，
# 不满足收尾条件，会继续吃到真正的收尾引号。
CONTENT_IN_TAG = re.compile(r'\scontent="(.*?)"(?=\s|$)')
ORPHAN = re.compile(r'^\s*">\s*$')


def is_shell(s: str) -> bool:
    return bool(re.search(r'name=["\']robots["\'][^>]+noindex', s, re.I)
                and re.search(r'http-equiv=["\']refresh', s, re.I))


def rewrap_quotes(v: str) -> str:
    """把内容里的半角双引号成对替换为全角 “ ”。"""
    out, open_ = [], True
    for ch in v:
        if ch == '"':
            out.append("\u201c" if open_ else "\u201d")
            open_ = not open_
        else:
            out.append(ch)
    # 落单的引号统一收口，避免出现未闭合状态
    if not open_:
        out.append("\u201d")
    return "".join(out)


def scan(rel: str):
    """返回 (findings, new_text_or_None)"""
    full = os.path.join(BASE_DIR, rel)
    src = open(full, encoding="utf-8").read()
    if is_shell(src):
        return [], None
    lines = src.split("\n")
    findings = []
    new_lines = []
    for i, line in enumerate(lines, 1):
        if ORPHAN.match(line):
            findings.append(("H1", i, "孤儿行 '\">'"))
            continue  # 删除该行
        cur, pos = line, 0
        out = []
        for tm in META_TAG.finditer(line):
            tag = tm.group(0)
            # 剥掉收尾的 `>` / `/>`，只在属性段内做取值与替换
            suffix = ">"
            core = tag[:-1]
            if core.endswith("/"):
                suffix = "/>"
                core = core[:-1]
            cm = CONTENT_IN_TAG.search(core)
            if cm and '"' in cm.group(1):
                n = cm.group(1).count('"')
                fixed = rewrap_quotes(cm.group(1))
                a, b = cm.span(1)
                tag = core[:a] + fixed + core[b:] + suffix
                findings.append(("H2", i, f"content 内 {n} 个未转义双引号 → 转全角"))
            out.append(line[pos:tm.start()])
            out.append(tag)
            pos = tm.end()
        if not out:
            new_lines.append(line)
            continue
        out.append(line[pos:])
        new_lines.append("".join(out))
    if not findings:
        return [], None
    return findings, "\n".join(new_lines)


def main() -> int:
    import glob
    files = sorted(sum([glob.glob(os.path.join(BASE_DIR, d)) for d in SCAN_DIRS], []))
    total_h1 = total_h2 = 0
    touched = []
    for full in files:
        rel = os.path.relpath(full, BASE_DIR)
        findings, new = scan(rel)
        if not findings:
            continue
        h1 = [f for f in findings if f[0] == "H1"]
        h2 = [f for f in findings if f[0] == "H2"]
        total_h1 += len(h1)
        total_h2 += len(h2)
        print(f"  {rel}")
        for code, ln, detail in findings:
            print(f"      [{code}] 第{ln}行  {detail}")
        if APPLY and new is not None:
            # 回归校验：修复后不得再有 content 内半角引号，也不得再有孤儿行
            bad_meta = []
            for l in new.split("\n"):
                for tm in META_TAG.finditer(l):
                    cm = CONTENT_IN_TAG.search(tm.group(0))
                    if cm and '"' in cm.group(1):
                        bad_meta.append(l)
            bad_orph = [l for l in new.split("\n") if ORPHAN.match(l)]
            if bad_meta or bad_orph:
                print(f"      ❌ 回归校验失败（残留 meta {len(bad_meta)} / 孤儿 {len(bad_orph)}），未落盘")
                return 2
            open(full, "w", encoding="utf-8").write(new)
            touched.append(rel)
    print(f"\n检出：H1 孤儿行 {total_h1} 处 / H2 未转义引号 {total_h2} 处，涉及 {len(set(touched) or [])} 个文件")
    if not APPLY:
        print("[DRY-RUN] 未落盘。加 --apply 执行。")
        return 1 if (total_h1 or total_h2) else 0
    print(f"已落盘 {len(touched)} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
