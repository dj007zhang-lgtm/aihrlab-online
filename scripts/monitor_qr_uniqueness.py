#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor_qr_uniqueness.py —— 二维码唯一性监控脚本（CI / 自动化友好）

用途：
  - 定期（周度自动化）扫描全站 HTML，确认「每页仅一个公众号二维码」。
  - 退出码 0 = 健康；非 0 = 发现违规（供告警 / 自动化判定失败）。
  - 可独立运行，也可被 quality_gate.Gate 0 复用同一判定逻辑（单一事实源）。

判定规则（与 quality_gate.gate_qr_uniqueness 保持一致）：
  1. 同一 HTML 文件内 .article-footer-qr 出现次数必须 == 1；
  2. 同一 HTML 文件内 .footer-col--qr 出现次数必须 == 0（全站禁止页脚二维码）；
  3. 两者不得共存。

用法：
  python3 scripts/monitor_qr_uniqueness.py            # 扫描全站，文本报告+退出码
  python3 scripts/monitor_qr_uniqueness.py --json     # 输出 JSON（供自动化解析）
"""
import os
import sys
import json

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scan():
    issues = []
    total = 0
    for root, _, names in os.walk(SITE_ROOT):
        # 跳过非站点目录
        if any(seg in root for seg in ("/node_modules", "/.git", "/.workbuddy")):
            continue
        for name in names:
            if not name.endswith(".html"):
                continue
            path = os.path.join(root, name)
            total += 1
            try:
                html = open(path, encoding="utf-8").read()
            except Exception:
                continue
            rel = os.path.relpath(path, SITE_ROOT)
            n_article = html.count('class="article-footer-qr"')
            n_footer = html.count('class="footer-col footer-col--qr"')
            if n_article > 1:
                issues.append({"file": rel, "type": "duplicate_article_qr",
                               "count": n_article, "msg": f".article-footer-qr 出现 {n_article} 次，必须恰好 1 个"})
            if n_footer > 0:
                issues.append({"file": rel, "type": "footer_qr_present",
                               "count": n_footer, "msg": f"站点页脚二维码 .footer-col--qr 出现 {n_footer} 次，全站禁止"})
            if n_article >= 1 and n_footer >= 1:
                issues.append({"file": rel, "type": "both_present",
                               "msg": "同一页同时出现 .article-footer-qr 与 .footer-col--qr"})
    return total, issues


def main():
    as_json = "--json" in sys.argv
    total, issues = scan()
    if as_json:
        print(json.dumps({"scanned": total, "violations": len(issues),
                          "healthy": len(issues) == 0, "issues": issues},
                         ensure_ascii=False, indent=2))
    else:
        print(f"扫描 HTML 文件: {total}")
        if not issues:
            print("✅ 二维码唯一性健康：全站每页仅一个公众号二维码。")
        else:
            print(f"❌ 发现 {len(issues)} 处二维码违规：")
            for it in issues:
                print(f"  - {it['file']} | {it['msg']}")
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
