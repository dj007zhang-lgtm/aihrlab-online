#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「战略人力规划」新文配图：banner(1216x832) + og(1200x630 jpg/webp)。
森林绿系（深林绿 #3F6212 / 陶土棕 #A86A2E / 暖沙 #F1EFE9），无署名水印。
视觉隐喻：左侧一根粗颗粒的人头刻度条，右侧一组细颗粒的任务方格，
两者刻度对不上，中间留出错配缺口。"""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

GREEN = (63, 98, 18)       # #3F6212 深林绿
GREEN_D = (46, 74, 14)     # 深一档
ORANGE = (168, 106, 46)    # #A86A2E 陶土棕
SAND = (241, 239, 233)     # #F1EFE9 暖沙
DARK = (26, 26, 26)
WHITE = (255, 255, 255)

SLUG = "strategic-workforce-planning-ai-2026"
TITLE = "战略人力规划失效：不是算不准，是算错对象"
CAT = "核心方法论 · 战略人力规划"


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


def draw_granularity_mismatch(d, w, h):
    """右侧：粗刻度条（人头）与细颗粒方格（任务x能力）刻度对不上。"""
    x0 = int(w * 0.62)
    top = int(h * 0.24)
    bot = int(h * 0.78)

    # 粗颗粒：3 段大刻度条 = headcount
    bar_w = 52
    seg = (bot - top) // 3
    for i in range(3):
        y = top + i * seg
        d.rectangle([x0, y + 6, x0 + bar_w, y + seg - 6],
                    outline=(210, 225, 190), width=3)

    # 细颗粒：7x5 小方格 = 任务 x 能力
    gx = x0 + bar_w + 74
    cell = 26
    gap = 8
    for r in range(5):
        for c in range(7):
            cx = gx + c * (cell + gap)
            cy = top + 10 + r * (cell + gap)
            # 少量格子用陶土棕点出「承担者已迁移」
            filled = (r * 7 + c) % 9 in (2, 5)
            if filled:
                d.rectangle([cx, cy, cx + cell, cy + cell], fill=ORANGE)
            else:
                d.rectangle([cx, cy, cx + cell, cy + cell],
                            outline=(160, 190, 130), width=2)

    # 中间错配缺口：三段横向虚线，刻度对不齐
    for i in range(3):
        y = top + i * seg + seg // 2
        for xx in range(x0 + bar_w + 10, gx - 8, 14):
            d.line([(xx, y), (xx + 7, y)], fill=(215, 160, 110), width=2)


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
    draw_granularity_mismatch(d, W, H)
    d.text((64, 56), "AIHR数智引擎", font=font(30), fill=WHITE)
    d.text((66, 94), "AI 时代组织变革实验室", font=font(20), fill=(210, 220, 200))
    f_title = font(50)
    lines = wrap(d, TITLE, f_title, int(W * 0.48))
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
