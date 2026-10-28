#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSS 构建：源版 → 压缩版（真相源唯一化）

背景（2026-10-28 实测）：
  368 个页面实际加载 assets/css/style.min.css，而 style.css（源版）只被 1 个页面引用。
  两个文件之间没有构建关系 —— 改源版不重压缩就完全不生效，是最典型的假成功温床。

纪律：
  - 源：assets/css/style.css      产物：assets/css/style.min.css
  - 产物永远由本脚本生成，禁止手改
  - 生成后必须通过对账：产物的选择器集合 ⊇ 源的选择器集合（防止压缩吃掉内容）
  - 幂等：同样输入必得同样输出

用法：
  python3 scripts/build_css.py            # 构建 + 对账
  python3 scripts/build_css.py --check    # 只检查产物是否最新（不改文件）
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets/css/style.css")
DST = os.path.join(ROOT, "assets/css/style.min.css")


def strip_comments(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def minify(s):
    s = strip_comments(s)
    strs = []

    def keep(m):
        strs.append(m.group(0))
        return "\x00%d\x00" % (len(strs) - 1)

    s = re.sub(r'"[^"]*"|\'[^\']*\'', keep, s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([{}:;,>])\s*", r"\1", s)
    s = s.replace(";}", "}")
    s = s.strip()
    for i, v in enumerate(strs):
        s = s.replace("\x00%d\x00" % i, v)
    return s


def selectors(s):
    """提取顶层与嵌套规则的选择器集合（去空白、小写）"""
    s = strip_comments(s)
    out = set()
    for m in re.finditer(r"([^{}]+)\{", s):
        sel = m.group(1).strip()
        if sel.startswith("@"):
            continue
        out.add(re.sub(r"\s+", "", sel).lower())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查产物是否最新")
    args = ap.parse_args()

    if not os.path.exists(SRC):
        print("源缺失：%s" % SRC)
        return 2
    src = open(SRC, encoding="utf-8").read()
    want = minify(src)

    if args.check:
        cur = open(DST, encoding="utf-8").read() if os.path.exists(DST) else ""
        same = cur == want
        print("产物是否最新：%s" % ("是" if same else "否（需跑 build_css.py）"))
        return 0 if same else 2

    # 对账：选择器集合必须一致
    a, b = selectors(src), selectors(want)
    missing = a - b
    if missing:
        print("!! 压缩后丢失选择器 %d 个，中止：" % len(missing))
        for x in sorted(missing)[:10]:
            print("   -", x[:90])
        return 2
    print("选择器对账：源 %d / 产物 %d，无丢失" % (len(a), len(b)))

    before = open(DST, encoding="utf-8").read() if os.path.exists(DST) else ""
    open(DST, "w", encoding="utf-8").write(want)
    check = open(DST, encoding="utf-8").read()
    if check != want:
        print("!! 落盘字节对账失败")
        return 2
    print("构建完成：%d → %d 字节（源 %d，省 %.0f%%）"
          % (len(before), len(want), len(src), (1 - len(want) / max(1, len(src))) * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
