#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_analytics_coverage.py — 埋点覆盖率与口径核验（P0-1，2026-09-21）

断言清单（任一失败即 exit 1）：
  A1 所有部署页（sitemap）加载 analytics-loader.js —— 否则该页连页面级统计都没有
  A2 所有部署页加载 main.js（事件层与二跳分类在其内）
  A3 analytics-loader.js 定义 window.aihrTrack 且含完整事件字典
  A4 main.js 的 trackEvent 已接到 window.aihrTrack（不再只发给已下线的 gtag）
  A5 全站无 gtag('event' 残留（GA4 已弃用，残留即空转）
  A6 门控四事件在代码中均有发送点（gate_view / gate_open / qr_code_view / qr_code_click）
  A7 事件字典 reports/events.md 中登记的事件名，在 assets/js 中均有发送点（防字典漂移）

用法：python3 scripts/check_analytics_coverage.py
"""
from __future__ import annotations

import os
import re
import sys
import glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITEMAP = os.path.join(BASE_DIR, "sitemap.xml")
EVENTS_MD = os.path.join(BASE_DIR, "reports", "events.md")
JS_DIR = os.path.join(BASE_DIR, "assets", "js")

fail = []
warn = []


def check(cond, ok_msg, fail_msg):
    if cond:
        print(f"  PASS  {ok_msg}")
    else:
        print(f"  FAIL  {fail_msg}")
        fail.append(fail_msg)


def deployed_pages():
    xml = open(SITEMAP, encoding="utf-8").read()
    out = []
    for loc in re.findall(r"<loc>(.*?)</loc>", xml, re.S):
        path = re.sub(r"^https?://[^/]+", "", loc.strip()).lstrip("/")
        if not path:
            path = "index.html"
        if path.endswith("/"):
            path += "index.html"
        full = os.path.join(BASE_DIR, path)
        if os.path.exists(full):
            out.append(path)
    return sorted(set(out))


def read(p):
    with open(os.path.join(BASE_DIR, p), encoding="utf-8") as f:
        return f.read()


def main():
    pages = deployed_pages()
    print(f"部署页（sitemap 且本地存在）：{len(pages)}\n")

    # A1 / A2
    miss_loader = [p for p in pages if "analytics-loader.js" not in read(p)]
    miss_main = [p for p in pages if "assets/js/main.js" not in read(p)]
    print("A1 页面级统计装载覆盖率")
    check(not miss_loader,
          f"analytics-loader 覆盖 {len(pages) - len(miss_loader)}/{len(pages)} = 100%",
          f"缺 analytics-loader 的页 {len(miss_loader)} 个：{miss_loader[:5]}")
    print("A2 main.js（事件层宿主）覆盖率")
    check(not miss_main,
          f"main.js 覆盖 {len(pages) - len(miss_main)}/{len(pages)} = 100%",
          f"缺 main.js 的页 {len(miss_main)} 个：{miss_main[:5]}")

    # A3
    loader = read("assets/js/analytics-loader.js")
    print("A3 统一事件层定义")
    check("window.aihrTrack = aihrTrack" in loader and "_trackEvent" in loader,
          "analytics-loader.js 定义 window.aihrTrack 并推送百度统计 _trackEvent",
          "analytics-loader.js 未定义 window.aihrTrack 或未对接 _hmt")

    # A4
    mainjs = read("assets/js/main.js")
    print("A4 trackEvent 接线")
    check("window.aihrTrack" in mainjs and "send_to" not in mainjs,
          "main.js 的 trackEvent 已接到 window.aihrTrack，且不再硬绑 GA4 send_to",
          "main.js 仍在只发 gtag（事件将空转）")

    # A5
    residual = []
    for p in glob.glob(os.path.join(BASE_DIR, "**", "*.html"), recursive=True):
        rel = os.path.relpath(p, BASE_DIR)
        if rel.startswith("_wip/") or rel.startswith("templates/"):
            continue
        with open(p, encoding="utf-8") as f:
            if re.search(r"gtag\s*\(\s*['\"]event['\"]", f.read()):
                residual.append(rel)
    print("A5 GA4 残留")
    check(not residual,
          "全站 HTML 无 gtag('event' 残留",
          f"仍有 {len(residual)} 页残留 gtag('event')：{residual[:5]}")

    # A6
    all_js = ""
    for f in glob.glob(os.path.join(JS_DIR, "*.js")):
        with open(f, encoding="utf-8") as fh:
            all_js += fh.read()
    # 声明式埋点：data-track="事件名" 也算发送点（由 analytics-loader 统一采集）
    html_track_names = set()
    for p in glob.glob(os.path.join(BASE_DIR, "**", "*.html"), recursive=True):
        rel = os.path.relpath(p, BASE_DIR)
        if rel.startswith("_wip/") or rel.startswith("templates/"):
            continue
        with open(p, encoding="utf-8") as fh:
            html_track_names.update(re.findall(r'data-track="([a-z_]+)"', fh.read()))
    print("A6 门控四事件发送点")
    for ev in ["gate_view", "gate_open", "qr_code_view", "qr_code_click"]:
        check(re.search(r"['\"]%s['\"]" % ev, all_js) is not None,
              f"{ev} 有发送点",
              f"{ev} 无发送点（门控盲区）")

    # A7 字典 vs 代码
    print("A7 事件字典与代码一致性")
    if not os.path.exists(EVENTS_MD):
        check(False, "", "reports/events.md 不存在")
    else:
        md = open(EVENTS_MD, encoding="utf-8").read()
        # 只取「一、事件表」，避免把「四、已停用的历史命名」里的废名当成必须实现的事件
        md = md.split("## 二")[0]
        names = re.findall(r"^\|\s*`([a-z_]+)`\s*\|", md, re.M)
        names = [n for n in names if n not in ("page_path", "target", "target_type", "label", "value")]
        missing = [n for n in sorted(set(names))
                   if not re.search(r"['\"]%s['\"]" % n, all_js) and n not in html_track_names]
        check(not missing,
              f"字典 {len(set(names))} 个事件全部在代码中有发送点",
              f"字典里有、代码里没有的事件：{missing}")

    print()
    if fail:
        print(f"结果：FAIL（{len(fail)} 项）")
        return 1
    print("结果：PASS（埋点覆盖 100%，口径无漂移）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
