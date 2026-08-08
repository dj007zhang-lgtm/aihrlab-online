#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_r1_fix_inline_comments.py —— 修复「单行压缩内联脚本 + // 行注释」导致的整块 JS 静默崩溃。

根因：
  minify 把内联 <script> 压成单行，但保留了 `//` 行注释。单行中第一个 `//`
  会把其后**全部代码**吞成注释 → 括号失衡 → SyntaxError: Unexpected end of input
  → 整块脚本不执行（浏览器静默失败，页面照常渲染，功能全废）。

为什么双闸测不出：
  Gate 15 只对 assets/js/*.js 跑 node --check，不扫 HTML 内联脚本；
  stability_guard 只看 .html/.css 文本结构，不做 JS 解析。

修法（最小影响面）：
  在目标 script 块内，按**精确字面串**删除注释文本，不改任何一行可执行代码。
  每处替换断言「命中且仅命中 1 次」，替换后立即 node --check 复验。

用法：
  python3 tools/_r1_fix_inline_comments.py [--dry-run]
"""
import re
import subprocess
import sys
import tempfile
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
NODE = "/Users/andyzhang/.workbuddy/binaries/node/versions/22.22.2/bin/node"

# (相对路径, 用于定位 script 块的唯一锚点, [要删除的注释字面串...])
TARGETS = [
    (
        "articles/index.html",
        "INITIAL_BATCH",
        [
            "// ========== 配置 ==========",
            "// 首屏展示条数",
            "// 滚动每次加载条数",
            "// ========== 渲染批次 ==========",
            "// 更新底部指示器",
            "// ========== 滚动懒加载 ==========",
            "// 距离底部 < 400px 时触发",
            "// 节流 scroll 事件",
            "// ========== 分类筛选（集成批次逻辑）==========",
            "// 按钮状态",
            "// 先淡出所有卡片",
            "// 延迟后显示匹配的卡片",
            "// 重置批次，显示前 INITIAL_BATCH 条",
            "// 更新 URL hash",
            "// ========== 页面加载时初始化 ==========",
            "// ========== spin 动画 ==========",
        ],
    ),
    (
        "articles/microsoft-anthropic-ai-org-restructure.html",
        "showQRModal",
        ["// 门控事件追踪", "// 门控曝光追踪"],
    ),
    (
        "assets/hr-prompt-cards.html",
        "toggleExpand",
        ["// Fallback"],
    ),
    # 以下两处：注释吞掉代码后语法**依然有效**（变成空脚本/半截脚本），
    # 故 node --check 抓不到，只有「单行 + 真 // 注释」这条规则能抓 —— 静默失效最危险。
    (
        "resources/index.html",
        "window.openGate",
        # openGate 定义保住了（弹窗能开），但 ESC 关闭与点遮罩关闭被整段吞掉 → 弹窗打开后关不掉
        ["// ESC 关闭", "// 点击遮罩关闭"],
    ),
    (
        "assets/dq-evaluation.html",
        "updateDimScore",
        # 注释在整段最开头 → 整个 DQ 打分卡逻辑（选项点击/计分/计算/出结果）全被吞 → 工具完全不可用
        ["// QOption click handling", "// Weighted: dim1=30%, dim2=25%, dim3=25%, dim4=20%"],
    ),
]

# 额外的精确修补：(相对路径, 锚点, [(原文, 替换)...])
# dq-evaluation.html 的 actions 数组用 `}` 闭合（应为 `];`）——这处真实语法错误
# 长期被开头的 `//` 注释掩盖，删注释后才会暴露，必须同时修掉。
PATCHES = [
    (
        "assets/dq-evaluation.html",
        "updateDimScore",
        [("（他们是最好的AI采纳推动者）', }", "（他们是最好的AI采纳推动者）' ]; }")],
    ),
]

SCRIPT_RE = re.compile(r"(<script\b([^>]*)>)(.*?)(</script>)", re.S | re.I)


def node_check(js: str):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        tmp = f.name
    r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True)
    os.unlink(tmp)
    return r.returncode == 0, r.stderr.strip()


def main():
    dry = "--dry-run" in sys.argv
    failed = 0
    for rel, anchor, comments in TARGETS:
        path = ROOT / rel
        html = path.read_text(encoding="utf-8")
        hit = None
        for m in SCRIPT_RE.finditer(html):
            if anchor in m.group(3) and "src=" not in m.group(2).lower():
                hit = m
                break
        if not hit:
            print(f"❌ {rel}: 未找到锚点 {anchor} 的内联脚本块")
            failed += 1
            continue

        body = hit.group(3)
        ok_before, _ = node_check(body)
        new_body = body

        # 先应用精确修补（修复被注释掩盖的真实语法错误）
        for prel, panchor, pairs in PATCHES:
            if prel != rel or panchor != anchor:
                continue
            for old, new in pairs:
                n = new_body.count(old)
                if n > 1:
                    print(f"❌ {rel}: 修补字面串命中 {n} 次（期望 0 或 1）: {old!r}")
                    failed += 1
                    break
                if n == 1:
                    new_body = new_body.replace(old, new)

        removed = 0
        for c in comments:
            n = new_body.count(c)
            if n > 1:
                print(f"❌ {rel}: 注释字面串命中 {n} 次（期望 0 或 1）: {c!r}")
                failed += 1
                break
            if n == 1:
                new_body = new_body.replace(c, "")
                removed += 1
        else:
            ok_after, err = node_check(new_body)
            if not ok_after:
                print(f"❌ {rel}: 替换后仍语法错误 → {err.splitlines()[0] if err else '?'}")
                failed += 1
                continue
            if new_body == body:
                print(f"⏭️  {rel}: 已是修复后状态，跳过（幂等）")
                continue
            status = "修复前语法崩溃" if not ok_before else "修复前语法有效但注释吞码（静默失效）"
            if dry:
                print(f"🔍 {rel}: 可修复（{status} → 修复后 node --check 通过，删除 {removed} 处注释）")
            else:
                out = html[: hit.start(3)] + new_body + html[hit.end(3):]
                path.write_text(out, encoding="utf-8")
                print(f"✅ {rel}: 已修复（{status}，删除 {removed} 处注释，node --check 通过）")

    print(f"\n{'DRY-RUN 完成' if dry else '修复完成'}，失败 {failed} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
