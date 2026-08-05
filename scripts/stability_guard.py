#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stability_guard.py —— 网站发布前稳定性 / 专业性 / 真实性 自检与拦截模块

定位：
  质量门（quality_gate.py）负责「内容质量 / SEO / GEO / 信源」维度；
  本模块负责「页面是否能正常呈现、是否有低级硬伤」维度 —— 即用户
  因空白页 / 加载失败 / 内容错乱 / 链接失效 / 品牌色回退 / 导航错乱
  而秒关页面、跳走的高跳出率根因。

职责：
  1. 在发布前（publish.py 第二道强制关卡）扫描即将上线的页面，
     拦截任何会破坏「专业形象与用户信任」的低级错误。
  2. 任何 BLOCKER 级问题 → 进程返回非 0，publish.py 中止推送、零远程写入。
  3. 支持实时守护（--serve 文件监听）与一键自动修复（--autofix，仅安全项）。

检测项（单一真相源见 DETECTION_ITEMS）：
  S1 空白页        S2 乱码/编码损坏     S3 结构损坏（标签未闭合）
  S4 组件泄漏      S5 资源加载失败      S6 内部链接失效
  S7 品牌色回退    S8 导航顺序错乱      S9 不安全外链

用法：
  python3 scripts/stability_guard.py --all            # 全站扫描
  python3 scripts/stability_guard.py --files a.html b.css
  python3 scripts/stability_guard.py --serve          # 实时守护（监听变更）
  python3 scripts/stability_guard.py --autofix --all  # 仅对安全项自动修复
  python3 scripts/stability_guard.py --emit-doc       # 生成检测项清单文档
  python3 scripts/stability_guard.py --json --all     # 机器可读输出（CI）
"""

import os
import re
import sys
import json
import time
import html
import argparse
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 常量
# ============================================================
SEVERITY_BLOCKER = "BLOCKER"
SEVERITY_WARN = "WARN"

# 标准导航顺序（相对顺序不可颠倒）
CANON_NAV = ["首页", "文章", "资源库", "测评", "策展", "关于"]
# 列表页用「全部文章」作为文章槽的展示文案，归一化为「文章」再比较
NAV_NORMALIZE = {"全部文章": "文章"}

# 旧引擎蓝品牌色（品牌升级后不得复现）——仅锁定 unambiguous 的蓝/浅蓝 token，
# 避免把中性灰误判。检测与自动修复共用此表。
BRAND_OLD_TO_NEW = {
    "#228be6": "#3F6212", "#1c7ed6": "#3F6212", "#1971c2": "#365314",
    "#3b5bdb": "#365314", "#2f49c2": "#223A0C", "#e7f5ff": "#ECF3E0",
    "#d0ebff": "#DCE9C4", "#a5d8ff": "#9CC06A", "#eef1fe": "#ECF3E0",
    "#f0f4fa": "#f0f4ea",
}
# rgba 形式（旧蓝 -> 新绿）
BRAND_RGBA_OLD = [
    (re.compile(r"rgba\(\s*34\s*,\s*139\s*,\s*230\s*,([^)]*)\)"), r"rgba(63,98,18,\1)"),
    (re.compile(r"rgba\(\s*18\s*,\s*123\s*,\s*194\s*,([^)]*)\)"), r"rgba(54,83,20,\1)"),
]
BRAND_OLD_TOKENS_RE = re.compile(
    r"#(?:228be6|1c7ed6|1971c2|3b5bdb|2f49c2|e7f5ff|d0ebff|a5d8ff|eef1fe|f0f4fa)",
    re.IGNORECASE,
)

# 乱码特征：UTF-8 被当成 latin1 解码后的典型残影 + 替换符
MOJIBAKE_RE = re.compile(
    r"Ã©|Ã¨|Ã |Ã¢|Ã¶|Ã¼|Ã±|Ã§|Ã\x9f|â‚¬|â€|â„¢|â€œ|â€\x9d|â€™|Â°|Â°|Ã\u00a0|Ã\u0161"
)
REPLACEMENT_CHAR = "\ufffd"

# HTML void 元素（无需闭合）
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
# 结构损坏时的「硬阻断」容器：这些若未闭合必然导致内容错乱
CRITICAL_CONTAINERS = {
    "html", "head", "body", "article", "main", "section", "table",
    "ul", "ol", "nav", "header", "footer", "aside", "figure", "form", "blockquote",
}

SKIP_DIRS = {".git", "node_modules", "design-system", ".workbuddy", "templates"}


# ============================================================
# 数据类
# ============================================================
class Finding:
    def __init__(self, check_id, severity, path, message, handling):
        self.check_id = check_id
        self.severity = severity
        self.path = path
        self.message = message
        self.handling = handling

    def as_dict(self):
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
            "handling": self.handling,
        }


class CheckResult:
    def __init__(self, check_id, name, severity, findings):
        self.check_id = check_id
        self.name = name
        self.severity = severity  # 该检查自身的默认严重级（用于报告分组）
        self.findings = findings

    @property
    def passed(self):
        return not any(f.severity == SEVERITY_BLOCKER for f in self.findings)

    def report(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        lines = [f"  [{status}] {self.check_id} {self.name}"]
        for f in self.findings:
            tag = "🔴 BLOCKER" if f.severity == SEVERITY_BLOCKER else "🟡 WARN"
            lines.append(f"    • [{tag}] {f.path}: {f.message}")
        return "\n".join(lines)


# ============================================================
# 检测项注册表（单一真相源：报告 + 文档均由此生成）
# ============================================================
DETECTION_ITEMS = [
    {
        "id": "S1-BLANK", "name": "空白页检测", "category": "呈现完整性",
        "severity": SEVERITY_BLOCKER,
        "trigger": "页面 <body> 可见文本（去除 script/style/标签后）非空白字符数 < 200；"
                   "或主内容容器（article/main）为空。重定向桩页（含 http-equiv=refresh）豁免。",
        "handling": "拦截发布。定位为空根因：模板未渲染 / 内容注入失败 / 批量脚本误删正文。"
                   "修复后重跑，直到可见文本达标。",
        "autofix": False,
    },
    {
        "id": "S2-GARBLED", "name": "乱码 / 编码损坏检测", "category": "呈现完整性",
        "severity": SEVERITY_BLOCKER,
        "trigger": "页面出现 Unicode 替换符（U+FFFD）或 UTF-8 被 latin1 误解码的典型残影"
                   "（如 Ã© / â€ / Â° 等）。",
        "handling": "拦截发布。根因为文件以错误编码写入（如 UTF-8 文本被按 latin1 保存/读取）。"
                   "统一以 UTF-8 重写文件，重跑确认零替换符。",
        "autofix": False,
    },
    {
        "id": "S3-STRUCTURE", "name": "结构损坏检测（标签未闭合）", "category": "内容错乱",
        "severity": SEVERITY_BLOCKER,
        "trigger": "HTML 解析后，关键容器（html/head/body/article/main/section/table/ul/ol/"
                   "nav/header/footer/aside/figure/form/blockquote）在文末仍未闭合 → BLOCKER；"
                   "div 开闭不平衡差 > 3 → WARN（注：桩页豁免）。",
        "handling": "拦截发布。根因为批量 HTML 注入误删了闭合标签。用手术式注入铁律修复，"
                   "重跑直到关键容器全部闭合。",
        "autofix": False,
    },
    {
        "id": "S4-LEAK", "name": "组件泄漏检测（GEO 胶囊错置）", "category": "内容错乱",
        "severity": SEVERITY_BLOCKER,
        "trigger": "GEO 答案胶囊（geo-answer-capsule）出现在文章列表页 articles/index.html → BLOCKER；"
                   "出现在其它 index.html 列表页 → WARN；胶囊正文文本 < 10 字（注入失败）→ BLOCKER。"
                   "（hub / 测评内容页允许含胶囊，非泄漏。）",
        "handling": "拦截发布。列表页不得承载文章级内容组件。删除列表页误注入的胶囊块，"
                   "或补全空胶囊正文。重跑确认 articles/index.html 无胶囊。",
        "autofix": False,
    },
    {
        "id": "S5-ASSET", "name": "资源加载失败检测", "category": "加载失败",
        "severity": SEVERITY_BLOCKER,
        "trigger": "本地 CSS（link[rel=stylesheet]）、JS（script[src]）、图片（img/source[src]、"
                   "og:image、style 中 url()）引用了不存在的文件；或 src 为空。",
        "handling": "拦截发布。缺失 CSS/JS 导致整页白屏或无样式；缺失图片破坏专业形象。"
                   "补齐资源或修正路径后重跑。",
        "autofix": False,
    },
    {
        "id": "S6-LINK", "name": "内部链接失效检测", "category": "链接失效",
        "severity": SEVERITY_BLOCKER,
        "trigger": "本地超链接（a[href] 指向站内 .html / 目录）解析后文件不存在 → BLOCKER；"
                   "指向页内锚点 #id 但目标页无该 id → WARN。",
        "handling": "拦截发布。死链直接拉高跳出率。修正链接目标或补全锚点 id 后重跑。",
        "autofix": False,
    },
    {
        "id": "S7-BRAND", "name": "品牌色回退检测", "category": "专业性",
        "severity": SEVERITY_BLOCKER,
        "trigger": "页面内联样式或 CSS 源文件中复现旧引擎蓝 token"
                   "（#228be6/#1c7ed6/#1971c2/#3b5bdb/#2f49c2/#e7f5ff/#d0ebff/#a5d8ff/#eef1fe/#f0f4fa"
                   "及对应 rgba）→ BLOCKER。",
        "handling": "拦截发布。品牌升级后任何旧蓝复现都破坏视觉一致性。"
                   "可用 --autofix 按既定映射一键替换为森林绿系。",
        "autofix": True,
    },
    {
        "id": "S8-NAV", "name": "导航顺序错乱检测", "category": "专业性",
        "severity": SEVERITY_BLOCKER,
        "trigger": "主导航 <nav class=\"site-nav\"> 中规范项（首页/文章/资源库/测评/策展/关于，"
                   "其中「全部文章」归一为「文章」）的相对顺序被颠倒 → BLOCKER；"
                   "缺失规范项 → WARN。verify / 设计系统页豁免。",
        "handling": "拦截发布。导航顺序错乱让用户找不到入口、秒关。可用 --autofix 按规范顺序重排。"
                   "重跑确认全站主导航顺序一致。",
        "autofix": True,
    },
    {
        "id": "S9-INSECURE", "name": "不安全外链检测", "category": "真实性 / 安全",
        "severity": SEVERITY_WARN,
        "trigger": "外链使用 http://（非 https）或 javascript: 伪协议 → WARN（不阻断发布，但须复核）。",
        "handling": "不阻断发布，但告警。https 缺失会产生混合内容警告并损害信任；"
                   "javascript: 链接多为残留脚本。逐一复核改为 https 或移除。",
        "autofix": False,
    },
]


# ============================================================
# 基础工具
# ============================================================
def _is_verify_page(path):
    basename = os.path.basename(path).lower()
    return any(x in basename for x in ["baidu_", "google", "bingsiteauth", "verify"])


def _is_stub(html):
    return 'http-equiv="refresh"' in html


def _should_skip(path):
    rel = os.path.relpath(path, SITE_ROOT)
    if "design-system" in rel.split(os.sep):
        return True
    if _is_verify_page(path):
        return True
    return False


def _get_all_html_and_css():
    results = []
    for root, dirs, files in os.walk(SITE_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".html") or f.endswith(".css"):
                fp = os.path.join(root, f)
                if _should_skip(fp):
                    continue
                results.append(fp)
    return results


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _rel(path):
    return os.path.relpath(path, SITE_ROOT)


# ---- 标签 / 属性解析 ----
TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*?)(/?)>", re.S)
ATTR_RE = re.compile(
    r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^\s>]*))"
)


def iter_tags(html):
    for m in TAG_RE.finditer(html):
        tag = m.group(1).lower()
        attrs_raw = m.group(2)
        self_close = m.group(3) == "/"
        attrs = {}
        for am in ATTR_RE.finditer(attrs_raw):
            key = am.group(1).lower()
            # 组3=双引号内容, 组4=单引号内容, 组5=无引号内容
            if am.group(3) is not None:
                val = am.group(3)
            elif am.group(4) is not None:
                val = am.group(4)
            else:
                val = am.group(5)
            attrs[key] = val
        yield tag, attrs, self_close


# ---- 本地引用解析 ----
def resolve_local(ref, base_file):
    """返回本地引用的绝对路径；非本地引用 / 模板占位符返回 None。"""
    if ref is None:
        return None
    ref = ref.strip()
    if not ref:
        return None
    # 模板 / JS 占位符（含 ' ` < > 等字符），非静态本地路径，跳过
    if any(c in ref for c in ("'", "`", "<", ">")) or ref.startswith("+"):
        return None
    if ref.startswith(("http://", "https://", "//", "data:", "mailto:",
                        "tel:", "javascript:", "#")):
        return None
    frag = ref.split("#", 1)[0]
    frag = frag.split("?", 1)[0]          # 去掉查询串
    frag = urllib.parse.unquote(frag)     # 解码 URL 编码（CJK/百分号）
    if frag == "":
        return None
    if frag.startswith("/"):
        p = os.path.normpath(os.path.join(SITE_ROOT, frag.lstrip("/")))
    else:
        base_dir = os.path.dirname(base_file)
        p = os.path.normpath(os.path.join(base_dir, frag))
    return p


def local_exists(p):
    if p and os.path.exists(p):
        return True
    if p and os.path.isdir(p) and os.path.exists(os.path.join(p, "index.html")):
        return True
    return False


def visible_text(html):
    html = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", "", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", html)
    return text


def has_anchor_id(target_html, anchor):
    return (f'id="{anchor}"' in target_html) or (f"id='{anchor}'" in target_html) or \
           (f'name="{anchor}"' in target_html)


# ============================================================
# 各检测项实现
# ============================================================
def check_blank(files):
    findings = []
    for p in files:
        if not p.endswith(".html"):
            continue
        html = _read(p)
        if _is_stub(html):
            continue
        text = visible_text(html)
        n = len(re.sub(r"\s", "", text))
        if n < 200:
            findings.append(Finding(
                "S1-BLANK", SEVERITY_BLOCKER, _rel(p),
                f"可见正文仅 {n} 字（<200），疑似空白/未渲染页",
                "定位模板渲染或内容注入失败，补全正文后重跑",
            ))
    return findings


def check_garbled(files):
    findings = []
    for p in files:
        if not p.endswith(".html"):
            continue
        raw = _read(p)
        if REPLACEMENT_CHAR in raw:
            cnt = raw.count(REPLACEMENT_CHAR)
            findings.append(Finding(
                "S2-GARBLED", SEVERITY_BLOCKER, _rel(p),
                f"检测到 {cnt} 个 Unicode 替换符（U+FFFD），编码损坏",
                "以 UTF-8 重写文件，消除替换符后重跑",
            ))
        mo = MOJIBAKE_RE.findall(raw)
        if mo:
            findings.append(Finding(
                "S2-GARBLED", SEVERITY_BLOCKER, _rel(p),
                f"检测到 {len(mo)} 处 UTF-8/latin1 误解码残影（如 {mo[0]}）",
                "确认文件以 UTF-8 保存，去除误解码字符后重跑",
            ))
    return findings


class _StructParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.svg_depth = 0
        self.unclosed_critical = []
        self.div_imbalance = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("svg", "math"):
            self.svg_depth += 1
        if self.svg_depth > 0:
            return
        if tag in VOID_ELEMENTS:
            return
        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        # 自闭合 <x/> 不入栈
        return

    def handle_endtag(self, tag):
        if tag in ("svg", "math") and self.svg_depth > 0:
            self.svg_depth -= 1
        if self.svg_depth > 0:
            return
        if tag in VOID_ELEMENTS:
            return
        if not self.stack:
            return
        if self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        # 游离结束标签忽略

    def finish(self):
        for t in self.stack:
            if t == "div":
                self.div_imbalance += 1
            elif t in CRITICAL_CONTAINERS:
                self.unclosed_critical.append(t)


def check_structure(files):
    findings = []
    for p in files:
        if not p.endswith(".html"):
            continue
        html = _read(p)
        if _is_stub(html):
            continue
        parser = _StructParser()
        try:
            parser.feed(html)
            parser.finish()
        except Exception as e:
            findings.append(Finding(
                "S3-STRUCTURE", SEVERITY_BLOCKER, _rel(p),
                f"HTML 解析异常：{e}",
                "检查文件是否含非法结构，修复后重跑",
            ))
            continue
        if parser.unclosed_critical:
            findings.append(Finding(
                "S3-STRUCTURE", SEVERITY_BLOCKER, _rel(p),
                f"关键容器未闭合：{', '.join(parser.unclosed_critical)}",
                "用手术式注入铁律补全闭合标签后重跑",
            ))
        if parser.div_imbalance > 3:
            findings.append(Finding(
                "S3-STRUCTURE", SEVERITY_WARN, _rel(p),
                f"div 开闭不平衡（差 {parser.div_imbalance} 个）",
                "复核是否有误删的 </div>，但不阻断发布",
            ))
    return findings


def check_component_leak(files):
    findings = []
    for p in files:
        if not p.endswith(".html"):
            continue
        html = _read(p)
        rel = _rel(p)
        if "geo-answer-capsule" not in html:
            continue
        # 容忍额外 class / 嵌套标签：取胶囊区块文本判断是否为空
        idx = html.find("geo-answer-capsule")
        seg = html[idx:idx + 2500]
        cap_text = re.sub(r"<[^>]+>", "", seg)
        cap_text = re.sub(r"\s+", "", cap_text)
        if len(cap_text) < 10:
            findings.append(Finding(
                "S4-LEAK", SEVERITY_BLOCKER, rel,
                "GEO 胶囊正文为空或过小（<10 字），内容注入失败",
                "补全胶囊正文或删除空胶囊，重跑",
            ))
        basename = os.path.basename(p)
        if basename == "index.html" and rel == "articles/index.html":
            findings.append(Finding(
                "S4-LEAK", SEVERITY_BLOCKER, rel,
                "文章列表页 articles/index.html 出现 GEO 胶囊（组件泄漏）",
                "删除列表页误注入的胶囊块，重跑",
            ))
        elif basename == "index.html":
            findings.append(Finding(
                "S4-LEAK", SEVERITY_WARN, rel,
                "列表页 index.html 出现 GEO 胶囊，确认是否泄漏",
                "复核该列表页是否应承载文章级组件，酌情移除",
            ))
    return findings


def _collect_local_refs(html, base_file):
    """返回 [(kind, ref, exists_bool, is_empty)]，仅本地引用。"""
    out = []
    for tag, attrs, _ in iter_tags(html):
        # 资源类
        if tag == "link" and attrs.get("rel") in ("stylesheet", "preload", "icon") \
                and "href" in attrs:
            ref = attrs["href"]
            if resolve_local(ref, base_file) is not None:
                p = resolve_local(ref, base_file)
                out.append(("link", ref, local_exists(p), ref.strip() == ""))
        elif tag == "script" and "src" in attrs:
            ref = attrs["src"]
            if resolve_local(ref, base_file) is not None:
                p = resolve_local(ref, base_file)
                out.append(("script", ref, local_exists(p), ref.strip() == ""))
        elif tag in ("img", "image", "source", "use") and "src" in attrs:
            ref = attrs["src"]
            if resolve_local(ref, base_file) is not None:
                p = resolve_local(ref, base_file)
                out.append(("img", ref, local_exists(p), ref.strip() == ""))
        elif tag == "meta" and attrs.get("property", "").lower() == "og:image" \
                and "content" in attrs:
            ref = attrs["content"]
            if resolve_local(ref, base_file) is not None:
                p = resolve_local(ref, base_file)
                out.append(("og:image", ref, local_exists(p), ref.strip() == ""))
        elif tag == "a" and "href" in attrs:
            ref = attrs["href"]
            if resolve_local(ref, base_file) is not None:
                p = resolve_local(ref, base_file)
                out.append(("a", ref, local_exists(p), ref.strip() == ""))
    # style 属性 / 内联样式中的 url()
    for um in re.finditer(r"url\(\s*([\"']?)([^\"')]+)\1\s*\)", html):
        ref = um.group(2).strip()
        if ref.lower().startswith(("http://", "https://", "//", "data:")):
            continue
        p = resolve_local(ref, base_file)
        if p is not None:
            out.append(("css-url", ref, local_exists(p), ref.strip() == ""))
    return out


def check_asset(files):
    findings = []
    for p in files:
        if not (p.endswith(".html") or p.endswith(".css")):
            continue
        raw = _read(p)
        refs = _collect_local_refs(raw, p)
        for kind, ref, exists, empty in refs:
            if empty:
                findings.append(Finding(
                    "S5-ASSET", SEVERITY_BLOCKER, _rel(p),
                    f"{kind} 引用 src/href 为空",
                    "补全资源路径后重跑",
                ))
            elif not exists and kind in ("link", "script", "img", "og:image", "css-url"):
                findings.append(Finding(
                    "S5-ASSET", SEVERITY_BLOCKER, _rel(p),
                    f"{kind} 引用本地资源不存在：{ref}",
                    "补齐资源文件或修正相对路径后重跑",
                ))
    return findings


def check_link(files):
    findings = []
    cache = {}
    for p in files:
        if not p.endswith(".html"):
            continue
        html = _read(p)
        for tag, attrs, _ in iter_tags(html):
            if tag != "a" or "href" not in attrs:
                continue
            ref = attrs["href"].strip()
            if ref == "" or ref.startswith(("#", "http://", "https://", "//",
                                             "mailto:", "tel:", "javascript:", "data:")):
                continue
            base = resolve_local(ref, p)
            if base is None:
                continue
            if not local_exists(base):
                findings.append(Finding(
                    "S6-LINK", SEVERITY_BLOCKER, _rel(p),
                    f"内部链接目标不存在：{ref}",
                    "修正链接目标或创建目标页后重跑",
                ))
            else:
                # 页内锚点存在性（仅 WARN）
                if "#" in ref:
                    anchor = ref.split("#", 1)[1]
                    if anchor:
                        if base not in cache:
                            cache[base] = _read(base)
                        if not has_anchor_id(cache[base], anchor):
                            findings.append(Finding(
                                "S6-LINK", SEVERITY_WARN, _rel(p),
                                f"锚点 #{anchor} 在目标页 {ref.split('#')[0]} 中不存在",
                                "补全目标页锚点 id 或修正锚点",
                            ))
    return findings


def check_brand(files):
    findings = []
    for p in files:
        if not (p.endswith(".html") or p.endswith(".css")):
            continue
        raw = _read(p)
        hits = BRAND_OLD_TOKENS_RE.findall(raw)
        for pat, _ in BRAND_RGBA_OLD:
            hits.extend(pat.findall(raw))
        if hits:
            findings.append(Finding(
                "S7-BRAND", SEVERITY_BLOCKER, _rel(p),
                f"复现旧引擎蓝 token {len(hits)} 处（如 {hits[0]}）",
                "用 --autofix 或手动替换为森林绿系后重跑",
            ))
    return findings


def _extract_site_nav(html):
    """返回 (nav_inner_html, list_of_(text,href)) 或 None。"""
    m = re.search(r'<nav\b[^>]*class="[^"]*site-nav[^"]*"[^>]*>(.*?)</nav>',
                  html, re.S | re.I)
    if not m:
        return None
    inner = m.group(1)
    items = []
    for am in re.finditer(r"<a\b[^>]*>(.*?)</a>", inner, re.S):
        txt = re.sub(r"<[^>]+>", "", am.group(1)).strip()
        hm = re.search(r'href="([^"]*)"', am.group(0))
        href = hm.group(1) if hm else ""
        items.append((txt, href))
    return inner, items


def check_nav(files):
    findings = []
    for p in files:
        if not p.endswith(".html"):
            continue
        html = _read(p)
        nav = _extract_site_nav(html)
        if not nav:
            continue
        _, items = nav
        texts = [NAV_NORMALIZE.get(t, t) for t, _ in items]
        # 相对顺序校验
        positions = {}
        for label in CANON_NAV:
            idxs = [i for i, t in enumerate(texts) if t == label]
            if idxs:
                positions[label] = idxs[0]
        ordered = sorted(positions.items(), key=lambda kv: kv[1])
        seq = [k for k, _ in ordered]
        if seq != sorted(seq, key=lambda x: CANON_NAV.index(x)):
            findings.append(Finding(
                "S8-NAV", SEVERITY_BLOCKER, _rel(p),
                f"主导航顺序错乱：实际 {texts}，规范 {CANON_NAV}",
                "用 --autofix 或手动按规范顺序重排主导航后重跑",
            ))
        # 缺失规范项
        missing = [l for l in CANON_NAV if l not in positions]
        if missing:
            findings.append(Finding(
                "S8-NAV", SEVERITY_WARN, _rel(p),
                f"主导航缺失规范项：{missing}",
                "复核是否应有该入口，酌情补齐",
            ))
    return findings


def check_insecure(files):
    findings = []
    for p in files:
        if not p.endswith(".html"):
            continue
        html = _read(p)
        for tag, attrs, _ in iter_tags(html):
            if tag == "a" and "href" in attrs:
                ref = attrs["href"].strip()
                if ref.startswith("http://"):
                    findings.append(Finding(
                        "S9-INSECURE", SEVERITY_WARN, _rel(p),
                        f"外链使用 http（非 https）：{ref}",
                        "改为 https 或确认目标不支持 https",
                    ))
                elif ref.startswith("javascript:"):
                    findings.append(Finding(
                        "S9-INSECURE", SEVERITY_WARN, _rel(p),
                        f"javascript: 伪协议链接：{ref[:40]}",
                        "移除残留脚本链接，改为正常导航",
                    ))
    return findings


# ============================================================
# 自动修复（仅安全项：S7 品牌色 / S8 导航）
# ============================================================
def autofix_brand(files):
    changed = []
    for p in files:
        if not (p.endswith(".html") or p.endswith(".css")):
            continue
        try:
            raw = _read(p)
        except Exception:
            continue
        new = raw
        for old, newc in BRAND_OLD_TO_NEW.items():
            new = re.sub(re.escape(old), newc, new, flags=re.IGNORECASE)
            new = re.sub(re.escape(old.upper()), newc.upper(), new)
        for pat, repl in BRAND_RGBA_OLD:
            new = pat.sub(repl, new)
        if new != raw:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(new)
            changed.append(_rel(p))
    return changed


def _reorder_nav(m):
    """仅对 <a> 项按规范顺序就地重排，保留导航块内其它内容（如搜索按钮）。"""
    block = m.group(0)
    a_matches = list(re.finditer(r"<a\b[^>]*>.*?</a>", block, re.S))
    labels = []
    for am in a_matches:
        txt = re.sub(r"<[^>]+>", "", am.group(0)).strip()
        labels.append(NAV_NORMALIZE.get(txt, txt))
    present = [l for l in CANON_NAV if l in labels]
    # 仅当标签多重集与规范项完全一致时才安全重排（避免误删/误加自定义项）
    if sorted(labels) != sorted(present):
        return block
    frag_by_label = {l: am.group(0) for l, am in zip(labels, a_matches)}
    ordered_frags = [frag_by_label[l] for l in present]
    result = ""
    last = 0
    for am, of in zip(a_matches, ordered_frags):
        result += block[last:am.start()] + of
        last = am.end()
    result += block[last:]
    return result


def autofix_nav(files):
    changed = []
    for p in files:
        if not p.endswith(".html"):
            continue
        try:
            raw = _read(p)
        except Exception:
            continue
        new = re.sub(
            r'<nav\b[^>]*class="[^"]*site-nav[^"]*"[^>]*>.*?</nav>',
            _reorder_nav, raw, flags=re.S | re.I,
        )
        if new != raw:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(new)
            changed.append(_rel(p))
    return changed


# ============================================================
# 编排
# ============================================================
CHECKS = [
    ("S1-BLANK", "空白页检测", check_blank),
    ("S2-GARBLED", "乱码/编码损坏检测", check_garbled),
    ("S3-STRUCTURE", "结构损坏检测", check_structure),
    ("S4-LEAK", "组件泄漏检测", check_component_leak),
    ("S5-ASSET", "资源加载失败检测", check_asset),
    ("S6-LINK", "内部链接失效检测", check_link),
    ("S7-BRAND", "品牌色回退检测", check_brand),
    ("S8-NAV", "导航顺序错乱检测", check_nav),
    ("S9-INSECURE", "不安全外链检测", check_insecure),
]


def run_checks(target_files, autofix=False):
    results = []
    if autofix:
        cb = autofix_brand(target_files)
        cn = autofix_nav(target_files)
        if cb or cn:
            print(f"🛠  自动修复：品牌色 {len(cb)} 个文件，导航 {len(cn)} 个文件")
            # 修复后重新读取
    for cid, name, fn in CHECKS:
        meta = next(d for d in DETECTION_ITEMS if d["id"] == cid)
        findings = fn(target_files)
        results.append(CheckResult(cid, name, meta["severity"], findings))
    return results


def print_report(results, as_json=False):
    all_findings = [f for r in results for f in r.findings]
    n_block = sum(1 for f in all_findings if f.severity == SEVERITY_BLOCKER)
    n_warn = sum(1 for f in all_findings if f.severity == SEVERITY_WARN)
    if as_json:
        print(json.dumps({
            "blockers": n_block, "warns": n_warn,
            "checks": [
                {"id": r.check_id, "name": r.name, "passed": r.passed,
                 "findings": [f.as_dict() for f in r.findings]}
                for r in results
            ],
        }, ensure_ascii=False, indent=2))
    else:
        print("=" * 64)
        print("  网站稳定性 / 专业性 / 真实性 自检（Stability Guard）")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 64)
        print()
        for r in results:
            print(r.report())
            print()
        print("=" * 64)
        if n_block == 0:
            print(f"  🟢 稳定性自检通过（{n_warn} 条 WARN，不阻断发布）")
        else:
            print(f"  🔴 稳定性自检未通过 — {n_block} 处 BLOCKER，{n_warn} 条 WARN")
            print("  ❌ 已拦截：请修复 BLOCKER 后再发布")
        print("=" * 64)
    return n_block


def emit_doc():
    lines = []
    lines.append("# 网站稳定性自检 · 检测项清单、触发条件与处理流程")
    lines.append("")
    lines.append("> 模块：`scripts/stability_guard.py`　|　强制关卡：发布前第二道闸门（quality_gate 之后、原子推送之前）")
    lines.append(">")
    lines.append("> 本文档由检测项注册表自动生成，与代码单一真相源同步。")
    lines.append("")
    lines.append("## 一、总览")
    lines.append("")
    lines.append("本模块拦截「会让用户秒关页面、拉高跳出率」的低级硬伤，覆盖用户反馈的")
    lines.append("**空白页 / 加载失败 / 内容错乱 / 链接失效 / 品牌回退 / 导航错乱** 六大类。")
    lines.append("")
    lines.append("| 编号 | 检测项 | 类别 | 严重级 | 阻断发布 |")
    lines.append("|------|--------|------|--------|----------|")
    for d in DETECTION_ITEMS:
        block = "是" if d["severity"] == SEVERITY_BLOCKER else "否（告警）"
        lines.append(f"| {d['id']} | {d['name']} | {d['category']} | {d['severity']} | {block} |")
    lines.append("")
    lines.append("**严重级约定**")
    lines.append("- `BLOCKER`：必然破坏专业形象或可用性 → 进程返回非 0，publish.py 中止推送，零远程写入。")
    lines.append("- `WARN`：需复核但不阻断发布（如缺失导航项、http 外链）。")
    lines.append("")
    lines.append("## 二、检测项明细（触发条件 + 处理流程）")
    lines.append("")
    for d in DETECTION_ITEMS:
        lines.append(f"### {d['id']} · {d['name']}")
        lines.append("")
        lines.append(f"- **类别**：{d['category']}")
        lines.append(f"- **严重级**：{d['severity']}")
        lines.append(f"- **触发条件**：{d['trigger']}")
        lines.append(f"- **处理流程**：{d['handling']}")
        lines.append(f"- **自动修复**：{'支持（--autofix）' if d['autofix'] else '否（人工修复）'}")
        lines.append("")
    lines.append("## 三、统一预警与拦截机制")
    lines.append("")
    lines.append("1. **发布前强制双闸**：`publish.py` 先跑 `quality_gate.py --all`，")
    lines.append("   通过后再跑 `stability_guard.py --all`；任一 BLOCKER → 立即中止，")
    lines.append("   本次发布**零远程写入**，绝不带病上线。")
    lines.append("2. **实时守护**：`python3 scripts/stability_guard.py --serve` 监听工作区")
    lines.append("   `.html/.css` 变更，作者保存即扫，发现 BLOCKER 即时终端告警。")
    lines.append("3. **CI 门禁**：`--json` 输出供流水线消费；BLOCKER 计数 > 0 即非零退出。")
    lines.append("4. **误报护栏**：列表页豁免桩页（refresh）、verify 页、设计系统页；")
    lines.append("   品牌色仅锁定 unambiguous 的旧引擎蓝 token，避免误伤中性灰。")
    lines.append("")
    lines.append("## 四、使用命令")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 scripts/stability_guard.py --all            # 全站扫描")
    lines.append("python3 scripts/stability_guard.py --files a.html b.css")
    lines.append("python3 scripts/stability_guard.py --serve          # 实时守护")
    lines.append("python3 scripts/stability_guard.py --autofix --all   # 安全项自动修复")
    lines.append("python3 scripts/stability_guard.py --json --all     # CI 机器可读")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def serve_mode(interval=2.0):
    print("🔭 实时守护模式：监听 .html/.css 变更，发现低级错误即时拦截（Ctrl-C 退出）")
    last_mtime = {}
    try:
        while True:
            changed = []
            for fp in _get_all_html_and_css():
                try:
                    m = os.path.getmtime(fp)
                except OSError:
                    continue
                if fp not in last_mtime or m > last_mtime[fp] + 1e-6:
                    last_mtime[fp] = m
                    changed.append(fp)
            if changed:
                results = run_checks(changed, autofix=False)
                block = print_report(results)
                if block > 0:
                    print(f"⛔ 已拦截 {block} 处上线前错误，请修复后保存。\n")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n👋 守护模式已退出。")


def main():
    ap = argparse.ArgumentParser(description="网站发布前稳定性自检与拦截模块")
    ap.add_argument("--all", action="store_true", help="全站扫描")
    ap.add_argument("--files", nargs="+", help="指定文件扫描")
    ap.add_argument("--serve", action="store_true", help="实时守护（监听变更）")
    ap.add_argument("--autofix", action="store_true", help="对安全项自动修复")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--emit-doc", action="store_true", help="生成检测项清单文档并退出")
    args = ap.parse_args()

    if args.emit_doc:
        sys.stdout.write(emit_doc())
        return 0

    if args.serve:
        serve_mode()
        return 0

    if args.files:
        target = [os.path.abspath(f) for f in args.files]
    else:
        target = _get_all_html_and_css()

    if not target:
        print("未找到待检文件。")
        return 0

    results = run_checks(target, autofix=args.autofix)
    n_block = print_report(results, as_json=args.json)
    return 1 if n_block > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
