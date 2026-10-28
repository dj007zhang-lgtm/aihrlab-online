#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSS 去冲突重构（视觉零变化）

原理：对「选择器串完全相同 + 属性相同」的多处定义，保留源码顺序上的最后一条，
删除前面的。特异性相同、后者胜出，被删的本来就不生效 → 视觉零变化。

三条必须守住的正确性约束（违反任何一条都会变成破坏样式）：
  C1 作用域：@media 内外是不同作用域，禁止跨作用域去重。
     （桌面 html{17px} 会被响应式 14px「更晚出现」误判为被覆盖。）
  C2 多选择器：.a,.b{color:red} 只有当 .a 与 .b 都被更晚的同属性规则覆盖时才能删；
     只覆盖其中一个就删整条，会连带破坏另一个。否则保守不删。
  C3 幂等：重跑一次应得 0 条删除。

用法：
  python3 scripts/dedupe_css.py assets/css/style.css            # dry-run
  python3 scripts/dedupe_css.py assets/css/style.css --apply    # 落盘（含字节对账）
  python3 scripts/dedupe_css.py X --apply --verify-idempotent   # 落盘后再跑一遍必须为 0
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- 结构解析

def parse_blocks(s):
    """递归解析，返回块列表。块 = rule | at | text"""
    items = []
    i, n = 0, len(s)
    while i < n:
        j = s.find("{", i)
        if j == -1:
            if s[i:].strip():
                items.append({"type": "text", "text": s[i:]})
            break
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
            items.append({"type": "at", "head": head, "children": parse_blocks(inner)})
        elif hs.startswith("@"):
            items.append({"type": "at", "head": head, "children": None, "raw": inner})
        else:
            items.append({"type": "rule", "sel": head, "body": inner})
        i = k
    return items


def render(blocks):
    out = []
    for b in blocks:
        if b["type"] == "text":
            out.append(b["text"])
        elif b["type"] == "at":
            if b["children"] is None:
                out.append(b["head"] + "{" + b["raw"] + "}")
            else:
                out.append(b["head"] + "{" + render(b["children"]) + "}")
        else:
            out.append(b["sel"] + "{" + b["body"] + "}")
    return "".join(out)


def parse_decls(body):
    decls = []
    for d in body.split(";"):
        d = d.strip()
        if not d or ":" not in d:
            continue
        p, v = d.split(":", 1)
        decls.append((p.strip().lower(), v.strip(), "%s:%s" % (p.strip(), v.strip())))
    return decls


def norm_sel(raw):
    return [x.strip() for x in re.sub(r"\s+", " ", raw.strip()).split(",") if x.strip()]


# ---------------------------------------------------------------- 去重

def dedupe_scope(blocks, removed):
    """同一作用域内去重，返回新 blocks"""
    # C1：只取本层规则。@media / @supports 内部由递归调用单独成作用域，
    #     绝不能把内部的响应式覆盖算成顶层的「更晚定义」。
    flat = [b for b in blocks if b["type"] == "rule"]

    # 收集每个 (选择器, 属性) 最后出现的规则对象
    last = {}
    for b in flat:
        sels = norm_sel(b["sel"])
        if not sels:
            continue
        for prop, val, raw in parse_decls(b["body"]):
            for s in sels:
                last[(s, prop)] = b

    # 本规则内若同 (选择器,属性) 重复，自身也是保留最后
    for b in flat:
        sels = norm_sel(b["sel"])
        if not sels:
            continue
        decls = parse_decls(b["body"])
        local = {}
        for prop, val, raw in decls:
            for s in sels:
                local[(s, prop)] = (val, raw)
        keep = {}
        for (s, prop), (val, raw) in local.items():
            keep[(s, prop)] = (val, raw)
        b["_keepmap"] = keep

    out = []
    for b in blocks:
        if b["type"] != "rule":
            if b["type"] == "at" and b["children"] is not None:
                b["children"] = dedupe_scope(b["children"], removed)
            out.append(b)
            continue
        sels = norm_sel(b["sel"])
        if not sels:
            out.append(b)
            continue
        decls = parse_decls(b["body"])
        if not decls:
            out.append(b)
            continue
        # 本规则内自身重复 → 保留最后
        local_last = {}
        for di, (prop, val, raw) in enumerate(decls):
            for s in sels:
                local_last[(s, prop)] = (di, val, raw)
        self_keep_idx = set(di for (di, val, raw) in local_last.values())

        newdecls = []
        for di, (prop, val, raw) in enumerate(decls):
            if di not in self_keep_idx:
                continue
            # C2：全部子选择器都被更晚的规则覆盖，才能删
            all_covered = True
            any_covered = False
            for s in sels:
                later = last.get((s, prop))
                if later is not None and later is not b:
                    any_covered = True
                else:
                    all_covered = False
            if all_covered and any_covered:
                removed.append((re.sub(r"\s+", " ", b["sel"].strip())[:60], prop, val[:40]))
                continue
            newdecls.append(raw)
        b["body"] = ";".join(newdecls)
        out.append(b)
    return out


def dedupe_file(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    blocks = parse_blocks(raw)
    removed = []
    new_blocks = dedupe_scope(blocks, removed)
    new_text = render(new_blocks)
    # 结构对账：解析后的重渲染必须能再解析出相同结构
    return new_text, removed


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify-idempotent", action="store_true",
                    help="落盘后重跑，必须得到 0 条删除（否则回滚思路：说明算法不收敛）")
    args = ap.parse_args()

    total = 0
    for rel in args.targets:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print("缺失：%s" % rel)
            continue
        before = open(p, encoding="utf-8", errors="replace").read()
        new_text, removed = dedupe_file(p)
        print("== %s" % rel)
        print("   原 %d 字节 → 新 %d 字节（-%d）" % (len(before), len(new_text), len(before) - len(new_text)))
        print("   删除被覆盖声明：%d 条" % len(removed))
        for sel, prop, val in removed[:8]:
            print("     - %s { %s: %s }" % (sel, prop, val))
        if len(removed) > 8:
            print("     ... 共 %d 条" % len(removed))
        total += len(removed)

        if args.apply:
            open(p, "w", encoding="utf-8").write(new_text)
            check = open(p, encoding="utf-8", errors="replace").read()
            if check != new_text:
                print("   !! 落盘字节对账失败")
                return 2
            print("   已落盘，字节对账通过")
            if args.verify_idempotent:
                _, again = dedupe_file(p)
                print("   幂等复检：二次删除 %d 条" % len(again))
                if again:
                    print("   !! 不幂等，算法有问题")
                    return 2
    print("合计删除 %d 条" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
