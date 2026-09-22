#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_analytics.py — 全站埋点脚本覆盖注入（P0-1，2026-09-21）

背景（为什么要这个脚本）：
  GA4 于 2026-09-08 弃用后，全站事件仍发往一个已下线的接收方（gtag），等于零采集；
  且 engagement-tracking.js 从未被任何页面引用（0 页），categories/tags/hub/tools
  共 33 个部署页连 analytics-loader（百度统计页面级）都没有 —— 这些页在统计里根本不存在。
  手改 331 个文件不可维护，故做成幂等脚本：每次跑都把「脚本契约」对齐，可重跑、可核验。

脚本契约（每个部署页 body 末尾，defer 顺序固定）：
  qa-config.js → search.js → analytics-loader.js → main.js → content-protect.js
其中 analytics-loader.js 现在同时是「统计装载 + 全站统一事件层 window.aihrTrack」，
缺它 = 该页既无页面级统计、也无任何事件上报。

用法：
  python3 scripts/inject_analytics.py            # 实际写入
  python3 scripts/inject_analytics.py --dry-run  # 只看会改哪些页
"""
from __future__ import annotations

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITEMAP = os.path.join(BASE_DIR, "sitemap.xml")

# 缺失即注入；(标签, 匹配串)
# 只补「页面级统计装载 + main.js」两个已存在的全站脚本，不新增第三个 script 标签：
# 事件层已并入 analytics-loader.js，二跳分类已并入 main.js，全站改动面压到 33 个缺脚本页。
REQUIRED = [
    ("analytics-loader", '<script src="/assets/js/analytics-loader.js" defer></script>'),
    ("assets/js/main.js", '<script src="/assets/js/main.js" defer></script>'),
]

MAIN_RE = re.compile(r'[ \t]*<script src="/assets/js/main\.js"[^>]*>\s*(?:</script>)?[ \t]*\n')
BODY_END_RE = re.compile(r"</body>", re.I)


def deployed_pages():
    """sitemap 里的线上页面 → 本地相对路径（只处理真实存在的文件）。"""
    if not os.path.exists(SITEMAP):
        print("[FATAL] sitemap.xml 不存在，无法确定部署页集合", file=sys.stderr)
        sys.exit(2)
    xml = open(SITEMAP, encoding="utf-8").read()
    out = []
    for loc in re.findall(r"<loc>(.*?)</loc>", xml, re.S):
        path = re.sub(r"^https?://[^/]+", "", loc.strip()).lstrip("/")
        if not path:
            path = "index.html"
        if path.endswith("/"):
            path += "index.html"
        if os.path.exists(os.path.join(BASE_DIR, path)):
            out.append(path)
    return sorted(set(out))


def inject(html: str, tag: str) -> str:
    """把 tag 插到 main.js 之前（保证执行顺序），没有 main.js 则插到 </body> 前。"""
    m = MAIN_RE.search(html)
    if m:
        indent = "  " if m.group(0).startswith("  ") else ""
        return html[: m.start()] + indent + tag + "\n" + html[m.start():]
    m2 = BODY_END_RE.search(html)
    if m2:
        return html[: m2.start()] + "  " + tag + "\n" + html[m2.start():]
    return html + "\n" + tag + "\n"


def process(path: str, dry: bool):
    full = os.path.join(BASE_DIR, path)
    html = open(full, encoding="utf-8").read()
    orig = html
    added = []
    for name, tag in REQUIRED:
        if name in html:
            continue
        html = inject(html, tag)
        added.append(name)
    if not added:
        return None
    if not dry:
        with open(full, "w", encoding="utf-8") as f:
            f.write(html)
    return added


def main():
    dry = "--dry-run" in sys.argv
    pages = deployed_pages()
    changed = []
    for p in pages:
        r = process(p, dry)
        if r:
            changed.append((p, r))
    print(f"部署页总数: {len(pages)} | 需变更: {len(changed)} | dry-run={dry}")
    for p, r in changed[:20]:
        print(f"  + {p}  ← {','.join(r)}")
    if len(changed) > 20:
        print(f"  ... 另 {len(changed) - 20} 个")
    # 覆盖率核验
    missing = {name: [] for name, _ in REQUIRED}
    for p in pages:
        html = open(os.path.join(BASE_DIR, p), encoding="utf-8").read()
        for name, _ in REQUIRED:
            if name not in html:
                missing[name].append(p)
    for name, _ in REQUIRED:
        print(f"核验 · 缺 {name}: {len(missing[name])}")
    if dry:
        return
    with open(os.path.join(BASE_DIR, ".analytics_injected_files.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(p for p, _ in changed) + "\n")


if __name__ == "__main__":
    main()
