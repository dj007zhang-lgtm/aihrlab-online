#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 h2>=4 的长文批量注入右侧粘性目录栏（D 支柱 / 跳出率改造）。

设计原则（手术式、幂等、零内容破坏）：
- 仅给正文 <h2> 的【开始标签】加 id="s{n}"（已有 id 则复用），绝不触碰 h2 内容。
- <aside class="toc-rail"> 插到「已加完 id 的 html」里 rfind('</article>') 之前，
  避免任何 offset 位移 bug（上一版用 offset 累计导致插入点错乱、误删 h2 内容）。
- 兼容 article-layout / article-body / 其他结构（CSS 用 position:fixed 右栏）。
- 自动跳过：桩页(http-equiv=refresh)、已含 toc-sidebar/toc-rail 的文。
- 幂等：重跑安全（先跳过的逻辑保证；若需重跑，先 revert）。

用法：
  python3 scripts/build_toc_rail.py --dry     # 仅统计
  python3 scripts/build_toc_rail.py --apply   # 注入
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "articles")

OPEN = re.compile(r"<h2\b([^>]*)>")          # 仅开始标签
STRIP = re.compile(r"<[^>]+>")


def plain(text):
    return STRIP.sub("", text).strip()


def main():
    mode = "apply" if "--apply" in sys.argv else "dry"
    articles = sorted(f for f in os.listdir(ART) if f.endswith(".html"))
    changed = skipped_stub = skipped_existing = skipped_few = 0
    for fn in articles:
        path = os.path.join(ART, fn)
        html = open(path, encoding="utf-8").read()
        if 'http-equiv="refresh"' in html:
            skipped_stub += 1
            continue
        if "toc-sidebar" in html or "toc-rail" in html:
            skipped_existing += 1
            continue

        # 正文范围：article-header 闭合之后、</article> 之前
        hstart = html.find('<header class="article-header"')
        if hstart == -1:
            hstart = html.find("<header")
        hc = html.find("</header>", hstart) if hstart != -1 else -1
        ae = html.rfind("</article>")
        cs = hc + 1 if hc != -1 else 0

        opens = [m for m in OPEN.finditer(html) if cs <= m.start() < ae]
        if len(opens) < 4:
            skipped_few += 1
            continue

        # 文档序收集 (start, end, new_opening_tag_or_None, mid, label)
        entries = []
        for i, m in enumerate(opens, 1):
            attr = m.group(1)
            if re.search(r"\bid\s*=", attr):
                mid = re.search(r'\bid="([^"]+)"', attr).group(1)
                newtag = None
            else:
                mid = f"s{i}"
                newtag = f'<h2{attr} id="{mid}">'
            cend = html.find("</h2>", m.end())
            txt = plain(html[m.end():cend]) if cend != -1 else f"第{i}节"
            entries.append((m.start(), m.end(), newtag, mid, txt))

        # 右→左替换开始标签，避免位置漂移
        new_html = html
        for start, end, newtag, mid, txt in reversed(entries):
            if newtag is not None:
                new_html = new_html[:start] + newtag + new_html[end:]

        # 构建 aside 并插入到「已加 id 的 html」的 </article> 之前
        ol = "".join(f'<li><a href="#{mid}">{txt}</a></li>' for _, _, _, mid, txt in entries)
        aside = (
            f'<aside class="toc-rail"><nav class="toc"><h4>目录</h4>'
            f"<ol>{ol}</ol></nav></aside>"
        )
        ae2 = new_html.rfind("</article>")
        final_html = new_html[:ae2] + aside + new_html[ae2:]

        if mode == "apply":
            open(path, "w", encoding="utf-8").write(final_html)
        changed += 1
        print(f"[{mode}] {fn}: +{len(entries)} 目录项 (h2={len(opens)})")

    print(
        f"\n汇总: 注入={changed} | 跳过桩页={skipped_stub} | "
        f"跳过已有TOC={skipped_existing} | 跳过h2<4={skipped_few}"
    )


if __name__ == "__main__":
    main()
