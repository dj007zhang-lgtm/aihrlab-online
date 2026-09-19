# -*- coding: utf-8 -*-
"""
ci/gates/__init__.py —— qa_guardian 门基础设施

统一约定（鲁棒性第一）：
  - 每个 gate 模块暴露 run(site_root, cfg, baseline) -> GateReport
  - 不变量：检测门绝无副作用；自愈在编排器 --heal 分支单独处理。
  - 任一 gate 抛异常由编排器捕获为 status=ERROR，绝不拖垮整体运行。
"""
import os
import re
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

SKIP_DIRS = {"templates", "_wip", "node_modules", ".git", "__pycache__", "assets", "compare", "bridge", "ask", "glossary", "categories", "tags"}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def count_cjk(text):
    """统计中文字符数（正文深度主指标）。"""
    return len(CJK_RE.findall(text or ""))


def is_stub_html(html):
    """判定重定向/迁移桩页（noindex + meta refresh）。这类页是刻意存在的，不应被桩页检测/克隆检测误伤。"""
    return ('http-equiv="refresh"' in html) or ('name="robots" content="noindex' in html)


def is_indexable(html):
    """可索引正文页（无 noindex、非 refresh 桩、非纯功能页）。"""
    if is_stub_html(html):
        return False
    head = html[:4000].lower()
    if 'name="robots" content="noindex' in head:
        return False
    return True


def walk_html(site_root, scan_dirs=None):
    """枚举站内 .html 文件（绝对路径）。scan_dirs 限定只扫指定一级目录；None=全站。"""
    out = []
    if scan_dirs:
        for d in scan_dirs:
            dp = os.path.join(site_root, d)
            if not os.path.isdir(dp):
                continue
            for fn in sorted(os.listdir(dp)):
                if fn.endswith(".html") and fn != "index.html":
                    out.append(os.path.join(dp, fn))
    else:
        for dirpath, dirnames, filenames in os.walk(site_root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".html"):
                    out.append(os.path.join(dirpath, fn))
    return sorted(out)


def read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def strip_tags(html):
    return re.sub(r"<[^>]+>", "", html or "")


def clean_text(html):
    return re.sub(r"\s+", " ", strip_tags(html)).strip()


def extract_article_body(html):
    """返回文章主正文区域（<article> 内全文，未截断）——用于字数/深度统计。
    注：含注入块（CTA/回链/延伸阅读）的文本，但那部分很短且各页一致，
    对「中位数/薄内容」判定只有微小、一致的膨胀，不影响阈值判定。"""
    m = re.search(r"<article\b[^>]*>(.*?)</article>", html, re.S | re.I)
    return m.group(1) if m else html


def extract_article_core(html):
    """返回剔除注入块后的文章核心（用于克隆指纹，避免全站共用的页脚 QR/回链段
    制造假共享段落）。在第一个注入块标记处截断。"""
    region = extract_article_body(html)
    markers = ["article-footer-qr", "📚 本文收录于", 'class="inline-related"',
               "<!-- ★ 公众号二维码", "newsletter", "related-reading"]
    cut = len(region)
    for mk in markers:
        idx = region.find(mk)
        if idx != -1 and idx < cut:
            cut = idx
    return region[:cut]


def extract_paragraphs(html, min_cjk=20):
    """从正文抽段落（p/li/blockquote/二级以下标题），归一化并过滤过短段。返回段落哈希集合。"""
    body = extract_article_core(html)
    chunks = re.findall(r"<(?:p|li|blockquote|h2|h3|h4)\b[^>]*>(.*?)</(?:p|li|blockquote|h2|h3|h4)>", body, re.S | re.I)
    hashes = set()
    for c in chunks:
        txt = clean_text(c)
        if count_cjk(txt) >= min_cjk:
            hashes.add(hashlib.sha1(txt.strip().encode("utf-8")).hexdigest())
    return hashes


def rel(site_root, path):
    return os.path.relpath(path, site_root)


@dataclass
class Finding:
    severity: str           # BLOCK / WARN / ERROR / INFO
    code: str
    file: str = ""
    detail: str = ""

    def to_dict(self):
        return {"severity": self.severity, "code": self.code,
                "file": self.file, "detail": self.detail}


@dataclass
class GateReport:
    name: str
    title: str
    status: str = "PASS"    # PASS / WARN / FAIL / ERROR
    blocking: bool = False
    metrics: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    summary: str = ""
    elapsed_s: float = 0.0

    def add(self, f: Finding):
        self.findings.append(f.to_dict())

    def to_dict(self):
        d = asdict(self)
        return d


def gate_blocked(report: GateReport) -> bool:
    """存在任意 BLOCK 级发现 → 该门视为阻断级失败。"""
    return any(f["severity"] == "BLOCK" for f in report.findings)
