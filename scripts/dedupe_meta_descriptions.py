#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去掉 meta description 里的重复句段。

问题：上一轮「用正文续写补足长度」时，把已有句子和正文段落直接拼接，
      两者重叠造成同一句出现两次（共 94 篇），在 SERP 摘要里直接可见。

做法：按句号切分后顺序去重（保留首次出现），再校验长度；
      长度不足时用正文中「未出现在描述里」的句子补足，宁短勿重。
"""
import os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r"[\u4e00-\u9fff]")
DESC_RE = re.compile(r'(<meta\s+name="description"\s+content=")([^"]*)(")')
NOISE = ("关注公众号", "免责声明", "转载请注明", "©", "上一篇", "下一篇")

MIN_HAN, MAX_CHARS = 55, 230


def split_sents(d):
    out = []
    for s in re.split(r"(?<=[。！？])\s*", d):
        s = s.strip()
        if s and len(HAN.findall(s)) >= 8:
            out.append(s)
    return out


def dedupe(desc):
    seen, out = set(), []
    for s in split_sents(desc):
        key = re.sub(r"[\s，、；：]", "", s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return " ".join(out).strip()


def extra_from_body(html, exclude_keys):
    h = re.sub(r"<script[\s\S]*?</script>", "", html)
    h = re.sub(r"<head[\s\S]*?</head>", "", h)
    m = re.search(r"<main[\s\S]*?</main>", h)
    if m:
        h = m.group(0)
    h = re.sub(r"<nav[\s\S]*?</nav>", "", h)
    h = re.sub(r"<footer[\s\S]*?</footer>", "", h)
    for p in re.findall(r"<p[^>]*>([\s\S]*?)</p>", h):
        t = re.sub(r"<[^>]+>", "", p)
        t = re.sub(r"\s+", " ", t).strip()
        if len(HAN.findall(t)) < 25 or any(n in t for n in NOISE):
            continue
        for s in split_sents(t):
            k = re.sub(r"[\s，、；：]", "", s)
            if k in exclude_keys:
                continue
            yield s


def main():
    fixed, remaining = 0, []
    for f in sorted(glob.glob(os.path.join(ROOT, "articles", "*.html"))):
        html = open(f, encoding="utf-8").read()
        if 'http-equiv="refresh"' in html:
            continue
        m = DESC_RE.search(html)
        if not m:
            continue
        cur = m.group(2)
        new = dedupe(cur)
        if not new:
            continue
        # 去重后长度不足 → 从未被收录的正文句子里补
        if len(HAN.findall(new)) < MIN_HAN:
            keys = {re.sub(r"[\s，、；：]", "", s) for s in split_sents(new)}
            for s in extra_from_body(html, keys):
                if len(HAN.findall(new)) >= MIN_HAN:
                    break
                new = (new + " " + s).strip()
                keys.add(re.sub(r"[\s，、；：]", "", s))
        new = re.sub(r"\s+", " ", new).strip()
        if len(new) > MAX_CHARS:
            cut = None
            for mm in re.finditer(r"[。！？]", new):
                if mm.end() > 90:
                    cut = mm.end()
                    break
            new = new[:cut] if cut and cut <= MAX_CHARS else new[: MAX_CHARS - 1] + "…"
        if new == cur:
            continue
        n = len(HAN.findall(new))
        if n < MIN_HAN:
            remaining.append((os.path.basename(f), n))
        html = DESC_RE.sub(lambda x: x.group(1) + new + x.group(3), html, count=1)
        open(f, "w", encoding="utf-8").write(html)
        fixed += 1
    print(f"去重完成：{fixed} 篇")
    if remaining:
        print(f"⚠ 去重后仍不足 {MIN_HAN} 汉字：{len(remaining)} 篇")
        for name, n in remaining:
            print(f"   {name}  {n} 汉字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
