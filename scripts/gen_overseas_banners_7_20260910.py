#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate 7 brand banners (1216x832 webp, text-free) for the remaining overseas HR articles.
Palette: sand #F1EFE9, sand-deep #E2DDD3, forest #3F6212, forest-light #6F9A3C, clay #A86A2E."""
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


def node(d, c, rad, fill=SAND_CARD, outline=FOREST, width=5):
    d.ellipse([c[0]-rad, c[1]-rad, c[0]+rad, c[1]+rad], fill=fill, outline=outline, width=width)


def accent(d):
    d.line([(110, 740), (1106, 740)], fill=CLAY, width=5)


# 1. cross-cultural: two overlapping culture circles
def banner_cross_cultural():
    img = make_bg(); d = ImageDraw.Draw(img)
    cx = W // 2
    node(d, (cx-150, 400), 150, fill=SAND_CARD, outline=FOREST, width=6)
    node(d, (cx+150, 400), 150, fill=SAND_CARD, outline=CLAY, width=6)
    # overlap lens accent dots
    for (ox, oy) in [(cx, 320), (cx-30, 420), (cx+30, 420), (cx, 500)]:
        d.ellipse([ox-9, oy-9, ox+9, oy+9], fill=FOREST_L)
    accent(d)
    return img


# 2. global-compensation: balance scale (two pans, different sized coins)
def banner_compensation():
    img = make_bg(); d = ImageDraw.Draw(img)
    cx = W // 2
    # beam
    d.line([(cx-300, 300), (cx+300, 300)], fill=FOREST, width=8)
    d.line([(cx, 180), (cx, 300)], fill=FOREST, width=8)  # post
    node(d, (cx, 170), 26, fill=CLAY, outline=FOREST, width=5)
    # left pan (big local market)
    d.line([(cx-300, 300), (cx-300, 470)], fill=FOREST_L, width=4)
    rr(d, [cx-360, 470, cx-240, 520], 14, fill=SAND_CARD, outline=FOREST, width=5)
    for i in range(3):
        node(d, (cx-330+i*40, 450), 18, fill=FOREST_L, outline=FOREST, width=3)
    # right pan (small fairness)
    d.line([(cx+300, 300), (cx+300, 460)], fill=FOREST_L, width=4)
    rr(d, [cx+240, 460, cx+360, 500], 14, fill=SAND_CARD, outline=CLAY, width=5)
    node(d, (cx+300, 440), 14, fill=CLAY, outline=FOREST, width=3)
    accent(d)
    return img


# 3. EOR: hub connecting distributed local nodes
def banner_eor():
    img = make_bg(); d = ImageDraw.Draw(img)
    hub = (W//2, 410)
    locals_ = [(260, 250), (980, 250), (220, 600), (1000, 600), (W//2, 660)]
    for n in locals_:
        d.line([hub, n], fill=FOREST_L, width=4)
    for n in locals_:
        node(d, n, 30, fill=SAND_CARD, outline=FOREST, width=5)
    node(d, hub, 44, fill=CLAY, outline=FOREST, width=5)
    accent(d)
    return img


# 4. expat vs localization: pendulum
def banner_expat():
    img = make_bg(); d = ImageDraw.Draw(img)
    cx = W // 2
    pivot = (cx, 180)
    node(d, pivot, 26, fill=CLAY, outline=FOREST, width=5)
    # arm to left (expat) and right (local)
    d.line([pivot, (cx-300, 560)], fill=FOREST, width=8)
    d.line([pivot, (cx+300, 560)], fill=FOREST, width=8)
    node(d, (cx-300, 560), 40, fill=SAND_CARD, outline=FOREST, width=5)
    node(d, (cx+300, 560), 40, fill=SAND_CARD, outline=CLAY, width=5)
    # mid arc
    d.arc([cx-300, 300, cx+300, 600], 200, 340, fill=FOREST_L, width=4)
    accent(d)
    return img


# 5. labor-risk: layered shield / barrier
def banner_labor_risk():
    img = make_bg(); d = ImageDraw.Draw(img)
    cx = W // 2
    # nested rounded rects (layers of protection)
    for i, (col, wd) in enumerate([(FOREST, 6), (FOREST_L, 5), (CLAY, 7)]):
        inset = 60 + i*70
        rr(d, [cx-260+inset-30, 220+inset-30, cx+260-inset+30, 620-inset+30], 28,
           fill=None, outline=col, width=wd)
    node(d, (cx, 420), 46, fill=CLAY, outline=FOREST, width=6)
    accent(d)
    return img


# 6. ai-in-overseas-hr: node with human-oversight check + shield
def banner_ai():
    img = make_bg(); d = ImageDraw.Draw(img)
    cx = W // 2
    hub = (cx, 410)
    node(d, hub, 70, fill=SAND_CARD, outline=FOREST, width=6)
    # inner check (human oversight)
    d.line([(cx-28, 410), (cx-6, 432), (cx+34, 386)], fill=CLAY, width=10, joint="curve")
    # surrounding regulation nodes
    surround = [(cx-260, 250), (cx+260, 250), (cx-260, 570), (cx+260, 570)]
    for n in surround:
        d.line([hub, n], fill=FOREST_L, width=4)
        node(d, n, 26, fill=SAND_CARD, outline=FOREST_L, width=5)
    accent(d)
    return img


# 7. metrics: bar chart varying heights
def banner_metrics():
    img = make_bg(); d = ImageDraw.Draw(img)
    cx = W // 2
    bars = [0.45, 0.72, 0.33, 0.88, 0.6]
    bw = 110; gap = 40
    x0 = cx - (len(bars)*(bw+gap))//2
    base = 640
    for i, h in enumerate(bars):
        bx = x0 + i*(bw+gap)
        top = base - int(h*400)
        rr(d, [bx, top, bx+bw, base], 12, fill=FOREST if i % 2 == 0 else CLAY,
           outline=FOREST, width=4)
    d.line([(x0-30, base), (x0+len(bars)*(bw+gap)+10, base)], fill=FOREST, width=6)
    accent(d)
    return img


def save(img, name):
    out = os.path.join(ROOT, "assets/images/banners", name)
    img.save(out, "WEBP", quality=92, method=4)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    save(banner_cross_cultural(), "cross-cultural-team-management-2026.webp")
    save(banner_compensation(), "global-compensation-design-2026.webp")
    save(banner_eor(), "eor-employer-of-record-2026.webp")
    save(banner_expat(), "expatriate-vs-localization-2026.webp")
    save(banner_labor_risk(), "overseas-labor-risk-2026.webp")
    save(banner_ai(), "ai-in-overseas-hr-2026.webp")
    save(banner_metrics(), "overseas-hr-metrics-2026.webp")
