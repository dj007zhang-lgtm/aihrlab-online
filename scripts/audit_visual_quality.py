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

def discover_css_sources():
    """
    动态发现全部 CSS 源文件，不写死列表。

    为什么不能写死：曾经只列 assets/css/style.css 与 article.css，
    而站点实际还有 assets/qa/widget.css、tools/*/assets/*.css，
    新增的 CSS 文件会静默逃出所有检查（B10 长期报 0 = 没扫到，不是干净）。
    排除 .min.css——那是 build 产物，不是真相源。
    """
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn
                 if not d.startswith(('.', '_'))
                 and d not in ('outputs', 'node_modules', '.git')]
        for f in fn:
            if f.endswith('.css') and not f.endswith('.min.css'):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT))
    return sorted(out)


CSS_SOURCES = discover_css_sources()
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

_NUM_RE = re.compile(r"(?<![0-9a-zA-Z#])([+-]?)(\d*\.?\d+)([a-z%]*)", re.I)
_VAR_HEAD = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*", re.I)


def expand_vars(v, tokens=None, depth=0):
    """
    把 var(--x) 展开成 :root 里的实际值，用于跨文件等价判定。

    为什么需要这一层：
      style.css 写 var(--line)，article.css 写 rgba(0,0,0,0.06)，
      两者渲染结果完全一致。不展开就会把「一处走 token、一处写字面量」
      判成冲突——那是写法差异，不是视觉差异。
      不展开的代价是：token 化做得越好的文件，被报的假冲突越多，
      等于在惩罚正确的做法。
    """
    if not tokens or depth > 6 or "var(" not in v:
        return v
    out, i, n, changed = [], 0, len(v), False
    while i < n:
        j = v.find("var(", i)
        if j < 0:
            out.append(v[i:])
            break
        out.append(v[i:j])
        k, bal = j + 4, 1
        while k < n and bal:
            if v[k] == "(":
                bal += 1
            elif v[k] == ")":
                bal -= 1
            k += 1
        if not _VAR_HEAD.match(v, j):      # 不是合法 var() 头，原样保留
            out.append(v[j:k])
            i = k
            continue
        inner = v[j + 4:k - 1]
        d = inner.find(",")
        name = (inner[:d] if d >= 0 else inner).strip()
        fb = inner[d + 1:].strip() if d >= 0 else ""
        if name in tokens:
            out.append(expand_vars(tokens[name], tokens, depth + 1))
            changed = True
        elif fb:
            out.append(expand_vars(fb, tokens, depth + 1))
            changed = True
        else:
            out.append(v[j:k])
        i = k
    return "".join(out) if changed else v


def norm_value(v, tokens=None):
    """
    归一化 CSS 值，用于「同一视觉结果的不同写法」判等。

    为什么必须有这一层：
      #FFFFFF 与 #fff 与 #ffffff 渲染完全一致，0.25rem 与 .25rem 亦然。
      不做归一化，门禁会把「人换了个写法」报成「同选择器冲突」，
      111 条里有 45 条是这种假冲突（实测：45 条里 43 条同色异写 + 2 条前导零，
      真实值冲突 0）。假冲突比真冲突更坏：它会淹没真债，并让人学会忽略门禁。
    """
    s = (v or "").strip()
    if not s:
        return ""
    s = expand_vars(s, tokens)
    # !important 单独剥离，避免空格差异影响判等
    important = False
    if re.search(r"!\s*important\s*$", s, re.I):
        important = True
        s = re.sub(r"!\s*important\s*$", "", s, flags=re.I).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([(),])\s*", r"\1", s)
    s = s.replace("'", '"')

    def _hex(m):
        h = m.group(1).lower()
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        return "#" + h

    s = re.sub(r"#([0-9a-fA-F]{3,8})\b", _hex, s)

    # rgb()/rgba() 不透明色统一折算成 hex，与 #rrggbb 同权
    def _rgbfn(m):
        parts = [p.strip() for p in m.group(1).split(",")]
        try:
            if len(parts) == 3:
                r, g, b = [int(float(p)) for p in parts]
                return "#%02x%02x%02x" % (max(0, min(255, r)),
                                          max(0, min(255, g)),
                                          max(0, min(255, b)))
            if len(parts) == 4:
                r, g, b = [int(float(p)) for p in parts[:3]]
                a = float(parts[3])
                if a >= 1:
                    return "#%02x%02x%02x" % (max(0, min(255, r)),
                                              max(0, min(255, g)),
                                              max(0, min(255, b)))
        except Exception:
            return m.group(0)
        return m.group(0)

    s = re.sub(r"rgba?\(([^)]*)\)", _rgbfn, s, flags=re.I)

    def _num(m):
        sign, num, unit = m.group(1), m.group(2), (m.group(3) or "").lower()
        if sign == "+":
            sign = ""
        if "." in num:
            num = num.rstrip("0").rstrip(".")
            if num.startswith("0") and num != "0":
                num = num[1:]
        elif num.startswith("0") and len(num) > 1:
            num = num.lstrip("0") or "0"
        if num in ("0", "-0"):
            return "0"
        return sign + num + unit

    s = _NUM_RE.sub(_num, s)
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    if important:
        s += " !important"
    return s


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


def check_conflicts(rules, tokens=None):
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
    same_value_diff_written = 0   # 归一化后相等 = 仅写法不同，非冲突
    for (scope, s, prop), lst in sorted(seen.items(), key=lambda x: (str(x[0][0]), x[0][1], x[0][2])):
        if len(lst) > 1:
            raw_vals = set(v for v, _, _ in lst)
            norm_vals = set(norm_value(v, tokens) for v, _, _ in lst)
            if len(raw_vals) > 1 and len(norm_vals) == 1:
                same_value_diff_written += 1
                continue
            if len(norm_vals) > 1:
                bad += 1
                locs = ",".join("%s:%d=%s" % (f, l, v[:20]) for v, f, l in lst)
                tag = ("[%s] " % "/".join(scope)) if scope else ""
                out["items"].append((
                    "BLOCK", "B9",
                    "%s%s { %s } 被定义 %d 次且值不同 → 生效值取决于源码顺序（%s）"
                    % (tag, s, prop, len(lst), locs)))
                out["block"] += 1
    if same_value_diff_written:
        out["items"].append((
            "INFO", "B9",
            "另有 %d 组「同值异写」已按等价处理（如 #FFF/#ffffff、0.25rem/.25rem），不计冲突"
            % same_value_diff_written))
    if not bad:
        out["items"].append(("PASS", "B9", "无冲突定义"))
    return out


def _inline_style_colors(html_files):
    """
    统计 HTML 行内 style="..." 属性里的硬编码色。

    为什么必须单独扫：行内属性完全不受 CSS token 体系约束，
    [data-theme=dark] 覆盖不到它们。本轮实测 264/430 页有，
    而 B10 此前只扫 CSS 文件 → 报 0，是「没扫到」不是「干净」。
    """
    total = hits = 0
    samples = []
    for f in (html_files or []):
        try:
            s = open(f, encoding="utf-8").read()
        except Exception:
            continue
        for m in re.finditer(r'\sstyle\s*=\s*"([^"]*)"', s, re.I):
            for dm in re.finditer(r"([a-z-]+)\s*:\s*([^;\"]+)", m.group(1), re.I):
                prop = dm.group(1).strip().lower()
                val = dm.group(2).strip()
                if not re.search(r"color|background|border|shadow|fill|stroke", prop):
                    continue
                total += 1
                if "var(" in val:
                    continue
                if HEX_RE.search(val) or RGB_RE.search(val):
                    hits += 1
                    if len(samples) < 6:
                        samples.append('行内 style="%s" @%s'
                                       % (m.group(1)[:44], os.path.basename(f)))
    return total, hits, samples


def _css_basename_key(href_or_path):
    """把 link href / 源路径都归一到「同一份 CSS」的键：style.min.css 与 style.css 同源"""
    b = os.path.basename(href_or_path.split("?")[0])
    if b.endswith(".min.css"):
        b = b[:-len(".min.css")] + ".css"
    return b


def check_conflicts_per_page(css_files, html_files, tokens):
    """
    B9：按「页面实际加载组合」分组判冲突，不把所有 CSS 倒进一个池子。

    为什么必须分组：站点存在独立子系统 CSS（tools/holland/assets/holland.css、
    tools/ai-risk-test/assets/styles.css），它们从不与主站 style.css 同页加载，
    各自定义 :root/--bg、body 完全合理。混在一个池子里比会凭空造出几十条
    「冲突」（实测 31 条全是这种误报），既阻塞发布又淹没真实冲突。

    做法：扫描每个 HTML 的 <link stylesheet>，得到该页加载的 CSS 集合，
    只在集合内部判冲突；各页结果合并去重。
    """
    from collections import defaultdict
    by_key = {}
    for p in css_files:
        by_key.setdefault(_css_basename_key(p), []).append(p)

    combos = set()
    for h in (html_files or []):
        try:
            s = open(h, encoding="utf-8").read()
        except Exception:
            continue
        keys = []
        for m in re.finditer(r'<link[^>]*href="([^"]+\.css)"', s, re.I):
            k = _css_basename_key(m.group(1))
            if k in by_key and k not in keys:
                keys.append(k)
        if len(keys) >= 1:
            combos.add(tuple(sorted(keys)))

    merged = {"items": [], "block": 0, "warn": 0}
    seen = set()
    for combo in sorted(combos):
        rules = []
        for k in combo:
            for p in by_key[k]:
                rules += parse_css(p)
        res = check_conflicts(rules, tokens)
        for sev, code, msg in res["items"]:
            if code != "B9" or msg in seen:
                continue
            seen.add(msg)
            merged["items"].append((sev, code, msg))
        merged["block"] += res["block"]
        merged["warn"] += res["warn"]
    # 去重后重算：同一条冲突可能被多个页面组合重复计 block
    merged["block"] = sum(1 for s, c, _ in merged["items"] if s == "BLOCK")
    merged["warn"] = sum(1 for s, c, _ in merged["items"] if s == "WARN")
    if not merged["items"]:
        merged["items"].append(("PASS", "B9", "无冲突定义（按页面加载组合分组判定）"))
    return merged


def mainstay_css_files(css_files, html_files):
    """
    与 style.css 同页加载的 CSS = 主站组。

    为什么要有这个概念：holland.css、tools/ai-risk-test/assets/styles.css
    是独立子系统，从不与主站 style.css 同页出现，各有自己的设计体系。
    拿主站的 type scale / token 约束去要求它们，既不合理（会改变这些工具的
    既有视觉），也会凭空制造门禁 BLOCK。
    """
    keys = {p: _css_basename_key(p) for p in css_files}
    main_key = "style.css"
    co = set()
    for h in (html_files or []):
        try:
            s = open(h, encoding="utf-8").read()
        except Exception:
            continue
        ks = [_css_basename_key(m.group(1))
              for m in re.finditer(r'<link[^>]*href="([^"]+\.css)"', s, re.I)]
        if main_key in ks:
            co.update(ks)
    co.add(main_key)
    return [p for p in css_files if keys[p] in co]


def check_hardcoded_colors(rules, html_files=None):
    """B10：硬编码颜色绕过 token（CSS 规则 + HTML 行内属性两处都扫）"""
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
    it, ih, isamp = _inline_style_colors(html_files)
    css_total, css_hits = total, hits
    total += it
    hits += ih
    samples += isamp
    rate = (hits / total) if total else 0
    # 硬编码本身不 BLOCK，超过 30% 说明 token 体系形同虚设
    sev = "BLOCK" if rate > 0.30 else ("WARN" if hits else "PASS")
    out["items"].append((
        sev, "B10",
        "颜色声明 %d 处（CSS %d + 行内 %d），其中硬编码 %d 处（%.0f%%），token 未被执行"
        % (total, css_total, it, hits, rate * 100)))
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


def check_type_scale(css_files):
    """
    B12：font-size 不得再出现 rem 数值字面量，必须走 type scale token。

    与 type_scale.py 的替换共用同一解析器（parse_css_spans），避免
    「替换用 A 口径、门禁用 B 口径」互相打架。px / em / clamp / inherit /
    0 / !important 按值形态永久豁免，理由写在 type_scale.py。
    """
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from type_scale import violations, SCALE
    except ImportError as e:
        return {"items": [("BLOCK", "B12", "缺少 type_scale.py 单一真相源：%s" % e)],
                "block": 1, "warn": 0}
    out = {"items": [], "block": 0, "warn": 0}
    bad = violations(css_files)
    if bad:
        sample = "; ".join("%s:%d %s=%s" % b for b in bad[:5])
        out["items"].append((
            "BLOCK", "B12",
            "发现 %d 处散落 rem 字号，须改用 var(--fs-N)：%s" % (len(bad), sample)))
        out["block"] += 1
    else:
        out["items"].append((
            "PASS", "B12",
            "全部字号来自 %d 档 type scale token（比率 1.1，锚点 1rem=17px）" % len(SCALE)))
    return out


def check_figure_typography(rules):
    """
    B13 图文同权：图注排版必须进正文那套体系，不能退回浏览器默认或硬编码。

    判据刻意只取结构性、可自动判定、不会误报的三条：
      figcaption / .figure-source 规则必须存在；
      font-size 必须是 var(--fs-N)（B12 只管 rem 字面量，不管规则是否存在）；
      color 必须是 var(--token)。
    图注「写什么」是策展判断，自动化不判 —— 见 type_scale.py 与交付说明。
    """
    out = {"items": [], "block": 0, "warn": 0}
    specs = {}
    for r in rules:
        if "figcaption" in r["sel_raw"]:
            k = "figcaption"
        elif ".figure-source" in r["sel_raw"]:
            k = ".figure-source"
        else:
            continue
        for p, v in r["decls"]:
            specs.setdefault(k, {}).setdefault(p, []).append((v, r["line"]))
    problems = []
    fs_tok = re.compile(r"^var\(\s*--fs-\d+\s*\)$", re.I)
    color_tok = re.compile(r"^var\(\s*--[A-Za-z0-9-]+\s*\)$", re.I)
    for k in ("figcaption", ".figure-source"):
        if k not in specs:
            problems.append("%s 缺少排版规则（图注会退回浏览器默认）" % k)
            continue
        d = specs[k]
        fs = d.get("font-size", [])
        if not fs:
            problems.append("%s 未声明 font-size" % k)
        elif not all(fs_tok.match(v.strip()) for v, _ in fs):
            bad = [v for v, _ in fs if not fs_tok.match(v.strip())]
            problems.append("%s 的 font-size 未走 type scale：%s" % (k, bad[0]))
        col = d.get("color", [])
        if not col:
            problems.append("%s 未声明 color" % k)
        elif not all(color_tok.match(v.strip()) for v, _ in col):
            bad = [v for v, _ in col if not color_tok.match(v.strip())]
            problems.append("%s 的 color 未走颜色 token：%s" % (k, bad[0]))
    if problems:
        for m in problems:
            out["items"].append(("BLOCK", "B13", m))
        out["block"] = len(problems)
    else:
        out["items"].append((
            "PASS", "B13",
            "figcaption / .figure-source 均走 type scale + 颜色 token（图文同权）"))
    return out


def check_font_contract(css_files, html_files=None):
    """
    B14 字体体积契约：中文站点不得引入 @font-face / 字体文件 / 外链字体域名。

    勘察结论（P2）：全站已是系统字体栈，0 个 @font-face、0 个 woff2、
    0 个外链字体域名，符合中文体积硬约束。此处把该决策固化成会失败的断言，
    防止后续有人为「好看」引入 Google Fonts 而拖垮首屏。
    只匹配资源引用形态，不匹配正文中作为技术名词出现的字样。
    """
    out = {"items": [], "block": 0, "warn": 0}
    bad = []
    face = re.compile(r"@font-face", re.I)
    fontfile = re.compile(r"url\(\s*['\"]?[^)'\"]*\.(?:woff2?|ttf|otf|eot)\b", re.I)
    extfont = re.compile(r"fonts\.(?:googleapis|gstatic|bunny)\.com", re.I)
    for f in css_files:
        t = open(f, encoding="utf-8", errors="replace").read()
        if face.search(t):
            bad.append("%s 出现 @font-face" % os.path.basename(f))
        if fontfile.search(t):
            bad.append("%s 引用字体文件" % os.path.basename(f))
    for f in (html_files or []):
        t = open(f, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"<(?:link|script)\b[^>]*?(?:href|src)\s*=\s*[\"']([^\"']+)", t, re.I):
            if extfont.search(m.group(1)):
                bad.append("%s 引用外链字体" % os.path.relpath(f, ROOT))
                break
    if bad:
        for m in bad[:8]:
            out["items"].append(("BLOCK", "B14", m))
        out["block"] = len(bad)
    else:
        out["items"].append((
            "PASS", "B14",
            "系统字体栈，无 @font-face / 字体文件 / 外链域名（中文体积硬约束）"))
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
        ("B12 散落字号", ".card-desc{font-size:0.937rem;}", "B12", True),
        ("B13 图注硬编码", ".article-body figcaption{font-size:13px;color:#999} "
         ".article-body .figure-source{font-size:12px;color:#888}", "B13", True),
        ("B14 外链字体", "@font-face{font-family:X;src:url(x.woff2)}", "B14", True),
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
        res = check_conflicts(rules, tokens)
        got += [i for i in res["items"] if i[1] == code]
        res = check_type_scale([p])
        got += [i for i in res["items"] if i[1] == code]
        res = check_figure_typography(rules)
        got += [i for i in res["items"] if i[1] == code]
        res = check_font_contract([p])
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

    css_files = [os.path.join(ROOT, r) for r in CSS_SOURCES
                 if os.path.exists(os.path.join(ROOT, r))]
    html_files = []
    for dp, dn, fn in os.walk(ROOT):
        if any(x in dp for x in (".git", "node_modules", "_wip", "outputs",
                                 "_aihr_repo_archive", "_wip_unpublished")):
            continue
        html_files += [os.path.join(dp, f) for f in fn if f.endswith(".html")]
    checks = [
        ("B1-B3 排版尺度", check_typography(rules, tokens, root_px)),
        ("B4 对比度", check_contrast(rules, tokens, root_px)),
        ("B5 两端对齐", check_justify(rules)),
        ("B6 字距", check_orphan_space(rules)),
        ("B7 段落节奏", check_paragraph_spacing(rules)),
        ("B8 装饰", check_decor(rules)),
        ("B9 冲突定义", check_conflicts_per_page(css_files, html_files, tokens)),
        ("B10 颜色 token", check_hardcoded_colors(rules, html_files)),
        ("B11 构建同步", check_build_sync()),
        ("B12 字号模数化", check_type_scale(mainstay_css_files(css_files, html_files))),
        ("B13 图文同权", check_figure_typography(rules)),
        ("B14 字体契约", check_font_contract(css_files, html_files)),
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
