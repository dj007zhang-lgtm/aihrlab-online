#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把全站 meta description 统一规范到可发布区间（55–110 汉字 / ≤230 字符）。

处理四类残留：
  1. 含污染句（导航文本、站级套话、通用兜底句）→ 去掉该句，用正文续写补足；
  2. 过短（<50 汉字）→ 用本页正文的后续句子补足；
  3. 过长（>230 字符）→ 在句号边界截断；
  4. 通用套话重复 → 整段用正文重建。

原则：只使用页面自己正文里的内容，不虚构、不复用他文导语。
正文确实不足的页面会被列出交给「合并/下线」处理，而不是硬凑字数。
"""
import os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r"[\u4e00-\u9fff]")
DESC_RE = re.compile(r'(<meta\s+name="description"\s+content=")([^"]*)(")')

BAD_SENTS = (
    "本文基于公开信息与原创分析，拆解 AI 时代组织怎么变、HR 怎么做",
    "本文基于公开信息与原创分析，拆解 AI 时代组织怎么变",
    "AIHR数智引擎——专注",
    "AI搜索",
    "深度解析，AI时代组织变革实践指南",
    "本文提供实战框架与权威信源支撑，帮助HR在AI时代建立组织能力",
)
NOISE = ("关注公众号", "免责声明", "转载请注明", "©", "上一篇", "下一篇")

MIN_HAN, TARGET_HAN = 55, 95
MAX_CHARS = 230


def strip_bad(desc):
    parts = re.split(r"(?<=[。！？])\s*", desc)
    keep = [p for p in parts if p.strip() and not any(b in p for b in BAD_SENTS)]
    return " ".join(keep).strip()


def body_paragraphs(html):
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
        t = re.sub(r"<[^>]+>", "", p)
        t = t.replace("&nbsp;", " ").replace("&amp;", "&")
        t = re.sub(r"\s+", " ", t).strip()
        if len(HAN.findall(t)) < 25:
            continue
        if any(n in t for n in NOISE):
            continue
        if any(b in t for b in BAD_SENTS):
            continue
        out.append(t)
    return out


def truncate_sentence(text):
    if len(text) <= MAX_CHARS:
        return text
    cut = None
    for m in re.finditer(r"[。！？]", text):
        if m.end() > 90:
            cut = m.end()
            break
    if cut and cut <= MAX_CHARS:
        return text[:cut]
    return text[: MAX_CHARS - 1] + "…"


def sanitize(t):
    t = t.replace('"', "“").replace("'", "’")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"^[，、；：\s]+", "", t)
    t = re.sub(r"，\s*，", "，", t)
    return t.strip()


def main():
    fixed, short = 0, []
    for f in sorted(glob.glob(os.path.join(ROOT, "articles", "*.html"))):
        html = open(f, encoding="utf-8").read()
        if 'http-equiv="refresh"' in html:
            continue
        m = DESC_RE.search(html)
        if not m:
            continue
        cur = m.group(2)
        h1m = re.search(r"<h1>(.*?)</h1>", html, re.S)
        h1 = re.sub(r"<[^>]+>", "", h1m.group(1)).strip() if h1m else ""

        base = strip_bad(cur)
        pool = [base] if base else []
        for p in body_paragraphs(html):
            if p.startswith(h1) and len(set(p)) < 40:
                continue
            if p in pool:
                continue
            pool.append(p)

        built = ""
        for cand in pool:
            if len(HAN.findall(built)) >= TARGET_HAN:
                break
            built = (built + " " + cand).strip() if built else cand
        new = sanitize(truncate_sentence(built))
        n = len(HAN.findall(new))

        if n < MIN_HAN:
            short.append((os.path.basename(f), n, new[:60]))
            # 正文不足，保留清洗后的版本（去掉套话优于留着套话）
            if not new:
                continue
        if new == cur:
            continue
        html = DESC_RE.sub(lambda x: x.group(1) + new + x.group(3), html, count=1)
        open(f, "w", encoding="utf-8").write(html)
        fixed += 1

    print(f"规范化完成：{fixed} 篇")
    if short:
        print(f"\n⚠ 正文不足以支撑 55 汉字描述（需另行合并/扩充）：{len(short)} 篇")
        for name, n, prev in short:
            print(f"   {name}  仅 {n} 汉字  | {prev}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
