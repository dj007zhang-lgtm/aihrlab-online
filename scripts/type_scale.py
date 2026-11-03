#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
type_scale.py — 排版尺度（type scale）单一真相源 + 收敛 + 校验

为什么需要它
------------
收敛前 style.css + article.css 共 312 处 font-size 声明、77 种原始写法，
折算成 px 后仍有 52 种不同取值，且集中在 11.56–20.4px 的窄带里连续分布：
0.82 / .84 / .85 / .86 / 0.88 / .9 / 0.92 / .94 / 0.95rem 彼此只差 0.17–0.5px，
肉眼无法区分却让同一视觉层级在全站有七八套近似值。这类「没调过」的参差
不是精度问题，是缺少一个可全局调节的尺度。

设计口径
--------
- 比率 1.1（11:10）。主流体系用 1.125–1.25，本站中文层级密、断点多，
  取较缓的 1.1 可把 269 处 rem 声明的加权平均偏差压到 0.412px、最大 1.19px。
  无渲染比对能力（F4 缺口）时，偏差小比档位少更重要。
- 锚点 1rem = 17px（顶层 html 根字号）。13 档覆盖 12.75–40.12px，
  全部有声明消费，不留装饰性空档。
- 单位用 rem。rem 恒相对根元素，token 定义在 :root 也不改变相对基准，
  因此 768/480 断点（根字号 16/15/14px）的等比缩放行为完整保留。
  换成 px token 会让响应式整体失效，是真实回退。
- 刻意不用 calc() 链式生成：静态站无渲染比对，显式值可逐条核对，风险更低。

收敛范围与刻意豁免
------------------
只替换「纯 rem 数值字面量」。以下按值形态永久豁免，无需手工维护白名单
（另一个需要同步的文件就是新的双真相源）：

  px         固定锚点。正文权威段 17.5px 经 720px / 41 汉字每行 验证；
             门禁 B1/B3 的 px_of() 不解析 var()，改成 token 会让断言退化成 WARN。
             html 根字号 17/16/15/14px 是尺度本身，不能引用尺度。
             .ds-* 是设计系统演示样本，本就展示不同像素值。
  em         相对父级，语义与 rem 不同
  clamp()    流体排版，自带独立响应式策略
  inherit    继承
  0          消除 inline-block 间隙的技巧
  !important 优先级差异，G1 护栏不自动处理

正确性约束
----------
  T1 精确字面量：只替换声明 value 的字符区间，不重排文件、不动属性名与缩进。
  T2 坐标校验：替换前断言原文切片 == 期望值，防止坐标漂移。
  T3 字节对账：落盘后文件大小变化必须等于各替换的字节差之和。
  T4 幂等：重跑必须得到 0 条替换、0 条违规。
  T5 F5 反向验证：--self-test 注入已知缺陷，确认校验抓得住。

用法
----
  python3 scripts/type_scale.py                    # dry-run 报告
  python3 scripts/type_scale.py --apply            # 落盘（含 T2/T3/T4）
  python3 scripts/type_scale.py --check           # 只报 B12 违规
  python3 scripts/type_scale.py --self-test       # F5 注入验证
"""

import argparse
import os
import re
import sys
import tempfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_SOURCES = ["assets/css/style.css", "assets/css/article.css"]

# 档位换算基准。仅用于「把历史 px 值归到哪一档」的静态换算；
# 运行时字号由浏览器按 html 根字号自动计算，不读这个常量。
ROOT_PX = 17.0
RATIO = 1.1

# 单一真相源：新增/调整档位只改这里。
SCALE = [
    ("--fs-1",  0.75),
    ("--fs-2",  0.825),
    ("--fs-3",  0.91),
    ("--fs-4",  1.0),
    ("--fs-5",  1.1),
    ("--fs-6",  1.21),
    ("--fs-7",  1.33),
    ("--fs-8",  1.46),
    ("--fs-9",  1.61),
    ("--fs-10", 1.77),
    ("--fs-11", 1.95),
    ("--fs-12", 2.14),
    ("--fs-13", 2.36),
]

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from converge_css import blank_comments, parse_css_spans  # noqa: E402

_REM = re.compile(r"^\.?\d+(?:\.\d+)?rem$", re.I)
# 声明段形态：前导空白 + 属性名 + 冒号 + value + 余部（!important / 尾随空白）
_DECL = re.compile(r"^(\s*font-size\s*:\s*)([^\s;!]+)(.*)$", re.I | re.S)


def rem_literal(v):
    """纯 rem 数值字面量。var()/px/em/clamp/inherit/!/0 一律 False。"""
    v = (v or "").strip()
    return bool(_REM.match(v)) and "!" not in v


def snap(px):
    """把 px 归到最近档位，返回 (token, rem)。"""
    return min(SCALE, key=lambda x: abs(x[1] * ROOT_PX - px))


def token_for(raw):
    """'0.9rem' / '.92rem' → '--fs-N'"""
    return snap(float(raw.strip()[:-3]) * ROOT_PX)[0]


def plan(files):
    """返回 {file: [(start, end, old, new, meta)]}，坐标为原文字节偏移。"""
    plans = {}
    for f in files:
        text = blank_comments(open(f, encoding="utf-8").read())
        items = []
        for r in parse_css_spans(text):
            for prop, val, s, e in r["decls"]:
                if prop != "font-size" or not rem_literal(val):
                    continue
                seg = text[s:e]
                m = _DECL.match(seg)
                if not m:
                    continue
                old = m.group(2)
                # 解析器给的值必须与原文切片逐字一致，否则保守跳过（T2）
                if old != val:
                    continue
                new = "var(%s)" % token_for(old)
                items.append((s + m.start(2), s + m.end(2), old, new,
                              (r["sel_raw"], val, r["line"])))
        plans[f] = items
    return plans


def apply_text(text, items, path=""):
    """原地替换，从后往前。返回 (new_text, byte_delta)。T2 断言在调用方校验。"""
    delta = 0
    for s, e, old, new, _ in sorted(items, reverse=True):
        if text[s:e] != old:
            raise AssertionError(
                "坐标漂移 %s@%d: 原文 %r != 期望 %r" % (path, s, text[s:e], old))
        text = text[:s] + new + text[e:]
        delta += len(new) - len(old)
    return text, delta


def violations(files):
    """B12 用：仍在用 rem 字面量的 font-size 声明。"""
    out = []
    for f in files:
        text = blank_comments(open(f, encoding="utf-8").read())
        for r in parse_css_spans(text):
            for prop, val, s, e in r["decls"]:
                if prop == "font-size" and rem_literal(val):
                    out.append((os.path.basename(f), r["line"], r["sel_raw"], val))
    return out


def self_test():
    """F5：注入已知缺陷，验证校验有效且替换幂等。"""
    print("== type_scale 自检（注入已知缺陷）==")
    ok_all = True

    # 1) 散落 rem 字号必须被抓到
    good = tempfile.NamedTemporaryFile("w", suffix=".css", delete=False,
                                      encoding="utf-8")
    good.write(".a{font-size:0.937rem;} .b{font-size:.88rem;}")
    good.close()
    got = violations([good.name])
    ok = len(got) == 2
    print("  注入 2 处散落 rem 字号      → %s (%d 处)" % ("抓到" if ok else "漏掉", len(got)))
    ok_all &= ok

    # 2) 豁免形态不得误报
    exempt = tempfile.NamedTemporaryFile("w", suffix=".css", delete=False,
                                         encoding="utf-8")
    exempt.write(".a{font-size:var(--fs-3)} .b{font-size:17.5px} "
                 ".c{font-size:0.9em} .d{font-size:inherit} "
                 ".e{font-size:0} .f{font-size:clamp(1rem,2vw,2rem)} "
                 ".g{font-size:0.85rem !important}")
    exempt.close()
    got = violations([exempt.name])
    ok = len(got) == 0
    print("  6 类豁免形态不得误报        → %s (%d 处)" % ("通过" if ok else "误报", len(got)))
    ok_all &= ok

    # 3) 替换后幂等：再规划必须 0 条
    p = plan([good.name])
    text = open(good.name, encoding="utf-8").read()
    new_text, delta = apply_text(text, p[good.name], good.name)
    tmp2 = tempfile.NamedTemporaryFile("w", suffix=".css", delete=False,
                                       encoding="utf-8")
    tmp2.write(new_text); tmp2.close()
    ok = len(plan([tmp2.name])[tmp2.name]) == 0 and len(violations([tmp2.name])) == 0
    print("  替换后重跑 0 条（幂等 T4）  → %s" % ("通过" if ok else "失败"))
    ok_all &= ok

    # 4) 字节对账 T3
    expect = sum(len(n) - len(o) for _, _, o, n, _ in p[good.name])
    ok = (len(new_text) - len(text)) == delta == expect
    print("  字节对账 T3                 → %s (%+d)" % ("通过" if ok else "失败", delta))
    ok_all &= ok

    # 5) 档位严格递增、比率近似 1.1
    vals = [v for _, v in SCALE]
    ratios = [vals[i + 1] / vals[i] for i in range(len(vals) - 1)]
    ok = all(a < b for a, b in zip(vals, vals[1:])) and all(1.05 < r < 1.15 for r in ratios)
    print("  13 档单调递增 / 比率≈1.1    → %s (%.3f–%.3f)"
          % ("通过" if ok else "失败", min(ratios), max(ratios)))
    ok_all &= ok

    for f in (good.name, exempt.name, tmp2.name):
        os.unlink(f)
    print("自检结论：", "全部命中" if ok_all else "存在漏检（工具不可用）")
    return 0 if ok_all else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="落盘替换")
    ap.add_argument("--check", action="store_true", help="只报 B12 违规")
    ap.add_argument("--self-test", action="store_true", help="F5 注入验证")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    files = [os.path.join(ROOT, r) for r in CSS_SOURCES
             if os.path.exists(os.path.join(ROOT, r))]
    bad = violations(files)
    if args.check:
        print("B12 违规（散落 rem 字号）: %d 处" % len(bad))
        for b in bad[:20]:
            print("  %s:%d %s → %s" % b)
        return 2 if bad else 0

    plans = plan(files)
    total = sum(len(v) for v in plans.values())
    c = Counter(token_for(o) for v in plans.values() for _, _, o, _, _ in v)
    print("待替换 rem 字号声明: %d 处，分布于 %d 档" % (total, len(c)))
    for t in sorted(c, key=lambda x: int(x.split("-")[-1])):
        print("  %-9s ×%d" % (t, c[t]))
    print("刻意豁免（px/em/clamp/inherit/0/!）: %d 处" %
          sum(1 for f in files
              for r in parse_css_spans(blank_comments(open(f, encoding="utf-8").read()))
              for p, v, _, _ in r["decls"]
              if p == "font-size" and not rem_literal(v)))

    if not args.apply:
        print("\n[dry-run] 未落盘。加 --apply 执行。")
        return 0

    for f in files:
        items = plans[f]
        text = open(f, encoding="utf-8").read()
        new_text, delta = apply_text(text, items, f)
        if delta != len(new_text) - len(text):
            print("字节对账失败: %s" % f)
            return 2
        open(f, "w", encoding="utf-8").write(new_text)
        print("写入 %-32s %3d 处  %+d 字节" %
              (os.path.relpath(f, ROOT), len(items), delta))

    # T4 幂等复检
    after = sum(len(v) for v in plan(files).values())
    bad2 = violations(files)
    print("幂等复检: 待替换 %d 处，B12 违规 %d 处" % (after, len(bad2)))
    if after or bad2:
        print("失败：替换未收敛干净")
        return 2
    print("OK：%d 处已收敛，重跑 0 条" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
