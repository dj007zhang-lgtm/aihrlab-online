#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 AI 伦理治理新文配图：banner(1216x832) + og(1200x630 jpg/webp)。
森林绿系（深林绿 #3F6212 / 陶土棕 #A86A2E / 暖沙 #F1EFE9），无署名水印。"""
import os
import math
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

GREEN = (63, 98, 18)       # #3F6212 深林绿
GREEN_D = (46, 74, 14)     # 深一档
ORANGE = (168, 106, 46)    # #A86A2E 陶土棕
SAND = (241, 239, 233)     # #F1EFE9 暖沙
DARK = (26, 26, 26)
WHITE = (255, 255, 255)

SLUG = "ai-ethics-performance-evaluation-2026"
TITLE = "当AI开始写绩效评语：算法问责与可解释性红线"
CAT = "治理与伦理 · HR 合规"

def font(sz, idx=0):
    return ImageFont.truetype(FONT, sz, index=idx)

def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines

def draw_lock_pattern(d, w, h, seed):
    """右侧锁形图案，象征问责与合规"""
    import random
    rnd = random.Random(seed)
    # 绘制多个锁形轮廓
    for i in range(5):
        x = rnd.randint(int(w * 0.6), int(w * 0.9))
        y = rnd.randint(int(h * 0.15), int(h * 0.85))
        size = rnd.randint(20, 40)
        # 锁体
        d.rectangle([x, y, x + size, y + size * 0.7],
                   outline=(255, 255, 255), width=1)
        # 锁环
        d.arc([x + size * 0.2, y - size * 0.3, x + size * 0.8, y + size * 0.3],
              0, 180, fill=(255, 255, 255), width=1)

def gen_banner():
    W, H = 1216, 832
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(GREEN[0] + (GREEN_D[0] - GREEN[0]) * t)
        g = int(GREEN[1] + (GREEN_D[1] - GREEN[1]) * t)
        b = int(GREEN[2] + (GREEN_D[2] - GREEN[2]) * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    draw_lock_pattern(d, W, H, 20260820)
    d.text((64, 56), "AIHR数智引擎", font=font(30), fill=WHITE)
    d.text((66, 94), "AI 时代组织变革实验室", font=font(20), fill=(210, 220, 200))
    f_title = font(50)
    lines = wrap(d, TITLE, f_title, W - 160)
    line_h = 72
    total = len(lines) * line_h
    y0 = (H - total) // 2 + 30
    for ln in lines:
        d.text((64, y0), ln, font=f_title, fill=WHITE)
        y0 += line_h
    d.rectangle([66, y0 - 6, 196, y0 - 2], fill=ORANGE)
    d.text((66, H - 70), CAT, font=font(24), fill=(220, 230, 210))
    out = os.path.join(BASE, "assets", "images", "banners", f"{SLUG}.webp")
    img.save(out, "WEBP", quality=92)
    print("wrote", out)

def gen_og():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), SAND)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 440, H], fill=GREEN)
    d.text((60, 150), "AI", font=font(230), fill=WHITE)
    d.text((64, 420), "AIHR数智引擎", font=font(34), fill=WHITE)
    d.text((64, 470), "AI 时代组织变革实验室", font=font(24), fill=(210, 220, 200))
    f_title = font(48)
    lines = wrap(d, TITLE, f_title, 690)
    line_h = 68
    total = len(lines) * line_h
    y = (H - total) // 2 + 20
    for ln in lines:
        d.text((485, y), ln, font=f_title, fill=DARK)
        y += line_h
    d.rectangle([487, y - 6, 587, y - 2], fill=ORANGE)
    d.text((485, 70), CAT, font=font(26), fill=(120, 120, 120))
    p_jpg = os.path.join(BASE, "assets", "og-covers", f"og-{SLUG}.jpg")
    p_webp = os.path.join(BASE, "assets", "og-covers", f"og-{SLUG}.webp")
    img.save(p_jpg, "JPEG", quality=92)
    img.save(p_webp, "WEBP", quality=92)
    print("wrote", p_jpg, p_webp)

if __name__ == "__main__":
    gen_banner()
    gen_og()
