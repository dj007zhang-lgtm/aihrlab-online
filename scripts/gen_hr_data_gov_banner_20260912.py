#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate brand banner (1216x832 webp, text-free) for
hr-data-governance-2026.html.

Motif: the organization's "data truth layer" (a lattice of people/AI data
nodes) guarded by an accountability node (the new HR data-governance function).
- human node (forest) + AI agent node (forest-light) feed the data layer
- a clay governance node sits above, arbitrating trust/accountability
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
CLAY_D = (120, 74, 30)
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


def node(d, cx, cy, r, fill, outline, width=4):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=width)


def main():
    img = make_bg()
    d = ImageDraw.Draw(img)

    # central data truth layer: 5 x 3 lattice of small nodes
    cols, rows = 5, 3
    gx0, gx1 = 300, 916
    gy0, gy1 = 470, 690
    pts = []
    for ri in range(rows):
        for ci in range(cols):
            x = gx0 + (gx1 - gx0) * ci / (cols - 1)
            y = gy0 + (gy1 - gy0) * ri / (rows - 1)
            pts.append((x, y))
    # connectors
    for ri in range(rows):
        for ci in range(cols):
            x, y = pts[ri * cols + ci]
            if ci + 1 < cols:
                x2, y2 = pts[ri * cols + ci + 1]
                d.line([(x, y), (x2, y2)], fill=FOREST_L, width=2)
            if ri + 1 < rows:
                x2, y2 = pts[(ri + 1) * cols + ci]
                d.line([(x, y), (x2, y2)], fill=FOREST_L, width=2)
    for (x, y) in pts:
        node(d, int(x), int(y), 16, SAND_CARD, FOREST_L, 3)

    # human node (forest) feeding the layer from the left
    hx, hy = 200, 300
    node(d, hx, hy, 46, FOREST, (40, 64, 12), 5)
    d.line([(hx, hy + 46), (pts[0][0], pts[0][1] - 16)], fill=FOREST, width=4)

    # AI agent node (forest-light) feeding from the right
    ax, ay = 1016, 300
    node(d, ax, ay, 46, FOREST_L, (70, 104, 38), 5)
    d.line([(ax, ay + 46), (pts[cols - 1][0], pts[cols - 1][1] - 16)], fill=FOREST_L, width=4)

    # governance / accountability node (clay) centered above, guarding the layer
    gx, gy = 608, 250
    rr(d, [gx - 54, gy - 54, gx + 54, gy + 54], 20, fill=CLAY, outline=CLAY_D, width=6)
    node(d, gx, gy, 20, SAND_CARD, CLAY_D, 4)
    # link governance to the data layer center
    d.line([(gx, gy + 54), (608, gy0 - 16)], fill=CLAY, width=5)

    # baseline (the organizational substrate the data layer rests on)
    d.line([(120, gy1 + 28), (1096, gy1 + 28)], fill=CLAY, width=5)

    out = os.path.join(ROOT, "assets", "images", "banners",
                       "hr-data-governance-2026.webp")
    img.save(out, "WEBP", quality=92)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
