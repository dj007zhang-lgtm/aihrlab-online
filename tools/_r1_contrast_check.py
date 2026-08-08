#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R1 深色模式对比度自校验（P1 闸门前置）。
验证拟采用的 [data-theme="dark"] token 集在深底上的 WCAG 对比度：
  - 正文文本 vs 底色  ≥ 4.5:1 (AA)
  - 次要/大文本 vs 底色 ≥ 3:1  (AA 大文本/次要)
  - 交互色（链接/按钮文字）vs 底色 ≥ 4.5:1
  - 按钮文字 vs 按钮底（accent）≥ 4.5:1
不依赖第三方库，纯计算。
"""
def lum(hexv):
    h = hexv.lstrip('#')
    r, g, b = int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255
    def f(c):
        return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)

def ratio(c1, c2):
    L1, L2 = lum(c1), lum(c2)
    hi, lo = max(L1, L2), min(L1, L2)
    return (hi+0.05)/(lo+0.05)

# 拟采用的深色 token（草案）
BG      = "#0B0C0E"   # obsidian
BG_SUB  = "#16191D"
BG_WARM = "#1A1D21"
TEXT        = "#ECEAE4"
TEXT_SEC    = "#A6ADB8"
TEXT_MUTED  = "#6B7280"
TEXT_LINK   = "#9CC06A"
TEXT_LINK_H = "#B4E33D"
ACCENT      = "#6F9A3C"
ACCENT_PALE = "#1E2A12"  # 深苔底（accent-pale 在深底的取值，用于提示块）
SURFACE     = "#16191D"

checks = [
    ("正文 TEXT on BG",            TEXT,     BG,      4.5),
    ("次要 TEXT_SEC on BG",        TEXT_SEC, BG,      3.0),
    ("弱 TEXT_MUTED on BG",        TEXT_MUTED,BG,      3.0),
    ("链接 TEXT_LINK on BG",       TEXT_LINK,BG,      4.5),
    ("链接hover TEXT_LINK_H on BG",TEXT_LINK_H,BG,    4.5),
    ("accent 作文字 TEXT on ACCENT",BG,       ACCENT,  4.5),  # 按钮：深字 on accent
    ("正文 TEXT on BG_SUBTLE",     TEXT,     BG_SUB,  4.5),
    ("正文 TEXT on SURFACE",       TEXT,     SURFACE, 4.5),
    ("次要 TEXT_SEC on BG_SUBTLE", TEXT_SEC, BG_SUB,  3.0),
    ("提示块 TEXT on ACCENT_PALE", TEXT,     ACCENT_PALE,4.5),
    ("链接 TEXT_LINK on BG_SUBTLE",TEXT_LINK,BG_SUB,  4.5),
]

all_ok = True
for name, fg, bg, need in checks:
    r = ratio(fg, bg)
    ok = r >= need
    all_ok = all_ok and ok
    print(f"{'✓' if ok else '✗'} {name:32s} {r:5.2f}:1  (需≥{need})")

print("\n结论:", "全部达标 AA" if all_ok else "存在未达标项，需调整 token")
raise SystemExit(0 if all_ok else 1)
