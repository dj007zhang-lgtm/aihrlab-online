#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站文风去AI味监测 · 审美层机检代理 (monitor_ai_taste.py)
========================================================
回答主理人拷问：「每一篇文章是否都经过去AI味监测？」
  - 机械层（taste_gate / quality_gate Gate5）已全站覆盖，本脚本不复测。
  - 本脚本补「审美层文风 AI 味」全站机检代理：
      1. 破折号违规（纪律：破折号 0）
      2. 半角标点（纪律：半角 0；排除英文/数字合法上下文）
      3. 对称腔（AI 对称句式）
      4. 报幕句（AI 报幕引导）
      5. 匠气 coda（结尾升华套话）
      6. 翻译腔（进行+动词 / 基于…的 / 值得注意的是 / 不难看出 …）
      7. 物理借词框架（R-10）
      8. 诗意隐喻（R-11）
      9. 营销水文（R-05 扩展）
     10. 升级升华句（spine 拔高套话）
  每个信号带「首个命中样例（前后20字）」便于主理人抽样核验，避免盲信计数。

输出：reports/ai-taste-monitor-<YYYYMMDD>.json / .md
"""
import os, re, json, glob, datetime

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(SITE_ROOT, "articles")
REPORTS_DIR = os.path.join(SITE_ROOT, "reports")
INDEX_JSON = os.path.join(SITE_ROOT, "assets", "js", "article-index.json")
RUN_DATE = datetime.date.today().strftime("%Y%m%d")

CJK = r"\u4e00-\u9fff"
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

def extract(html):
    m = re.search(r'<article\b[^>]*>(.*?)</article>', html, re.S | re.I)
    body = m.group(1) if m else html
    body = re.sub(r"<(script|style|aside|footer|section)\b.*?</\1>", " ", body, flags=re.S | re.I)
    # 剔除信源区 / 延伸阅读 / 相关阅读
    body = re.sub(r'<section class="verified-sources".*?</section>', " ", body, flags=re.S | re.I)
    body = re.sub(r'延伸阅读.*?(?=<footer)', " ", body, flags=re.S)
    body = re.sub(r'<h3>相关阅读</h3>.*?(?=<footer)', " ", body, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", body)
    txt = re.sub(r"&nbsp;", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

# ── 信号定义（name -> 正则）──
SIGNALS = {
    "破折号违规": re.compile(r"——|--"),
    "半角标点": re.compile(r"[\u4e00-\u9fff][,:;?!()\[\]{}]|[,;:?!()\[\]{}][\u4e00-\u9fff]"),
    "对称腔": re.compile(r"(不是.{0,14}而是)|(既要.{0,14}也要)|(不仅.{0,14}更)|(一方面.{0,14}另一方面)|(与其.{0,14}不如)|(看似.{0,14}实则)|(从.{0,10}到.{0,10})|(无论.{0,10}都)|(越是.{0,10}越)"),
    "报幕句": re.compile(r"(接下来)|(下面我们)|(首先来看)|(本文将从)|(我们不妨)|(让我们(共同|一起)?(看|探讨|深入))|(值得注意的是)|(不难看出)|(可以发现)"),
    "匠气coda": re.compile(r"(总之，)|(总之。)|(归根结底)|(一言以蔽之)|(综上所述)|(说到底)|(说白了)|(由此可见)|(毋庸讳言)"),
    "翻译腔": re.compile(r"(进行.{0,4}(分析|研究|探讨|处理|优化|评估|设计|开发|测试|改进|调整|管理|建设|推进|落实|实施))|(基于.{0,8}的)|(在.{0,6}方面)|(对于.{0,6}来说)|(发挥着.{0,6}作用)|(扮演着.{0,6}角色)|(某种程度上)|(从某种意义)|(可以说，)|(换言之)|(具体而言)"),
    "物理借词": re.compile(r"(齿轮)|(引擎)|(燃料)|(地基)|(基石)|(土壤)|(毛细血管)|(压舱石)|(造血)|(输血)|(闭环)|(赋能)|(底座)"),
    "诗意隐喻": re.compile(r"(星辰)|(灯塔)|(航向)|(征途)|(破浪)|(远航)|(星辰大海)|(画卷)|(丰碑)|(里程碑)|(新篇章)"),
    "营销水文": re.compile(r"(干货)|(保姆级)|(一文搞懂)|(彻底搞懂)|(速收藏)|(码住)|(绝绝子)|(封神)|(yyds)|(宝藏)|(无脑冲)|(闭眼入)|(神器)|(必看)|(强烈推荐)|(不得不看)|(建议转发)"),
    "升级升华句": re.compile(r"(标志着)|(开启了.{0,6}新)|(步入)|(迈向)|(驶入)|(翻开.{0,6}新)|(见证了)|(预示着)|(必将)|(势必将)|(迎来了.{0,6}新)|(奏响)|(谱写)"),
}

def sample(txt, m):
    s = max(0, m.start() - 20)
    e = min(len(txt), m.end() + 20)
    return txt[s:e]

def main():
    idx = json.load(open(INDEX_JSON))
    def norm(u):
        b = os.path.basename(u)
        return b[:-5] if b.endswith(".html") else b
    slugs = {norm(e["url"]) for e in idx}
    results = []
    for slug in sorted(slugs):
        p = os.path.join(ARTICLES_DIR, slug + ".html")
        if not os.path.exists(p):
            continue
        html = open(p, encoding="utf-8").read()
        txt = extract(html)
        if not txt:
            continue
        rec = {"file": slug + ".html", "len": len(txt), "signals": {}, "samples": {}}
        for name, rx in SIGNALS.items():
            hits = list(rx.finditer(txt))
            if hits:
                rec["signals"][name] = len(hits)
                rec["samples"][name] = sample(txt, hits[0])
        if rec["signals"]:
            results.append(rec)
    # 汇总
    summary = {name: {"articles": 0, "total": 0} for name in SIGNALS}
    for rec in results:
        for name, c in rec["signals"].items():
            summary[name]["articles"] += 1
            summary[name]["total"] += c
    # 排序：总信号数
    results.sort(key=lambda r: sum(r["signals"].values()), reverse=True)

    out = {"run_date": RUN_DATE, "scanned": len(results), "summary": summary,
           "ranked": results}
    json.dump(out, open(os.path.join(REPORTS_DIR, f"ai-taste-monitor-{RUN_DATE}.json"), "w"),
              ensure_ascii=False, indent=2)
    # MD
    lines = [f"# 全站文风去AI味监测（审美层机检代理）· {RUN_DATE}", "",
             f"扫描已索引文章 {len(slugs)} 篇，命中任一信号 {len(results)} 篇。",
             "", "## 信号全站分布（按篇数）", ""]
    for name in SIGNALS:
        s = summary[name]
        lines.append(f"- **{name}**：{s['articles']} 篇含 / 共 {s['total']} 处")
    lines += ["", "## 高风险文章 Top 20（按信号总数）", ""]
    for rec in results[:20]:
        total = sum(rec["signals"].values())
        lines.append(f"### {rec['file']} · 信号 {total} 处（正文 {rec['len']} 字）")
        for name, c in sorted(rec["signals"].items(), key=lambda x: -x[1]):
            lines.append(f"- {name} ×{c}：`…{rec['samples'][name]}…`")
        lines.append("")
    open(os.path.join(REPORTS_DIR, f"ai-taste-monitor-{RUN_DATE}.md"), "w").write("\n".join(lines))
    print(f"扫描 {len(slugs)} 篇，命中 {len(results)} 篇。报告：reports/ai-taste-monitor-{RUN_DATE}.md")

if __name__ == "__main__":
    main()
