#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为「自带 <style>、从未接深色」的独立页生成 html[data-theme="dark"] 覆写块。

为什么需要它
------------
站内存在两类页面：
  A 类 —— 加载 style.min.css + main.js，主题可切换，深色状态**用户可达**；
  B 类 —— 自带 <style>、不加载站点 CSS，永远浅色，深色状态**不可达**。
A 类里有一批页面（tools/ 测评、assets/ 专题）虽然加载了站点 CSS，
但正文样式是页内 <style> 硬编码的 Tailwind 系浅色板，从未写深色分支，
深色下整片白底 + 深字（实测 assets/iceberg-model.html 一处就 100 处缺陷）。

逐个手补是打地鼠，故做生成器：解析页内 <style> → 按映射表改写 → 产出深色块 →
**由 audit_dark_theme.py --urls 定向验证**（映射表写错会被 D1/D2/D3 抓出来）。

映射原则（保守，宁可少改）
--------------------------
1. 只映射「浅底 / 深字 / 浅描边」这一族——它们是深色下必然破损的；
2. **饱和品牌色（#1E40AF 这类）与 color:#fff 一律不动**：深蓝底白字在两主题下
   都可读（≈9.5:1），改了反而制造新缺陷；真出问题由审计点名再单独处理；
3. 能映射到站内有 token 的语义色就走 token（--text/--surface/--note-bg …），
   避免再造一批硬编码。

用法
----
    python3 scripts/dark_override_gen.py --page assets/iceberg-model.html   # dry-run
    python3 scripts/dark_override_gen.py --page X --page Y --apply
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converge_css import parse_css_spans  # noqa: E402  复用既有解析器，不复制

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = "/* dark-override-gen:"

# ---------------------------------------------------------------- 映射表
# 文字色（color）：浅色下的深字 / 中灰 / 浅灰 → 深色下的对应层级
TEXT = {
    # slate / gray 深字族
    "#0f172a": "var(--text)", "#0f1729": "var(--text)", "#111827": "var(--text)",
    "#1f2937": "var(--text)", "#1e2937": "var(--text)", "#374151": "var(--text)",
    "#334155": "var(--text)", "#1a1a1a": "var(--text)", "#212529": "var(--text)",
    "#222": "var(--text)", "#333": "var(--text)", "#222222": "var(--text)",
    # 中灰
    "#4b5563": "var(--text-secondary)", "#475569": "var(--text-secondary)",
    "#6b7280": "var(--text-secondary)", "#495057": "var(--text-secondary)",
    "#5b6478": "var(--text-secondary)", "#64748b": "var(--text-secondary)",
    "#5a626f": "var(--text-secondary)",
    # 浅灰（浅色下本就偏弱，深色下必须换层级）
    "#868e96": "var(--text-muted)", "#9ca3af": "var(--text-muted)",
    "#94a3b8": "var(--text-muted)", "#9aa3b5": "var(--text-muted)",
    "#a6adb8": "var(--text-muted)", "#6b7280b3": "var(--text-muted)",
    "#2b2f3a": "var(--text)", "#2d3140": "var(--text)", "#3a4152": "var(--text)",
    "#6b6585": "var(--text-secondary)", "#6b6478": "var(--text-secondary)",
    "#3a3550": "var(--text)", "#1e293b": "var(--text)",
    "#1a1a2e": "var(--text)", "#1a1a2c": "var(--text)",
    "#e67e22": "#FDBA74", "#27ae60": "#6EE7B7", "#c0392b": "#FCA5A5",
    "#1e40af": "#93C5FD", "#1e3a8a": "#93C5FD",
    "#2d6a4f": "var(--data-border)", "#157f5f": "var(--data-border)",
    "#1d4ed8": "#93C5FD", "#2563eb": "#93C5FD", "#3b82f6": "#93C5FD",
    "#e0566e": "#FDA4AF", "#dc2626": "#FCA5A5", "#ea580c": "#FDBA74",
    "#7c3aed": "#C4B5FD", "#6d28d9": "#C4B5FD", "#9cc06a": "#B4E33D",
    # 语义强调色：保留色相，切到深色下可读的浅调
    "#b91c1c": "var(--danger-border)", "#92400e": "var(--note-border)",
    "#065f46": "var(--data-border)", "#5b21b6": "var(--key-insight-border)", "#6d28d9": "#C4B5FD",
    "#f0a0b8": "#F9A8C8", "#fdd0dc": "#FBCFE8",
}
# 背景色（background / background-color）：浅底 → 深色表面
SURFACE = {
    "#ffffff": "var(--surface)", "#fff": "var(--surface)",
    "#f8fafc": "var(--bg-card)", "#f9fafb": "var(--bg-card)",
    "#fafafa": "var(--bg-card)", "#faf9f7": "var(--bg-card)",
    "#f7fafc": "var(--bg-card)", "#f8f7f4": "var(--bg-card)",
    "#f3f4f6": "var(--bg-subtle)", "#f1f5f9": "var(--bg-subtle)",
    "#f1efe9": "var(--bg-subtle)", "#eef2f7": "var(--bg-subtle)",
    "#f5f5f5": "var(--bg-subtle)", "#faf5ed": "var(--bg-card)",
    "#f7f5f0": "var(--bg-card)", "#fdfbf7": "var(--bg-card)",
    # callout 底色（浅色淡彩 → 深色暗调同色系）
    "#fee2e2": "var(--danger-bg)", "#fff5f5": "var(--danger-bg)",
    "#fef3c7": "var(--note-bg)", "#fffbe6": "var(--note-bg)",
    "#d1fae5": "var(--data-bg)", "#e6fcf5": "var(--data-bg)",
    "#ede9fe": "var(--key-insight-bg)", "#f8f7ff": "var(--key-insight-bg)",
    "#eff6ff": "var(--key-insight-bg)", "#fff4e6": "var(--analogy-bg)",
    "#f6f7f9": "var(--bg-subtle)", "#f2f2f2": "var(--bg-subtle)",
    "#eef3fa": "var(--bg)", "#fff0f4": "var(--bg-card)",
    "#eef1fb": "var(--bg-card)", "#f0f4ff": "var(--bg-card)",
    "#eef2ff": "var(--bg-card)", "#eff6ffb3": "var(--bg-card)",
    "#5cb88a": "#2F6B4F", "#f2b23a": "#8A5A12", "#e8b04b": "#8A5A12",
    "#e0a83c": "#8A5A12", "#dbeafe": "var(--bg-card)", "#ffedd5": "var(--bg-card)",
    "#dcfce7": "var(--bg-card)", "#fef9c3": "var(--bg-card)", "#fce7f3": "var(--bg-card)",
    "#fff3e0": "var(--bg-card)", "#e8f5e9": "var(--bg-card)", "#fdecea": "var(--bg-card)",
}

# 半透明浅底（玻璃卡）：rgba(255,255,255,.xx) → 深色半透明底。
# 为什么必须处理：D1 判定取「a>0.5 的第一个背景」，0.55 的白玻璃会被当成实心白底。
# 任意「浅色 + 半透明」背景都要处理，不能只认纯白：
# 实测 tools/mbti 的 nav.nav 是 rgba(238,241,251,.72)，alpha>0.5 会被判为有效背景，
# 于是整条导航在深色下仍是浅蓝底，只认 rgba(255,255,255,…) 会漏掉它。
RGBA_RE = re.compile(
    r"rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9.]+)\s*\)", re.I)
GLASS_DARK = "rgba(30,34,40,%s)"
LIGHT_CH = 220          # 三通道都 ≥ 此值才算「浅色半透明」


def _rgba_sub(val):
    """把浅色半透明背景替换为深色半透明（保留原 alpha）。返回 (新值, 命中数)。"""
    n = 0

    def rep(m):
        nonlocal n
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        if min(r, g, b) < LIGHT_CH:
            return m.group(0)
        n += 1
        return GLASS_DARK % m.group(4)

    return RGBA_RE.sub(rep, val), n
# 边框色：浅描边 → 深色下可见的低透明描边
BORDER = {
    "#e5e7eb": "rgba(236,234,228,0.14)", "#cbd5e1": "rgba(236,234,228,0.18)",
    "#e2e8f0": "rgba(236,234,228,0.14)", "#f1f5f9": "rgba(236,234,228,0.10)",
    "#eeeeee": "rgba(236,234,228,0.14)", "#ddd": "rgba(236,234,228,0.18)",
    "#d1d5db": "rgba(236,234,228,0.20)", "#eef0f3": "rgba(236,234,228,0.14)",
    "#1e3a8a": "rgba(147,197,253,0.45)", "#1e40af": "rgba(147,197,253,0.45)",
}

COLOR_PROPS = ("color", "background", "background-color", "border",
               "border-color", "border-top", "border-bottom",
               "border-left", "border-right", "outline", "outline-color")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
SHORTHAND_BORDER = ("border", "border-top", "border-bottom",
                    "border-left", "border-right")


def table_for(prop):
    p = prop.lower()
    if p == "color" and p not in SHORTHAND_BORDER:
        return TEXT
    if p.startswith("background"):
        return SURFACE
    if p.startswith("border") or p.startswith("outline"):
        return BORDER
    return None


def map_value(prop, val):
    """返回 (新值, 命中数)。shorthand border 只改其中的色值部分。"""
    tbl = table_for(prop)
    if not tbl:
        return val, 0
    n = 0

    def rep(m):
        nonlocal n
        key = m.group(0).lower()
        if key in tbl:
            n += 1
            return tbl[key]
        return m.group(0)

    if prop.lower().startswith("background") and RGBA_RE.search(val):
        return _rgba_sub(val)

    new = HEX.sub(rep, val)
    return new, n


# 站内 token 的深色字面量。为什么必须展开：页面局部 :root 里常有与站内同名的变量
# （如页面自己定义了 --bg），若写成 `--bg:var(--bg)` 就是自引用，
# 计算值阶段判为无效循环 → 整个声明失效（静默不生效，且审计会继续报缺陷）。
TOKEN_LITERAL = {
    "--bg": "#0B0C0E", "--surface": "#16191D", "--bg-card": "#1E2228",
    "--bg-subtle": "#16191D", "--bg-warm": "#1A1D21",
    "--text": "#ECEAE4", "--text-secondary": "#A6ADB8", "--text-muted": "#828C9A",
    "--danger-border": "#ff8787", "--note-border": "#ffc078",
    "--data-border": "#38d9a9", "--key-insight-border": "#9775fa",
    "--note-bg": "rgba(245,159,0,0.12)", "--data-bg": "rgba(12,166,120,0.12)",
    "--analogy-bg": "rgba(232,89,12,0.12)", "--danger-bg": "rgba(250,82,82,0.12)",
    "--key-insight-bg": "#1c1a2b",   # callout 深色底是半透明淡彩，非实心（B9 曾有重复定义）
}
VAR_REF = re.compile(r"var\(\s*(--[\w-]+)\s*\)")


def expand_literal(val, self_name):
    """把 var(--x) 展开为深色字面量；若引用自身则视为无效，返回 None。"""
    def rep(m):
        name = m.group(1)
        if name == self_name:
            return m.group(0)          # 自引用标记，下面整体跳过
        return TOKEN_LITERAL.get(name, m.group(0))
    out = VAR_REF.sub(rep, val)
    # 注意：self_name 自带 "--" 前缀，格式串里不能再写一次，
    # 否则 "var(--%s)" % "--bg" 会得到 "var(----bg)"，判定恒不成立（曾致自引用漏网）。
    return None if ("var(%s)" % self_name) in out else out


def token_rules(html):
    """覆写页面**自己的 :root 自定义属性**——这类页的最高杠杆修法。

    为什么它比逐条映射字面量更有效：这些独立页的调色板是先定义成
    `--ink-2:#5b6478`、`--glass:rgba(255,255,255,.55)`，再由 `var(--ink-2)` 派生出去。
    只映射字面量够不到 var()，于是 h4/p/li 一批元素一起漏（实测 bigfive 一页就漏几十处）。
    改 :root 变量，一条规则覆盖全部派生。

    归类：先按变量名语义（bg/surface/ink/text/line/border…），再按值回退到映射表。
    """
    decls = {}
    blobs = ([html] if html.lstrip().startswith(("--", ":", ".", "#", "@", "*", "h"))
              and "<style" not in html[:2000]
             else [m.group(1) for m in
                   re.finditer(r"<style[^>]*>(.*?)</style>", html, re.S)])
    for css in blobs:
        for r in parse_css_spans(css):
            joined = " ".join(r["sels"]).lower()
            if ":root" not in joined and joined not in ("html", "body"):
                continue
            for d in r["decls"]:
                name, val = d[0], d[1]
                if not name.startswith("--"):
                    continue
                decls.setdefault(name, val)
    if not decls:
        return []

    def classify(name, val):
        n = name.lower()
        if any(k in n for k in ("bg", "background", "surface", "glass", "card",
                                "panel", "fill", "tint")):
            return "surface"
        if any(k in n for k in ("ink", "text", "fg", "color", "title", "label")):
            return "text"
        if any(k in n for k in ("line", "border", "stroke", "divider", "edge")):
            return "border"
        return None

    out = []
    for name in sorted(decls):
        val = decls[name]
        kind = classify(name, val)
        # 值回退：变量名叫不出语义时，看值本身落在哪张表里
        if not kind:
            v = val.lower()
            if v in SURFACE or RGBA_RE.search(val):
                kind = "surface"
            elif v in TEXT:
                kind = "text"
            elif v in BORDER:
                kind = "border"
        tbl = {"surface": SURFACE, "text": TEXT, "border": BORDER}.get(kind)
        if not tbl:
            continue
        if RGBA_RE.search(val) and kind == "surface":
            new, ng = _rgba_sub(val)
            if not ng:
                continue
        else:
            new, n = map_value("background" if kind == "surface" else
                               ("color" if kind == "text" else "border"), val)
            if not n:
                continue
            new = expand_literal(new, name)
            if new is None:
                continue                 # 自引用，宁可不写也不写无效声明
        out.append("%s:%s" % (name, new))
    if not out:
        return []
    return ['html[data-theme="dark"]{%s}' % ";".join(out)]


def inline_style_rules(html):
    """扫描行内 style="..." 里的硬编码色，产出属性选择器覆写规则。

    为什么单独处理：<style> 规则改不到行内属性，而行内属性优先级最高，
    必须 !important + 属性选择器才能压住（与 style.css 的 P3 块同一手法）。
    """
    seen, out = set(), []
    for m in re.finditer(r'style\s*=\s*"([^"]*)"', html, re.I):
        body = m.group(1)
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, val = decl.split(":", 1)
            prop, val = prop.strip().lower(), val.strip()
            if prop not in COLOR_PROPS:
                continue
            new, n = map_value(prop, val)
            if not n:
                continue
            # 原串写法（保留大小写/空格）用于选择器匹配；可能带前导空格
            key = (prop, val.lower().replace(" ", ""))
            if key in seen:
                continue
            seen.add(key)
            bare = val.split(",")[0] if prop.startswith("background") else val
            # 只按「不含空格的规范化串」匹配，配 i 标志忽略大小写；
            # 同时给出带空格与不带空格两种写法，覆盖两种书写习惯
            lit = bare.strip()
            forms = {lit, re.sub(r"\s*", "", lit)}
            sels = ",".join(
                'html[data-theme="dark"] [style*="%s: %s" i],'
                'html[data-theme="dark"] [style*="%s:%s" i]' % (prop, f, prop, f)
                for f in sorted(forms))
            out.append("%s{%s:%s !important}" % (sels, prop, new))
    return out


def literal_fallback_rules(html):
    """兜底：页面里出现过的任何可映射色值，都补一条属性选择器覆写。

    针对「颜色写在 JS 数据结构里、运行时才拼出 style=」的情况——
    静态扫 <style> 与 style="..." 都够不到，但值本身在页面文本里能找到。
    只在深色下、且只作用于行内含该字面量的元素，副作用可控。
    """
    out, seen = [], set()
    for m in HEX.finditer(html):
        key = m.group(0).lower()
        if key in seen:
            continue
        seen.add(key)
        for prop, tbl in (("color", TEXT), ("background", SURFACE)):
            if key not in tbl:
                continue
            new = expand_literal(tbl[key], "--none") or tbl[key]
            out.append('html[data-theme="dark"] [style*="%s:%s" i]{%s:%s !important}'
                       % (prop, key, prop, new))
    return out


def gen_block(page_path):
    """为单个页面生成深色覆写块（字符串）；无可用映射则返回 ('', 0)。"""
    text = open(page_path, encoding="utf-8").read()
    is_css = page_path.lower().endswith(".css")
    rules_out = []
    # 独立子系统 CSS（如 tools/holland/assets/holland.css）也要能处理：
    # 它们的浅色板同样从未写深色分支，而生成器原本只扫 HTML 页内 <style>。
    blobs = [text] if is_css else [m.group(1) for m in
                                   re.finditer(r"<style[^>]*>(.*?)</style>", text, re.S)]
    for css in blobs:
        for r in parse_css_spans(css):
            sel = r["sel_raw"]
            if 'data-theme="dark"' in sel:
                continue                      # 已有深色分支，跳过
            decls = []
            for d in r["decls"]:
                prop, val = d[0], d[1]        # parse_decls_spans → (prop, val, s, e)
                if prop.lower() not in COLOR_PROPS:
                    continue
                new, n = map_value(prop, val)
                if n:
                    decls.append("%s:%s" % (prop, new))
            if decls:
                rules_out.append("html[data-theme=\"dark\"] %s{%s}"
                                 % (sel, ";".join(decls)))
    rules_out = token_rules(text) + rules_out
    if not is_css:
        rules_out += inline_style_rules(text) + literal_fallback_rules(text)
    if not rules_out:
        return "", 0
    body = "\n".join(rules_out)
    block = ("\n%s 自动生成（dark_override_gen.py）。"
             "只映射浅底/深字/浅描边一族；饱和品牌色与 color:#fff 不动，"
             "改完须用 audit_dark_theme.py --urls 定向验证。 */\n%s\n"
             % (MARKER, body))
    return block, len(rules_out)


def strip_block(text):
    """移除已生成的块（从 MARKER 到其后的 </style>），供 --regen 使用。"""
    i = text.find(MARKER)
    if i == -1:
        return text, False
    if "</style>" in text[i:]:
        j = text.find("</style>", i)
        return text[:i] + text[j:], True
    return text[:i].rstrip() + "\n", True   # CSS 文件：块在末尾，截到 MARKER 之前


def apply_page(page_path, dry=True, regen=False):
    text = open(page_path, encoding="utf-8").read()
    if MARKER in text:
        if not regen:
            return "SKIP  已存在深色块（加 --regen 可重生成）", 0
        text, ok = strip_block(text)
        if not ok:
            return "FAIL  无法剥离旧块", 0
        if not dry:
            open(page_path, "w", encoding="utf-8").write(text)
        text = open(page_path, encoding="utf-8").read()
    block, n = gen_block(page_path)
    if not n:
        return "SKIP  无可用映射", 0
    # 插到最后一个 </style> 之前（页内样式之后才轮到它）；CSS 文件则追加到末尾
    if page_path.lower().endswith(".css"):
        idx = len(text)
    else:
        idx = text.rfind("</style>")
        if idx == -1:
            return "FAIL  无 </style>", 0
    new = text[:idx] + block + text[idx:]
    if not dry:
        open(page_path, "w", encoding="utf-8").write(new)
    return ("DRY   %d 条规则（%d→%d 字节）" % (n, len(text), len(new))
            if dry else "APPLY %d 条规则（%d→%d 字节）" % (n, len(text), len(new))), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", action="append", default=[], required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--regen", action="store_true",
                    help="已存在生成块时先剥离再重新生成（映射表扩充后必须用它）")
    a = ap.parse_args()
    total = 0
    for p in a.page:
        rel = p if os.path.exists(p) else os.path.join(ROOT, p)
        if not os.path.exists(rel):
            print("FAIL  不存在: %s" % p)
            continue
        msg, n = apply_page(rel, dry=not a.apply, regen=a.regen)
        print("%-46s %s" % (os.path.relpath(rel, ROOT), msg))
        total += n
    print("-" * 78)
    print("规则合计 %d 条（%s）" % (total, "已写入" if a.apply else "dry-run，未写入"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
