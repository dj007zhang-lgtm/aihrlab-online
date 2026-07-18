#!/usr/bin/env python3
"""
内链完整性扫描（主理人质量门第1关的可复用引擎）

作用：
  - 扫描全站所有 .html 文件中的内部链接（href="/..."、JSON-LD 的 url/item 字段）
  - 解析为本地路径（处理中文文件名 URL 编码、目录尾斜杠）
  - 找出所有指向不存在文件的「断裂链接」——即 Google/Bing 会返回 404 的源头
  - 找出 sitemap.xml 中指向不存在文件的「孤儿 URL」

用法：
  python3 scripts/check_broken_links.py            # 打印扫描报告 + 退出码(0=无断裂,1=有断裂)
  python3 scripts/check_broken_links.py --json     # 输出 JSON（供自动化/质量门调用）
  from check_broken_links import find_broken_links, find_sitemap_orphans
"""

import os
import re
import sys
import json
import urllib.parse

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 已知合法的「软目标」——不检查存在性
# 1) 重定向桩页（resources 等，运行时 301/refresh 到真实目录）
# 2) 站外链接（http/https）由调用方跳过，这里只管内部绝对路径
KNOWN_REDIRECT_DIRS = {"/resources/", "/resources"}


def _resolve_internal_path(href, site_root):
    """把内部绝对链接解析为本地文件路径；返回 (path_or_None, is_internal)

    - 站外/http/锚点/mailto → (None, False) 跳过
    - 内部路径 → 解码 + 处理目录斜杠 → 返回本地绝对路径
    """
    if not href:
        return None, False
    href = href.strip()
    # 跳过非内部链接
    if href.startswith("http://") or href.startswith("https://"):
        return None, False
    if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
        return None, False
    if href.startswith("//"):
        return None, False
    # 只处理以 / 开头的站点根相对路径
    if not href.startswith("/"):
        return None, False
    # 去掉查询串/锚点
    clean = href.split("#")[0].split("?")[0]
    if clean in KNOWN_REDIRECT_DIRS:
        return None, False
    # 解码（处理中文文件名 URL 编码）
    decoded = urllib.parse.unquote(clean)
    local = os.path.join(site_root, decoded.lstrip("/"))
    # 目录尾斜杠 → index.html
    if decoded.endswith("/"):
        local = os.path.join(local, "index.html")
    return local, True


def _collect_internal_hrefs(html_content, site_root):
    """从一段 HTML 中抽取所有内部链接目标（href + JSON-LD url/item）"""
    targets = set()
    # 普通 href
    for m in re.findall(r'href=["\']([^"\']+)["\']', html_content):
        targets.add(m)
    # JSON-LD 中的 url / item 字段
    for m in re.findall(r'"(?:url|item)"\s*:\s*"([^"]+)"', html_content):
        targets.add(m)
    return targets


def find_broken_links(site_root=SITE_ROOT):
    """返回断裂内链列表：[{'source', 'href', 'resolved'}]"""
    broken = []
    for root, dirs, files in os.walk(site_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules" and d != "templates"]
        for fn in files:
            if not fn.endswith(".html"):
                continue
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception:
                continue
            rel = os.path.relpath(fpath, site_root)
            for href in _collect_internal_hrefs(content, site_root):
                local, is_internal = _resolve_internal_path(href, site_root)
                if not is_internal:
                    continue
                if not os.path.exists(local):
                    broken.append({
                        "source": rel,
                        "href": href,
                        "resolved": os.path.relpath(local, site_root),
                    })
    return broken


def find_sitemap_orphans(site_root=SITE_ROOT):
    """返回 sitemap.xml 中指向不存在文件的孤儿 URL 列表"""
    sm_path = os.path.join(site_root, "sitemap.xml")
    if not os.path.exists(sm_path):
        return []
    with open(sm_path, "r", encoding="utf-8", errors="ignore") as fh:
        sm = fh.read()
    orphans = []
    for url in re.findall(r"<loc>(.*?)</loc>", sm, re.S):
        url = url.strip()
        if not url.startswith("https://www.aihrlab.online/"):
            continue
        path = url.replace("https://www.aihrlab.online/", "")
        # 目录 → index.html
        if path.endswith("/"):
            path = path + "index.html"
        local = os.path.join(site_root, path)
        if not os.path.exists(local):
            orphans.append(url)
    return orphans


def main():
    as_json = "--json" in sys.argv
    broken = find_broken_links(SITE_ROOT)
    orphans = find_sitemap_orphans(SITE_ROOT)

    if as_json:
        print(json.dumps({
            "broken_links": broken,
            "sitemap_orphans": orphans,
            "broken_count": len(broken),
            "orphan_count": len(orphans),
        }, ensure_ascii=False, indent=2))
        sys.exit(1 if (broken or orphans) else 0)

    print("=" * 60)
    print("  内链完整性扫描 (check_broken_links)")
    print("=" * 60)
    if broken:
        print(f"\n❌ 断裂内部链接: {len(broken)} 处\n")
        # 按 source 分组
        by_src = {}
        for b in broken:
            by_src.setdefault(b["source"], []).append(b)
        for src, items in sorted(by_src.items()):
            print(f"  📄 {src}")
            for it in items:
                print(f"     → {it['href']}  (解析为 {it['resolved']}，不存在)")
    else:
        print("\n✅ 全站无断裂内部链接")

    if orphans:
        print(f"\n⚠️ sitemap 孤儿 URL: {len(orphans)} 个（指向不存在文件）\n")
        for o in orphans:
            print(f"  → {o}")
    else:
        print("✅ sitemap 无孤儿 URL")

    total = len(broken) + len(orphans)
    print("\n" + "=" * 60)
    print(f"  结论: {'🔴 发现 ' + str(total) + ' 处问题' if total else '🟢 全部健康'}")
    print("=" * 60)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
