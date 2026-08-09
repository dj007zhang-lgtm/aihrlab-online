#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inject-references.py — 幂等注入「本文信源」块 + Article JSON-LD citation。

锚点策略: 仅依赖 .article-footer-qr 块闭合后插入 (真实已发布文章与
  templates/article-v2.html 的 DOM 已严重分叉, 不依赖 .article-content /
  .article-body / toc-rail)。插入位置 = 二维码块闭合后、<aside class="toc-rail">
  或 </article> 之前, 对 113/20 两种包裹结构、有/无 toc-rail 都通吃。

双写:
  1) HTML: 在 .article-footer-qr 后插入 .article-references 信源块。
  2) JSON-LD: 在 Article 的 application/ld+json 对象上加 "citation":[...] 数组。

幂等:
  - 文件已含 .article-references -> 跳过 (HTML 已注入)。
  - Article JSON-LD 已含 "citation" -> 跳过 (citation 已注入)。
  - slug 未命中 references.json -> 跳过 (不虚构文章未引用的来源)。
  - 可重跑, 不产生重复块。
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(ROOT, "assets", "js", "references.json")
ARTDIR = os.path.join(ROOT, "articles")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html_block(refs):
    items = "".join(
        '<li class="verified-sources__item">'
        f'<a class="verified-sources__link" href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a>'
        f'<span class="verified-sources__meta">{esc(r["publisher"])} · {r["year"]}</span>'
        "</li>"
        for r in refs
    )
    return (
        '<section class="verified-sources" aria-label="本文信源">'
        '<h2 class="verified-sources__title">本文信源</h2>'
        '<p class="verified-sources__intro">以下为与本文议题相关的已核验一手资料，链接均指向原始发布方。</p>'
        f'<ul class="verified-sources__list">{items}</ul>'
        "</section>"
    )


def insert_after_qr(html, block):
    """在 .article-footer-qr 的匹配闭合 </div> 后插入 block。无匹配返回 None。"""
    m = re.search(r'<div class="article-footer-qr"[^>]*>', html)
    if not m:
        return None
    depth = 1
    i = m.end()
    n = len(html)
    while i < n:
        if html.startswith("<div", i):
            depth += 1
            i += 4
            continue
        if html.startswith("</div>", i):
            depth -= 1
            if depth == 0:
                return html[: i + 6] + block + html[i + 6 :]
            i += 6
            continue
        i += 1
    return None


def _is_article(d):
    t = d.get("@type")
    if t == "Article":
        return True
    if isinstance(t, list) and "Article" in t:
        return True
    return False


def inject_citation(html, refs):
    """在 Article 的 ld+json 对象上添加 citation 数组 (若已存在则跳过)。"""
    pattern = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
    new_html = html
    changed = False
    for m in pattern.finditer(html):
        blob = m.group(1)
        try:
            data = json.loads(blob)
        except Exception:
            continue
        target = None
        if isinstance(data, dict) and _is_article(data):
            target = data
        elif isinstance(data, list):
            for el in data:
                if isinstance(el, dict) and _is_article(el):
                    target = el
                    break
        if target is None:
            continue
        if "citation" in target:
            continue
        target["citation"] = [
            {"@type": "Article", "name": r["title"], "url": r["url"]} for r in refs
        ]
        new_blob = json.dumps(data, ensure_ascii=False, indent=2)
        new_html = new_html.replace(blob, new_blob, 1)
        changed = True
    return new_html, changed


def process_file(path, refs_map, check=False):
    slug = os.path.basename(path)[:-5]  # strip .html
    refs = refs_map.get(slug)
    if not refs:
        return None  # 未命中, 跳过
    html = open(path, encoding="utf-8").read()
    if "verified-sources" in html:
        return None  # 已注入, 幂等跳过

    block = html_block(refs)
    new_html = insert_after_qr(html, block)
    if new_html is None:
        return {"slug": slug, "status": "NO_QR_ANCHOR", "written": False}
    new_html, cit_changed = inject_citation(new_html, refs)
    if not cit_changed:
        # 块已插入但 Article JSON-LD 未找到/已含 citation; 仍写回 (块是新增的)
        pass
    if check:
        return {
            "slug": slug,
            "status": "WOULD_INJECT",
            "refs": len(refs),
            "cit": cit_changed,
            "written": False,
        }
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return {
        "slug": slug,
        "status": "INJECTED",
        "refs": len(refs),
        "cit": cit_changed,
        "written": True,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="演练, 不写回")
    ap.add_argument("--slug", help="只处理指定 slug (调试)")
    args = ap.parse_args()

    if not os.path.exists(REFS):
        print(f"[ERR] 找不到 {REFS}, 请先运行 build_references.py", file=sys.stderr)
        sys.exit(1)
    refs_map = json.load(open(REFS, encoding="utf-8"))

    files = []
    if args.slug:
        p = os.path.join(ARTDIR, args.slug + ".html")
        if os.path.exists(p):
            files = [p]
    else:
        files = sorted(
            os.path.join(ARTDIR, f)
            for f in os.listdir(ARTDIR)
            if f.endswith(".html")
        )

    injected = 0
    skipped = 0
    no_anchor = 0
    for p in files:
        r = process_file(p, refs_map, check=args.check)
        if r is None:
            skipped += 1
            continue
        if r["status"] == "NO_QR_ANCHOR":
            no_anchor += 1
            print(f"  [锚点缺失] {r['slug']} (无 .article-footer-qr)")
            continue
        injected += 1
        tag = "演练" if args.check else "注入"
        print(f"  [{tag}] {r['slug']}  信源={r['refs']}  JSON-LD={r['cit']}")

    print(
        f"\n[完成] 处理文件={len(files)}  命中注入={injected}  未命中跳过={skipped}"
        + (f"  锚点缺失={no_anchor}" if no_anchor else "")
    )


if __name__ == "__main__":
    main()
