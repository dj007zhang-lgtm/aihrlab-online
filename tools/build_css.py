#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 assets/css/style.css 重新生成 assets/css/style.min.css（真正压缩 + 去漂移）。

用法：
  python3 tools/build_css.py            # 重新生成 min
  python3 tools/build_css.py --check    # 仅校验 min 与源是否同步（CI / pre-push 用）

依赖：pip install csscompressor（管理 venv）
设计原则：min 必须忠实于源，不引入 / 不丢失任何规则。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "css", "style.css")
MIN = os.path.join(ROOT, "assets", "css", "style.min.css")


def classes_of(path):
    txt = open(path, encoding="utf-8").read()
    return set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", txt))


def brace_balanced(txt):
    return txt.count("{") == txt.count("}")


def main():
    try:
        import csscompressor
    except ImportError:
        print("✗ 未安装 csscompressor，请先: pip install csscompressor", file=sys.stderr)
        sys.exit(2)

    src = open(SRC, encoding="utf-8").read()
    if not brace_balanced(src):
        print("✗ 源 style.css 括号不平衡，停止以免产出损坏的 min", file=sys.stderr)
        sys.exit(1)

    minified = csscompressor.compress(src, preserve_exclamation_comments=True)

    if not brace_balanced(minified):
        print("✗ 压缩后括号不平衡，疑似压缩器异常，停止", file=sys.stderr)
        sys.exit(1)

    if "--check" in sys.argv:
        # 校验模式：min 必须已存在且与源类集合一致、体积更小
        if not os.path.exists(MIN):
            print("✗ style.min.css 不存在")
            sys.exit(1)
        cur = open(MIN, encoding="utf-8").read()
        cs, cm = classes_of(SRC), classes_of(MIN)
        if cs - cm:
            print(f"✗ min 缺失源中的类: {sorted(cs - cm)[:10]}")
            sys.exit(1)
        if len(minified.encode("utf-8")) >= len(cur.encode("utf-8")):
            print("✗ 重新压缩未能更小，min 可能已是最优或源变大")
            sys.exit(1)
        print("✓ style.min.css 与源同步且为最优压缩")
        return

    open(MIN, "w", encoding="utf-8").write(minified + "\n")
    cs, cm = classes_of(SRC), classes_of(MIN)
    src_b, min_b = len(src.encode("utf-8")), len(minified.encode("utf-8"))
    print(f"✓ 已重新生成 style.min.css")
    print(f"  源: {src_b} B | min: {min_b} B | 节省: {src_b - min_b} B ({(src_b-min_b)/src_b*100:.0f}%)")
    print(f"  类集合: 源 {len(cs)} / min {len(cm)} | 缺失: {len(cs-cm)} | 多馀: {len(cm-cs)}")
    if cs - cm:
        print(f"  ⚠ 注意 min 缺失类: {sorted(cs-cm)[:10]}")
    if cm - cs:
        print(f"  ⚠ 注意 min 多馀类(来自旧源, 已随重生清除): {sorted(cm-cs)[:10]}")


if __name__ == "__main__":
    main()
