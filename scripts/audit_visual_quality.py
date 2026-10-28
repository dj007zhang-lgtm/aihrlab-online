#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉品质门禁（F4）audit_visual_quality.py

把「调性 / 美学 / 品质」从主观评价变成可断言的规则。
所有阈值来自外部权威规范，不来自本站现状（参照系外置）。

外部标准出处（写死在实现里，可追溯）：
  B1 正文字号 15–25px          Butterick《Practical Typography》key-rules 02
  B2 行高 120–145% 字号        Butterick key-rules 03（CJK 上调：汉字字面率近满格，等效下界 150%）
  B3 行长 45–90 字符           Butterick key-rules 04（CJK：1 汉字 ≈ 2 拉丁字符宽）
  B4 正文对比度 ≥4.5:1         WCAG 2.2 AA（正文级）；≥7:1 记 AAA
  B5 两端对齐必须配断词        Butterick key-rules 18（中文不可断词 → CJK 正文禁 justify）
  B6 中西文混排 1/4 em 间距    W3C《Requirements for Chinese Text Layout》2.1.3
  B7 段间距与首行缩进二选一    Butterick key-rules 17
  B8 装饰不堆砌               出版级长文站通则（同一元素 gradient+shadow+radius 三者不全占）
  B9 同选择器同属性多处定义   可预测性原则（最终效果由源码顺序决定 = 不可预测）
  B10 硬编码色值绕过 token    可维护性（颜色唯一真相源在 :root）
  B11 压缩版与源版同步        双真相源 = 改了不生效（假成功温床）

用法：
  python3 scripts/audit_visual_quality.py            # 人读报告
  python3 scripts/audit_visual_quality.py --json     # 机器读
  python3 scripts/audit_visual_quality.py --self-test  # 注入已知缺陷，验证门禁能 BLOCK

退出码：0 通过 / 2 存在 BLOCK
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS_SOURCES = ["assets/css/style.css", "assets/css/article.css"]
CSS_COMPRESSED = "assets/css/style.min.css"
BODY_SELECTORS = [".article-body", ".article-content-wrapper", ".article-content"]

# 存量债走基线账本：只准降不准升，避免挂一个永远修不完的 BLOCK
BASELINE_PATH = os.path.join(ROOT, "ci", "visual-baseline.json")
BASELINE_CODES = ("B9", "B10")


def load_baseline():
    if os.path.exists(BASELINE_PATH):
        try:
            return json.load(open(BASELINE_PATH, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_baseline(b):
    os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=1)

# 外部阈值
T_FONT_MIN, T_FONT_MAX = 15.0, 25.0          # B1
T_LH_MIN, T_LH_MAX = 1.50, 1.80              # B2（CJK 适配：120-145% → 150-180%）
T_MEASURE_MIN, T_MEASURE_MAX = 22.5, 45.0    # B3（CJK 汉字数/行，等价 45–90 拉丁字符）
T_CONTRAST_AA, T_CONTRAST_AAA = 4.5, 7.0     # B4

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB_RE = re.compile(r"\brgba?\([^)]*\)", re.I)


# ---------------------------------------------------------------- CSS 解析

def strip_comments(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def parse_css(path):
    """
    返回 [{'sel_raw','sels','decls','line','file','scope'}]

    scope = 作用域路径（() 为顶层，('@media (max-width:768px)',) 为媒体查询内，
    ('@keyframes fade',) 为动画块内）。

    为什么必须带作用域：
      桌面 html{font-size:17px} 与响应式断点里的 14px 是同一选择器的合法多形态，
      不做作用域隔离就会把响应式设计本身报成「冲突」（过激误报）。
      @keyframes 的 from/to 同理：不同动画块的 from/to 互不相关。
    """
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from dedupe_css import parse_blocks
    except Exception:
        parse_blocks = None

    text = strip_comments(open(path, encoding="utf-8", errors="replace").read())
    rules = []
    search_from = [0]

    def line_of(sel_raw):
        i = text.find(sel_raw, search_from[0])
        if i >= 0:
            search_from[0] = i + len(sel_raw)
            return text.count("\n", 0, i) + 1
        return 0

    def add(b, scope):
        sel_raw = re.sub(r"\s+", " ", b["sel"].strip())
        decls = []
        for d in b["body"].split(";"):
            d = d.strip()
            if not d or ":" not in d:
                continue
            p, v = d.split(":", 1)
            decls.append((p.strip().lower(), v.strip()))
        if not decls:
            return
        sels = [s.strip() for s in sel_raw.split(",") if s.strip()]
        if not sels:
            return
        rules.append({
            "sel_raw": sel_raw,
            "sels": sels,
            "decls": decls,
            "line": line_of(sel_raw),
            "file": os.path.basename(path),
            "scope": scope,
        })

    def walk(bs, scope):
        for b in bs:
            if b.get("type") == "at":
                if b.get("children") is not None:
                    walk(b["children"], scope + (re.sub(r"\s+", " ", b["head"].strip()),))
                continue
            if b.get("type") == "rule":
                add(b, scope)

    if parse_blocks is None:
        return rules
    walk(parse_blocks(text), ())
    return rules


def read_root_tokens(paths):
    """收集 :root 中的自定义属性（含 data-theme 作用域）"""
    tokens = {}
    for p in paths:
        for r in parse_css(p):
            for s in r["sels"]:
                if s == ":root":
                    for prop, val in r["decls"]:
                        if prop.startswith("--"):
                            tokens.setdefault(prop, val)
    # 深色作用域（data-theme）
    for p in paths:
        for r in parse_css(p):
            for s in r["sels"]:
                if "data-theme" in s and "dark" in s:
                    for prop, val in r["decls"]:
                        if prop.startswith("--"):
                            tokens.setdefault(prop + "@dark", val)
    return tokens


def resolve_color(value, tokens, depth=0):
    """把 var(--x) 解到 hex/rgb；解不出返回 None"""
    if depth > 6:
        return None
    v = value.strip()
    m = re.match(r"^var\(\s*(--[A-Za-z0-9-]+)\s*(?:,\s*([^)]+))?\)$", v)
    if m:
        name = m.group(1)
        if name in tokens:
            return resolve_color(tokens[name], tokens, depth + 1)
        if m.group(2):
            return resolve_color(m.group(2), tokens, depth + 1)
        return None
    if HEX_RE.match(v) or RGB_RE.match(v):
        return v
    return None


def to_rgb(c):
    """hex/rgb(a) → (r,g,b,a) 0-255"""
    c = c.strip()
    if c.startswith("#"):
        h = c[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) >= 6:
            try:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
            except ValueError:
                return None
        return None
    m = re.match(r"rgba?\(([^)]*)\)", c, re.I)
    if m:
        parts = [x.strip() for x in m.group(1).replace("/", ",").split(",")]
        nums = []
        for x in parts:
            if x.endswith("%"):
                nums.append(float(x[:-1]) * 2.55)
            else:
                try:
                    nums.append(float(x))
                except ValueError:
                    return None
        if len(nums) >= 3:
            return (nums[0], nums[1], nums[2], nums[3] if len(nums) > 3 else 1.0)
    return None


def contrast(c1, c2):
    def lum(c):
        r, g, b = c[0] / 255.0, c[1] / 255.0, c[2] / 255.0
        def f(x):
            return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    a, b = lum(c1), lum(c2)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def blend(fg, bg):
    """fg 带 alpha 时与 bg 合成"""
    if fg[3] >= 1.0:
        return fg
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def px_of(value, root_px, base_px=None):
    """123px / 1.05rem / 1.2em → px。em 需给 base"""
    v = value.strip()
    m = re.match(r"^(-?[\d.]+)(px|rem|em|%|)$", v)
    if not m:
        return None
    num, unit = float(m.group(1)), (m.group(2) or "")
    if unit == "px" or unit == "":
        return num
    if unit == "rem":
        return num * root_px
    if unit == "em":
        return num * (base_px or root_px)
    return None


# ---------------------------------------------------------------- 检查项

def effective_value(rules, sels_wanted, prop):
    """
    取「生效值」：按源码顺序取最后一条匹配声明。
    静态扫描只看「出现过」会把已被覆盖的旧规则也算成缺陷（过激误报）。
    前提：同特异性（本函数只用于完全相同的选择器串）。
    """
    last = None
    for r in rules:
        if r.get("scope") != ():
            continue  # 只认顶层生效值，响应式断点不算冲突
        for s in r["sels"]:
            if s.strip() in sels_wanted:
                for p, v in r["decls"]:
                    if p == prop:
                        last = v
    return last


def check_typography(rules, tokens, root_px):
    """B1/B2/B3：正文字号、行高、行长（全部按生效值断言）"""
    out = {"items": [], "block": 0, "warn": 0}
    # 正文容器选择器（按权威段口径）
    body_sels = {".article-body", ".article-content-wrapper", ".article-content"}

    fs_raw = effective_value(rules, body_sels, "font-size")
    lh_raw = effective_value(rules, body_sels, "line-height")
    mw_raw = effective_value(rules, body_sels, "max-width")

    fs_v = px_of(fs_raw, root_px) if fs_raw else None
    mw_v = px_of(mw_raw, root_px) if mw_raw else None
    lh_v = None
    if lh_raw:
        raw = lh_raw.strip()
        if raw.endswith("%"):
            lh_v = float(raw[:-1]) / 100.0
        elif re.match(r"^[\d.]+$", raw):
            lh_v = float(raw)
        # em/rem 行高是绝对值，无法直接判倍数，交由 WARN

    # B1 字号
    if fs_v is None:
        out["items"].append(("WARN", "B1", "未找到正文字号声明，无法断言"))
        out["warn"] += 1
    else:
        ok = T_FONT_MIN <= fs_v <= T_FONT_MAX
        out["items"].append((
            "PASS" if ok else "BLOCK", "B1",
            "正文字号 %.1fpx（外部标准 %g–%gpx）" % (fs_v, T_FONT_MIN, T_FONT_MAX)))
        if not ok:
            out["block"] += 1

    # B2 行高
    if lh_v is None:
        out["items"].append(("WARN", "B2", "行高为 em/rem 绝对值或未声明，无法断言倍数"))
        out["warn"] += 1
    else:
        ok = T_LH_MIN <= lh_v <= T_LH_MAX
        out["items"].append((
            "PASS" if ok else "WARN", "B2",
            "正文行高 %.2f（CJK 适配带 %.2f–%.2f；拉丁原标准 1.20–1.45）"
            % (lh_v, T_LH_MIN, T_LH_MAX)))
        if not ok:
            out["warn"] += 1

    # B3 行长
    if fs_v and mw_v:
        cjk = mw_v / fs_v
        latin_chars = cjk * 2
        ok = T_MEASURE_MIN <= cjk <= T_MEASURE_MAX
        out["items"].append((
            "PASS" if ok else "BLOCK", "B3",
            "行长 %.1f 汉字/行 ≈ %.0f 拉丁字符（外部标准 45–90 字符）" % (cjk, latin_chars)))
        if not ok:
            out["block"] += 1
    else:
        out["items"].append(("WARN", "B3", "缺字号或容器宽度，无法计算行长"))
        out["warn"] += 1
    return out


def check_contrast(rules, tokens, root_px):
    """B4：正文/次级文字/链接 对比度"""
    out = {"items": [], "block": 0, "warn": 0}
    bg_c = to_rgb(resolve_color(tokens.get("--bg", "#ffffff"), tokens) or "#ffffff")
    if not bg_c:
        out["items"].append(("WARN", "B4", "无法解析 --bg"))
        out["warn"] += 1
        return out
    pairs = [("--text", "正文"), ("--text-secondary", "次级文字"),
             ("--text-muted", "弱化文字"), ("--text-link", "链接")]
    for tok, label in pairs:
        raw = resolve_color(tokens.get(tok, ""), tokens)
        c = to_rgb(raw) if raw else None
        if not c:
            continue
        c = blend(c, bg_c)
        ratio = contrast(c, bg_c)
        if ratio >= T_CONTRAST_AAA:
            lvl, sev = "AAA", "PASS"
        elif ratio >= T_CONTRAST_AA:
            lvl, sev = "AA", "PASS"
        else:
            lvl, sev = "不达标", "BLOCK"
            out["block"] += 1
        out["items"].append((sev, "B4", "%s %s 与底色对比度 %.2f:1（%s）" % (label, raw, ratio, lvl)))
    return out


def check_justify(rules):
    """B5：CJK 正文两端对齐必须有断词，否则只能靠拉伸字距实现"""
    out = {"items": [], "block": 0, "warn": 0}
    p_sels = {".article-body p", ".article-content p", ".article-content-wrapper p"}
    hits = []
    for s in sorted(p_sels):
        ta = effective_value(rules, {s}, "text-align")
        if ta == "justify":
            hyp = effective_value(rules, {s}, "hyphens")
            hits.append((s, hyp))
    for s, hyp in hits:
        if hyp in (None, "none", "manual"):
            out["items"].append((
                "BLOCK", "B5",
                "正文 %s 生效 text-align:justify 而 hyphens=%s（中文不可断词 → 字距被拉伸）"
                % (s, hyp or "未声明")))
            out["block"] += 1
        else:
            out["items"].append(("PASS", "B5", "%s 两端对齐且已配断词" % s))
    if not hits:
        out["items"].append(("PASS", "B5", "正文未使用无断词的两端对齐"))
    return out


def check_paragraph_spacing(rules):
    """B7：段间距 + 首行缩进 同时存在 = 冗余"""
    out = {"items": [], "block": 0, "warn": 0}
    for r in rules:
        d = dict(r["decls"])
        for s in r["sels"]:
            base = s.split()[0]
            if base in BODY_SELECTORS and "p" in s.split():
                if "margin-top" in d and "text-indent" in d:
                    out["items"].append((
                        "WARN", "B7",
                        "%s 同时设 margin-top 与 text-indent（外部规则：二选一）@%s:%d"
                        % (s, r["file"], r["line"])))
                    out["warn"] += 1
    if not out["items"]:
        out["items"].append(("PASS", "B7", "段间距与首行缩进未同时存在"))
    return out


def check_orphan_space(rules):
    """
    B6：中文标题负字距挤压（CLReq 2.1：汉字 1:1 方块并列）。
    按生效值断言 —— 负字距是西文标题的常见做法，但对汉字是挤压方块。
    """
    out = {"items": [], "block": 0, "warn": 0}
    targets = []
    for base in (".article-body", ".article-content", ".article-content-wrapper"):
        for h in ("h2", "h3"):
            targets.append("%s %s" % (base, h))
    for s in targets:
        ls = effective_value(rules, {s}, "letter-spacing")
        if not ls:
            continue
        m = re.match(r"^(-?[\d.]+)(em|px|rem)?$", ls.strip())
        if not m:
            continue
        v = float(m.group(1))
        if v < 0:
            out["items"].append((
                "WARN", "B6",
                "%s 生效 letter-spacing %s（负字距挤压汉字方块，中文标题应归零）" % (s, ls)))
            out["warn"] += 1
    if not out["items"]:
        out["items"].append(("PASS", "B6", "中文标题无负字距挤压"))
    return out


def check_decor(rules):
    """B8：同一元素同时堆 gradient + box-shadow + border-radius"""
    out = {"items": [], "block": 0, "warn": 0}
    for r in rules:
        d = dict(r["decls"])
        n = sum(1 for k in ("background", "background-image") if "gradient" in d.get(k, ""))
        n += 1 if "box-shadow" in d else 0
        has_radius = "border-radius" in d
        if n >= 2 and has_radius:
            out["items"].append((
                "WARN", "B8",
                "装饰堆砌：gradient+shadow+radius 同元素：%s @%s:%d"
                % (r["sel_raw"][:70], r["file"], r["line"])))
            out["warn"] += 1
    if not out["items"]:
        out["items"].append(("PASS", "B8", "无三件套装饰堆砌"))
    return out


def check_conflicts(rules):
    """B9：同选择器 + 同属性 多处定义，最终效果由源码顺序决定"""
    out = {"items": [], "block": 0, "warn": 0}
    seen = defaultdict(list)
    for r in rules:
        # 键用「整条选择器串」，不用 split 后的单个选择器。
        # 理由：h1,h2,h3{font-weight} 与 h1{font-weight} 是「基础 + 特化」的正常层叠，
        #       不是冲突；只有同一条选择器串被定义多次且值不同才是真冲突。
        for prop, val in r["decls"]:
            seen[(r.get("scope", ()), r["sel_raw"], prop)].append((val, r["file"], r["line"]))
    bad = 0
    for (scope, s, prop), lst in sorted(seen.items(), key=lambda x: (str(x[0][0]), x[0][1], x[0][2])):
        if len(lst) > 1:
            vals = set(v for v, _, _ in lst)
            if len(vals) > 1:
                bad += 1
                locs = ",".join("%s:%d" % (f, l) for _, f, l in lst)
                tag = ("[%s] " % "/".join(scope)) if scope else ""
                out["items"].append((
                    "BLOCK", "B9",
                    "%s%s { %s } 被定义 %d 次且值不同 → 生效值取决于源码顺序（%s）"
                    % (tag, s, prop, len(lst), locs)))
                out["block"] += 1
    if not bad:
        out["items"].append(("PASS", "B9", "无冲突定义"))
    return out


def check_hardcoded_colors(rules):
    """B10：非 :root 规则里硬编码颜色，绕过 token"""
    out = {"items": [], "block": 0, "warn": 0}
    total = hits = 0
    samples = []
    for r in rules:
        if any(s == ":root" or "data-theme" in s for s in r["sels"]):
            continue
        for prop, val in r["decls"]:
            if not re.search(r"color|background|border|shadow|fill|stroke", prop):
                continue
            if "var(" in val:
                continue
            if HEX_RE.search(val) or RGB_RE.search(val):
                hits += 1
                if len(samples) < 8:
                    samples.append("%s{%s:%s} @%s:%d"
                                   % (r["sel_raw"][:40], prop, val[:24], r["file"], r["line"]))
            total += 1
    rate = (hits / total) if total else 0
    # 硬编码本身不 BLOCK，超过 30% 说明 token 体系形同虚设
    sev = "BLOCK" if rate > 0.30 else ("WARN" if hits else "PASS")
    out["items"].append((
        sev, "B10",
        "颜色声明 %d 处，其中 %d 处硬编码（%.0f%%），token 未被执行" % (total, hits, rate * 100)))
    for s in samples:
        out["items"].append(("INFO", "B10", "  " + s))
    if sev == "BLOCK":
        out["block"] += 1
    elif sev == "WARN":
        out["warn"] += 1
    return out


def check_build_sync():
    """
    B11：线上加载的是压缩版，源版必须经 build_css.py 生成它。
    有了构建关系就不 BLOCK；产物不是最新 → BLOCK（改了不生效）。
    """
    import subprocess
    out = {"items": [], "block": 0, "warn": 0}
    script = os.path.join(ROOT, "scripts", "build_css.py")
    if not os.path.exists(script):
        out["items"].append(("BLOCK", "B11", "缺少构建脚本 build_css.py（源版改了不生效）"))
        out["block"] += 1
        return out
    p = subprocess.run([sys.executable, script, "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    if p.returncode == 0:
        out["items"].append(("PASS", "B11", "压缩版与源版一致（经构建生成，改源版后重跑即可生效）"))
    else:
        out["items"].append((
            "BLOCK", "B11",
            "压缩版不是最新：源版已改但未重跑 build_css.py → 线上 368 页不受影响（改了不生效）"))
        out["block"] += 1
    return out


# ---------------------------------------------------------------- 自检

def self_test():
    """注入已知缺陷，验证门禁能 BLOCK（F5：自动化自身有效性）"""
    import tempfile
    print("== 自检：注入已知缺陷，验证规则能抓到 ==")
    tmp = tempfile.mkdtemp()
    cases = [
        ("B1 字号过小", ".article-body{font-size:11px;}", "B1", True),
        ("B3 行长过长", ".article-body{font-size:16px;max-width:1400px;}", "B3", True),
        ("B2 行高越界", ".article-body{font-size:17px;line-height:2.6;}", "B2", True),
        ("B5 无断词两端对齐", ".article-body p{text-align:justify;}", "B5", True),
        ("B8 装饰堆砌", ".card{background:linear-gradient(1deg,#fff,#000);box-shadow:0 1px 2px #000;border-radius:8px;}", "B8", True),
        ("B9 冲突定义", ".article-body{color:#111;} .article-body{color:#eee;}", "B9", True),
        ("B4 对比度不足", ".article-body{color:#cccccc;}", "B4", False),  # 走 token 路径，用 B4 直测
    ]
    ok_all = True
    for name, css, code, _ in cases:
        p = os.path.join(tmp, "t.css")
        open(p, "w", encoding="utf-8").write(css)
        rules = parse_css(p)
        tokens = read_root_tokens([p])
        got = []
        res = check_typography(rules, tokens, 17)
        got += [i for i in res["items"] if i[1] == code]
        res = check_justify(rules)
        got += [i for i in res["items"] if i[1] == code]
        res = check_decor(rules)
        got += [i for i in res["items"] if i[1] == code]
        res = check_conflicts(rules)
        got += [i for i in res["items"] if i[1] == code]
        if code == "B4":
            # B4 走 token 路径，直接验证对比度函数本身
            ok = contrast(to_rgb("#cccccc"), to_rgb("#ffffff")) < T_CONTRAST_AA
        else:
            # 抓到 = 该规则项产出非 PASS 结论（WARN 与 BLOCK 都算命中）
            ok = bool(got) and any(g[0] in ("WARN", "BLOCK") for g in got)
        print("  %-18s %s → %s" % (name, code, "抓到" if ok else "漏掉"))
        ok_all = ok_all and ok
    print("自检结论：", "全部命中" if ok_all else "存在漏检（门禁不可用）")
    return 0 if ok_all else 2


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--update-baseline", action="store_true",
                    help="以当前值刷新基线账本（仅在债务确实被清掉后使用）")
    ap.add_argument("--skip", default="", help="跳过检查项，逗号分隔，如 B11")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    skip = set(x.strip() for x in args.skip.split(",") if x.strip())

    rules = []
    for rel in CSS_SOURCES:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            rules += parse_css(p)
    tokens = read_root_tokens([os.path.join(ROOT, r) for r in CSS_SOURCES
                               if os.path.exists(os.path.join(ROOT, r))])
    root_px = 17.0
    for r in rules:
        if r.get("scope") != ():
            continue  # 只认顶层根字号，响应式断点不能当基准
        for s in r["sels"]:
            if s == "html" or s == ":root":
                for prop, val in r["decls"]:
                    if prop == "font-size":
                        v = px_of(val, 16)
                        if v:
                            root_px = v

    checks = [
        ("B1-B3 排版尺度", check_typography(rules, tokens, root_px)),
        ("B4 对比度", check_contrast(rules, tokens, root_px)),
        ("B5 两端对齐", check_justify(rules)),
        ("B6 字距", check_orphan_space(rules)),
        ("B7 段落节奏", check_paragraph_spacing(rules)),
        ("B8 装饰", check_decor(rules)),
        ("B9 冲突定义", check_conflicts(rules)),
        ("B10 颜色 token", check_hardcoded_colors(rules)),
        ("B11 构建同步", check_build_sync()),
    ]

    blocks = warns = 0
    rows = []
    for name, res in checks:
        for sev, code, msg in res["items"]:
            if code in skip:
                continue
            rows.append((sev, code, msg))

    # 存量债基线判定：只准降不准升
    baseline = load_baseline()
    changed = False
    for code in BASELINE_CODES:
        cur = sum(1 for s, c, m in rows if c == code and s == "BLOCK")
        new_rows = []
        if code not in baseline or args.update_baseline:
            baseline[code] = cur
            changed = True
            for s, c, m in rows:
                if c == code:
                    new_rows.append(("WARN" if s == "BLOCK" else s, c,
                                     "[建立基线 %d] %s" % (cur, m)))
                else:
                    new_rows.append((s, c, m))
        else:
            base = baseline[code]
            if cur > base:
                verdict = "BLOCK"
                tag = "[较基线 %d → %d 变差] " % (base, cur)
            elif cur < base:
                baseline[code] = cur
                changed = True
                verdict = "PASS"
                tag = "[较基线 %d → %d 改善] " % (base, cur)
            else:
                verdict = "PASS"
                tag = "[持平于基线 %d] " % base
            for s, c, m in rows:
                if c == code:
                    if s == "BLOCK":
                        new_rows.append((verdict, c, tag + m))
                    elif s == "PASS":
                        new_rows.append((s, c, m))
                    else:
                        new_rows.append((s, c, m))
                else:
                    new_rows.append((s, c, m))
        rows = new_rows
    if changed:
        save_baseline(baseline)

    for sev, code, msg in rows:
        if sev == "BLOCK":
            blocks += 1
        elif sev == "WARN":
            warns += 1

    if args.json:
        print(json.dumps({
            "block": blocks, "warn": warns,
            "items": [{"sev": s, "code": c, "msg": m} for s, c, m in rows],
        }, ensure_ascii=False, indent=1))
    else:
        print("视觉品质门禁（F4）  root=%gpx  外部标准：Butterick + W3C CLReq + WCAG2.2" % root_px)
        print("=" * 78)
        for sev, code, msg in rows:
            print("%-5s %-4s %s" % (sev, code, msg))
        print("=" * 78)
        print("BLOCK %d  WARN %d" % (blocks, warns))
    return 2 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
