#!/usr/bin/env python3
"""基线冻结器 · AIHR 站点架构 P0

用途：把站点结构性现状（页面分布 / 导航一致性 / 孤儿页 / 索引真源 / sitemap 覆盖）
一次性量出来，写入 reports/baseline-<date>.json，供后续每个阶段 diff 对照。

纪律：
  - 只读脚本，绝不修改任何页面。
  - 可重复运行；同一天重复运行应产出近似相同结果（除时间戳）。
  - 任何阶段验收时，先跑本脚本，与本基线 diff，再判定是否引入回归。

用法：
  python3 scripts/freeze_baseline.py            # 写入 reports/baseline-<YYYY-MM-DD>.json
  python3 scripts/freeze_baseline.py --diff X   # 与既有基线 X 比对
"""
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL_NAV = [
    ("/index.html", "首页"),
    ("/articles/index.html", "文章"),
    ("/resources/index.html", "资源库"),
    ("/tools/index.html", "测评"),
    ("/brief/index.html", "策展"),
    ("/about.html", "关于"),
]
# 非读者页面：不参与导航一致性判定（性质：验证桩页/内部运营页/构建模板/静态资源/未发布草稿）
NAV_EXEMPT = (
    "404.html", "seo-monitor.html",
    "baidu_verify_codeva-e9RlNB7KYx.html", "googlecbc66c5d343f6aed.html",
    "templates/", "assets/", "projects/",
)
NAV_RE = re.compile(r'<nav class="site-nav"[^>]*>([\s\S]*?)</nav>')
HREF_RE = re.compile(r'<a\s+[^>]*href="([^"]+)"')
DIRS = ["articles", "hub", "tools", "assessments", "products", "resources",
        "brief", "bridge", "ask", "glossary", "compare", "categories", "tags", "projects"]


def all_html():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for f in files:
            if f.endswith(".html"):
                out.append(os.path.relpath(os.path.join(base, f), ROOT))
    return sorted(out)


def is_indexable(rel):
    t = open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read()
    m = re.search(r'<meta\s+name="robots"\s+content="([^"]+)"', t)
    return not (m and "noindex" in m.group(1).lower())


def is_redirect_shell(rel):
    t = open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read()
    return bool(re.search(r'http-equiv=["\']refresh["\']', t, re.I))


def main():
    files = all_html()
    nav_dev = []
    nav_present = 0
    for rel in files:
        # 跳转壳（noindex + refresh）瞬间跳走，不需要导航，也不参与一致性判定
        if is_redirect_shell(rel) or rel.startswith(NAV_EXEMPT):
            continue
        # 必须全文扫描：articles/index.html 的导航在 42KB 之后，截断扫描会误报
        t = open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read()
        m = NAV_RE.search(t)
        if not m:
            # 独立单文件工具页允许用自包含入口条（site-nav-mini）替代全局页头
            if "site-nav-mini" in t:
                nav_present += 1
                continue
            nav_dev.append((rel, "NO_NAV"))
            continue
        nav_present += 1
        items = re.findall(r'<a\s+[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', m.group(1))
        got = [(h, x.strip()) for h, x in items if x.strip()]
        if len(got) != len(CANONICAL_NAV) or any(
                a[0] != b[0] or a[1] != b[1] for a, b in zip(got, CANONICAL_NAV)):
            nav_dev.append((rel, "DEVIATES"))

    targets = set()
    for rel in files:
        t = open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read()
        for h in HREF_RE.findall(t):
            h = h.split("#")[0].split("?")[0]
            if h.startswith("/"):
                targets.add(h.lstrip("/"))
            elif not h.startswith(("http", "mailto", "javascript", "tel")):
                targets.add(os.path.normpath(os.path.join(os.path.dirname(rel), h)))

    # 孤儿判定纪律：跳转壳（noindex + meta refresh + canonical）是刻意保留的 URL 合并壳，
    # 不是孤儿，单独计数。把二者混在一起会得出「批量下线」的错误结论（口径铁律：指标须与性质有因果）。
    raw_orphans = [f for f in files
                   if f not in targets and not f.endswith("index.html")
                   and f not in ("404.html",) and not f.startswith(NAV_EXEMPT)]
    shell_orphans = [f for f in raw_orphans if is_redirect_shell(f)]
    orphans = [f for f in raw_orphans if f not in shell_orphans]

    idx = json.load(open(os.path.join(ROOT, "assets/js/article-index.json"), encoding="utf-8"))
    sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8", errors="ignore").read()
    sm_urls = re.findall(r"<loc>(.*?)</loc>", sm)
    kb_path = os.path.join(ROOT, "assets/qa/scf/kb.json")
    kb = json.load(open(kb_path, encoding="utf-8")) if os.path.exists(kb_path) else {}

    data = {
        "date": str(date.today()),
        "files_total": len(files),
        "files_indexable": sum(1 for f in files if is_indexable(f)),
        "files_noindex": sum(1 for f in files if not is_indexable(f)),
        "redirect_shells": sum(1 for f in files if is_redirect_shell(f)),
        "dirs": {d: sum(1 for f in files if f.startswith(d + "/")) for d in DIRS},
        "root_files": sorted(f for f in files if "/" not in f),
        "nav_pages": nav_present,
        "nav_deviations": nav_dev[:40],
        "nav_deviation_count": len(nav_dev),
        "orphan_count": len(orphans),
        "orphans_sample": orphans[:40],
        "shell_orphan_count": len(shell_orphans),
        "article_index_count": len(idx),
        "sitemap_url_count": len(sm_urls),
        "brief_in_sitemap": sum(1 for u in sm_urls if "/brief/" in u),
        "kb_articles_indexed": kb.get("articles_indexed"),
    }

    if "--diff" in sys.argv:
        prev = json.load(open(sys.argv[sys.argv.index("--diff") + 1], encoding="utf-8"))
        print("=== 与基线 %s 的差异 ===" % prev["date"])
        for k in prev:
            if isinstance(prev[k], (int, str)) and k != "date" and prev[k] != data.get(k):
                print("  %-24s %s -> %s" % (k, prev[k], data.get(k)))
        return

    out = os.path.join(ROOT, "reports", "baseline-%s.json" % data["date"])
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("基线已写入: reports/baseline-%s.json" % data["date"])
    for k, v in data.items():
        if k in ("nav_deviations", "orphans_sample", "root_files", "dirs"):
            continue
        print("  %-24s %s" % (k, v))
    print("  目录分布:", data["dirs"])


if __name__ == "__main__":
    main()
