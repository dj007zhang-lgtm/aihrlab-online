#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate two 1216x832 brand banners for the overseas HR cornerstone articles.

Motifs (text-free, brand palette):
  - overseas-employment-compliance-2026 : a checklist grid with one clay
    strike-through (the red line) beside a governance node network.
  - overseas-control-model-2026          : a three-tier hub-and-spoke graph
    (HQ / region / local) with decision-flow accents.
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


def round_rect(d, box, r, fill=None, outline=None, width=4):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def banner_compliance():
    img = make_bg()
    d = ImageDraw.Draw(img)
    # left: checklist of 5 rounded cards, 3rd struck through by a clay line
    x0, y0 = 110, 210
    cw, ch, gap = 360, 70, 26
    for i in range(5):
        cy = y0 + i * (ch + gap)
        round_rect(d, [x0, cy, x0 + cw, cy + ch], 16, fill=SAND_CARD,
                   outline=FOREST, width=4)
        # tick mark
        tx = x0 + 34
        d.line([(tx, cy + ch // 2), (tx + 16, cy + ch // 2 + 14),
                (tx + 40, cy + ch // 2 - 18)], fill=FOREST_L, width=6,
               joint="curve")
        if i == 2:  # the red line: governance mode, not the list
            d.line([(x0 + 14, cy + 14), (x0 + cw - 14, cy + ch - 14)],
                   fill=CLAY, width=10)
    # right: governance node network
    nodes = [(980, 250), (870, 430), (1080, 430), (930, 600), (1040, 600)]
    hub = (980, 400)
    for n in nodes:
        d.line([hub, n], fill=FOREST_L, width=4)
    for n in nodes:
        d.ellipse([n[0] - 26, n[1] - 26, n[0] + 26, n[1] + 26],
                  fill=SAND_CARD, outline=FOREST, width=5)
    d.ellipse([hub[0] - 34, hub[1] - 34, hub[0] + 34, hub[1] + 34],
              fill=CLAY, outline=FOREST, width=5)
    # bottom accent line
    d.line([(110, 740), (1106, 740)], fill=CLAY, width=5)
    return img


def banner_control():
    img = make_bg()
    d = ImageDraw.Draw(img)
    cx = W // 2
    # tiers
    hq = (cx, 180)
    region = [(cx - 230, 400), (cx, 400), (cx + 230, 400)]
    local = [(cx - 380, 640), (cx - 190, 640), (cx, 640), (cx + 190, 640),
             (cx + 380, 640)]
    # spokes
    for r in region:
        d.line([hq, r], fill=FOREST_L, width=4)
    for l in local:
        # connect each local to nearest region
        nr = min(region, key=lambda rr: abs(rr[0] - l[0]))
        d.line([nr, l], fill=FOREST_L, width=3)
    # accent path hq -> center region -> center local
    d.line([hq, region[1]], fill=CLAY, width=7)
    d.line([region[1], local[2]], fill=CLAY, width=7)
    # nodes
    d.ellipse([hq[0] - 40, hq[1] - 40, hq[0] + 40, hq[1] + 40],
              fill=CLAY, outline=FOREST, width=5)
    for r in region:
        d.ellipse([r[0] - 32, r[1] - 32, r[0] + 32, r[1] + 32],
                  fill=SAND_CARD, outline=FOREST, width=5)
    for l in local:
        d.ellipse([l[0] - 26, l[1] - 26, l[0] + 26, l[1] + 26],
                  fill=SAND_CARD, outline=FOREST_L, width=5)
    d.line([(110, 740), (1106, 740)], fill=CLAY, width=5)
    return img


def save(img, name):
    out = os.path.join(ROOT, "assets/images/banners", name)
    img.save(out, "WEBP", quality=92, method=4)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    save(banner_compliance(),
         "overseas-employment-compliance-2026.webp")
    save(banner_control(),
         "overseas-control-model-2026.webp")
