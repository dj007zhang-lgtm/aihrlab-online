#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate brand banner (1216x832 webp, text-free) for
ai-hr-three-pillar-model-2026.html.

Motif: three HR operating-model "pillars" being re-weighted by AI.
- SSC (shared service): short + clay  -> shrinking transactional leg
- COE (center of excellence): tall + forest-light -> elevated expertise leg
- HRBP (business partner): mid + forest -> the only human-facing leg
- a four-point AI spark above, signalling the cost curve rewrite.
Palette: sand #F1EFE9, sand-deep #E2DDD3, forest #3F6212, forest-light #6F9A3C, clay #A86A2E.
"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1216, 832
SAND = (241, 239, 233)
SAND_DEEP = (226, 221, 211)
FOREST = (63, 98, 18)
FOREST_L = (111, 154, 60)
CLAY = (168, 106, 46)
SAND_CARD = (250, 248, 244)


def make_bg():
    img = Image.new("RGB", (W, H), SAND)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(SAND[0] + (SAND_DEEP[0] - SAND[0]) * t)
        g = int(SAND[1] + (SAND_DEEP[1] - SAND[1]) * t)
        b = int(SAND[2] + (SAND_DEEP[2] - SAND[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def rr(d, box, rad, fill=None, outline=None, width=4):
    d.rounded_rectangle(box, radius=rad, fill=fill, outline=outline, width=width)


def pillar(d, cx, base_y, height, half_w, fill, outline):
    top = base_y - height
    rr(d, [cx - half_w, top, cx + half_w, base_y], 26, fill=fill, outline=outline, width=6)
    # inner accent notch (agent node) near top
    d.ellipse([cx - 16, top + 34, cx + 16, top + 66], fill=SAND_CARD, outline=outline, width=4)


def spark(d, cx, cy, r, fill):
    # four-point star
    pts = [(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy),
           (cx + r * 0.28, cy + r * 0.28), (cx, cy + r), (cx - r * 0.28, cy + r * 0.28),
           (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)]
    d.polygon(pts, fill=fill)


def main():
    img = make_bg()
    d = ImageDraw.Draw(img)
    base_y = 660
    # SSC: short, clay (shrinking)
    pillar(d, 360, base_y, 250, 78, CLAY, (120, 74, 30))
    # COE: tall, forest-light (elevated)
    pillar(d, 608, base_y, 470, 78, FOREST_L, (70, 104, 38))
    # HRBP: mid, forest (steady, human-facing)
    pillar(d, 856, base_y, 360, 78, FOREST, (40, 64, 12))
    # AI spark above COE (the cost-curve rewrite)
    spark(d, 608, 150, 54, CLAY)
    # baseline
    d.line([(120, base_y + 18), (1096, base_y + 18)], fill=CLAY, width=5)
    # subtle connector dots between pillars (information routing)
    for (x, y) in [(484, 560), (732, 560), (484, 470), (732, 470)]:
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=FOREST_L)
    out = os.path.join(ROOT, "assets", "images", "banners",
                       "ai-hr-three-pillar-model-2026.webp")
    img.save(out, "WEBP", quality=92)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
