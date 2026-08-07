#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《远程办公没有退潮》配图：banner(1216x832) + og(1200x630 jpg/webp)。
森林绿系（深林绿 #3F6212 / 陶土棕 #A86A2E / 暖沙 #F1EFE9），无署名水印。
注意：OG 输出目录为 assets/images/og-covers/（与文章 HTML 引用路径一致）。"""
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

SLUG = "remote-work-ai-era-2026"
TITLE = "远程办公没有退潮：灵活性正在变成一种薪酬"
CAT = "组织变革 · 混合办公"


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


def draw_distributed_nodes(d, w, h, seed):
    """右侧『分布式协作』装饰：三簇节点 + 稀疏跨簇连线（低调，不抢标题）。"""
    import random
    rnd = random.Random(seed)
    centers = [(int(w * 0.68), int(h * 0.26)),
               (int(w * 0.86), int(h * 0.55)),
               (int(w * 0.62), int(h * 0.78))]
    clusters = []
    for cx, cy in centers:
        pts = []
        for _ in range(6):
            pts.append((cx + rnd.randint(-70, 70), cy + rnd.randint(-60, 60)))
        clusters.append(pts)
    # 簇内密连（白色，模拟高协调密度）
    for pts in clusters:
        for i, (x1, y1) in enumerate(pts):
            for (x2, y2) in pts[i + 1:]:
                d.line([x1, y1, x2, y2], fill=(255, 255, 255), width=1)
    # 跨簇稀疏连线（陶土棕，模拟远程弱连接）
    for i in range(len(clusters)):
        a = clusters[i][0]
        b = clusters[(i + 1) % len(clusters)][2]
        d.line([a[0], a[1], b[0], b[1]], fill=ORANGE, width=2)
    # 节点
    for pts in clusters:
        for (x, y) in pts:
            r = rnd.randint(5, 9)
            d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)
            d.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3],
                      outline=ORANGE, width=1)


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
    draw_distributed_nodes(d, W, H, 20260807)
    d.text((64, 56), "AIHR数智引擎", font=font(30), fill=WHITE)
    d.text((66, 94), "AI 时代组织变革实验室", font=font(20), fill=(210, 220, 200))
    f_title = font(58)
    lines = wrap(d, TITLE, f_title, W - 420)
    line_h = 80
    total = len(lines) * line_h
    y0 = (H - total) // 2 + 30
    for ln in lines:
        d.text((64, y0), ln, font=f_title, fill=WHITE)
        y0 += line_h
    d.rectangle([66, y0 - 6, 196, y0 - 2], fill=ORANGE)
    d.text((66, H - 70), CAT, font=font(24), fill=(220, 230, 210))
    outdir = os.path.join(BASE, "assets", "images", "banners")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{SLUG}.webp")
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
    lines = wrap(d, TITLE, f_title, 660)
    line_h = 74
    total = len(lines) * line_h
    y = (H - total) // 2 + 20
    for ln in lines:
        d.text((485, y), ln, font=f_title, fill=DARK)
        y += line_h
    d.rectangle([487, y - 6, 587, y - 2], fill=ORANGE)
    d.text((485, 70), CAT, font=font(26), fill=(120, 120, 120))
    outdir = os.path.join(BASE, "assets", "images", "og-covers")
    os.makedirs(outdir, exist_ok=True)
    p_jpg = os.path.join(outdir, f"og-{SLUG}.jpg")
    p_webp = os.path.join(outdir, f"og-{SLUG}.webp")
    img.save(p_jpg, "JPEG", quality=92)
    img.save(p_webp, "WEBP", quality=92)
    print("wrote", p_jpg, p_webp)


if __name__ == "__main__":
    gen_banner()
    gen_og()
