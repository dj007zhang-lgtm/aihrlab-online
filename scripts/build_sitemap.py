#!/usr/bin/env python3
"""
build_sitemap.py — 重建 aihrlab.online 的 sitemap.xml

发现全部真实可收录页面并生成符合 sitemap.org 规范的 XML：
  - articles/*.html         (文章正文)
  - tags/*.html             (P1 标签/归档页)
  - 根目录着陆页 (*.html)     (index/about/articles/resources 等)
排除：404、搜索引擎验证桩页、seo-monitor、_backup、未跟踪备份图。

用法:
  python3 scripts/build_sitemap.py            # 重建 sitemap.xml
  python3 scripts/build_sitemap.py --dry-run  # 仅打印将收录的 URL 数，不写文件

接线: 由 scripts/publish.py 在每次发布前调用，保证 sitemap 与站点同步。
"""
import os
import re
import sys
import subprocess
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")
HOST = "https://www.aihrlab.online"

# 根目录需排除的桩/验证页（不进 sitemap）
ROOT_EXCLUDE = {
    "404.html",
    "seo-monitor.html",
}
# 文件名模式排除（验证/备份）
NAME_EXCLUDE_PREFIX = ("baidu_verify", "google", "yandex_verify")
NAME_EXCLUDE_SUFFIX = ("_verify.html",)


def is_excluded(name: str) -> bool:
    low = name.lower()
    if name in ROOT_EXCLUDE:
        return True
    for p in NAME_EXCLUDE_PREFIX:
        if low.startswith(p):
            return True
    for s in NAME_EXCLUDE_SUFFIX:
        if low.endswith(s):
            return True
    return False


def is_redirect_page(relpath: str) -> bool:
    """检测页面是否为 meta-refresh 重定向桩页（不应进 sitemap）。"""
    p = os.path.join(ROOT, relpath)
    try:
        with open(p, "r", encoding="utf-8") as f:
            head = f.read(4096)
    except Exception:
        return False
    return bool(re.search(r'<meta[^>]*http-equiv\s*=\s*["\']?refresh["\']?', head, re.I))


def lastmod_for(relpath: str) -> str:
    """优先用 git 最近提交日期，失败回退到文件 mtime，再回退今天。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", relpath],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    try:
        ts = os.path.getmtime(os.path.join(ROOT, relpath))
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return datetime.date.today().strftime("%Y-%m-%d")


def collect() -> list:
    """返回 [(url, lastmod), ...] 按 url 排序。"""
    entries = []

    # 1) 根目录着陆页
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".html"):
            continue
        if is_excluded(fn) or is_redirect_page(fn):
            continue
        rel = fn
        entries.append((f"{HOST}/{fn}", lastmod_for(rel)))

    # 2) 文章
    art_dir = os.path.join(ROOT, "articles")
    if os.path.isdir(art_dir):
        for fn in sorted(os.listdir(art_dir)):
            if not fn.endswith(".html"):
                continue
            rel = f"articles/{fn}"
            if fn.startswith("_") or "stub" in fn.lower() or is_redirect_page(rel):
                continue
            entries.append((f"{HOST}/articles/{fn}", lastmod_for(rel)))

    # 3) 标签/归档页
    tags_dir = os.path.join(ROOT, "tags")
    if os.path.isdir(tags_dir):
        for fn in sorted(os.listdir(tags_dir)):
            if not fn.endswith(".html"):
                continue
            rel = f"tags/{fn}"
            entries.append((f"{HOST}/tags/{fn}", lastmod_for(rel)))

    # 4) 内容子目录（资源库/深度手册/测评/枢纽/词典/分类等）
    #    与整站「学→用→测→查→串」分层链路对齐，均为一等公民内容页。
    #    不扫 assets/（静态资源目录，含即将废弃的旧 DQ 重定向页）。
    EXTRA_DIRS = [
        "resources",   # 用：资源库
        "products",    # 深度手册（资源库子类）
        "tools",       # 测：测评聚合
        "assessments", # 测：测评详情
        "bridge",      # 策展
        "hub",         # 串：主题枢纽
        "glossary",    # 查：术语词典
        "categories",  # 文章分类聚合
        "compare",     # 横向对比专题
    ]
    for d in EXTRA_DIRS:
        sub = os.path.join(ROOT, d)
        if not os.path.isdir(sub):
            continue
        for fn in sorted(os.listdir(sub)):
            if not fn.endswith(".html"):
                continue
            rel = f"{d}/{fn}"
            if fn.startswith("_") or "stub" in fn.lower() or is_redirect_page(rel):
                continue
            entries.append((f"{HOST}/{d}/{fn}", lastmod_for(rel)))

    # 去重并排序（URL 稳定顺序，便于 diff）
    seen = {}
    for url, lm in entries:
        if url not in seen:
            seen[url] = lm
    return sorted(seen.items())


def render(entries: list) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9',
        '        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">',
    ]
    for url, lm in entries:
        lines.append("    <url>")
        lines.append(f"        <loc>{url}</loc>")
        lines.append(f"        <lastmod>{lm}</lastmod>")
        lines.append("    </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def main():
    dry = "--dry-run" in sys.argv
    entries = collect()
    if dry:
        print(f"[dry-run] 将收录 {len(entries)} 个 URL")
        for url, lm in entries[:10]:
            print(f"  {lm}  {url}")
        if len(entries) > 10:
            print(f"  ... 其余 {len(entries)-10} 个")
        return
    xml = render(entries)
    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"✅ sitemap.xml 已重建: {len(entries)} 个 URL → {SITEMAP_PATH}")


if __name__ == "__main__":
    main()
