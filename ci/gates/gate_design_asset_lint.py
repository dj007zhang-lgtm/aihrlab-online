# -*- coding: utf-8 -*-
"""
gate_design_asset_lint —— 设计资产自检（自设计环节预防）

用户担忧：未来"自设计"自动化若产出坏 CSS / 缺 OG 图 / 丢共享资源，会比内容环节更糟。
本门把设计产物的低级硬伤变成可自动拦截的信号：
  - og:image 存在且指向磁盘真实资源（否则社交分享卡片崩）。
  - 站点主 CSS 存在 + 大括号平衡（否则整站样式崩）。
  - 抽样页引用的本地 CSS/JS 资源存在（否则白屏）。
  - 主 CSS 含品牌色 token 之一（否则设计系统漂移）。
默认 severity=WARN（不阻断内容发布），但每周深度扫描会据此预警；若配置
block_on_trigger=true 则升级为阻断。
"""
import os
import re
import time
from . import (walk_html, read, is_indexable, rel, GateReport, Finding)

OG_IMG_PAT = re.compile(r'<meta\s+[^>]*property=["\']og:image["\']\s+content=["\'](.*?)["\']', re.I | re.S)
ASSET_REF_PAT = re.compile(r'(?:href|src)=["\']((?:assets|static)/[^"\']+\.(?:css|js))["\']')
CSS_FILE_PAT = re.compile(r'href=["\']([^"\']+\.css)["\']')


def run(site_root, cfg, baseline=None):
    t0 = time.time()
    p = cfg.get("params", {})
    sample_n = p.get("scan_sample", 40)
    brand_tokens = p.get("brand_tokens", ["#5C8A2C", "#3F6212", "#F4F1EA", "#F1EFE9", "#A86A2E", "#1A1A17"])
    check_brace = p.get("check_css_brace_balance", True)

    rep = GateReport("design_asset_lint", "设计资产自检（OG 图 / CSS / 共享资源 / 品牌 token）")
    rep.metrics = {"og_missing": 0, "og_broken": 0, "css_broken": 0, "asset_missing": 0, "css_unbalanced": 0}

    # 主 CSS 平衡 + 品牌 token
    main_css = os.path.join(site_root, "assets", "css", "style.min.css")
    if os.path.exists(main_css):
        css = read(main_css)
        if check_brace:
            if css.count("{") != css.count("}"):
                rep.add(Finding("WARN", "CSS-UNBALANCED", detail="主 CSS 大括号不平衡（样式可能崩）。"))
                rep.metrics["css_unbalanced"] += 1
        if not any(tok.lower() in css.lower() for tok in brand_tokens):
            rep.add(Finding("WARN", "BRAND-DRIFT", detail="主 CSS 未发现任何品牌色 token（设计系统漂移）。"))
    else:
        rep.add(Finding("WARN", "CSS-MISSING", detail="assets/css/style.min.css 不存在。"))
        rep.metrics["css_broken"] += 1

    # 抽样页
    pages = [f for f in walk_html(site_root) if is_indexable(read(f))]
    sample = pages[:sample_n]
    for f in sample:
        html = read(f)
        relf = rel(site_root, f)
        # og:image
        om = OG_IMG_PAT.search(html)
        if not om:
            rep.add(Finding("WARN", "OG-IMG-MISSING", file=relf, detail="缺 og:image（社交分享卡片缺图）。"))
            rep.metrics["og_missing"] += 1
        else:
            og = om.group(1).strip()
            if og and not og.startswith(("http://", "https://", "//", "data:")):
                og_clean = re.sub(r"[?#].*$", "", og)
                abs_p = os.path.normpath(os.path.join(os.path.dirname(f), og_clean))
                if not os.path.exists(abs_p):
                    rep.add(Finding("WARN", "OG-IMG-BROKEN", file=relf, detail=f"og:image 指向不存在资源 {og}。"))
                    rep.metrics["og_broken"] += 1
        # 共享资源
        for m in ASSET_REF_PAT.finditer(html):
            aref = m.group(1)
            abs_p = os.path.normpath(os.path.join(site_root, aref.lstrip("/")))
            if not os.path.exists(abs_p):
                rep.add(Finding("WARN", "ASSET-MISSING", file=relf, detail=f"引用本地资源不存在 {aref}。"))
                rep.metrics["asset_missing"] += 1

    total = (rep.metrics["og_missing"] + rep.metrics["og_broken"] + rep.metrics["css_broken"]
             + rep.metrics["asset_missing"] + rep.metrics["css_unbalanced"])
    if total == 0:
        rep.status = "PASS"
        rep.summary = f"抽样 {len(sample)} 页：OG 图/CSS/共享资源/品牌 token 均正常。"
    else:
        rep.status = "WARN"
        rep.summary = (f"抽样 {len(sample)} 页发现 {total} 处设计资产告警"
                       f"（og缺 {rep.metrics['og_missing']} / og坏 {rep.metrics['og_broken']} / "
                       f"资源缺失 {rep.metrics['asset_missing']} / css {rep.metrics['css_unbalanced']+rep.metrics['css_broken']}）。")
    rep.elapsed_s = round(time.time() - t0, 2)
    return rep
