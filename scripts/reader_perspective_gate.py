#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读者视角门 (Reader Perspective Gate) — 质量门体系 Gate 14

以「读者」身份审视每篇待上线文章，评估它是否真正为读者提供价值、并带来良好的
阅读体验。这是一个**可机器校验的启发式评分门**，不是主观打分：每个维度都由
确定的文本信号代理，给出 0-100 分与可执行的改进建议。

设计纪律（来自 quality-gate-playbook）：
- 门看不见的 = 没查。所以每个子指标都要对应一个能被脚本稳定识别的失败模式。
- 频繁误报会毁掉门。所以阈值偏宽、评分透明，好文必须稳过；只有真正弱的文章才拦。
- 自证全绿不可信。内置 --selftest：注入已知「好/坏」样本，断言门能抓能放。

五个维度（权重合计 100）：
  content_value  内容价值   25  —— 读者问：我拿到真东西了吗，还是空话？
  readability    可读性     20  —— 读者问：读着累不累？
  structure      结构清晰度 20  —— 读者问：我找不找得到、理不清脉络？
  accuracy       信息准确度 20  —— 读者问：这数字/结论靠谱吗、有出处吗？
  fluency        阅读流畅度 15  —— 读者问：节奏舒服吗、有没有大段蹲读？

综合 = Σ(维度分 × 权重)。>= 80 才允许上线；< 80 拦截并反馈改进建议。

用法：
  python3 scripts/reader_perspective_gate.py articles/xxx.html   # 单篇评分
  python3 scripts/reader_perspective_gate.py --selftest          # 自测（负样本证伪）
  （作为 quality_gate.py 的 Gate 14 被调用：evaluate_articles(files)）
"""

import os
import re
import sys

# ============================================================
# 配置：维度与权重
# ============================================================
PASS_THRESHOLD = 80

WEIGHTS = {
    "content_value": 25,
    "readability": 20,
    "structure": 20,
    "accuracy": 20,
    "fluency": 15,
}

DIM_LABELS = {
    "content_value": "内容价值",
    "readability": "可读性",
    "structure": "结构清晰度",
    "accuracy": "信息准确度",
    "fluency": "阅读流畅度",
}


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


# ============================================================
# 信号正则（代理「读者体验」的可机器识别失败模式）
# ============================================================
THESIS_SIGNALS = re.compile(
    r'本质|核心|关键不在于|真正|本文认为|结论是|本文的核心|一句话|其实|问题的关键|'
    r'重点不在于|换言之|说到底|根本原因在于|其要害'
)
CONCRETE_YEAR = re.compile(r'20\d{2}')
ORG_ENTITY = re.compile(
    r'(亚马逊|微软|谷歌|Google|Meta|苹果|京东|阿里|腾讯|字节|百度|IBM|Salesforce|SAP|'
    r'德勤|麦肯锡|波士顿|贝恩|埃森哲|Gartner|IDC|Stanford|斯坦福|哈佛|MIT|牛津|'
    r'Nature|彭博|摩根|AT&T|戴尔|Dell|JLL|世邦魏理仕|高力|Randstad|任仕达|'
    r'Robert Half|盖洛普|Gallup|携程|Trip\.?com|摩根大通|JPMorgan|美银|微软)'
)
MARKETING_REDFLAG = re.compile(
    r'赋能|颠覆|重塑未来|一站式|最佳实践|革命性|划时代|必看|震惊|干货满满|深度长文|'
    r'一文搞懂|保姆级|震惊业界|史无前例|颠覆性|降维打击|王炸|绝绝子|天花板|'
    r'yyds|神器|爆款|躺赢|弯道超车|遥遥领先'
)
ACTION_SIGNALS = re.compile(
    r'建议|怎么做|策略|框架|三步|清单|你可以|行动|落地|实践|操作|步骤|你可以这样|'
    r'如何做|做这一步|落地路径|可操作'
)
ABSOLUTE = re.compile(r'一定|必然|所有|完全|100%|毋庸置疑|绝对|永远|全都|无一例外|必定')
TRANSITION = re.compile(
    r'然而|但|与此同时|换句话说|回到|进一步|其本质|换言之|另一方面|事实上|需要说明的是|'
    r'不过|与此相对|从另一个角度看|说到底|换句话说|换言之'
)
HARD_NUM = re.compile(r'[\d.]+[\s]*?(?:万亿|亿|万|%|倍|×|倍于|千人|万人|亿元|亿美元|万小时)')
SRC_PHRASE = re.compile(
    r'据|来源|披露|援引|引自|公开数据|IDC|微软|火山引擎|券商|研报|报告|证券时报|'
    r'腾讯|字节|百度|阿里|谷歌|公开披露|官方|晚点|第一财经|QuestMobile|野村|GSC|Bing|'
    r'Stanford|斯坦福|Nature|Gallup|盖洛普|JLL|Randstad|Robert Half|携程|Trip|'
    r'研究显示|数据表明|调研|调查发现|白皮书|年报'
)
EXCLUDE_HOSTS = ('aihrlab.online', 'googletagmanager', 'hm.baidu')
CONCLUSION_SIGNAL = re.compile(r'结语|总结|写在最后|最后|结论|收尾|写在最后|小结|总体来看|一句话总结')
CURRENT_SIGNAL = re.compile(r'2026|最新|当前|近日|刚刚|新近|近期')


# ============================================================
# HTML 解析辅助
# ============================================================
def _strip_tags(html):
    return re.sub(r'<[^>]+>', ' ', html)


def _extract_article(html):
    """抽取「读者实际可见的主内容区」，按优先级回退。

    规则：
    1. 若页面恰好一个 <article>：那是精确正文块，直接用（覆盖绝大多数文章）。
    2. 若 <article> 数量为 0 或多个（hub/主题簇页、卡片网格）：改用 <main>，
       以覆盖读者实际可见的全部内容（FAQ、各卡片、阅读指引），避免被首个
       <article class="cluster-card"> 截住、只分析到一张卡片造成误判。
    3. 多 <article> 且无 <main>：合并所有 <article> 块。
    4. 最后回退到 <body>。
    """
    articles = re.findall(r'<article[\s\S]*?</article>', html, re.I | re.S)
    if len(articles) == 1:
        return articles[0]
    m = re.search(r'<main[\s\S]*?</main>', html, re.I | re.S)
    if m:
        return m.group(0)
    if articles:
        return "\n".join(articles)
    m = re.search(r'<body[\s\S]*?</body>', html, re.I | re.S)
    return m.group(0) if m else html


def _extract_blocks(article_html):
    """从文章块抽取结构化单元。"""
    # 正文纯文本
    body_text = _strip_tags(article_html)
    body_text = re.sub(r'\s+', ' ', body_text).strip()

    # 段落（<p> 内容）
    paras = [re.sub(r'\s+', ' ', _strip_tags(p)).strip()
             for p in re.findall(r'<p[^>]*>(.*?)</p>', article_html, re.S | re.I)]
    paras = [p for p in paras if p]

    # 标题层级
    headings = []
    for lvl, h in re.findall(r'<h([1-6])[^>]*>(.*?)</h\1>', article_html, re.S | re.I):
        txt = re.sub(r'\s+', ' ', _strip_tags(h)).strip()
        if txt:
            headings.append((int(lvl), txt))

    # 结构元素计数
    n_lists = len(re.findall(r'<(?:ul|ol)\b', article_html, re.I))
    n_blockquote = len(re.findall(r'<blockquote\b', article_html, re.I))
    n_tables = len(re.findall(r'<table\b', article_html, re.I))
    n_imgs = len(re.findall(r'<img\b', article_html, re.I))
    n_callouts = len(re.findall(
        r'class="[^"]*(?:callout|note|aside|box|tip|warning|highlight)[^"]*"',
        article_html, re.I))

    return {
        "body_text": body_text,
        "paras": paras,
        "headings": headings,
        "n_lists": n_lists,
        "n_blockquote": n_blockquote,
        "n_tables": n_tables,
        "n_imgs": n_imgs,
        "n_callouts": n_callouts,
    }


# ============================================================
# 各维度评分（每个返回 (score, subs_dict, notes)）
# subs_dict: 子指标名 -> 数值（用于生成改进建议）
# ============================================================

def _score_content_value(b, head, html):
    body = b["body_text"]
    blen = max(1, len(body))
    notes = []
    subs = {}

    # V1 论点清晰度：首屏是否抛出明确主张（BLUF）
    lead = body[:520]
    if THESIS_SIGNALS.search(lead):
        v1 = 95
    else:
        first_sent = re.split(r'[。！？]', lead)[0]
        v1 = 72 if len(first_sent) >= 45 else 52
    subs["thesis_signal"] = 1 if THESIS_SIGNALS.search(lead) else 0

    # V2 具体性：年份/机构/硬数字密度（每千字）
    n_year = len(CONCRETE_YEAR.findall(body))
    n_org = len(ORG_ENTITY.findall(body))
    n_num = len(HARD_NUM.findall(body))
    density = (n_year * 1.0 + n_org * 1.5 + n_num * 1.2) / (blen / 1000.0)
    if density >= 9:
        v2 = 100
    elif density >= 5:
        v2 = 90
    elif density >= 2.5:
        v2 = 75
    elif density >= 1:
        v2 = 62
    else:
        v2 = 45
    subs["concrete_density"] = round(density, 1)

    # V3 信源支撑：有硬数字则须有出处
    has_num = bool(HARD_NUM.search(body))
    has_src = bool(SRC_PHRASE.search(body)) or bool(_external_links(html))
    if has_num and not has_src:
        v3 = 45
        notes.append("含硬数字但无信源署名/站外引用")
    else:
        v3 = 100
    subs["has_source"] = 1 if (has_src or not has_num) else 0

    # V4 反营销/反空话：营销红词数量
    n_mkt = len(MARKETING_REDFLAG.findall(body))
    if n_mkt == 0:
        v4 = 100
    elif n_mkt <= 2:
        v4 = 85
    elif n_mkt <= 4:
        v4 = 65
    else:
        v4 = 45
    subs["marketing_redflags"] = n_mkt

    # V5 可行动收获：是否有建议/框架/清单类信号或结语段
    has_action = bool(ACTION_SIGNALS.search(body)) or bool(CONCLUSION_SIGNAL.search(body))
    v5 = 92 if has_action else 55
    subs["actionable"] = 1 if has_action else 0

    score = round((v1 + v2 + v3 + v4 + v5) / 5.0)
    return score, subs, notes


def _score_readability(b):
    body = b["body_text"]
    paras = b["paras"]
    notes = []
    subs = {}

    sentences = [s.strip() for s in re.split(r'[。！？；\n]', body) if s.strip()]
    if sentences:
        avg_sent = sum(len(s) for s in sentences) / len(sentences)
        long_sent = sum(1 for s in sentences if len(s) > 100)
        long_ratio = long_sent / len(sentences)
    else:
        avg_sent = 0
        long_ratio = 0
    subs["avg_sentence_len"] = round(avg_sent, 1)
    subs["long_sentence_ratio"] = round(long_ratio, 2)

    # R1 平均句长
    if 18 <= avg_sent <= 70:
        r1 = 100
    elif avg_sent > 70:
        r1 = clamp(100 - (avg_sent - 70) * 0.7)
    else:  # 过短（碎句也伤阅读）
        r1 = clamp(100 - (18 - avg_sent) * 1.5)

    # R3 长句比例
    if long_ratio <= 0.10:
        r3 = 100
    elif long_ratio >= 0.40:
        r3 = 40
    else:
        r3 = clamp(100 - (long_ratio - 0.10) / 0.30 * 60)

    # R2 段长
    if paras:
        avg_para = sum(len(p) for p in paras) / len(paras)
    else:
        avg_para = 0
    subs["avg_paragraph_len"] = round(avg_para, 1)
    if 80 <= avg_para <= 420:
        r2 = 100
    elif avg_para > 420:
        r2 = clamp(100 - (avg_para - 420) * 0.08)
    elif avg_para > 0:
        r2 = clamp(100 - (80 - avg_para) * 0.5)
    else:
        r2 = 60

    # R4 标题扫描密度（每千字 H2+H3 数量）
    nh = sum(1 for lv, _ in b["headings"] if lv in (2, 3))
    density = nh / max(1, len(body) / 1000.0)
    subs["heading_density"] = round(density, 2)
    if density >= 1.0:
        r4 = 100
    elif density >= 0.5:
        r4 = clamp(60 + (density - 0.5) / 0.5 * 40)
    else:
        r4 = 50

    if avg_sent == 0:
        notes.append("正文过短，无法评估句长")
    score = round((r1 + r2 + r3 + r4) / 4.0)
    return score, subs, notes


def _score_structure(b, html=""):
    headings = b["headings"]
    paras = b["paras"]
    notes = []
    subs = {}

    levels = [lv for lv, _ in headings]
    n_h2 = sum(1 for lv, _ in headings if lv == 2)
    subs["n_h2"] = n_h2

    # S1 H2 数量
    if 4 <= n_h2 <= 8:
        s1 = 100
    elif n_h2 in (3, 9, 10):
        s1 = 72
    else:
        s1 = 42
        notes.append(f"H2 数量 {n_h2}（建议 4-8 节）")

    # S2 层级跳级（如 h1 直接到 h3）
    jump = False
    prev = 1
    for lv in levels:
        if lv > prev + 1:
            jump = True
            break
        prev = lv
    s2 = 60 if jump else 100
    if jump:
        notes.append("标题层级存在跳级（如 h1 直跳 h3）")

    # S3 导读/目录
    has_toc = bool('toc-rail' in html) or bool(re.search(r'目录|导读', b["body_text"], re.I))
    s3 = 100 if has_toc else 72
    subs["has_toc"] = 1 if has_toc else 0

    # S4 引言与结语
    has_intro = bool(paras and len(paras[0]) >= 40)
    has_concl = bool(CONCLUSION_SIGNAL.search(b["body_text"]))
    subs["has_intro"] = 1 if has_intro else 0
    subs["has_conclusion"] = 1 if has_concl else 0
    if has_intro and has_concl:
        s4 = 100
    elif has_intro or has_concl:
        s4 = 72
    else:
        s4 = 45
        notes.append("缺明确引言或结语段")

    # S5 标题长度合规（全部 <= 28 字）
    over = [t for lv, t in headings if len(t) > 28]
    s5 = 100 if not over else 60
    subs["overlong_headings"] = len(over)
    if over:
        notes.append(f"{len(over)} 个标题超 28 字")

    score = round((s1 + s2 + s3 + s4 + s5) / 5.0)
    return score, subs, notes


def _score_accuracy(b, head, html):
    body = b["body_text"]
    notes = []
    subs = {}

    # A1 硬数字有出处
    has_num = bool(HARD_NUM.search(body))
    has_src = bool(SRC_PHRASE.search(body)) or bool(_external_links(html))
    if has_num and not has_src:
        a1 = 45
        notes.append("硬数字无出处（须挂信源或站外引用）")
    else:
        a1 = 100
    subs["num_attributed"] = 1 if (has_src or not has_num) else 0

    # A2 信源时效：定位当前则须含 2026 实质年份
    is_current = bool(CURRENT_SIGNAL.search(head)) or ('2026' in html[:60])
    has_2026 = bool(re.search(r'2026', body))
    if is_current and not has_2026:
        a2 = 45
        notes.append("标注当前(2026)但正文无 2026 实质信源")
    else:
        a2 = 100
    subs["fresh_2026"] = 1 if (has_2026 or not is_current) else 0

    # A3 谨慎表述：绝对化词数量
    n_abs = len(ABSOLUTE.findall(body))
    if n_abs <= 1:
        a3 = 100
    elif n_abs <= 3:
        a3 = 90
    elif n_abs <= 5:
        a3 = 75
    else:
        a3 = 60
        notes.append(f"绝对化表述 {n_abs} 处，建议加限定词")
    subs["absolute_terms"] = n_abs

    # A4 事实-观点区分：归因措辞
    has_frame = bool(re.search(
        r'据|研究显示|数据表明|笔者认为|一种观点|有研究指出|调查发现|调研',
        body))
    a4 = 100 if has_frame else 70
    subs["attribution_frame"] = 1 if has_frame else 0

    score = round((a1 + a2 + a3 + a4) / 4.0)
    return score, subs, notes


def _score_fluency(b):
    body = b["body_text"]
    paras = b["paras"]
    notes = []
    subs = {}

    # F1 结构元素 break 密度（每千字）
    E = (b["n_lists"] * 1.0 + b["n_blockquote"] * 1.0 + b["n_tables"] * 2.0
         + b["n_imgs"] * 1.0 + b["n_callouts"] * 1.5)
    density = E / max(1, len(body) / 1000.0)
    subs["structure_element_density"] = round(density, 2)
    if density >= 1.0:
        f1 = 100
    elif density >= 0.5:
        f1 = clamp(60 + (density - 0.5) / 0.5 * 40)
    else:
        f1 = 50
        notes.append("结构元素偏少，正文易成「大段蹲读」")

    # F2 段落节奏：长段占比
    if paras:
        long_para = sum(1 for p in paras if len(p) > 400)
        long_ratio = long_para / len(paras)
    else:
        long_ratio = 0
    subs["long_para_ratio"] = round(long_ratio, 2)
    if long_ratio <= 0.30:
        f2 = 100
    elif long_ratio >= 0.70:
        f2 = 50
    else:
        f2 = clamp(100 - (long_ratio - 0.30) / 0.40 * 50)

    # F3 过渡衔接
    n_trans = len(TRANSITION.findall(body))
    subs["transition_count"] = n_trans
    if n_trans >= 2:
        f3 = 100
    elif n_trans == 1:
        f3 = 75
    else:
        f3 = 55
        notes.append("段落间过渡词偏少")

    # F4 连续长段（无元素打断）
    run = 0
    max_run = 0
    for p in paras:
        if len(p) > 400:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    subs["max_consecutive_long_para"] = max_run
    if max_run <= 3:
        f4 = 100
    elif max_run >= 5:
        f4 = 60
    else:
        f4 = clamp(100 - (max_run - 3) * 20)
    if max_run >= 5:
        notes.append(f"出现 {max_run} 段连续超长段落，建议插入小标题/列表打断")

    score = round((f1 + f2 + f3 + f4) / 4.0)
    return score, subs, notes


def _external_links(html):
    return [u for u in re.findall(r'href="(https?://[^"]+)"', html)
            if not any(h in u for h in EXCLUDE_HOSTS)]


# ============================================================
# 顶层评分
# ============================================================
def score_article(html, rel_path=""):
    """返回单篇评分字典。"""
    article_html = _extract_article(html)
    b = _extract_blocks(article_html)
    head = html[:html.find('</head>')] if '</head>' in html else html[:8000]

    dims = {}
    all_notes = []
    for key, fn in (
        ("content_value", lambda: _score_content_value(b, head, html)),
        ("readability", lambda: _score_readability(b)),
        ("structure", lambda: _score_structure(b, html)),
        ("accuracy", lambda: _score_accuracy(b, head, html)),
        ("fluency", lambda: _score_fluency(b)),
    ):
        sc, subs, notes = fn()
        dims[key] = {"label": DIM_LABELS[key], "score": sc, "subs": subs}
        all_notes.extend(notes)

    composite = round(sum(dims[k]["score"] * WEIGHTS[k] for k in WEIGHTS) / 100.0)
    passed = composite >= PASS_THRESHOLD

    suggestions = _build_suggestions(dims, all_notes)

    return {
        "rel": rel_path,
        "composite": composite,
        "passed": passed,
        "dims": dims,
        "suggestions": suggestions,
        "notes": all_notes,
    }


def _build_suggestions(dims, notes):
    """为 < 80 的维度生成可执行改进建议（基于子指标实测值）。"""
    sugg = []
    # 把 notes 里已有的具体提示放前面
    for n in notes:
        sugg.append(n)

    for key in WEIGHTS:
        d = dims[key]
        if d["score"] >= 80:
            continue
        s = d["subs"]
        label = d["label"]
        if key == "content_value":
            if s.get("thesis_signal") == 0:
                sugg.append(f"【{label}】首屏未抛出明确主张：开头 500 字加入「本质/核心/关键」式论点，先给读者一个能记住的判断。")
            if s.get("concrete_density", 99) < 2.5:
                sugg.append(f"【{label}】具体性不足（密度 {s.get('concrete_density')}/千字）：补充年份、机构名、数据，减少空泛概括。")
            if s.get("marketing_redflags", 0) >= 3:
                sugg.append(f"【{label}】营销红词 {s.get('marketing_redflags')} 处：删掉「赋能/颠覆/重塑未来」等口号，用事实代替渲染。")
            if s.get("actionable") == 0:
                sugg.append(f"【{label}】缺少可行动收获：文末补「建议/框架/清单」段，让读者带走方法。")
        elif key == "readability":
            if s.get("avg_sentence_len", 0) > 70:
                sugg.append(f"【{label}】平均句长 {s.get('avg_sentence_len')} 字偏长：拆分长句，单句控制在 50 字左右。")
            if s.get("long_sentence_ratio", 0) > 0.1:
                sugg.append(f"【{label}】长句占比 {s.get('long_sentence_ratio')}：超过 100 字的句子过多，打断节奏。")
            if s.get("avg_paragraph_len", 0) > 420:
                sugg.append(f"【{label}】平均段长 {s.get('avg_paragraph_len')} 字：段落太长，按意群拆成 80-300 字。")
            if s.get("heading_density", 9) < 0.5:
                sugg.append(f"【{label}】小标题密度 {s.get('heading_density')}/千字：增加 H2/H3 让文章可扫读。")
        elif key == "structure":
            if s.get("n_h2", 4) < 4 or s.get("n_h2", 4) > 8:
                sugg.append(f"【{label}】H2 数量 {s.get('n_h2')} 不在 4-8：调整章节数。")
            if s.get("overlong_headings", 0) > 0:
                sugg.append(f"【{label}】{s.get('overlong_headings')} 个标题超 28 字：精简。")
            if s.get("has_intro", 1) == 0 or s.get("has_conclusion", 1) == 0:
                sugg.append(f"【{label}】缺引言或结语：补一段导语 + 一段收尾。")
        elif key == "accuracy":
            if s.get("num_attributed") == 0:
                sugg.append(f"【{label}】硬数字无出处：为数据挂信源署名或站外引用链接。")
            if s.get("fresh_2026") == 0:
                sugg.append(f"【{label}】标注当前却无 2026 信源：补入当年实质论据。")
            if s.get("absolute_terms", 0) > 3:
                sugg.append(f"【{label}】绝对化表述 {s.get('absolute_terms')} 处：加「多数/往往/在 X 条件下」等限定。")
        elif key == "fluency":
            if s.get("structure_element_density", 9) < 0.5:
                sugg.append(f"【{label}】结构元素密度 {s.get('structure_element_density')}/千字：插入列表/引用/图表打断大段文字。")
            if s.get("long_para_ratio", 0) > 0.3:
                sugg.append(f"【{label}】长段占比 {s.get('long_para_ratio')}：增加段落呼吸感。")
            if s.get("transition_count", 2) < 2:
                sugg.append(f"【{label}】过渡词仅 {s.get('transition_count')} 处：段间加「然而/换句话说/回到」衔接。")
            if s.get("max_consecutive_long_para", 0) >= 5:
                sugg.append(f"【{label}】连续 {s.get('max_consecutive_long_para')} 段超长：插小标题或列表。")
    # 去重
    seen = set()
    out = []
    for s in sugg:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def evaluate_articles(files):
    """批量评分，返回结果列表。"""
    results = []
    for f in files:
        try:
            with open(f, encoding='utf-8', errors='ignore') as fh:
                html = fh.read()
        except Exception as e:
            continue
        rel = os.path.relpath(f)
        results.append(score_article(html, rel))
    return results


# ============================================================
# 自测（负样本证伪）：好样本必须过、坏样本必须拦
# ============================================================
GOOD_SAMPLE = """<html><head><title>远程办公没有退潮：灵活性正在变成一种薪酬 | AIHR数智引擎</title>
<meta name="description" content="2026 年大厂 RTO 回潮的真实驱动力，是 AI 重新定价『在场』。本文拆解其本质，并给出 HR 可落地的远程/混合度量框架。">
</head><body><article>
<h1>远程办公没有退潮：灵活性正在变成一种薪酬</h1>
<p>2026 年，亚马逊、摩根大通、AT&T 先后把到岗要求收紧到每周五天。表面看是远程办公退潮，但本质不在于员工想不想来办公室，而在于 AI 接管了大量个体任务之后，企业开始重新为「在场」定价。本文的核心判断是：RTO 回潮的真正驱动力是控制权，而不是效率。</p>
<h2>一、RTO 回潮的真实数据</h2>
<p>据 Stanford 的 SIEPR 研究，美国约 25% 到 28% 的带薪工作日在家完成，远高于疫情前的 5% 到 7%。JLL 2026 办公基准显示，工位实际使用率仅 56%，远低于 74% 的目标。换句话说，强制回岗并没有带来工位的高效利用。</p>
<h2>二、AI 如何重新定价「在场」</h2>
<p>Robert Half 2026 年第二季度调研显示，全在岗职位占 87%，混合占 10%，全远程仅 3%。然而真正的变化是：当会议纪要与初稿由 AI 完成时，线下协调的溢价反而上升。其本质是一场控制权的再分配。</p>
<h2>三、混合制并不伤产出</h2>
<p>携程 Trip.com 在 Nature 发表的随机对照试验显示，混合制让离职率下降 33%，绩效无损失。这说明「远程不可控」更多是管理借口，而非事实。</p>
<h2>四、HR 该怎么做</h2>
<p>建议把远程与混合做成结果导向的可度量体系：用产出而非工时评价，用季度校准代替年度考核。你可以从三步落地：先定义可度量产出，再设混合基线，最后做季度复盘。</p>
<h2>五、写在最后</h2>
<p>灵活性正在变成一种薪酬。企业若只把它当人事政策管，就会继续在控制与效率之间摇摆。数据表明，做得好的公司把灵活性写进了定价逻辑。</p>
</article></body></html>"""

BAD_SAMPLE = """<html><head><title>远程办公干货满满一文搞懂 | AIHR数智引擎</title>
<meta name="description" content="远程办公必看神文">
</head><body><article>
<h1>远程办公干货满满一文搞懂</h1>
<p>远程办公是颠覆性的革命性趋势。所有公司都必须完全拥抱远程。这绝对是未来的方向，毫无疑问。远程办公赋能组织，重塑未来，是天花板级的最佳实践。我们一定要彻底远程，完全远程才是正确。未来所有工作都会在线上，永远如此，无一例外。这是划时代的降维打击，王炸。远程办公遥遥领先，所有企业必然全面转型。这完全是对的，100% 正确。</p>
<p>远程办公颠覆一切。所有岗位都要远程。这绝对正确。未来完全在线上。所有公司都必须彻底改变。这是革命性的。所有员工都要远程。这永远是对的。所有组织都要转型。完全的远程是唯一的答案。所有工作都会被重塑。这必然发生。所有企业都要拥抱。完全线上是终点。所有趋势都指向远程。这毫无疑问。</p>
<p>远程办公赋能一切。所有公司都该彻底转型。这绝对是方向。未来完全在线上。所有岗位都远程。这是革命性的最佳实践。所有组织必然改变。完全线上是未来。所有员工都要远程。这永远正确。所有工作都被重塑。这必然发生。所有企业拥抱远程。完全线上是终点。所有趋势指向远程。这毫无疑问是对的。</p>
</article></body></html>"""


def selftest():
    print("=" * 60)
    print("  读者视角门 自测 (负样本证伪)")
    print("=" * 60)
    ok = True

    good = score_article(GOOD_SAMPLE, "SELFTEST/good.html")
    bad = score_article(BAD_SAMPLE, "SELFTEST/bad.html")

    print(f"\n[好样本] 综合 {good['composite']} 分 -> {'PASS' if good['passed'] else 'FAIL'}")
    for k, d in good["dims"].items():
        print(f"    · {d['label']}: {d['score']}")
    if not good["passed"]:
        ok = False
        print("  ❌ 好样本被误拦（假阳性）— 门过严，需放宽阈值")
    else:
        print("  ✅ 好样本正确放行")

    print(f"\n[坏样本] 综合 {bad['composite']} 分 -> {'PASS' if bad['passed'] else 'FAIL'}")
    for k, d in bad["dims"].items():
        print(f"    · {d['label']}: {d['score']}")
    if bad["passed"]:
        ok = False
        print("  ❌ 坏样本被误放（假阴性）— 门过松，需收紧阈值")
    else:
        print("  ✅ 坏样本正确拦截")
        print("  改进建议示例:")
        for s in bad["suggestions"][:6]:
            print(f"    → {s}")

    print("\n" + "=" * 60)
    if ok:
        print("  🟢 自测通过：门能放好文、能拦弱文")
    else:
        print("  🔴 自测失败：阈值需重新校准")
    print("=" * 60)
    return ok


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)

    targets = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not targets:
        print("用法: python3 reader_perspective_gate.py <article.html> [--selftest]")
        sys.exit(2)

    for path in targets:
        if not os.path.exists(path):
            print(f"文件不存在: {path}")
            continue
        with open(path, encoding='utf-8', errors='ignore') as fh:
            html = fh.read()
        r = score_article(html, os.path.relpath(path))
        print("=" * 60)
        print(f"  {r['rel']}")
        print(f"  综合得分: {r['composite']}  ->  {'✅ 放行' if r['passed'] else '❌ 拦截(<80)'}")
        print("-" * 60)
        for k, d in r["dims"].items():
            print(f"  {d['label']:<6} {d['score']:>3}  权重 {WEIGHTS[k]}")
        if r["suggestions"]:
            print("-" * 60)
            print("  改进建议:")
            for s in r["suggestions"]:
                print(f"    → {s}")
        print("=" * 60)
        sys.exit(0 if r["passed"] else 1)
