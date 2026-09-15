#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the 1216x832 brand banner for cross-cultural-team-management-2026.

Motif (text-free, brand palette): two speech bubbles (low power distance on the
left in forest, high power distance on the right in clay) joined by a translation
bridge in the middle. A clay "residue" dot stays behind on the right, symbolising
that power distance is not translated even when the words are.
Palette: sand #F1EFE9, forest #3F6212, forest-light #6F9A3C, clay #A86A2E.
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


def bubble(d, cx, cy, fill, outline, tail="down"):
    bw, bh = 320, 200
    x0, y0 = cx - bw // 2, cy - bh // 2
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=34,
                        fill=fill, outline=outline, width=6)
    # three short "text" lines inside
    for i in range(3):
        ly = y0 + 56 + i * 42
        lw = bw - 90 - (i % 2) * 50
        d.rounded_rectangle([x0 + 45, ly, x0 + 45 + lw, ly + 16],
                            radius=8, fill=outline)
    # tail
    if tail == "down":
        d.polygon([(cx - 26, y0 + bh - 2), (cx + 26, y0 + bh - 2),
                   (cx, y0 + bh + 46)], fill=fill)
        d.line([(cx - 26, y0 + bh - 2), (cx, y0 + bh + 46),
                (cx + 26, y0 + bh - 2)], fill=outline, width=6)
    else:
        d.polygon([(cx - 26, y0 + 2), (cx + 26, y0 + 2),
                   (cx, y0 - 46)], fill=fill)
        d.line([(cx - 26, y0 + 2), (cx, y0 - 46),
                (cx + 26, y0 + 2)], fill=outline, width=6)


def make():
    img = make_bg()
    d = ImageDraw.Draw(img)
    # left bubble: low power distance (forest)
    bubble(d, 250, 330, SAND_CARD, FOREST, tail="down")
    # right bubble: high power distance (clay)
    bubble(d, 966, 330, SAND_CARD, CLAY, tail="down")
    # translation bridge in the middle
    bx0, bx1 = 430, 786
    by = 330
    d.line([(bx0, by), (bx1, by)], fill=FOREST_L, width=8)
    # arrowhead into the right bubble
    d.polygon([(bx1, by), (bx1 - 34, by - 22), (bx1 - 34, by + 22)],
              fill=FOREST_L)
    # small "words passed" ticks along the bridge
    for i, tx in enumerate(range(bx0 + 40, bx1 - 30, 70)):
        d.ellipse([tx - 7, by - 7, tx + 7, by + 7], fill=FOREST_L)
    # clay residue dot staying behind on the right (power distance not translated)
    d.ellipse([966 - 18, 250, 966 + 18, 286], fill=CLAY, outline=FOREST, width=4)
    d.line([(966, 286), (966, 304)], fill=CLAY, width=4)
    # labels via short caption bars (no text rendering dependency)
    d.rounded_rectangle([150, 520, 350, 562], radius=12, fill=FOREST)
    d.rounded_rectangle([866, 520, 1066, 562], radius=12, fill=CLAY)
    # bottom accent line
    d.line([(110, 740), (1106, 740)], fill=CLAY, width=5)
    return img


def save(img, name):
    out = os.path.join(ROOT, "assets/images/banners", name)
    img.save(out, "WEBP", quality=92, method=4)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    save(make(), "cross-cultural-team-management-2026.webp")
