#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Brand banner (1216x832 webp, text-free) for ai-hr-shared-services-2026.html.

Motif: the centralized SSC hub (clay) being bypassed by a distributed
agent mesh (forest-light). Business-unit nodes (forest) that once all
routed through the central hub now also connect peer-to-peer via agents.
Palette: sand #F1EFE9, sand-deep #E2DDD3, forest #3F6212, forest-light
#6F9A3C, clay #A86A2E.
"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "images", "banners", "ai-hr-shared-services-2026.webp")
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

    cx, cy = 608, 416  # center

    # Business-unit nodes (forest) arranged in a ring around the center
    bus = []
    n = 6
    ring_r = 300
    for i in range(n):
        ang = 3.14159 / 2 + i * (2 * 3.14159 / n)
        x = cx + ring_r * (i - (n - 1) / 2.0) / ((n - 1) / 2.0) * 0.0  # placeholder
    # place BUs on a horizontal-ish ellipse for clarity
    bu_pos = [
        (180, 200), (360, 140), (856, 140), (1036, 200),
        (180, 632), (360, 692), (856, 692), (1036, 632),
    ]
    for (x, y) in bu_pos:
        node(d, x, y, 30, SAND_CARD, FOREST, 4)
        # spoke from BU to the central hub (the old centralized route)
        d.line([(x, y), (cx, cy)], fill=FOREST, width=2)

    # Central SSC hub (clay) with routed spokes — the legacy centralized model
    rr(d, [cx - 64, cy - 64, cx + 64, cy + 64], 22, fill=CLAY, outline=CLAY_D, width=6)

    # Distributed agent mesh (forest-light) linking BUs peer-to-peer,
    # bypassing the hub — the new AI-native delivery layer
    agent_pos = [
        (270, 360), (608, 250), (946, 360),
        (270, 472), (608, 582), (946, 472),
    ]
    for (x, y) in agent_pos:
        node(d, x, y, 18, FOREST_L, (70, 104, 38), 3)
    # mesh edges among agents + to nearby BUs
    mesh = [
        (0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (2, 5),
        (1, 4), (0, 3), (2, 5),
    ]
    for a, b in mesh:
        (x1, y1) = agent_pos[a]
        (x2, y2) = agent_pos[b]
        d.line([(x1, y1), (x2, y2)], fill=FOREST_L, width=2)
    # agents also reach BUs directly (bypass the hub)
    bu_agent_links = [
        (0, 0), (0, 0), (2, 2), (2, 7), (3, 3), (5, 4),
    ]
    pairs = [(agent_pos[0], bu_pos[0]), (agent_pos[2], bu_pos[3]),
             (agent_pos[3], bu_pos[4]), (agent_pos[5], bu_pos[7]),
             (agent_pos[1], bu_pos[2]), (agent_pos[4], bu_pos[5])]
    for (ax, ay), (bx, by) in pairs:
        d.line([(ax, ay), (bx, by)], fill=FOREST_L, width=2)

    img.save(OUT, "WEBP", quality=92)
    print("saved", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
