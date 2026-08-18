#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T0 调性门 · 机械自检（taste_gate.py）
独立可机检层，配合 reports/taste-gate.md 的人检清单。
三道门：T1 标题调性 / T2 开篇 hook / T3 图注承接。

用法:
  python3 scripts/taste_gate.py articles/xxx.html
  python3 scripts/taste_gate.py --all                # 扫 articles/
  python3 scripts/taste_gate.py --json articles/xxx.html

返回非 0 表示存在 FAIL（供 CI / publish 拦截）。
注：本脚本只做机械代理检查（调性违禁词 / 结构信号），最终调性判断仍由人 + 读者视角四环节诊断卡完成。
"""
import os
import sys
import re
import json
import glob

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES = os.path.join(SITE_ROOT, "articles")

# 标题级违禁调性词（FAIL）
BANNED_TITLE = ["终极考卷", "暴击", "崩塌", "末日", "交代后事",
                "你不够AI", "你连一块砖", "每个人都得重新标价", "算力怪兽"]
# 开篇 hook 级末日/恐慌词（FAIL）
DOOM_HOOK = ["交代后事", "末日", "崩", "慌", "凉透", "暴击"]


def extract(html):
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    subtitle = re.search(r'class="article-subtitle"[^>]*>(.*?)</p>', html, re.S)
    capsule = re.search(r'class="geo-answer-capsule"', html)
    figures = re.findall(r"<figure\b.*?</figure>", html, re.S)
    return {
        "title": title.group(1).strip() if title else "",
        "h1": re.sub(r"<.*?>", "", h1.group(1)).strip() if h1 else "",
        "subtitle": re.sub(r"<.*?>", "", subtitle.group(1)).strip() if subtitle else "",
        "has_capsule": bool(capsule),
        "figures": figures,
    }


def gate_title(d):
    reasons, warns = [], []
    t = d["title"] or d["h1"]
    if not t:
        reasons.append("无标题")
        return reasons, warns
    n = len(t)
    if n > 60:
        reasons.append(f"标题过长({n}字>60)")
    elif n < 15:
        warns.append(f"标题偏短({n}字<15)")
    if t.endswith("？") or t.endswith("?"):
        warns.append("标题以问号结尾(恐慌/悬念腔，需确认有由头)")
    for w in BANNED_TITLE:
        if w in t:
            reasons.append(f"标题含违禁调性词「{w}」")
    # R-16：标题不得含品牌后缀（| AIHR数智引擎）
    if "| AIHR数智引擎" in t or "｜AIHR数智引擎" in t:
        reasons.append("标题含品牌后缀（R-16）")
    # R-17：title 必须与 h1 一致
    if d["title"] and d["h1"] and d["title"] != d["h1"]:
        reasons.append(f"title ≠ h1（R-17）: title='{d['title']}' h1='{d['h1']}'")
    return reasons, warns


def gate_hook(d):
    reasons, warns = [], []
    text = d["subtitle"]
    if not text and not d["has_capsule"]:
        reasons.append("开篇无 hook（缺 subtitle 且缺 geo-answer-capsule）")
        return reasons, warns
    if len(text) < 30 and not d["has_capsule"]:
        warns.append(f"subtitle 过短({len(text)}字)，建议≥30字给由头")
    for w in DOOM_HOOK:
        if w in text:
            reasons.append(f"开篇 hook 含末日/恐慌词「{w}」")
    return reasons, warns


def gate_caption(d):
    reasons, warns = [], []
    for i, fig in enumerate(d["figures"]):
        is_banner = "article-banner" in fig
        has_cap = "<figcaption" in fig
        if not has_cap:
            if is_banner:
                warns.append(f"figure#{i} 为 banner 但无 figcaption（建议补图注承接）")
            else:
                reasons.append(f"figure#{i} 含图无 figcaption（图文承接断）")
    return reasons, warns


# R-15：h2/h3 不得自标数据出处（据X/公开X/一手X/权威X/可信X/核验X/数据来源X）
# 专业作者让底部参考信源块自己说话，不在节标题里贴"据X源"标签。
SELF_LABEL_RE = re.compile(
    r'<h[23][^>]*>[^<]*[（(][^）)]*(?:据|公开|一手|权威|可信|核验|数据来源)[^）)]*[）)]'
)


def gate_self_label(path):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    hits = SELF_LABEL_RE.findall(html)
    reasons = []
    for h in hits:
        reasons.append(f"h2/h3 自标数据出处（R-15）: {h[:80]}")
    return reasons, []


def check_file(path):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    d = extract(html)
    r1, w1 = gate_title(d)
    r2, w2 = gate_hook(d)
    r3, w3 = gate_caption(d)
    r4, w4 = gate_self_label(path)
    fails = r1 + r2 + r3 + r4
    warns = w1 + w2 + w3 + w4
    return {
        "file": os.path.relpath(path, SITE_ROOT),
        "fails": fails,
        "warns": warns,
        "pass": len(fails) == 0,
    }


def main():
    files = []
    if "--all" in sys.argv:
        files = sorted(glob.glob(os.path.join(ARTICLES, "*.html")))
    else:
        for a in sys.argv[1:]:
            if a.startswith("--"):
                continue
            files.append(a if os.path.isabs(a) else os.path.join(SITE_ROOT, a))
    if not files:
        print("用法: taste_gate.py <file> | --all")
        sys.exit(2)
    results = [check_file(p) for p in files]
    total_fail = 0
    for r in results:
        tag = "PASS" if r["pass"] else "FAIL"
        print(f"[{tag}] {r['file']}")
        for f in r["fails"]:
            print(f"   x {f}")
        for w in r["warns"]:
            print(f"   ! {w}")
        if not r["pass"]:
            total_fail += 1
    print(f"\n合计: {len(results)} 篇, FAIL {total_fail} 篇")
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    sys.exit(1 if total_fail else 0)


if __name__ == "__main__":
    main()
