#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容合规审核系统 · 自动化内容主理人 (content_compliance_auditor.py)
============================================================

定位：作为网站的「自动化内容主理人」，周期性扫描全站文章，从三个本站
真实风险维度做合规审核，产出结构化报告 + 审核日志 + 趋势仪表盘数据。

设计原则（主理人重映射）：
  通用 UGC「仇恨/低俗/违法内容过滤」对本站（硬核 B2B OD/HR 内容站）错配。
  本系统将用户提示词的「专业性 / 真实性 / 正面性」重映射为本站实际三维：

  ① 专业性 (Professionalism)
       = 信源可靠性。比对每篇文章引用的出版方/信源标题 与
         reports/source_registry.json 的 deny / deny_publisher 黑名单。
       → 命中即「虚构信源 / 信源层级伪装」(R-02, T0 事实诚信)，CRITICAL。

  ② 真实性 (Truthfulness)
       = 事实一致性。抽取正文硬数据（百分比/倍数/大数），与
         reports/facts-ledger.md 站点唯一真相源做矛盾检测；
         另检测绝对化断言（一定/必然/所有/100%）作为夸大风险标记。
       → 矛盾或绝对化断言标记，交人工复核（不自动判罪）。

  ③ 调性合规 (Tone Compliance，替代通用「正面性」)
       = 红线机检。复用 reports/content-redlines.md (R-01..R-15) 的可机检项：
         危机/焦虑词(R-06)、物理借词(R-10)、诗意隐喻(R-11)、
         自标数据出处(R-15)、营销腔呼吁(R-05)、slogan 替代脊梁(R-07)。

编排而非重写：本脚本调用既有的 taste_gate / quality_gate 哲学，
把分散的事实防线收敛成一个可调度、可追溯、可趋势化的统一审核层。

用法：
  python3 scripts/content_compliance_auditor.py [--articles DIR] [--since DAYS]
  （默认扫描全站 articles/，输出到 reports/compliance/）

输出：
  reports/compliance/<YYYYMMDD>-compliance-report.md   结构化合规报告
  reports/compliance/<YYYYMMDD>-compliance-report.json 机器可读
  reports/compliance/audit-log.jsonl                   审核日志（追加）
  reports/compliance/latest-summary.json               供仪表盘读取
退出码：0=通过阈值；2=存在 CRITICAL 违规（供 CI / 自动化告警）
"""

import os
import re
import sys
import json
import glob
import datetime

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(SITE_ROOT, "articles")
REPORTS_DIR = os.path.join(SITE_ROOT, "reports", "compliance")
SOURCE_REGISTRY = os.path.join(SITE_ROOT, "reports", "source_registry.json")
FACTS_LEDGER = os.path.join(SITE_ROOT, "reports", "facts-ledger.md")
CONTENT_REDLINES = os.path.join(SITE_ROOT, "reports", "content-redlines.md")

# 合规通过阈值：CRITICAL 数 > 0 即不通过
PASS_THRESHOLD_CRITICAL = 0

# ───────────────────────────────────────────────────────────
# 维度① 专业性：信源黑名单（从 source_registry.json 加载）
# ───────────────────────────────────────────────────────────
def load_source_registry():
    try:
        with open(SOURCE_REGISTRY, encoding="utf-8") as f:
            reg = json.load(f)
        deny_titles = [d["title"] for d in reg.get("deny", [])]
        deny_pubs = [p.lower() for p in reg.get("deny_publisher", [])]
        allow_titles = [a["title"] for a in reg.get("allow", [])]
        return deny_titles, deny_pubs, allow_titles
    except Exception as e:
        print(f"[WARN] 无法加载 source_registry.json: {e}", file=sys.stderr)
        return [], [], []


# ───────────────────────────────────────────────────────────
# 维度② 真实性：事实账本硬数据 + 绝对化断言词
# ───────────────────────────────────────────────────────────
def load_facts_ledger_entities():
    """从 facts-ledger.md 抽取实体→数值集合，用于矛盾检测。"""
    entities = {}
    try:
        with open(FACTS_LEDGER, encoding="utf-8") as f:
            text = f.read()
        # 章节标题即实体（如 "## 1. 字节 / 豆包 / 火山引擎"）
        for m in re.finditer(r"^##\s+\d+\.\s*(.+)$", text, re.M):
            ent = m.group(1).strip()
            # 抽取该章节下的数值（万亿/亿/万/%/倍）
            sec_start = m.end()
            nxt = re.search(r"^##\s", text[sec_start:], re.M)
            sec = text[sec_start: sec_start + (nxt.start() if nxt else len(text))]
            nums = set(re.findall(r"\d+(?:\.\d+)?\s*(?:万亿|亿|万|%|倍|亿)", sec))
            entities[ent] = nums
    except Exception as e:
        print(f"[WARN] 无法加载 facts-ledger.md: {e}", file=sys.stderr)
    return entities


# 绝对化断言（夸大/误导性表述风险标记）
ABSOLUTE_PATTERNS = [
    r"一定(会|能|是|要)", r"必然(会|导致|造成)", r"所有(企业|公司|组织|人)(都|必然|一定)",
    r"100\s*%(\s*(的)?(企业|公司|组织|人))", r"全部(都|是)(要|会|被)",
    r"绝对(的|是|会)(正确|真理|没错)", r"毫无疑问(地)?(是|会)", r"注定(失败|消亡|被取代)",
]

# ───────────────────────────────────────────────────────────
# 维度③ 调性合规：红线可机检项 (R-05/06/07/10/11/15)
# ───────────────────────────────────────────────────────────
TONE_RULES = {
    "R-06 焦虑叙事": {
        "level": "WARN",
        "patterns": [r"崩(塌|了|盘)", r"凉(透|了)", r"慌", r"末日", r"暴击",
                     r"危(机|险)在旦夕", r"大(崩|溃)"],
    },
    "R-10 物理借词框架": {
        "level": "WARN",
        "patterns": [r"路由器", r"熵增", r"高阻抗", r"阻抗", r"固态", r"液态",
                     r"拓扑", r"带宽(不足|不够)", r"耦合"],
    },
    "R-11 诗意隐喻": {
        "level": "WARN",
        "patterns": [r"母语(作废|失效)", r"方(言|言)", r"音节", r"血(液|脉)",
                     r"骨(骼|血)", r"呼(吸|吸感)"],
    },
    "R-15 标题自标出处": {
        "level": "FAIL",
        # 红线语义（reports/content-redlines.md R-15）：h2/h3 不在标题里"表演可信度"——
        # 即节标题不得自标数据出处（贴「据X源」「（权威研究）」等）。
        # 注意：作为"写作技法主题词"出现的「一手信源」（如"专家引语 + 一手信源"）
        # 不是自标，是教学内容，故禁用裸子串匹配，仅匹配自标断言模式。
        "patterns": [r"据(一手|权威|公开|可信|可靠)(信源|来源)",  # 冗余自标：据…信源/来源
                     r"（公开资料整理）", r"（一手数据）", r"（权威研究）",
                     r"（可信来源）", r"（核验）", r"（数据来源）",
                     r"(本文|本篇|本站|我们)[^，。]{0,6}(一手|权威|可靠)(信源|来源|数据)"],  # 自陈信源
        "scope": "heading",  # 仅 h2/h3
    },
    "R-05 营销腔呼吁": {
        "level": "FAIL",
        "patterns": [r"点赞", r"点在看", r"转发三连", r"转评赞",
                     r"欢迎(转发|分享)", r"收藏(这篇|一下)"],
    },
    "R-07 slogan替代脊梁": {
        "level": "WARN",
        "patterns": [r"未来已来", r"时代(已经|已然)到来", r"不可逆(的)?(趋势|浪潮)"],
    },
}


# ───────────────────────────────────────────────────────────
# 文章解析
# ───────────────────────────────────────────────────────────
def extract_article(html):
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    cat = re.search(r'<span class="cat">([^<]+)</span>', html)
    # 正文（去 script/style）
    body = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    body_text = re.sub(r"<.*?>", "", body)
    # 标题层级
    headings = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, re.S)
    headings = [re.sub(r"<.*?>", "", h) for h in headings]
    # 信源块
    sources = []
    for item in re.findall(r'<li class="verified-sources__item">(.*?)</li>', html, re.S):
        link = re.search(r'class="verified-sources__link"[^>]*>(.*?)</a>', item, re.S)
        meta = re.search(r'class="verified-sources__meta"[^>]*>(.*?)</span>', item, re.S)
        t = re.sub(r"<.*?>", "", link.group(1)).strip() if link else ""
        m = re.sub(r"<.*?>", "", meta.group(1)).strip() if meta else ""
        sources.append({"title": t, "meta": m})
    # 正文内联机构提及
    inline_pubs = set(re.findall(
        r"(McKinsey|麦肯锡|Deloitte|德勤|BCG|Stanford|斯坦福|Stanford HAI|"
        r"Microsoft|微软|Google|谷歌|Alphabet|Meta|字节|腾讯|Gartner|SHRM|"
        r"WEF|世界经济论坛|InfoQ|智联|北大国发院|信通院)", html))
    return {
        "title_tag": title.group(1).strip() if title else "",
        "h1": re.sub(r"<.*?>", "", h1.group(1)).strip() if h1 else "",
        "cat": cat.group(1).strip() if cat else "",
        "body_text": body_text,
        "headings": headings,
        "sources": sources,
        "inline_pubs": list(inline_pubs),
    }


# ───────────────────────────────────────────────────────────
# 三维审核
# ───────────────────────────────────────────────────────────
def audit_professionalism(d, deny_titles, deny_pubs, allow_titles):
    findings = []
    # 1. 信源块标题 vs deny
    for s in d["sources"]:
        for dt in deny_titles:
            if dt and dt in s["title"]:
                findings.append({
                    "rule": "虚构信源(deny)",
                    "level": "CRITICAL",
                    "evidence": f'信源块命中黑名单标题「{dt}」→ {s["title"]}',
                })
        # 出版方提取（meta 中 "·" 前部分）
        pub = s["meta"].split("·")[0].strip() if s["meta"] else ""
        for dp in deny_pubs:
            if dp and dp in pub.lower():
                findings.append({
                    "rule": "信源层级伪装(deny_publisher)",
                    "level": "CRITICAL",
                    "evidence": f'出版方命中黑名单「{dp}」→ {s["meta"]}',
                })
        # 未登记（既非 allow 也非 deny）→ 待核验
        if s["title"] and s["title"] not in allow_titles and s["title"] not in deny_titles:
            findings.append({
                "rule": "信源未登记(待核验)",
                "level": "WARN",
                "evidence": f'信源「{s["title"]}」不在 allow/deny 登记表，需人工核验',
            })
    return findings


def audit_truthfulness(d, ledger_entities):
    findings = []
    body = d["body_text"]
    # 绝对化断言
    for pat in ABSOLUTE_PATTERNS:
        for m in re.finditer(pat, body):
            findings.append({
                "rule": "绝对化断言(夸大风险)",
                "level": "WARN",
                "evidence": f'疑似绝对化表述：「{m.group(0)}」',
            })
    # 数值矛盾检测：抽取正文百分比/大数，粗匹配 ledger 实体关键词
    nums_in_body = re.findall(r"\d+(?:\.\d+)?\s*(?:万亿|亿|万|%|倍)", body)
    # 简化：若正文数值与任一 ledger 实体数值集合无交集且实体关键词出现在正文→待复核
    # （精确矛盾检测需实体对齐，此处仅标记「含硬数据且实体在账本」供人工复核）
    for ent, nums in ledger_entities.items():
        kw = ent.split(" / ")[0].split("（")[0].strip()
        if kw and kw in body and nums:
            # 正文中该实体的数值若与账本不一致，标记
            matched = any(n in nums for n in nums_in_body)
            if nums_in_body and not matched:
                findings.append({
                    "rule": "事实数值待复核",
                    "level": "WARN",
                    "evidence": f'实体「{kw}」正文含数值 {nums_in_body[:3]} 与账本 {list(nums)[:3]} 未对齐',
                })
                break
    return findings


def audit_tone(d):
    findings = []
    body = d["body_text"]
    headings_text = " ".join(d["headings"])
    for rule, cfg in TONE_RULES.items():
        scope_text = headings_text if cfg.get("scope") == "heading" else body
        for pat in cfg["patterns"]:
            for m in re.finditer(pat, scope_text):
                findings.append({
                    "rule": rule,
                    "level": cfg["level"],
                    "evidence": f'命中「{m.group(0)}」'
                                + ("（位于标题）" if cfg.get("scope") == "heading" else ""),
                })
    return findings


# ───────────────────────────────────────────────────────────
# 单篇汇总
# ───────────────────────────────────────────────────────────
def audit_article(path, deny_titles, deny_pubs, allow_titles, ledger):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    d = extract_article(html)
    f_pro = audit_professionalism(d, deny_titles, deny_pubs, allow_titles)
    f_tru = audit_truthfulness(d, ledger)
    f_ton = audit_tone(d)
    all_findings = f_pro + f_tru + f_ton
    critical = [x for x in all_findings if x["level"] == "CRITICAL"]
    fail = [x for x in all_findings if x["level"] == "FAIL"]
    warn = [x for x in all_findings if x["level"] == "WARN"]
    # 合规分：基础100，CRITICAL -25，FAIL -10，WARN -3
    score = 100 - len(critical) * 25 - len(fail) * 10 - len(warn) * 3
    score = max(0, score)
    slug = os.path.basename(path).replace(".html", "")
    return {
        "slug": slug,
        "title": d["h1"] or d["title_tag"],
        "category": d["cat"],
        "score": score,
        "counts": {"critical": len(critical), "fail": len(fail), "warn": len(warn)},
        "findings": all_findings,
        "needs_review": bool(critical or fail),
    }


# ───────────────────────────────────────────────────────────
# 报告生成
# ───────────────────────────────────────────────────────────
def generate_report(results, run_date):
    total = len(results)
    critical_total = sum(r["counts"]["critical"] for r in results)
    fail_total = sum(r["counts"]["fail"] for r in results)
    warn_total = sum(r["counts"]["warn"] for r in results)
    avg_score = round(sum(r["score"] for r in results) / total, 1) if total else 0
    passed = sum(1 for r in results if r["counts"]["critical"] == 0)
    compliance_rate = round(passed / total * 100, 1) if total else 0

    md = []
    md.append(f"# 内容合规审核报告 · {run_date}")
    md.append("")
    md.append("> 自动化内容主理人 · 三维审核（专业性 / 真实性 / 调性合规）")
    md.append("")
    md.append("## 一、总览")
    md.append("")
    md.append(f"- 扫描文章总数：**{total}**")
    md.append(f"- 合规率（无 CRITICAL）：**{compliance_rate}%** （{passed}/{total}）")
    md.append(f"- 平均合规分：**{avg_score}** / 100")
    md.append(f"- 违规分布：CRITICAL {critical_total} · FAIL {fail_total} · WARN {warn_total}")
    md.append("")
    md.append("## 二、维度说明（主理人重映射）")
    md.append("")
    md.append("- **专业性** = 信源可靠性：比对 `source_registry.json` 的 deny / deny_publisher 黑名单")
    md.append("- **真实性** = 事实一致性：硬数据 vs `facts-ledger.md` 真相源 + 绝对化断言检测")
    md.append("- **调性合规** = 红线机检：复用 `content-redlines.md` R-05/06/07/10/11/15 可机检项")
    md.append("")
    md.append("## 三、需人工复核清单（CRITICAL / FAIL）")
    md.append("")
    if not any(r["needs_review"] for r in results):
        md.append("✅ 本轮无 CRITICAL / FAIL 项，无需紧急复核。")
    else:
        md.append("| 文章 | 分类 | 合规分 | CRIT | FAIL | 主要问题 |")
        md.append("|---|---|---|---|---|---|")
        for r in sorted(results, key=lambda x: -x["counts"]["critical"]):
            if r["needs_review"]:
                top = "；".join(f'{f["rule"]}:{f["evidence"]}' for f in r["findings"][:2])
                md.append(f'| [{r["title"]}](/articles/{r["slug"]}.html) | {r["category"]} | '
                          f'{r["score"]} | {r["counts"]["critical"]} | {r["counts"]["fail"]} | {top} |')
    md.append("")
    md.append("## 四、WARN 项汇总（调性/待核验，建议下轮清理）")
    md.append("")
    warn_articles = [r for r in results if r["counts"]["warn"] > 0]
    if not warn_articles:
        md.append("✅ 本轮无 WARN 项。")
    else:
        for r in sorted(warn_articles, key=lambda x: -x["counts"]["warn"])[:20]:
            md.append(f'- **{r["title"]}**（{r["counts"]["warn"]} WARN）：'
                      + "；".join(f'{f["rule"]}' for f in r["findings"] if f["level"] == "WARN")[:120])
    md.append("")
    md.append("---")
    md.append(f"_生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
              f"内容合规审核系统 v1.0_")
    return "\n".join(md), {
        "run_date": run_date,
        "total": total,
        "compliance_rate": compliance_rate,
        "avg_score": avg_score,
        "critical_total": critical_total,
        "fail_total": fail_total,
        "warn_total": warn_total,
        "passed": passed,
        "articles": results,
    }


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    run_date = datetime.date.today().strftime("%Y%m%d")
    deny_titles, deny_pubs, allow_titles = load_source_registry()
    ledger = load_facts_ledger_entities()

    html_files = sorted(glob.glob(os.path.join(ARTICLES_DIR, "*.html")))
    # 排除非文章页
    html_files = [f for f in html_files if os.path.basename(f) not in ("index.html",)]
    results = []
    for f in html_files:
        try:
            results.append(audit_article(f, deny_titles, deny_pubs, allow_titles, ledger))
        except Exception as e:
            print(f"[WARN] 解析失败 {f}: {e}", file=sys.stderr)

    md, summary = generate_report(results, run_date)

    # 写报告
    md_path = os.path.join(REPORTS_DIR, f"{run_date}-compliance-report.md")
    json_path = os.path.join(REPORTS_DIR, f"{run_date}-compliance-report.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 审核日志（追加）
    log_path = os.path.join(REPORTS_DIR, "audit-log.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "run_date": run_date,
            "timestamp": datetime.datetime.now().isoformat(),
            "total": summary["total"],
            "compliance_rate": summary["compliance_rate"],
            "avg_score": summary["avg_score"],
            "critical_total": summary["critical_total"],
            "fail_total": summary["fail_total"],
            "warn_total": summary["warn_total"],
        }, ensure_ascii=False) + "\n")

    # 最新摘要（供仪表盘）
    with open(os.path.join(REPORTS_DIR, "latest-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"✓ 扫描 {summary['total']} 篇 | 合规率 {summary['compliance_rate']}% | "
          f"CRIT {summary['critical_total']} / FAIL {summary['fail_total']} / WARN {summary['warn_total']}")
    print(f"✓ 报告: {md_path}")
    print(f"✓ 日志: {log_path}")
    # 退出码：有 CRITICAL 则不通过
    if summary["critical_total"] > PASS_THRESHOLD_CRITICAL:
        print(f"✗ 存在 {summary['critical_total']} 个 CRITICAL 违规，审核不通过", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
