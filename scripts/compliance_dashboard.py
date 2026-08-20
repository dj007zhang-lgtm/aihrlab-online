#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合规仪表盘生成器 (compliance_dashboard.py)
读取 reports/compliance/audit-log.jsonl（历史）+ latest-summary.json（最新），
生成单文件 HTML 仪表盘：合规率趋势、维度分布、违规明细。
用法：python3 scripts/compliance_dashboard.py
输出：tools/compliance-dashboard.html
"""
import os
import json
import datetime

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPLIANCE_DIR = os.path.join(SITE_ROOT, "reports", "compliance")
LOG_PATH = os.path.join(COMPLIANCE_DIR, "audit-log.jsonl")
LATEST = os.path.join(COMPLIANCE_DIR, "latest-summary.json")
OUT = os.path.join(SITE_ROOT, "tools", "compliance-dashboard.html")


def load_history():
    rows = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def main():
    history = load_history()
    latest = {}
    if os.path.exists(LATEST):
        latest = json.load(open(LATEST, encoding="utf-8"))

    # 趋势数据
    dates = [r["run_date"] for r in history]
    rates = [r["compliance_rate"] for r in history]
    scores = [r["avg_score"] for r in history]
    crit = [r["critical_total"] for r in history]
    fail = [r["fail_total"] for r in history]
    warn = [r["warn_total"] for r in history]

    # 最新维度分布（从 latest.articles 聚合）
    dim_counts = {"专业性": 0, "真实性": 0, "调性合规": 0}
    if latest.get("articles"):
        for a in latest["articles"]:
            for f in a["findings"]:
                rule = f["rule"]
                if "信源" in rule or "deny" in rule:
                    dim_counts["专业性"] += 1
                elif "事实" in rule or "绝对化" in rule:
                    dim_counts["真实性"] += 1
                else:
                    dim_counts["调性合规"] += 1

    # 需复核清单
    review_list = [a for a in latest.get("articles", []) if a.get("needs_review")]

    # 人工复核队列 HTML（避免嵌套 f-string）
    if review_list:
        rows = []
        for a in review_list:
            pills = " ".join(
                f'<span class="pill {f["level"].lower()}">{f["rule"]}</span>'
                for f in a["findings"] if f["level"] in ("CRITICAL", "FAIL")
            )
            rows.append(
                f'<tr><td><a href="/articles/{a["slug"]}.html">{a["title"]}</a></td>'
                f'<td>{a["category"]}</td><td>{a["score"]}</td><td>{pills}</td></tr>'
            )
        review_html = (
            '<table><tr><th>文章</th><th>分类</th><th>合规分</th><th>问题</th></tr>'
            + "".join(rows)
            + "</table>"
        )
    else:
        review_html = '<p class="empty">✅ 当前无 CRITICAL / FAIL 项，无需紧急复核。</p>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>内容合规审核仪表盘 · AIHR数智引擎</title>
<style>
  :root {{
    --bg: #0B0C0E; --surface: #16191D; --text: #ECEAE4; --muted: #9a958c;
    --accent: #6F9A3C; --warn: #C9A227; --fail: #C44536; --crit: #B22222;
    --border: #2a2e34;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; padding: 32px; line-height: 1.6; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  .sub {{ color: var(--muted); font-size: 13px; margin-bottom: 28px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
  .card .v {{ font-size: 32px; font-weight: 700; }}
  .card .l {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
  .card.ok .v {{ color: var(--accent); }}
  .card.warn .v {{ color: var(--warn); }}
  .card.fail .v {{ color: var(--fail); }}
  .panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
  .panel h2 {{ font-size: 16px; margin-bottom: 16px; }}
  svg {{ width: 100%; height: 280px; }}
  .bar {{ display: flex; height: 28px; border-radius: 6px; overflow: hidden; margin: 8px 0; }}
  .bar > div {{ display: flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 500; }}
  a {{ color: var(--accent); text-decoration: none; }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; }}
  .pill.crit {{ background: var(--crit); color: #fff; }}
  .pill.fail {{ background: var(--fail); color: #fff; }}
  .pill.warn {{ background: var(--warn); color: #000; }}
  .empty {{ color: var(--muted); font-size: 13px; padding: 12px 0; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>内容合规审核仪表盘</h1>
  <p class="sub">自动化内容主理人 · 三维审核（专业性 / 真实性 / 调性合规）· 更新于 {latest.get('run_date','-')}</p>

  <div class="cards">
    <div class="card ok"><div class="v">{latest.get('compliance_rate',0)}%</div><div class="l">合规率（无 CRITICAL）</div></div>
    <div class="card"><div class="v">{latest.get('avg_score',0)}</div><div class="l">平均合规分 / 100</div></div>
    <div class="card fail"><div class="v">{latest.get('critical_total',0)}</div><div class="l">CRITICAL 违规</div></div>
    <div class="card warn"><div class="v">{latest.get('warn_total',0)}</div><div class="l">WARN 待复核</div></div>
  </div>

  <div class="panel">
    <h2>合规率与平均分趋势</h2>
    <svg viewBox="0 0 1000 280" preserveAspectRatio="none">
      <line x1="40" y1="240" x2="980" y2="240" stroke="#2a2e34" stroke-width="1"/>
      <line x1="40" y1="40" x2="40" y2="240" stroke="#2a2e34" stroke-width="1"/>
      {"".join(
        f'<circle cx="{60 + i*((920)/max(len(rates)-1,1))}" cy="{240 - (rates[i]/100)*200}" r="4" fill="#6F9A3C"/>'
        + f'<line x1="{60 + i*((920)/max(len(rates)-1,1))}" y1="{240 - (rates[i]/100)*200}" '
          f'x2="{60 + (i+1)*((920)/max(len(rates)-1,1))}" y2="{240 - (rates[min(i+1,len(rates)-1)]/100)*200}" stroke="#6F9A3C" stroke-width="2"/>'
        for i in range(len(rates))
      )}
      {"".join(
        f'<circle cx="{60 + i*((920)/max(len(scores)-1,1))}" cy="{240 - (scores[i]/100)*200}" r="3" fill="#4a90d9"/>'
        for i in range(len(scores))
      )}
    </svg>
    <p class="sub" style="margin-top:8px">绿=合规率% · 蓝=平均合规分 · 横轴=扫描批次（{len(rates)} 次）</p>
  </div>

  <div class="panel">
    <h2>违规分布（按维度）</h2>
    <div class="bar">
      <div style="width:{dim_counts['专业性']/max(sum(dim_counts.values()),1)*100}%;background:var(--crit)">{dim_counts['专业性']} 专业性</div>
      <div style="width:{dim_counts['真实性']/max(sum(dim_counts.values()),1)*100}%;background:var(--warn)">{dim_counts['真实性']} 真实性</div>
      <div style="width:{dim_counts['调性合规']/max(sum(dim_counts.values()),1)*100}%;background:var(--fail)">{dim_counts['调性合规']} 调性合规</div>
    </div>
    <p class="sub">基于最新一次扫描的 {sum(dim_counts.values())} 条发现聚合</p>
  </div>

  <div class="panel">
    <h2>人工复核队列（CRITICAL / FAIL）</h2>
    {review_html}
  </div>

  <p class="sub">数据来源：reports/compliance/audit-log.jsonl · 由 content_compliance_auditor.py 驱动</p>
</div>
</body>
</html>"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 仪表盘已生成: {OUT}")
    print(f"  历史批次: {len(history)} 次 | 当前需复核: {len(review_list)} 篇")


if __name__ == "__main__":
    main()
