#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「初级岗位门槛上移」新文配图：banner(1216x832) + og(1200x630 jpg/webp)。
森林绿系（深林绿 #3F6212 / 陶土棕 #A86A2E / 暖沙 #F1EFE9），无署名水印。
视觉隐喻：左下到右上的阶梯，第一级台阶被抬高、与地面之间留出缺口。"""
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

SLUG = "entry-level-jobs-ai-talent-pipeline-2026"
TITLE = "AI 抬高了初级岗位的门槛，中层三年后从哪来"
CAT = "组织变革 · 人才管道"


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


def draw_stair_gap(d, w, h):
    """右侧阶梯：底部第一级被抬高，与地面之间留缺口。"""
    base_y = int(h * 0.82)
    x0 = int(w * 0.60)
    step_w = 62
    step_h = 46
    # 地面基线
    d.line([(x0 - 30, base_y), (w - 40, base_y)], fill=(150, 175, 120), width=2)
    # 正常阶梯（第 2 级起）
    for i in range(1, 6):
        x = x0 + i * step_w
        y = base_y - i * step_h
        d.rectangle([x, y, x + step_w - 8, base_y], outline=(210, 225, 190), width=2)
    # 第一级被抬高：悬在空中，留缺口
    gap_y = base_y - step_h - 26
    d.rectangle([x0, gap_y, x0 + step_w - 8, gap_y + 14], fill=ORANGE)
    # 缺口虚线
    for yy in range(gap_y + 20, base_y, 12):
        d.line([(x0 + 6, yy), (x0 + 22, yy)], fill=(215, 160, 110), width=2)


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
    draw_stair_gap(d, W, H)
    d.text((64, 56), "AIHR数智引擎", font=font(30), fill=WHITE)
    d.text((66, 94), "AI 时代组织变革实验室", font=font(20), fill=(210, 220, 200))
    f_title = font(50)
    lines = wrap(d, TITLE, f_title, int(W * 0.52))
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
