#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate brand banner (1216x832 webp, text-free) for
ai-era-employee-retention-2026.html.

Motif: talent retention in the AI era as a "value-redistribution magnet".
- A central forest anchor node = the org's appreciating core (where redesigned
  human roles stay on the value side).
- Human nodes (forest) are pulled toward the anchor by magnetic curves.
- AI agent nodes (forest-light) are interspersed as the redistribution field.
- One human node drifts off to the right with a dashed, fading line = silent
  attrition (the mid-skill core slipping to the depreciating side).
Palette: sand #F1EFE9, sand-deep #E2DDD3, forest #3F6212, forest-light #6F9A3C,
clay #A86A2E. No text.
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


def node(d, cx, cy, r, fill, outline, width=4):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=width)


def main():
    img = make_bg()
    d = ImageDraw.Draw(img)

    # ---- value-redistribution field: faint lattice on the right (commoditized side)
    cols, rows = 6, 4
    gx0, gx1 = 720, 1110
    gy0, gy1 = 250, 600
    field = []
    for ri in range(rows):
        for ci in range(cols):
            x = gx0 + (gx1 - gx0) * ci / (cols - 1)
            y = gy0 + (gy1 - gy0) * ri / (rows - 1)
            field.append((x, y))
    for (x, y) in field:
        node(d, x, y, 9, FOREST_L, None, 0)
    # faint connecting lattice (depreciating side = cooler, sparser)
    for i in range(len(field)):
        for j in range(i + 1, len(field)):
            x1, y1 = field[i]
            x2, y2 = field[j]
            if abs(x1 - x2) < 60 and abs(y1 - y2) < 60:
                d.line([x1, y1, x2, y2], fill=(200, 206, 188), width=1)

    # ---- central forest anchor (the appreciating core / magnet)
    ax, ay = 360, 416
    node(d, ax, ay, 62, FOREST, CLAY, 6)
    # inner mark: a small clay "retention" triangle (magnet polarity)
    d.polygon([(ax, ay - 26), (ax - 23, ay + 18), (ax + 23, ay + 18)],
              fill=SAND_CARD)

    # ---- human nodes pulled toward anchor (retained talent)
    retained = [
        (560, 250, 30), (610, 470, 26), (520, 600, 28),
        (300, 250, 24), (250, 560, 26), (470, 180, 22),
    ]
    for (x, y, r) in retained:
        # magnetic curve from node to anchor
        mx, my = (x + ax) / 2, (y + ay) / 2 - 40
        d.line([(x, y), (mx, my), (ax, ay)], fill=FOREST_L, width=3)
        node(d, x, y, r, FOREST, SAND_CARD, 3)

    # ---- a few AI agent nodes in the field (forest-light, smaller)
    ai_nodes = [(700, 330, 18), (820, 430, 16), (930, 320, 18), (760, 540, 15)]
    for (x, y, r) in ai_nodes:
        node(d, x, y, r, FOREST_L, SAND_CARD, 3)

    # ---- silent attrition: one human node drifting off, dashed fading line
    dx, dy = 980, 640
    # dashed fading line from anchor side to the drifting node
    seg = 14
    steps = 18
    for s in range(steps):
        t0 = s / steps
        t1 = (s + 0.6) / steps
        x0 = ax + (dx - ax) * t0
        y0 = ay + (dy - ay) * t0
        x1 = ax + (dx - ax) * t1
        y1 = ay + (dy - ay) * t1
        alpha = int(150 * (1 - t0))
        d.line([x0, y0, x1, y1], fill=(150 + alpha // 4, 120 + alpha // 6, 80), width=2)
    node(d, dx, dy, 26, (120, 130, 96), SAND_CARD, 3)

    # ---- a couple of grounding feet under the anchor (stable base)
    rr(d, (ax - 80, ay + 110, ax + 80, ay + 130), 14, fill=CLAY, outline=None, width=0)

    out = os.path.join(ROOT, "assets", "images", "banners",
                       "ai-era-employee-retention-2026.webp")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, "WEBP", quality=92)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
