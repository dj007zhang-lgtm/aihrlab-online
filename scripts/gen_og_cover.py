#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成文章 OG 封面 (1200x630)：左侧引擎蓝面板 + 白色 AI 字标，右侧标题。
用法: python3 scripts/gen_og_cover.py <slug> <标题> [分类]
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
W, H = 1200, 630
BLUE = (59, 91, 219)      # #3B5BDB 引擎蓝
ORANGE = (194, 119, 46)   # #C2772E 暖橙
BG = (250, 250, 248)      # #FAFAF8 微暖背景
DARK = (26, 26, 26)
WHITE = (255, 255, 255)
GREY = (120, 120, 120)


def font(sz, idx=0):
    return ImageFont.truetype(FONT, sz, index=idx)


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) <= max_w:
            cur += ch
        else:
            lines.append(cur); cur = ch
    if cur:
        lines.append(cur)
    return lines


def gen(slug, title, cat="核心方法论"):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 左侧蓝面板
    d.rectangle([0, 0, 440, H], fill=BLUE)
    # 面板内 AI 字标
    f_ai = font(230)
    d.text((60, 150), "AI", font=f_ai, fill=WHITE)
    f_sub = font(34)
    d.text((64, 420), "AIHR数智引擎", font=f_sub, fill=WHITE)
    f_tag = font(24)
    d.text((64, 470), "AI 时代组织变革实验室", font=f_tag, fill=(210, 220, 255))
    # 右侧标题
    f_title = font(56)
    lines = wrap(d, title, f_title, 690)
    line_h = 76
    total = len(lines) * line_h
    y = (H - total) // 2 + 20
    for ln in lines:
        d.text((485, y), ln, font=f_title, fill=DARK)
        y += line_h
    # 橙色短下划线
    d.rectangle([487, y - 6, 587, y - 2], fill=ORANGE)
    # 右上角分类标签
    f_cat = font(26)
    d.text((485, 70), cat, font=f_cat, fill=GREY)

    out = os.path.join(BASE, "assets", "og-covers", f"og-{slug}.png")
    img.save(out, "PNG")
    print("wrote", out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: gen_og_cover.py <slug> <标题> [分类]")
        sys.exit(1)
    gen(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "核心方法论")
