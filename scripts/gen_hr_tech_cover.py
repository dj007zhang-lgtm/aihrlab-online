#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 HR 科技产品新文配图：banner(1216x832) + og(1200x630 jpg/webp)。
森林绿系（深林绿 #3F6212 / 陶土棕 #A86A2E / 暖沙 #F1EFE9），无署名水印。"""
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
GREEN_PALE = (236, 243, 224)  # #ECF3E0

SLUG = "hr-tech-talent-standard-2026"
TITLE = "你采购的不是效率：AI 招聘系统正在接管人才定义权"
CAT = "组织变革 · HR 科技"


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


def draw_nodes(d, w, h, seed):
    """右侧算法化人才评估节点网络装饰（低透明度，森林绿/白）。"""
    import random
    rnd = random.Random(seed)
    nodes = []
    for _ in range(16):
        x = rnd.randint(int(w * 0.52), int(w * 0.96))
        y = rnd.randint(int(h * 0.12), int(h * 0.9))
        nodes.append((x, y))
    # 连线
    for i, (x1, y1) in enumerate(nodes):
        for j, (x2, y2) in enumerate(nodes[i + 1:], i + 1):
            d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
            if d2 < (w * 0.22) ** 2:
                d.line([x1, y1, x2, y2], fill=(255, 255, 255), width=1)
    # 节点
    for (x, y) in nodes:
        r = rnd.randint(4, 9)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
        d.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3],
                  outline=(168, 106, 46), width=1)


def gen_banner():
    W, H = 1216, 832
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    # 背景渐变（深林绿 -> 更深）
    for y in range(H):
        t = y / H
        r = int(GREEN[0] + (GREEN_D[0] - GREEN[0]) * t)
        g = int(GREEN[1] + (GREEN_D[1] - GREEN[1]) * t)
        b = int(GREEN[2] + (GREEN_D[2] - GREEN[2]) * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    draw_nodes(d, W, H, 20260805)
    # 顶部品牌字标
    d.text((64, 56), "AIHR数智引擎", font=font(30), fill=WHITE)
    d.text((66, 94), "AI 时代组织变革实验室", font=font(20), fill=(210, 220, 200))
    # 标题
    f_title = font(58)
    lines = wrap(d, TITLE, f_title, W - 160)
    line_h = 80
    total = len(lines) * line_h
    y0 = (H - total) // 2 + 30
    for ln in lines:
        d.text((64, y0), ln, font=f_title, fill=WHITE)
        y0 += line_h
    # 陶土棕下划线
    d.rectangle([66, y0 - 6, 196, y0 - 2], fill=ORANGE)
    # 底部分类标签
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
    f_title = font(54)
    lines = wrap(d, TITLE, f_title, 690)
    line_h = 74
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
