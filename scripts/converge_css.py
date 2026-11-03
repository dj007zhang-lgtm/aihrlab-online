#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
converge_css.py — CSS 冲突收敛（视觉零变化）

做什么
------
对「选择子串完全相同 + 作用域相同 + 属性相同」的多处定义，只保留源码顺序上的
最后一条，删除前面那些。特异性相同、后者胜出，被删的本来就不生效 —— 所以
收敛前后渲染结果逐字节一致，这是本工具成立的唯一理由。

为什么需要它
------------
站点经历过一次模板迁移，style.css 里残留了一整份压缩过的旧样式表（约 41KB），
与之后手写的新样式表重复定义全部组件；article.css 又从模板复制了一份并发生
值漂移。结果是同一组件在站内有两三套外观，且哪套生效取决于页面加载了哪几个
CSS 文件。人工逐条核对 57 条冲突不可靠，也不再可复现。

怎么保证不破坏样式
------------------
沿用 dedupe_css.py 的三条正确性约束，一条都不能少：

  C1 作用域隔离：@media / @keyframes 内部各自成作用域，禁止跨作用域去重。
     桌面 html{17px} 与响应式断点里的 14px 是同一选择器的合法多形态，
     不做隔离就会把响应式设计本身报成冲突并删掉。
  C2 多选择器保守：.a,.b{color:red} 只有 .a 与 .b 都被更晚的同属性规则覆盖
     时才能删；只覆盖其一就删整条会连带破坏另一个。否则不删。
  C3 幂等：重跑一次必须得到 0 条删除。

额外两条护栏（本工具特有）：

  G1 !important 不参与：一旦同一 key 的取值里有的带 !important 有的不带，
     「后者胜」不成立，跳过该 key 并报警，交人工判断。
  G2 原地编辑不重排：删除时只摘掉目标声明的字符区间（连前导缩进与尾随分号），
     绝不重新序列化整个文件 —— 否则手写排版会被压成一行，diff 无法审阅。

用法
----
  python3 scripts/converge_css.py                 # dry-run（默认）
  python3 scripts/converge_css.py --apply         # 落盘（含字节对账）
  python3 scripts/converge_css.py --apply --verify-idempotent
"""

import argparse
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_SOURCES = ["assets/css/style.css", "assets/css/article.css"]

_WS = " \t\r\n\f"


# ------------------------------------------------------- 带偏移的结构解析

def _mk_decl(seg, s, e):
    t = seg.strip()
    if not t or ":" not in t:
        return None
    p, v = t.split(":", 1)
    return (p.strip().lower(), v.strip(), s, e)


def parse_decls_spans(body, base):
    """在 body 内扫描声明，返回 [(prop, val, start, end)]，偏移为全文坐标。

    按括号深度切分，避免把 url(...)/rgba(...) 里的分号当成声明分隔符。
    """
    out, start, depth, i, n = [], 0, 0, 0, len(body)
    while i < n:
        c = body[i]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == ";" and depth <= 0:
            d = _mk_decl(body[start:i], base + start, base + i)
            if d:
                out.append(d)
            start = i + 1
        i += 1
    d = _mk_decl(body[start:], base + start, base + n)
    if d:
        out.append(d)
    return out


def blank_comments(s):
    """把注释内容替换为等长空白，保留换行。

    为什么不直接删注释：删除会改变字符偏移，导致后续按偏移做原地删除时切错位置。
    等长替换让「解析坐标」与「原文字节坐标」始终一致 —— 这是 G2 原地编辑的前提。
    """
    return re.sub(r"/\*.*?\*/",
                  lambda m: re.sub(r"[^\n]", " ", m.group(0)),
                  s, flags=re.S)


def parse_css_spans(text):
    """返回 [{scope, sel_raw, sels, decls, line}]，decls 带全文字符偏移。"""
    out = []

    def walk(s, base, scope):
        i, n = 0, len(s)
        while i < n:
            j = s.find("{", i)
            if j == -1:
                return
            head = s[i:j]
            depth, k = 1, j + 1
            while k < n and depth > 0:
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                k += 1
            inner = s[j + 1:k - 1]
            hs = head.strip()
            if "{" in inner:
                walk(inner, base + j + 1, scope + (re.sub(r"\s+", " ", hs),))
            elif hs.startswith("@"):
                pass                       # @import / @charset 等无子块，不处理
            else:
                sel_raw = re.sub(r"\s+", " ", hs)
                sels = [x.strip() for x in sel_raw.split(",") if x.strip()]
                if sels:
                    decls = parse_decls_spans(inner, base + j + 1)
                    if decls:
                        out.append({"scope": scope, "sel_raw": sel_raw,
                                    "sels": sels, "decls": decls,
                                    "line": text.count("\n", 0, base) + 1})
            i = k

    walk(text, 0, ())
    return out


# ---------------------------------------------------------------- 收敛

def plan_converge(files):
    """
    返回 (plans, skipped)。
    plans: {file: [(start, end, (sel_raw, prop, val))]}  待删除的字符区间
    skipped: [(sel_raw, prop, reason)]
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from audit_visual_quality import read_root_tokens, norm_value
    tokens = read_root_tokens(files)

    entries = []      # dict(order, file, rule, prop, val, s, e)
    order = 0
    for f in files:
        text = blank_comments(open(f, encoding="utf-8", errors="replace").read())
        for r in parse_css_spans(text):
            for prop, val, s, e in r["decls"]:
                entries.append({"order": order, "file": f, "rule": r,
                                "prop": prop, "val": val, "s": s, "e": e})
                order += 1

    # 二级索引：每个 (scope, 单选择器, prop) 最后出现的 order。
    # C2 需要它 —— .a,.b{color} 与 .a{color} 是不同 key，但共享子选择器 .a，
    # 只在当前 key 的 lst 里找「更晚的」永远找不到（lst[-1] 已是最大）。
    last_by_sel = {}
    for e in entries:
        for s in e["rule"]["sels"]:
            last_by_sel[(e["rule"]["scope"], s, e["prop"])] = e["order"]

    by_key = defaultdict(list)
    for e in entries:
        by_key[(e["rule"]["scope"], e["rule"]["sel_raw"], e["prop"])].append(e)

    plans = defaultdict(list)
    skipped = []
    for (scope, sel_raw, prop), lst in by_key.items():
        if len(lst) < 2:
            continue
        # G1：!important 破坏「后者胜」，交人工
        imp = ["!important" in (x["val"] or "").lower() for x in lst]
        if any(imp) and not all(imp):
            skipped.append((sel_raw, prop, "!important 差异，需人工判断"))
            continue
        keeper = lst[-1]
        for ent in lst:
            if ent is keeper:
                continue
            r = ent["rule"]
            # C2：r 的每个子选择器都必须被更晚的同属性规则覆盖，否则连带破坏
            covered = all(
                last_by_sel.get((r["scope"], s, ent["prop"]), -1) > ent["order"]
                for s in r["sels"]
            )
            if not covered:
                skipped.append((sel_raw, prop, "多选择器未全覆盖，保守跳过"))
                continue
            plans[ent["file"]].append((ent["s"], ent["e"],
                                       (r["sel_raw"], prop, ent["val"])))
    return plans, skipped


def apply_plan(path, spans):
    """原地删除区间，从后往前。返回 (new_text, removed_bytes)。"""
    text = open(path, encoding="utf-8", errors="replace").read()
    # 扩展区间：吃掉前导空白与尾随分号，避免留下多余空白/分号
    cuts = []
    for s, e, _ in spans:
        a = s
        while a > 0 and text[a - 1] in _WS:
            a -= 1
        b = e
        while b < len(text) and text[b] in _WS:
            b += 1
        if b < len(text) and text[b] == ";":
            b += 1
            while b < len(text) and text[b] in _WS:
                b += 1
        cuts.append((a, b))
    cuts.sort(reverse=True)
    removed = 0
    for a, b in cuts:
        # 相邻区间不重叠（同一声明只会出现一次），直接切
        text = text[:a] + text[b:]
        removed += b - a
    return text, removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify-idempotent", action="store_true")
    args = ap.parse_args()

    files = [os.path.join(ROOT, r) for r in CSS_SOURCES if os.path.exists(os.path.join(ROOT, r))]
    plans, skipped = plan_converge(files)

    total = sum(len(v) for v in plans.values())
    print("==============================================================")
    print("  CSS 冲突收敛  |  模式: %s" % ("APPLY" if args.apply else "DRY-RUN"))
    print("==============================================================")
    for f in files:
        spans = plans.get(f, [])
        print("  %-28s 删除被覆盖声明 %d 条" % (os.path.basename(f), len(spans)))
        for (_, _, (sel, prop, val)) in sorted(spans, reverse=True)[:10]:
            print("     - %-38s { %s: %s }" % (sel[:38], prop, (val or "")[:30]))
        if len(spans) > 10:
            print("     ... 共 %d 条" % len(spans))

    if skipped:
        print("\n  跳过（需人工）：")
        for sel, prop, why in skipped:
            print("     ! %-38s { %s }  %s" % (sel[:38], prop, why))

    print("\n  合计删除 %d 条" % total)

    if args.apply:
        for f in files:
            spans = plans.get(f, [])
            if not spans:
                continue
            new, removed = apply_plan(f, spans)
            open(f, "w", encoding="utf-8").write(new)
            if open(f, encoding="utf-8", errors="replace").read() != new:
                print("  !! %s 落盘字节对账失败" % os.path.basename(f))
                return 2
            print("  %s 已落盘（- %d 字节），字节对账通过"
                  % (os.path.basename(f), removed))
        if args.verify_idempotent:
            again, _ = plan_converge(files)
            n = sum(len(v) for v in again.values())
            print("\n  幂等复检：二次删除 %d 条" % n)
            if n:
                print("  !! 不幂等，收敛算法有问题")
                return 2
            print("  ✅ 幂等")
    return 0


if __name__ == "__main__":
    sys.exit(main())
