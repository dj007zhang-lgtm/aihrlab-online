#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_related_reading.py — 全站「相关阅读」卡片化迁移

将纯文本 related-reading 块：
  <li><a href="URL">标题</a></li>
升级为 .rr-* 卡片组件：
  <li class="rr-feature"><a href="URL"><span class="rr-title">标题</span><span class="rr-desc">目标页 meta description</span></a></li>
  <li><a href="URL"><span class="rr-title">标题</span><span class="rr-desc">...</span></a></li>

纪律：
- rr-title = 原 <a> 可见文本（即文章真实标题），不改动、零虚构。
- rr-desc = 目标页 <meta name="description">，零虚构；读不到则省略该 span（优雅降级）。
- 首条 <li> 标记 li.rr-feature（全宽高亮，对应设计意图）。
- 保留原 href（无 404）、保留原缩进（无噪声 diff）。
- 已升级块（含 rr-title）整体跳过（幂等）。
- 仅处理「相关阅读」语义区块（class="related-reading" / article-related / <h3>相关阅读</h3>），不触碰 TOC 目录。

用法：
  python3 scripts/migrate_related_reading.py --dry-run            # 全站侦察报告
  python3 scripts/migrate_related_reading.py --dry-run articles/foo.html   # 单文件
  python3 scripts/migrate_related_reading.py                       # 全站执行
  python3 scripts/migrate_related_reading.py articles/foo.html     # 单文件执行
"""
import os
import re
import sys
import html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../site-migrated
SECTIONS = ["articles", "resources", "tools", "hub"]
DESC_CAP = 44  # 中文描述截断上限（含省略号后），零虚构（取真实描述前缀）

# 简单 li：<li><a href="U">T</a></li>（单行，无 rr-title）
LI_RE = re.compile(r'^(\s*)<li>(<a href="([^"]+)">(.*?)</a>)</li>\s*$')
META_RE = re.compile(r'<meta\s+name="description"\s+content="(.*?)">', re.IGNORECASE | re.DOTALL)
# 仅匹配真正的「相关阅读」容器，绝不命中 <style> 里的 CSS 注释（/* ---- 相关阅读 ---- */）。
# 触发器 = <section class="related-reading"> | <aside class="article-related"> | <h3/h4>相关阅读</h3/h4>
TRIGGER_RE = re.compile(
    r'<section[^>]*class="related-reading"|<aside[^>]*class="article-related"|<h[34][^>]*>相关阅读</h[34]>'
)


def get_meta_desc(href, current_file):
    """解析目标页 meta description，零虚构；读不到返回 None。"""
    if not href:
        return None
    if href.startswith(("http://", "https://", "#", "mailto:")):
        return None
    # 解析本地路径
    if href.startswith("/"):
        rel = href.lstrip("/")
    else:
        # 相对路径：相对当前文件目录
        rel = os.path.normpath(os.path.join(os.path.dirname(current_file), href))
    target = os.path.join(ROOT, rel)
    # 目录式链接（如 /tools/disc-test/ 或 /tools/mbti）回退到 index.html / .html
    candidates = [target]
    if target.endswith("/") or os.path.isdir(target):
        candidates.append(os.path.join(target, "index.html"))
    if not target.endswith("/"):
        candidates.append(target + ".html")
        candidates.append(os.path.join(target + ".html", "index.html") if False else target + "/index.html")
    resolved = None
    for c in candidates:
        if os.path.isfile(c):
            resolved = c
            break
    if resolved is None:
        return None
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        return None
    m = META_RE.search(txt)
    if not m:
        return None
    desc = m.group(1).strip()
    # HTML 实体保持原样（浏览器渲染）；截断到 DESC_CAP
    if len(desc) > DESC_CAP:
        desc = desc[:DESC_CAP] + "…"
    return desc or None


def find_related_blocks(lines):
    """返回 [(start_idx, end_idx_ul_close)] 仅含相关阅读区块。"""
    blocks = []
    n = len(lines)
    i = 0
    while i < n:
        if TRIGGER_RE.search(lines[i]):
            # 向前找到该区块的 </ul> 或 </ol>（列表收尾即止）
            j = i
            while j < n and "</ul>" not in lines[j] and "</ol>" not in lines[j]:
                j += 1
            if j < n:
                blocks.append((i, j))
                i = j + 1
                continue
        i += 1
    return blocks


def transform_file(path, dry_run=True):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks = find_related_blocks(lines)
    if not blocks:
        return {"skipped_no_block": True}

    file_changed = False
    li_transformed = 0
    li_skipped_upgraded = 0
    desc_missing = 0
    anomalies = []

    out_lines = list(lines)
    # 从后往前处理，避免索引偏移
    for (bstart, bend) in reversed(blocks):
        block_text = "".join(lines[bstart : bend + 1])
        if "rr-title" in block_text:
            # 已升级区块：跳过（幂等）
            li_skipped_upgraded += block_text.count("<li")
            continue
        # 在区块内逐行转换简单 li
        first_in_block = True
        new_block = []
        for idx in range(bstart, bend + 1):
            line = lines[idx]
            m = LI_RE.match(line.rstrip("\n"))
            if m and "</a></li>" in line and "rr-title" not in line:
                indent, _a, href, title = m.groups()
                title = title.strip()
                if not title:
                    new_block.append(line)
                    continue
                desc = get_meta_desc(href, path)
                # HTML 规范化转义：先 unescape 消除已有实体，再 escape 防注入/非法字符
                safe_title = html.escape(html.unescape(title))
                safe_desc = html.escape(html.unescape(desc)) if desc else ""
                desc_span = f'<span class="rr-desc">{safe_desc}</span>' if desc else ""
                if desc is None:
                    desc_missing += 1
                feature_attr = ' class="rr-feature"' if first_in_block else ""
                first_in_block = False
                new_line = (
                    f'{indent}<li{feature_attr}><a href="{href}">'
                    f'<span class="rr-title">{safe_title}</span>{desc_span}</a></li>\n'
                )
                new_block.append(new_line)
                li_transformed += 1
                file_changed = True
            else:
                new_block.append(line)
        # 替换
        out_lines[bstart : bend + 1] = new_block

    if file_changed and not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)

    return {
        "changed": file_changed,
        "li_transformed": li_transformed,
        "li_skipped_upgraded": li_skipped_upgraded,
        "desc_missing": desc_missing,
        "anomalies": anomalies,
    }


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    paths = [a for a in args if not a.startswith("--")]

    if not paths:
        paths = []
        for sec in SECTIONS:
            d = os.path.join(ROOT, sec)
            if os.path.isdir(d):
                for fn in sorted(os.listdir(d)):
                    if fn.endswith(".html"):
                        paths.append(os.path.join(sec, fn))

    total_files = 0
    total_changed = 0
    total_li = 0
    total_skipped = 0
    total_desc_missing = 0

    print(f"=== migrate_related_reading {'[DRY-RUN]' if dry_run else '[EXECUTE]'} ===")
    print(f"ROOT: {ROOT}\n")

    for p in paths:
        full = os.path.join(ROOT, p)
        if not os.path.isfile(full):
            continue
        r = transform_file(full, dry_run=dry_run)
        if r.get("skipped_no_block"):
            continue
        total_files += 1
        if r.get("changed"):
            total_changed += 1
        total_li += r.get("li_transformed", 0)
        total_skipped += r.get("li_skipped_upgraded", 0)
        total_desc_missing += r.get("desc_missing", 0)
        if r.get("li_transformed") or r.get("li_skipped_upgraded"):
            flag = "WRITE" if (r.get("changed") and not dry_run) else ("DRY" if dry_run else "no-op")
            print(f"[{flag}] {p}: 转 {r.get('li_transformed',0)} / 跳过已升级 {r.get('li_skipped_upgraded',0)} / 缺desc {r.get('desc_missing',0)}")

    print("\n=== 汇总 ===")
    print(f"处理含相关阅读区块的文件数: {total_files}")
    print(f"实际改写文件数: {total_changed}")
    print(f"转换 li 总数: {total_li}")
    print(f"跳过(已升级) li 总数: {total_skipped}")
    print(f"缺 meta description(已优雅省略 rr-desc) 数: {total_desc_missing}")


if __name__ == "__main__":
    main()
