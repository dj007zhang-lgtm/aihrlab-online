#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站内容质量深度监测 · 正见 + 深度 (monitor_zhengjian_depth.py)
============================================================

主理人监测任务的「深度」维度补齐 + 正见盲区补强 + 真相源对账。

复用（不重写）既有基线：
  - reports/compliance/latest-summary.json   ← content_compliance_auditor.py 产出（调性/信源/绝对化）
  - reports/fact_risk_census.json            ← fact_risk_census.py 产出（R1/R2/R3 事实风险）
本脚本补齐：
  A. 深度维度（既有的两个脚本完全没测）：
       字数 / 小标题结构 / 信源密度 / 数据·案例密度 / 脱水率 / 一稿多论
  B. 正见盲区补强（content_compliance_auditor 未覆盖的可机检项）：
       R-04 虚构具名场景 / R-03 推测写死 / R-05 营销腔扩展 / R-12 半角标点·破折号滥用
  C. 真相源对账：磁盘 286 篇文章 vs article-index.json 269 条 → 17 个孤儿文件
     （可达但不可发现 = 重复内容/索引同步缺口风险）

输出：
  reports/zhengjian-depth-monitor-<YYYYMMDD>.json   全量 per-article 机器可读
  reports/zhengjian-depth-monitor-<YYYYMMDD>.html   人读仪表盘（风险排名 + 分布）
  reports/zhengjian-depth-monitor-<YYYYMMDD>.md     摘要

深度评分(0-100) = 字数(40) + 结构(25) + 信源密度(25) + 证据(10)
  ≥70 深 / 50-69 中 / <50 浅（承接不住）
正见风险 = 既有 compliance WARN/FAIL + 本脚本补强信号（虚构场景/推测写死/营销腔/半角·破折号）
综合风险排名 = 深度浅(<50) ∪ 正见硬伤 ∪ R1 高危密集
"""
import os, re, json, glob, math, datetime, difflib

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(SITE_ROOT, "articles")
REPORTS_DIR = os.path.join(SITE_ROOT, "reports")
INDEX_JSON = os.path.join(SITE_ROOT, "assets", "js", "article-index.json")
COMPLIANCE_JSON = os.path.join(REPORTS_DIR, "compliance", "latest-summary.json")
FACTRISK_JSON = os.path.join(REPORTS_DIR, "fact_risk_census.json")

RUN_DATE = datetime.date.today().strftime("%Y%m%d")

# ───────────────────────────────────────────────────────────
# 解析
# ───────────────────────────────────────────────────────────
def extract(html):
    m = re.search(r'<article\b[^>]*>(.*?)</article>', html, re.S | re.I)
    body_html = m.group(1) if m else html
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    cat = re.search(r'<span class="cat">([^<]+)</span>', html)
    # 正文纯文本
    txt = re.sub(r"<(script|style)\b.*?</\1>", " ", body_html, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    # 小标题
    headings = [re.sub(r"<.*?>", "", h).strip()
                for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", body_html, re.S)]
    # 信源块
    vs_items = re.findall(r'class="verified-sources__item"', html)
    # 内联机构/具名实体
    orgs = set(re.findall(
        r"(McKinsey|麦肯锡|Deloitte|德勤|BCG|波士顿|IDC|Gartner|Stanford|斯坦福|"
        r"Microsoft|微软|Google|谷歌|Alphabet|Meta|字节|腾讯|阿里|百度|华为|京东|美团|"
        r"小米|Gartner|SHRM|WEF|世界经济论坛|OpenAI|Anthropic|ILO|OECD|普华永道|PwC|"
        r"埃森哲|Accenture|高盛|摩根|中金|智联|北大国发院|信通院|清华大学|哈佛|MIT)",
        html))
    people = set(re.findall(
        r"(张勇|张一鸣|梁汝波|马化腾|马云|李彦宏|雷军|王兴|黄峥|沈抖|周畅|"
        r"Satya|Nadella|Altman|Benioff|黄仁勋|Karpathy|Demis|Hassabis|李开复|"
        r"吴恩达|Andrew\s*Ng|陆奇|沈向洋)", html))
    return {
        "title_tag": title.group(1).strip() if title else "",
        "h1": re.sub(r"<.*?>", "", h1.group(1)).strip() if h1 else "",
        "cat": cat.group(1).strip() if cat else "",
        "body": txt,
        "chars": len(txt),
        "headings": headings,
        "vs_items": len(vs_items),
        "orgs": orgs,
        "people": people,
    }


# ───────────────────────────────────────────────────────────
# A. 深度维度
# ───────────────────────────────────────────────────────────
SRC_ANCHOR = re.compile(
    r"(据|来源|依据|引自|披露|公布|发布的|报告显示|调研显示|数据显示|统计显示|白皮书|研报|财报|年报|"
    r"麦肯锡|McKinsey|IDC|Gartner|德勤|Deloitte|BCG|SHRM|微软|Microsoft|谷歌|Google|OpenAI|"
    r"Anthropic|Meta|腾讯|阿里|字节|华为|世界经济论坛|WEF|ILO|OECD|普华永道|PwC|埃森哲|Accenture|"
    r"高盛|摩根|中金|智联|信通院|清华大学|哈佛|MIT|斯坦福|Stanford)")
BOOK = re.compile(r"《[^《》]{2,40}?》")
NUM = re.compile(r"(?<![\w.])\d[\d,]*\.?\d*\s*(万亿|千亿|亿|万|%|％|倍|个百分点|人|名|美元|元|pp)")
FILLER = re.compile(
    r"(总之|简单来说|值得注意的是|不可否认|事实上|换句话说|一言以蔽之|归根结底|毋庸置疑|"
    r"毫不夸张|说到底|平心而论|客观地说|坦率地讲|说白了)")


def depth_score(d):
    c = d["chars"]
    h = len(d["headings"])
    src_hits = len(SRC_ANCHOR.findall(d["body"])) + len(BOOK.findall(d["body"])) + d["vs_items"]
    density = src_hits / (c / 1000.0) if c else 0
    nums = len(NUM.findall(d["body"]))
    # 字数分(40)
    if c >= 3000: lsc = 40
    elif c >= 2500: lsc = 35
    elif c >= 1800: lsc = 30
    elif c >= 1200: lsc = 22
    elif c >= 800: lsc = 14
    else: lsc = 6
    # 结构分(25)
    if h >= 8: ssc = 25
    elif h >= 5: ssc = 20
    elif h >= 3: ssc = 15
    elif h == 2: ssc = 10
    elif h == 1: ssc = 6
    else: ssc = 3
    # 信源密度分(25)
    if density >= 3: srcsc = 25
    elif density >= 2: srcsc = 20
    elif density >= 1: srcsc = 14
    elif density >= 0.5: srcsc = 8
    else: srcsc = 3
    if d["vs_items"] > 0: srcsc = min(25, srcsc + 2)
    # 证据分(10)：具名实体 + 数值断言
    ev = 0
    if d["orgs"] or d["people"]: ev += 5
    if nums >= 5: ev += 5
    elif nums >= 2: ev += 3
    elif nums >= 1: ev += 1
    total = lsc + ssc + srcsc + ev
    # 脱水率
    filler = len(FILLER.findall(d["body"]))
    filler_rate = filler / (c / 1000.0) if c else 0
    # 一稿多论(弱信号)：h2/h3 很多但首词分散
    sprawl = False
    if h >= 9:
        sprawl = True
    flags = []
    if c < 1200: flags.append("字数偏薄(<1200)")
    if c >= 2000 and h <= 1: flags.append("长文无小标题(墙式文本)")
    if density < 1.0 and c >= 1500: flags.append("信源密度低(<1/千字)")
    if filler_rate >= 2.0: flags.append("脱水率低(填充词≥2/千字)")
    if sprawl: flags.append("疑似一稿多论(小标题≥9)")
    band = "深" if total >= 70 else ("中" if total >= 50 else "浅")
    return {
        "depth_score": total, "depth_band": band,
        "chars": c, "headings": h, "src_density": round(density, 2),
        "src_hits": src_hits, "vs_items": d["vs_items"],
        "nums": nums, "named_entities": len(d["orgs"]) + len(d["people"]),
        "filler_rate": round(filler_rate, 2), "sprawl": sprawl,
        "depth_flags": flags,
    }


# ───────────────────────────────────────────────────────────
# B. 正见盲区补强（content_compliance_auditor 未覆盖）
# ───────────────────────────────────────────────────────────
FABRICATED = re.compile(
    r"(小张|小王|小李|小赵|小刘|小陈|小杨|小黄|小周|小吴|小孙|小胡|"
    r"某员工|某HR|某经理|某主管|某同事|某总监|王经理|李总|张总|刘总|陈总|赵总|周总)")
SPECULATE = re.compile(
    r"(必将|必定|一定会|毫无疑问会|注定会|必然导致|必然带来|一定会被|毫无疑问将|势必将|"
    r"必然会|无可避免地(?:被|将)|注定(?:被|要))")
MARKETING = re.compile(
    r"(必看|干货满满|保姆级|一文搞懂|彻底搞懂|强烈推荐|不得不看|绝绝子|封神|yyds|"
    r"宝藏(?:干货|方法|攻略|清单)|速收藏|码住|建议转发|无脑冲|闭眼入|神器)")
HALFWIDTH_PUNCT = re.compile(r"(?<=[\u4e00-\u9fff])([,.!?:;])(?=[\u4e00-\u9fff])")
EMDASH = re.compile(r"—")  # 破折号滥用计数


def zhengjian_extra(d):
    body = d["body"]
    fab = FABRICATED.findall(body)
    spec = SPECULATE.findall(body)
    mkt = MARKETING.findall(body)
    hw = HALFWIDTH_PUNCT.findall(body)
    em = len(EMDASH.findall(body))
    findings = []
    if fab: findings.append({"rule": "R-04 虚构具名场景", "level": "WARN",
                              "evidence": "出现具名虚构人物：" + "、".join(sorted(set(fab))[:6])})
    if spec: findings.append({"rule": "R-03 推测写死", "level": "WARN",
                               "evidence": "推测性断言写死为事实：" + "、".join(sorted(set(spec))[:6])})
    if mkt: findings.append({"rule": "R-05 营销腔扩展", "level": "WARN",
                              "evidence": "营销腔词汇：" + "、".join(sorted(set(mkt))[:6])})
    if len(hw) >= 3: findings.append({"rule": "R-12 半角标点", "level": "WARN",
                                       "evidence": f"中文语境半角标点 {len(hw)} 处（如「{hw[0]}」）"})
    if em >= 8: findings.append({"rule": "R-12 破折号滥用", "level": "WARN",
                                  "evidence": f"破折号 {em} 处，疑似作逗号/括号滥用"})
    hard = any(f["level"] in ("CRITICAL", "FAIL") for f in findings)
    return {"findings": findings, "hard": hard,
            "counts": {"fabricated": len(fab), "speculate": len(spec),
                       "marketing": len(mkt), "halfwidth": len(hw), "emdash": em}}


# ───────────────────────────────────────────────────────────
# C. 真相源对账
# ───────────────────────────────────────────────────────────
def reconcile_orphans(disk_slugs, index_slugs):
    orphans = sorted(disk_slugs - index_slugs)
    classified = []
    for o in orphans:
        # 找最相近的 indexed slug
        best = max(index_slugs, key=lambda s: difflib.SequenceMatcher(None, o, s).ratio()) if index_slugs else ""
        ratio = difflib.SequenceMatcher(None, o, best).ratio() if best else 0
        if ratio >= 0.75:
            kind = "疑似重复/旧版本(应删或重定向)"
        elif ratio >= 0.5:
            kind = "疑似同主题变体(需人工判重)"
        else:
            kind = "疑为独立文章但漏索引(应补 sync)"
        classified.append({"slug": o, "nearest_index": best, "ratio": round(ratio, 2), "kind": kind})
    return classified


# ───────────────────────────────────────────────────────────
def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    # 载入既有基线
    compliance = {}
    if os.path.exists(COMPLIANCE_JSON):
        cs = json.load(open(COMPLIANCE_JSON, encoding="utf-8"))
        for a in cs.get("articles", []):
            compliance[a["slug"]] = a
    factrisk = {}
    if os.path.exists(FACTRISK_JSON):
        for r in json.load(open(FACTRISK_JSON, encoding="utf-8")):
            factrisk[r["file"].replace(".html", "")] = r

    # 真相源对账
    idx = json.load(open(INDEX_JSON, encoding="utf-8"))
    index_slugs = {os.path.basename(e["url"]).replace(".html", "") for e in idx}
    disk_files = [f for f in glob.glob(os.path.join(ARTICLES_DIR, "*.html"))
                  if os.path.basename(f) != "index.html"]
    disk_slugs = {os.path.basename(f).replace(".html", "") for f in disk_files}
    orphans = reconcile_orphans(disk_slugs, index_slugs)

    rows = []
    for f in sorted(disk_files):
        slug = os.path.basename(f).replace(".html", "")
        html = open(f, encoding="utf-8", errors="ignore").read()
        d = extract(html)
        dep = depth_score(d)
        zx = zhengjian_extra(d)
        comp = compliance.get(slug, {})
        fr = factrisk.get(slug, {})
        r1 = len(fr.get("R1", [])) if isinstance(fr.get("R1"), list) else 0
        r2 = len(fr.get("R2", [])) if isinstance(fr.get("R2"), list) else 0
        comp_warn = comp.get("counts", {}).get("warn", 0)
        comp_fail = comp.get("counts", {}).get("fail", 0)
        comp_crit = comp.get("counts", {}).get("critical", 0)
        # 综合风险判定
        risk_hit = []
        if dep["depth_band"] == "浅": risk_hit.append("深度浅承接不住")
        if zx["hard"] or comp_fail or comp_crit: risk_hit.append("正见硬伤")
        if any(f["rule"].startswith(("R-04", "R-03", "R-05")) for f in zx["findings"]):
            risk_hit.append("正见补强信号")
        if r1 >= 8: risk_hit.append(f"R1高危断言密集({r1})")
        in_index = slug in index_slugs
        rows.append({
            "slug": slug, "title": d["h1"] or d["title_tag"], "category": d["cat"],
            "in_index": in_index,
            "depth": dep, "zhengjian_extra": zx["counts"],
            "zhengjian_extra_findings": zx["findings"],
            "compliance": {"warn": comp_warn, "fail": comp_fail, "crit": comp_crit,
                           "score": comp.get("score")},
            "factrisk": {"R1": r1, "R2": r2, "R3": fr.get("R3", 0), "inlink": fr.get("inlink", 0)},
            "risk_hit": risk_hit,
        })

    # 风险排名：浅深度优先，其次正见硬伤，其次 R1 密集
    def risk_key(r):
        s = 0
        if r["depth"]["depth_band"] == "浅": s += 100
        if any(h in ("正见硬伤",) for h in r["risk_hit"]): s += 60
        if r["zhengjian_extra"]["fabricated"] or r["zhengjian_extra"]["speculate"]: s += 40
        s += min(r["factrisk"]["R1"], 20)
        s += r["zhengjian_extra"]["marketing"] * 2
        return -s
    rows.sort(key=risk_key)

    # 汇总
    n = len(rows)
    band_cnt = {"深": 0, "中": 0, "浅": 0}
    for r in rows: band_cnt[r["depth"]["depth_band"]] += 1
    thin = [r for r in rows if r["depth"]["depth_band"] == "浅"]
    fab = [r for r in rows if r["zhengjian_extra"]["fabricated"]]
    spec = [r for r in rows if r["zhengjian_extra"]["speculate"]]
    mkt = [r for r in rows if r["zhengjian_extra"]["marketing"]]
    r1dense = [r for r in rows if r["factrisk"]["R1"] >= 8]

    summary = {
        "run_date": RUN_DATE,
        "scan_universe": n,
        "index_entries": len(index_slugs),
        "orphans": len(orphans),
        "depth_band": band_cnt,
        "depth_thin_count": len(thin),
        "zhengjian": {
            "fabricated_scene_articles": len(fab),
            "speculate_written_articles": len(spec),
            "marketing_tone_articles": len(mkt),
        },
        "factrisk_R1_dense_articles": len(r1dense),
        "top_risk": [{"slug": r["slug"], "title": r["title"], "risk": r["risk_hit"],
                      "depth": r["depth"]["depth_score"], "band": r["depth"]["depth_band"],
                      "R1": r["factrisk"]["R1"]} for r in rows[:25]],
    }

    # 写 JSON
    out_json = os.path.join(REPORTS_DIR, f"zhengjian-depth-monitor-{RUN_DATE}.json")
    json.dump({"summary": summary, "orphans": orphans, "articles": rows},
              open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 写 MD
    md = []
    md.append(f"# 全站内容质量深度监测 · 正见 + 深度 · {RUN_DATE}\n")
    md.append(f"> 扫描宇宙：**{n}** 篇（磁盘 articles/ 不含 index.html）｜ 搜索索引：**{len(index_slugs)}** 条 ｜ 孤儿文件：**{len(orphans)}**\n")
    md.append("## 一、深度维度总览")
    md.append(f"- 深(≥70)：**{band_cnt['深']}** 篇 ｜ 中(50-69)：**{band_cnt['中']}** 篇 ｜ 浅(<50，承接不住)：**{band_cnt['浅']}** 篇")
    md.append(f"- 浅文 Top（按风险）：")
    for r in thin[:15]:
        md.append(f"  - `{r['slug']}`（{r['depth']['depth_score']}分/{r['depth']['depth_band']}｜{r['depth']['chars']}字｜{r['depth']['headings']}小标题｜信源{r['depth']['src_density']}/千字）— {r['title']}")
    md.append("\n## 二、正见维度（补强 + 既有基线）")
    md.append(f"- 虚构具名场景(R-04)：**{len(fab)}** 篇")
    for r in fab[:10]: md.append(f"  - `{r['slug']}`：{r['zhengjian_extra']['fabricated']} 处")
    md.append(f"- 推测写死(R-03)：**{len(spec)}** 篇")
    for r in spec[:10]: md.append(f"  - `{r['slug']}`：{r['zhengjian_extra']['speculate']} 处")
    md.append(f"- 营销腔扩展(R-05)：**{len(mkt)}** 篇")
    for r in mkt[:10]: md.append(f"  - `{r['slug']}`：{r['zhengjian_extra']['marketing']} 处")
    md.append(f"- R1 高危断言密集(≥8，无时间+无出处锚)：**{len(r1dense)}** 篇")
    md.append("\n## 三、真相源对账（孤儿文件 = 可达但不可发现）")
    for o in orphans:
        md.append(f"- `{o['slug']}` → 最近索引项 `{o['nearest_index']}`(相似度{o['ratio']})：{o['kind']}")
    md.append("\n## 四、综合风险 Top 25（供分层抽样深读）")
    md.append("| # | 文章 | 深度分 | 带 | R1 | 风险标签 |")
    md.append("|---|---|---|---|---|---|")
    for i, r in enumerate(rows[:25], 1):
        md.append(f"| {i} | {r['title']} | {r['depth']['depth_score']} | {r['depth']['depth_band']} | {r['factrisk']['R1']} | {'；'.join(r['risk_hit']) or '—'} |")
    md.append(f"\n---\n_生成：monitor_zhengjian_depth.py · {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    out_md = os.path.join(REPORTS_DIR, f"zhengjian-depth-monitor-{RUN_DATE}.md")
    open(out_md, "w", encoding="utf-8").write("\n".join(md))

    # 写 HTML 仪表盘
    write_html(summary, rows, orphans, RUN_DATE)

    print(f"✓ 扫描 {n} 篇 | 深度: 深{band_cnt['深']}/中{band_cnt['中']}/浅{band_cnt['浅']}")
    print(f"✓ 正见补强: 虚构场景{len(fab)}/推测写死{len(spec)}/营销腔{len(mkt)} | R1密集{len(r1dense)}")
    print(f"✓ 孤儿文件 {len(orphans)} 个")
    print(f"✓ JSON: {out_json}")
    print(f"✓ MD:   {out_md}")


def write_html(summary, rows, orphans, run_date):
    # 深度分布柱状
    b = summary["depth_band"]
    top = summary["top_risk"]
    top_rows = "\n".join(
        f"<tr><td>{i+1}</td><td><a href='/articles/{r['slug']}.html'>{r['title']}</a></td>"
        f"<td>{r['depth']}</td><td><span class='band band-{r['band']}'>{r['band']}</span></td>"
        f"<td>{r['R1']}</td><td>{'；'.join(r['risk'])}</td></tr>"
        for i, r in enumerate(top))
    orphan_rows = "\n".join(
        f"<tr><td><code>{o['slug']}</code></td><td>{o['nearest_index']}</td>"
        f"<td>{o['ratio']}</td><td>{o['kind']}</td></tr>" for o in orphans)
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全站内容质量监测 · {run_date}</title>
<style>
:root{{--bg:#0B0C0E;--card:#161A21;--text:#ECEAE4;--green:#6F9A3C;--sand:#F1EFE9;
--amber:#C9A227;--red:#C0533B;}}
*{{box-sizing:border-box}}body{{background:var(--bg);color:var(--text);
font-family:-apple-system,'Sarasa Gothic SC',sans-serif;margin:0;padding:32px;line-height:1.6}}
h1{{color:var(--green);font-size:24px}}h2{{color:var(--sand);border-left:4px solid var(--green);
padding-left:10px;margin-top:36px}}
.card{{background:var(--card);border-radius:12px;padding:20px;margin:16px 0}}
.kpis{{display:flex;gap:16px;flex-wrap:wrap}}
.kpi{{flex:1;min-width:140px;background:var(--card);border-radius:12px;padding:18px;text-align:center}}
.kpi .n{{font-size:30px;font-weight:700;color:var(--green)}}.kpi .l{{font-size:13px;opacity:.8}}
table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #2a2f38}}
th{{color:var(--sand);position:sticky;top:0;background:var(--card)}}
.band{{padding:2px 8px;border-radius:6px;font-size:12px}}
.band-深{{background:var(--green);color:#0B0C0E}}.band-中{{background:var(--amber);color:#0B0C0E}}
.band-浅{{background:var(--red);color:#fff}}
.bar{{display:flex;height:28px;border-radius:6px;overflow:hidden;margin-top:8px}}
.bar span{{display:flex;align-items:center;justify-content:center;font-size:12px;color:#0B0C0E}}
.bar .d{{background:var(--green)}}.bar .m{{background:var(--amber)}}.bar .s{{background:var(--red)}}
code{{background:#222;padding:1px 5px;border-radius:4px;font-size:12px}}
.warn{{color:var(--amber)}}.bad{{color:var(--red)}}
</style></head><body>
<h1>全站内容质量深度监测 · 正见 + 深度</h1>
<p>运行日期 {run_date} ｜ 扫描宇宙 {summary['scan_universe']} 篇 ｜ 搜索索引 {summary['index_entries']} 条 ｜ 孤儿文件 <span class="bad">{summary['orphans']}</span> 个</p>
<div class="kpis">
<div class="kpi"><div class="n">{b['深']}</div><div class="l">深文(≥70)</div></div>
<div class="kpi"><div class="n">{b['中']}</div><div class="l">中文(50-69)</div></div>
<div class="kpi"><div class="n bad">{b['浅']}</div><div class="l">浅文(<50，承接不住)</div></div>
<div class="kpi"><div class="n">{summary['zhengjian']['fabricated_scene_articles']}</div><div class="l">虚构具名场景(R-04)</div></div>
<div class="kpi"><div class="n">{summary['zhengjian']['speculate_written_articles']}</div><div class="l">推测写死(R-03)</div></div>
<div class="kpi"><div class="n">{summary['zhengjian']['marketing_tone_articles']}</div><div class="l">营销腔(R-05)</div></div>
<div class="kpi"><div class="n bad">{summary['factrisk_R1_dense_articles']}</div><div class="l">R1高危密集(≥8)</div></div>
</div>
<div class="card"><h2 style="margin-top:0">深度分布</h2>
<div class="bar"><span class="d" style="width:{b['深']/summary['scan_universe']*100:.1f}%">{b['深']}</span>
<span class="m" style="width:{b['中']/summary['scan_universe']*100:.1f}%">{b['中']}</span>
<span class="s" style="width:{b['浅']/summary['scan_universe']*100:.1f}%">{b['浅']}</span></div></div>
<h2>综合风险 Top 25（分层抽样深读队列）</h2>
<table><thead><tr><th>#</th><th>文章</th><th>深度分</th><th>带</th><th>R1</th><th>风险标签</th></tr></thead>
<tbody>{top_rows}</tbody></table>
<h2>真相源对账 · 孤儿文件（可达但不可发现 = 重复内容/索引缺口）</h2>
<table><thead><tr><th>孤儿 slug</th><th>最近索引项</th><th>相似度</th><th>判定</th></tr></thead>
<tbody>{orphan_rows}</tbody></table>
<p style="opacity:.6;margin-top:30px">monitor_zhengjian_depth.py · 正见基线复用 content_compliance_auditor + fact_risk_census</p>
</body></html>"""
    out_html = os.path.join(REPORTS_DIR, f"zhengjian-depth-monitor-{RUN_DATE}.html")
    open(out_html, "w", encoding="utf-8").write(html)


if __name__ == "__main__":
    main()
