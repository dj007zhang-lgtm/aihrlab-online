#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_inline_scripts.py —— Gate 18「内联脚本运行时语法关」

补的是什么盲区
--------------
Gate 15（共享资源完整性关）只对 `assets/js/*.js` 跑 `node --check`；
stability_guard 只做 .html/.css 的文本结构检查。**HTML 内联 <script> 无人校验。**

于是出现过这样的线上事故（2026-08-08 R1 冒烟时用真实浏览器才抓到）：
  minify 把内联脚本压成单行，却保留了 `//` 行注释 →
  单行中第一个 `//` 吞掉其后**全部代码** → 括号失衡 → SyntaxError →
  整块脚本静默不执行。页面照常渲染、双闸全绿、监控无感，但功能全废。
  实际损失：/articles/ 列表页分类筛选与滚动懒加载完全失效（站内导航主入口）。

检测项
------
硬失败：
  1. 内联脚本 `node --check` 不通过（确定性崩溃）。
  2. 单行内联脚本中存在真实 `//` 行注释（不在字符串/模板串/块注释内）。
     即使当前侥幸未崩，这也是同一根因的定时炸弹；正确压缩不应留下它。

跳过：
  - 带 src 的外链脚本；
  - type 非 JavaScript 的块（application/ld+json 等）；
  - 空白块。

契约：run(site_root) -> (passed: bool, details: list[str])
自测：python3 scripts/check_inline_scripts.py --selftest
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
TYPE_RE = re.compile(r'type\s*=\s*["\']([^"\']+)["\']', re.I)

_NODE_CANDIDATES = [
    "/Users/andyzhang/.workbuddy/binaries/node/versions/22.22.2/bin/node",
]


def _node_bin():
    for c in _NODE_CANDIDATES:
        if os.path.exists(c):
            return c
    return shutil.which("node")


def has_line_comment(js: str) -> bool:
    """判断 JS 源码中是否存在真实的 `//` 行注释（排除字符串 / 模板串 / 块注释内的 //）。"""
    i, n = 0, len(js)
    quote = None          # ' " ` 之一
    in_block = False
    while i < n:
        ch = js[i]
        nxt = js[i + 1] if i + 1 < n else ""
        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"`":
            quote = ch
            i += 1
            continue
        if ch == "/" and nxt == "*":
            in_block = True
            i += 2
            continue
        if ch == "/" and nxt == "/":
            return True
        i += 1
    return False


def iter_inline_scripts(html: str):
    """产出 (起始行号, 脚本源码)。"""
    for m in SCRIPT_RE.finditer(html):
        attrs, body = m.group(1), m.group(2)
        if "src=" in attrs.lower():
            continue
        t = TYPE_RE.search(attrs)
        if t and "javascript" not in t.group(1).lower():
            continue
        if not body.strip():
            continue
        yield html[: m.start()].count("\n") + 1, body


def node_check(node, js: str):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        tmp = f.name
    try:
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
    finally:
        os.unlink(tmp)
    if r.returncode == 0:
        return True, ""
    err = [l for l in (r.stderr or "").splitlines() if "Error" in l]
    return False, (err[0].strip() if err else "语法错误")


def run(site_root):
    node = _node_bin()
    if not node:
        return False, ["未找到 node，无法校验内联脚本语法"]

    details = []
    scanned_files = 0
    scanned_blocks = 0

    for dirpath, dirnames, filenames in os.walk(site_root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        for fn in filenames:
            if not fn.endswith(".html"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, site_root)
            try:
                html = open(path, encoding="utf-8", errors="replace").read()
            except Exception as e:
                details.append(f"{rel}: 读取失败 {e}")
                continue
            scanned_files += 1
            for line_no, body in iter_inline_scripts(html):
                scanned_blocks += 1
                ok, err = node_check(node, body)
                if not ok:
                    details.append(
                        f"{rel}:{line_no} 内联脚本语法错误 → {err}"
                        f"（片段: {body.strip()[:60]}…）"
                    )
                    continue
                if "\n" not in body.strip() and has_line_comment(body):
                    details.append(
                        f"{rel}:{line_no} 单行内联脚本残留 `//` 行注释（会吞掉后续代码，改用 /* */）"
                        f"（片段: {body.strip()[:60]}…）"
                    )

    if details:
        return False, details
    return True, [f"扫描 {scanned_files} 个 HTML / {scanned_blocks} 个内联脚本块，语法全部有效、无单行 // 注释隐患"]


# ============================================================
# 自测：用负样本证伪（不能只证真）
# ============================================================
def _selftest():
    node = _node_bin()
    if not node:
        print("❌ selftest: 未找到 node")
        return False

    cases = []

    # 1. has_line_comment 单元用例
    unit = [
        ("var a=1; // 注释", True, "裸行注释"),
        ("var u='https://a.com/x';", False, "字符串内 // 不算注释"),
        ('var u="http://a.com"; var b=1;', False, "双引号字符串内 //"),
        ("var t=`x://y`;", False, "模板串内 //"),
        ("/* // 块注释里的 */ var a=1;", False, "块注释内 //"),
        ("var a=1; /* x */ // 真注释", True, "块注释后的真注释"),
        ("var a=1;", False, "无注释"),
    ]
    for src, expect, name in unit:
        got = has_line_comment(src)
        cases.append((got == expect, f"has_line_comment[{name}] 期望{expect} 实得{got}"))

    # 2. 端到端负样本：真实事故形态必须被抓到
    with tempfile.TemporaryDirectory() as td:
        bad = os.path.join(td, "bad.html")
        # 单行压缩 + // 注释 → 吞掉后续代码 → 语法错误
        open(bad, "w", encoding="utf-8").write(
            "<html><body><script>(function(){ // 配置 var a=1; })();</script></body></html>"
        )
        passed, det = run(td)
        cases.append((passed is False, f"负样本(单行//吞代码) 应判 FAIL，实得 passed={passed}"))
        cases.append((any("语法错误" in d or "//" in d for d in det),
                      f"负样本应给出可定位详情，实得 {det[:1]}"))

    with tempfile.TemporaryDirectory() as td:
        # 语法正确但单行残留 // 注释（在末尾，侥幸没崩）→ 仍应拦截
        risky = os.path.join(td, "risky.html")
        open(risky, "w", encoding="utf-8").write(
            "<html><body><script>var a=1; // 末尾注释</script></body></html>"
        )
        passed, det = run(td)
        cases.append((passed is False, f"隐患样本(单行末尾//) 应判 FAIL，实得 passed={passed}"))

    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "good.html")
        open(good, "w", encoding="utf-8").write(
            "<html><body>"
            "<script>(function(){ /* 配置 */ var a=1; var u='https://x.com/y'; })();</script>"
            '<script type="application/ld+json">{"a": 1}</script>'
            '<script src="/assets/js/main.js" defer></script>'
            "<script>\nvar b = 2; // 多行脚本里的注释是安全的\nvar c = 3;\n</script>"
            "</body></html>"
        )
        passed, det = run(td)
        cases.append((passed is True, f"正样本应判 PASS，实得 passed={passed} det={det[:1]}"))

    ok = all(c[0] for c in cases)
    for good_case, msg in cases:
        print(("  ✅ " if good_case else "  ❌ ") + msg)
    print(("✅ check_inline_scripts selftest 全部通过" if ok else "❌ check_inline_scripts selftest 失败"))
    return ok


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if _selftest() else 1)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p, d = run(root)
    for x in d:
        print(("✅ " if p else "❌ ") + x)
    sys.exit(0 if p else 1)
