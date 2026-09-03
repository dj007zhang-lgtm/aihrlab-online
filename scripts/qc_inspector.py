#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QC Inspector · 审美与品控 Sub-Agent 每日巡检脚本

用法:
  python3 scripts/qc_inspector.py --daily              # 每日巡检
  python3 scripts/qc_inspector.py --report --date YYYY-MM-DD  # 生成报告
  python3 scripts/qc_inspector.py --summary            # 输出摘要
"""
import os
import sys
import re
import json
import subprocess
import glob
from datetime import datetime, timedelta
from pathlib import Path

SITE_ROOT = Path(__file__).parent.parent
ARTICLES_DIR = SITE_ROOT / "articles"
REPORTS_DIR = SITE_ROOT / "reports" / "qc-reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 严重度定义
SEVERITY = {
    "P0": "致命",
    "P1": "严重", 
    "P2": "一般",
    "P3": "轻微",
}

# 问题分类
CATEGORY = {
    "T": "技术",
    "C": "内容",
    "N": "调性",
    "S": "SEO",
    "M": "稳定性",
}


def run_gate(script, args="--all"):
    """运行检查脚本，返回 (exit_code, stdout)"""
    script_path = SITE_ROOT / "scripts" / script
    if not script_path.exists():
        return 1, f"脚本不存在: {script_path}"
    
    result = subprocess.run(
        [sys.executable, str(script_path), args],
        capture_output=True,
        text=True,
        cwd=str(SITE_ROOT)
    )
    return result.returncode, result.stdout


def parse_taste_gate(output):
    """解析 taste_gate 输出，提取问题"""
    issues = []
    for line in output.split('\n'):
        if line.startswith('   x '):
            # FAIL
            match = re.search(r'x (.+)', line)
            if match:
                issues.append({
                    "severity": "P1",
                    "type": "N",
                    "message": match.group(1).strip(),
                    "detail": line.strip()
                })
        elif line.startswith('   ! '):
            # WARN
            match = re.search(r'! (.+)', line)
            if match:
                issues.append({
                    "severity": "P2",
                    "type": "N",
                    "message": match.group(1).strip(),
                    "detail": line.strip()
                })
    return issues


def parse_quality_gate(output):
    """解析 quality_gate 输出，提取问题"""
    issues = []
    lines = output.split('\n')
    
    current_file = None
    for i, line in enumerate(lines):
        # 检测文件
        file_match = re.search(r'\[FAIL\] (.+\.html)', line)
        if file_match:
            current_file = file_match.group(1)
            continue
        
        # 检测问题
        if current_file and ('x ' in line or 'FAIL' in line):
            match = re.search(r'\s+x (.+)', line)
            if match:
                msg = match.group(1).strip()
                # 分类
                if "二维码" in msg or "内链" in msg or "结构" in msg or "H1" in msg:
                    cat = "T"
                    sev = "P0"
                elif "品味" in msg or "标题" in msg or "调性" in msg:
                    cat = "N"
                    sev = "P1"
                elif "SEO" in msg or "sitemap" in msg:
                    cat = "S"
                    sev = "P2"
                else:
                    cat = "T"
                    sev = "P2"
                
                issues.append({
                    "severity": sev,
                    "type": cat,
                    "file": current_file,
                    "message": msg,
                    "detail": line.strip()
                })
                current_file = None
    
    return issues


def check_title_issues():
    """专项检查标题问题（R-16, R-17）

    口径（2026-09-03 校准）：
    - <title> 允许带「 | AIHR数智引擎」品牌后缀；页面展示标题（h1/og:title/twitter:title）必须干净。
    - R-16：h1 / og:title / twitter:title 不得含品牌后缀。
    - R-17：h1 == og:title == twitter:title；<title> == h1 或 h1 + " | AIHR数智引擎"。
    - 标题长度按页面展示标题（h1）判定，避免 suffix 干扰。
    """
    issues = []
    BRAND_SUFFIX = " | AIHR数智引擎"
    SUFFIX_VARIANTS = ["| AIHR数智引擎", "｜AIHR数智引擎"]

    for html_file in sorted(ARTICLES_DIR.glob("*.html")):
        content = html_file.read_text(encoding="utf-8")

        # 提取各字段
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        h1_match = re.search(r'<h1[^>]*>([^<]+)</h1>', content, re.IGNORECASE)
        h1 = h1_match.group(1).strip() if h1_match else ""

        og_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', content, re.IGNORECASE)
        og_title = og_match.group(1).strip() if og_match else ""

        tw_match = re.search(r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)', content, re.IGNORECASE)
        tw_title = tw_match.group(1).strip() if tw_match else ""

        # 检查 R-16: 页面展示标题含品牌后缀
        for field_name, field_value in [("h1", h1), ("og:title", og_title), ("twitter:title", tw_title)]:
            if any(s in field_value for s in SUFFIX_VARIANTS):
                issues.append({
                    "severity": "P1",
                    "type": "N",
                    "file": f"articles/{html_file.name}",
                    "message": f"{field_name} 含品牌后缀: {field_value}",
                    "rule": "R-16"
                })

        # 检查 R-17: title 与 h1 的关系
        if title and h1:
            expected_title = h1 + BRAND_SUFFIX
            if title != h1 and title != expected_title:
                issues.append({
                    "severity": "P1",
                    "type": "N",
                    "file": f"articles/{html_file.name}",
                    "message": f"<title> 与 h1 不一致: title='{title}' h1='{h1}'",
                    "rule": "R-17"
                })

        # 检查 og:title / twitter:title 与 h1 一致性
        if h1:
            for field_name, field_value in [("og:title", og_title), ("twitter:title", tw_title)]:
                if field_value and field_value != h1:
                    issues.append({
                        "severity": "P1",
                        "type": "N",
                        "file": f"articles/{html_file.name}",
                        "message": f"{field_name} ≠ h1: {field_value} / h1={h1}",
                        "rule": "R-17"
                    })

        # 检查标题长度（按页面展示标题 h1，避免 suffix 干扰）
        display_title = h1 or title
        if len(display_title) > 60:
            issues.append({
                "severity": "P1",
                "type": "N",
                "file": f"articles/{html_file.name}",
                "message": f"展示标题过长 ({len(display_title)}字): {display_title}",
                "rule": "T1"
            })
        elif len(display_title) < 15 and display_title:
            issues.append({
                "severity": "P3",
                "type": "N",
                "file": f"articles/{html_file.name}",
                "message": f"展示标题过短 ({len(display_title)}字): {display_title}",
                "rule": "T1"
            })
    
    return issues


def check_related_reading():
    """检查延伸阅读链接截断问题（Gate 10）"""
    issues = []
    
    for html_file in sorted(ARTICLES_DIR.glob("*.html")):
        content = html_file.read_text(encoding="utf-8")
        
        # 查找延伸阅读部分
        if 'related-reading' not in content and '延伸阅读' not in content:
            continue
        
        # 查找链接和目标标题
        links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', content)
        for href, text in links:
            if '/articles/' in href and href.endswith('.html'):
                # 检查链接文字是否完整（不应被截断）
                target_file = href.replace('/articles/', '').replace('.html', '')
                target_path = ARTICLES_DIR / f"{target_file}.html"
                if target_path.exists():
                    target_content = target_path.read_text(encoding="utf-8")
                    target_h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', target_content, re.IGNORECASE)
                    target_title = target_h1.group(1).strip() if target_h1 else ""
                    
                    # 检查链接文字是否等于目标标题
                    if target_title and text.strip() != target_title:
                        # 检查是否被截断（链接文字是标题的前半部分）
                        if target_title.startswith(text.strip()):
                            issues.append({
                                "severity": "P1",
                                "type": "C",
                                "file": f"articles/{html_file.name}",
                                "message": f"延伸阅读链接截断: '{text.strip()}' vs '{target_title}'",
                                "rule": "Gate10"
                            })
    
    return issues


def generate_report(date_str=None):
    """生成质检报告"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    report_path = REPORTS_DIR / f"{date_str}.md"
    
    # 运行检查
    print("运行 quality_gate...")
    qg_code, qg_output = run_gate("quality_gate.py")
    
    print("运行 stability_guard...")
    sg_code, sg_output = run_gate("stability_guard.py")
    
    print("运行 taste_gate...")
    tg_code, tg_output = run_gate("taste_gate.py")
    
    # 专项检查
    print("检查标题问题...")
    title_issues = check_title_issues()
    
    print("检查延伸阅读...")
    rr_issues = check_related_reading()
    
    # 汇总问题
    all_issues = title_issues + rr_issues
    
    # 按严重度分组
    p0_issues = [i for i in all_issues if i["severity"] == "P0"]
    p1_issues = [i for i in all_issues if i["severity"] == "P1"]
    p2_issues = [i for i in all_issues if i["severity"] == "P2"]
    p3_issues = [i for i in all_issues if i["severity"] == "P3"]
    
    # 统计检查页数
    article_count = len(list(ARTICLES_DIR.glob("*.html")))
    
    # 生成报告
    report = f"""# QC 日报：{date_str}

## 一、巡检概览
- 检查页数：{article_count} 篇
- 发现问题：P0={len(p0_issues)}, P1={len(p1_issues)}, P2={len(p2_issues)}, P3={len(p3_issues)}
- quality_gate：{'✅ PASS' if qg_code == 0 else '❌ FAIL'}
- stability_guard：{'✅ PASS' if sg_code == 0 else '❌ FAIL'}
- taste_gate：{'✅ PASS' if tg_code == 0 else '❌ FAIL'}

## 二、问题清单
"""
    
    if p0_issues:
        report += "### P0 致命（立即修复）\n\n"
        for i, issue in enumerate(p0_issues, 1):
            report += f"| Q-{date_str.replace('-', '')[:4]}-{i:03d} | {issue['file']} | {issue['message']} | {issue.get('rule', 'N/A')} |\n"
        report += "\n"
    
    if p1_issues:
        report += "### P1 严重\n\n"
        report += "| 编号 | 文件 | 问题 | 规则 |\n|------|------|------|------|\n"
        for i, issue in enumerate(p1_issues, 1):
            report += f"| Q-{date_str.replace('-', '')[:4]}-{i:03d} | {issue['file']} | {issue['message']} | {issue.get('rule', 'N/A')} |\n"
        report += "\n"
    
    if p2_issues:
        report += "### P2 一般\n\n"
        report += "| 编号 | 文件 | 问题 | 规则 |\n|------|------|------|------|\n"
        for i, issue in enumerate(p2_issues, 1):
            report += f"| Q-{date_str.replace('-', '')[:4]}-{i:03d} | {issue['file']} | {issue['message']} | {issue.get('rule', 'N/A')} |\n"
        report += "\n"
    
    if p3_issues:
        report += "### P3 轻微\n\n"
        report += "| 编号 | 文件 | 问题 | 规则 |\n|------|------|------|------|\n"
        for i, issue in enumerate(p3_issues, 1):
            report += f"| Q-{date_str.replace('-', '')[:4]}-{i:03d} | {issue['file']} | {issue['message']} | {issue.get('rule', 'N/A')} |\n"
        report += "\n"
    
    if not all_issues:
        report += "✅ **无问题** — 所有内容符合质量标准\n\n"
    
    report += f"""## 三、双闸详情
### quality_gate
- 退出码：{qg_code}
- 输出摘要：{qg_output[-500:] if qg_output else '无输出'}

### stability_guard
- 退出码：{sg_code}
- 输出摘要：{sg_output[-300:] if sg_output else '无输出'}

### taste_gate
- 退出码：{tg_code}
- 输出摘要：{tg_output[-300:] if tg_output else '无输出'}

---
*本报告由 QC Inspector 自动生成 | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
    
    # 保存报告
    report_path = REPORTS_DIR / f"{date_str}.md"
    report_path.write_text(report, encoding="utf-8")
    
    print(f"\n报告已生成：{report_path}")
    
    # 输出摘要
    print(f"\n{'='*60}")
    print(f"QC 日报摘要：{date_str}")
    print(f"{'='*60}")
    print(f"检查页数：{article_count} 篇")
    print(f"发现问题：P0={len(p0_issues)}, P1={len(p1_issues)}, P2={len(p2_issues)}, P3={len(p3_issues)}")
    print(f"quality_gate：{'✅ PASS' if qg_code == 0 else '❌ FAIL'}")
    print(f"stability_guard：{'✅ PASS' if sg_code == 0 else '❌ FAIL'}")
    print(f"taste_gate：{'✅ PASS' if tg_code == 0 else '❌ FAIL'}")
    print(f"{'='*60}")
    
    return str(report_path), {
        "date": date_str,
        "articles": article_count,
        "p0": len(p0_issues),
        "p1": len(p1_issues),
        "p2": len(p2_issues),
        "p3": len(p3_issues),
        "qg": qg_code,
        "sg": sg_code,
        "tg": tg_code,
        "report_path": str(report_path)
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QC Inspector · 审美与品控 Sub-Agent")
    parser.add_argument("--daily", action="store_true", help="每日巡检")
    parser.add_argument("--report", action="store_true", help="生成报告")
    parser.add_argument("--date", type=str, help="报告日期 (YYYY-MM-DD)")
    parser.add_argument("--summary", action="store_true", help="输出摘要")
    
    args = parser.parse_args()
    
    if args.daily or args.report:
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        report_path, stats = generate_report(date_str)
        print(f"\n报告路径：{report_path}")
        sys.exit(0 if stats["p0"] == 0 and stats["qg"] == 0 and stats["sg"] == 0 and stats["tg"] == 0 else 1)
    
    elif args.summary:
        # 快速摘要
        print("运行 quality_gate...")
        qg_code, _ = run_gate("quality_gate.py")
        print("运行 stability_guard...")
        sg_code, _ = run_gate("stability_guard.py")
        print("运行 taste_gate...")
        tg_code, _ = run_gate("taste_gate.py")
        
        print(f"\n{'='*40}")
        print("QC 快速摘要")
        print(f"{'='*40}")
        print(f"quality_gate：{'✅ PASS' if qg_code == 0 else '❌ FAIL'}")
        print(f"stability_guard：{'✅ PASS' if sg_code == 0 else '❌ FAIL'}")
        print(f"taste_gate：{'✅ PASS' if tg_code == 0 else '❌ FAIL'}")
        print(f"{'='*40}")
    
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
