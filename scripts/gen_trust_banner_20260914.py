#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate brand banner (1216x832 webp, text-free) for
ai-era-organizational-trust-2026.html.

Motif: organizational trust as the bond between two networks.
- Left cluster = the employer / information network hub (forest anchor).
- Human nodes (forest) connected to the hub by SOLID trust bonds (transparent).
- AI agent nodes (forest-light) interspersed in the field.
- One human node has an OPAQUE black-box AI overlay and a BROKEN/dashed bond
  to the hub = eroded trust (surveillance / opacity).
- A "transparency" node on the right where a re-established SOLID bond shows
  trust rebuilt through human-in-the-loop.
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
BROKEN = (150, 130, 96)


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


def node(d, cx, cy, r, fill, outline, width=3):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=width)


def solid_bond(d, x1, y1, x2, y2, color=FOREST_L, width=4):
    d.line([x1, y1, x2, y2], fill=color, width=width)


def broken_bond(d, x1, y1, x2, y2):
    # dashed, fading line = eroded trust
    import math
    steps = 22
    seg = 0.55
    for s in range(steps):
        t0 = s / steps
        t1 = (s + seg) / steps
        xa = x1 + (x2 - x1) * t0
        ya = y1 + (y2 - y1) * t0
        xb = x1 + (x2 - x1) * t1
        yb = y1 + (y2 - y1) * t1
        alpha = int(170 * (1 - t0))
        d.line([xa, ya, xb, yb],
               fill=(BROKEN[0] + alpha // 6, BROKEN[1] + alpha // 8, BROKEN[2]),
               width=2)


def main():
    img = make_bg()
    d = ImageDraw.Draw(img)

    # ---- central employer / information-network hub (left-of-center)
    hx, hy = 330, 416
    node(d, hx, hy, 70, FOREST, CLAY, 6)
    d.polygon([(hx, hy - 30), (hx - 26, hy + 20), (hx + 26, hy + 20)],
              fill=SAND_CARD)

    # ---- retained human nodes with SOLID trust bonds to hub
    retained = [
        (560, 250, 30), (610, 470, 26), (520, 600, 28),
        (300, 250, 24), (250, 560, 26), (470, 170, 22),
    ]
    for (x, y, r) in retained:
        mx, my = (x + hx) / 2, (y + hy) / 2 - 40
        solid_bond(d, x, y, mx, my, FOREST_L, 3)
        solid_bond(d, mx, my, hx, hy, FOREST_L, 3)
        node(d, x, y, r, FOREST, SAND_CARD, 3)

    # ---- a few AI agent nodes in the field (forest-light, smaller)
    ai_nodes = [(700, 330, 18), (820, 430, 16), (930, 320, 18), (760, 540, 15)]
    for (x, y, r) in ai_nodes:
        node(d, x, y, r, FOREST_L, SAND_CARD, 3)

    # ---- eroded trust: one human node with opaque black-box AI overlay,
    #      BROKEN bond to hub
    dx, dy = 980, 640
    broken_bond(d, hx, hy, dx, dy)
    node(d, dx, dy, 28, BROKEN, SAND_CARD, 3)
    # opaque black-box square over the node = opacity / surveillance
    rr(d, (dx - 16, dy - 16, dx + 16, dy + 16), 6, fill=(60, 64, 58),
       outline=SAND_CARD, width=2)

    # ---- rebuilt trust: a transparency node on the right with re-established
    #      SOLID bond (human-in-the-loop)
    tx, ty = 1000, 280
    solid_bond(d, hx, hy, tx, ty, FOREST_L, 4)
    node(d, tx, ty, 30, FOREST, SAND_CARD, 3)
    # small open eye / aperture mark = transparency
    d.ellipse([tx - 12, ty - 8, tx + 12, ty + 8], outline=SAND_CARD, width=3)
    d.ellipse([tx - 4, ty - 4, tx + 4, ty + 4], fill=SAND_CARD)

    # ---- grounding feet under hub (stable base)
    rr(d, (hx - 90, hy + 120, hx + 90, hy + 142), 14, fill=CLAY, outline=None, width=0)

    out = os.path.join(ROOT, "assets", "images", "banners",
                       "ai-era-organizational-trust-2026.webp")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, "WEBP", quality=92)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
