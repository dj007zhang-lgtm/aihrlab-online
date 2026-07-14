#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站图片优化（移动端体验 / Core Web Vitals）：
  1. 非 logo 图片加 loading="lazy" + decoding="async"（defer + 异步解码，加速首屏）
  2. 本地图片缺尺寸(且无 style 尺寸)时，补真实 width/height 属性，防布局抖动(CLS)
  logo 类图片保持 eager（作为 LCP 不延迟）
  外链/模板动态图(src 含 OFFICIAL_QR 或 http)只加 lazy，不臆造尺寸。

用法：python3 tools/optimize_images.py [--dry]
"""
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def img_dimensions(path):
    """轻量读取 png/jpg/jpeg/webp 尺寸，失败返回 None。"""
    try:
        with open(path, "rb") as f:
            sig = f.read(12)
        if sig[:8] == b"\x89PNG\r\n\x1a\n":
            with open(path, "rb") as f:
                f.read(16)
                import struct
                w, h = struct.unpack(">II", f.read(8))
                return w, h
        if sig[:3] == b"\xff\xd8\xff":  # JPEG
            with open(path, "rb") as f:
                f.read(2)
                while True:
                    b = f.read(1)
                    if not b or b != b"\xff":
                        continue
                    marker = f.read(1)
                    if marker in (b"\xc0", b"\xc1", b"\xc2", b"\xc3"):
                        f.read(3)
                        import struct
                        h, w = struct.unpack(">HH", f.read(4))
                        return w, h
                    else:
                        ln = int.from_bytes(f.read(2), "big")
                        f.read(ln - 2)
        if sig[:4] == b"RIFF" and sig[8:12] == b"WEBP":
            with open(path, "rb") as f:
                f.read(12)
                fmt = f.read(4)
                if fmt == b"VP8X":
                    f.read(4)
                    import struct
                    w = int.from_bytes(f.read(3), "little") + 1
                    h = int.from_bytes(f.read(3), "little") + 1
                    return w, h
                if fmt == b"VP8 ":
                    f.read(6)
                    import struct
                    w = int.from_bytes(f.read(2), "little") & 0x3FFF
                    h = int.from_bytes(f.read(2), "little") & 0x3FFF
                    return w, h
                if fmt == b"VP8L":
                    f.read(5)
                    import struct
                    bits = int.from_bytes(f.read(4), "little")
                    w = (bits & 0x3FFF) + 1
                    h = ((bits >> 14) & 0x3FFF) + 1
                    return w, h
    except Exception:
        return None
    return None


def resolve_src(src, html_dir):
    if src.startswith("http://") or src.startswith("https://"):
        return None
    if "OFFICIAL_QR" in src or "+" in src:
        return None  # 模板动态图，跳过尺寸
    if src.startswith("/"):
        p = os.path.join(ROOT, src.lstrip("/"))
    else:
        p = os.path.normpath(os.path.join(html_dir, src))
    return p if os.path.exists(p) else None


def process(html, html_path):
    html_dir = os.path.dirname(html_path)
    changed = False

    def repl(m):
        nonlocal changed
        tag = m.group(0)
        # logo 保持 eager
        if re.search(r'class=["\'][^"\']*logo', tag, re.I):
            return tag
        new = tag
        if not re.search(r'\bloading=', new, re.I):
            new = new.replace("<img", '<img loading="lazy"', 1)
            changed = True
        if not re.search(r'\bdecoding=', new, re.I):
            new = new.replace("<img", '<img decoding="async"', 1)
            changed = True
        # 尺寸：无 width/height 属性 且 无 style 宽高 -> 尝试补
        has_attr_wh = bool(re.search(r'\b(width|height)=', new, re.I))
        has_style_wh = bool(re.search(r'style=["\'][^"\']*(width|height)\s*:', new, re.I))
        if not has_attr_wh and not has_style_wh:
            sm = re.search(r'src="([^"]*)"', new)
            if sm:
                rp = resolve_src(sm.group(1), html_dir)
                if rp:
                    dim = img_dimensions(rp)
                    if dim:
                        new = new.replace("<img", f'<img width="{dim[0]}" height="{dim[1]}"', 1)
                        changed = True
        return new

    return re.sub(r"<img\b[^>]*>", repl, html, flags=re.I), changed


def main():
    dry = "--dry" in sys.argv
    files = [f for f in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True)
             if ".git" not in f and "node_modules" not in f]
    total = 0
    for f in files:
        html = open(f, encoding="utf-8").read()
        new_html, changed = process(html, f)
        if changed:
            total += 1
            if not dry:
                open(f, "w", encoding="utf-8").write(new_html)
    print(f"{'[DRY] ' if dry else ''}已优化 {total} 个文件（加 lazy/async/尺寸）")


if __name__ == "__main__":
    main()
