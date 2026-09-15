#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复被污染/模板化的 meta description。

背景：2026-09-14 的一轮批量提取把导航区文本、站级通用口径、甚至另一篇文章的
导语写进了 description，导致 SERP 摘要与文章主题不符，且这批已经上线。

本脚本只用【页面自己的正文】重建描述：
  1. 取 <article>/<main> 区内的段落，剔除导航、页脚二维码、模板套话；
  2. 从句号边界取前 1–3 句，凑到 55–110 汉字；
  3. 清掉半角引号（曾因此截断 HTML 属性）、改用「」/『』；
  4. 若正文不足，则退回 <meta name="short-answer"> 或 h1 语义造句，绝不复制通用模板。

幂等：已是合规描述的页面跳过。
"""
import os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r"[\u4e00-\u9fff]")
DESC_RE = re.compile(r'(<meta\s+name="description"\s+content=")([^"]*)(")')

BAD_PATTERNS = (
    "AI搜索",
    "AIHR数智引擎——专注",
    "AI正在从「被使用的工具」",
    "本文基于公开信息与原创分析，拆解 AI 时代组织怎么变",
    "深度解析，AI时代组织变革实践指南",
)
NOISE = ("关注公众号", "免责声明", "转载请注明", "©", "面包屑", "上一篇", "下一篇")


def clean_text(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_body_paragraphs(html):
    h = re.sub(r"<script[\s\S]*?</script>", "", html)
    h = re.sub(r"<head[\s\S]*?</head>", "", h)
    m = re.search(r"<main[\s\S]*?</main>", h)
    if m:
        h = m.group(0)
    h = re.sub(r"<nav[\s\S]*?</nav>", "", h)
    h = re.sub(r"<footer[\s\S]*?</footer>", "", h)
    h = re.sub(r"<header class=\"site-header\"[\s\S]*?</header>", "", h)
    out = []
    for p in re.findall(r"<p[^>]*>([\s\S]*?)</p>", h):
        t = clean_text(p)
        if len(HAN.findall(t)) < 30:
            continue
        if any(n in t for n in NOISE):
            continue
        out.append(t)
    return out


def build_desc(paras, h1, fallback_meta):
    cands = []
    for p in paras:
        if any(b in p for b in BAD_PATTERNS):
            continue
        if p.startswith(h1) and len(set(p)) < 40:  # 标题复读句
            continue
        cands.append(p)
    text = ""
    for c in cands:
        if len(HAN.findall(text)) >= 55:
            break
        text = (text + " " + c).strip() if text else c
    if not text and fallback_meta:
        text = fallback_meta
    if not text:
        text = h1
    # 截到句号边界
    cut = None
    for m in re.finditer(r"[。！？]", text):
        if len(HAN.findall(text[: m.end()])) >= 55:
            cut = m.end()
            break
    if cut and len(HAN.findall(text[:cut])) <= 120:
        text = text[:cut]
    else:
        n = 0
        for i, ch in enumerate(text):
            if HAN.match(ch):
                n += 1
            if n >= 95:
                text = text[: i + 1]
                break
    # 引号清理：半角引号会提前闭合 HTML 属性
    text = text.replace('"', "“").replace("'", "’")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    targets = []
    for f in sorted(glob.glob(os.path.join(ROOT, "articles", "*.html"))):
        html = open(f, encoding="utf-8").read()
        if 'http-equiv="refresh"' in html:
            continue  # 迁移桩页无需描述
        m = DESC_RE.search(html)
        if not m:
            continue
        cur = m.group(2)
        if not any(b in cur for b in BAD_PATTERNS):
            continue
        if len(HAN.findall(cur)) >= 50 and not cur.startswith(("AI搜索", "AIHR数智引擎——专注")):
            # 仅含弱兜底句但已足够长的，保留（语义仍由正文支撑）
            if "本文基于公开信息与原创分析" in cur:
                continue
        targets.append(f)

    # 顺带处理文章列表页
    idx = os.path.join(ROOT, "articles", "index.html")
    if os.path.exists(idx):
        h = open(idx, encoding="utf-8").read()
        m = DESC_RE.search(h)
        if m and any(b in m.group(2) for b in BAD_PATTERNS):
            targets.append(idx)

    fixed = skipped = 0
    for f in targets:
        html = open(f, encoding="utf-8").read()
        h1m = re.search(r"<h1>(.*?)</h1>", html, re.S)
        h1 = clean_text(h1m.group(1)) if h1m else ""
        sa = re.search(r'name="short-answer"\s+content="([^"]*)"', html)
        fallback = sa.group(1) if sa else ""
        paras = extract_body_paragraphs(html)
        new = build_desc(paras, h1, fallback)
        if os.path.basename(f) == "index.html":
            new = "AI 时代组织变革与 AI+HR 的深度文章库：大厂案例拆解、AI 原生组织设计、人才与招聘重构、落地实战与合规，按主题成簇编排，方便按问题切入而非按时间翻页。"
        n = len(HAN.findall(new))
        if n < 50:
            print(f"  SKIP(正文不足) {os.path.relpath(f, ROOT)}  only={n}han")
            skipped += 1
            continue
        html = DESC_RE.sub(lambda x: x.group(1) + new + x.group(3), html, count=1)
        open(f, "w", encoding="utf-8").write(html)
        fixed += 1
        print(f"  FIXED({n}字) {os.path.relpath(f, ROOT)}")
        print(f"        {new[:88]}")

    print(f"\nSummary: fixed={fixed} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
