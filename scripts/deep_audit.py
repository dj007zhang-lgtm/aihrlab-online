#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deep_audit.py —— 独立于 quality_gate / qa_guardian 的正交深度审计。

存在理由：现有门禁全绿但事故仍发生。已实证的盲区：
  1. 阈值门盲区：hard>=2 漏掉 hard=1 的单点硬伤；
  2. 静态配置盲区：宣言与实际实现不一致，门照宣言绿；
  3. 基础设施盲区：某组件 CSS 完全不存在，无任何门覆盖。

本审计不复用上述门的逻辑，专查它们不查的维度：
  A 非白名单标签（被截断开标签，如 `ion class="references">`）
  B CSS 类无定义（组件裸奔）
  C head 三源一致（title/h1/og/twitter/canonical/description）
  D 日期三源一致 + JSON-LD 健康
  E 资源存在性（站内 img/script/link、og:image）
  F 占位符与模板残留
  G 重复段落
  H 信源块结构 + 正文机构覆盖关系
  I 含硬数字却无可见信源块（阈值降到 >=1，补 hard>=2 的盲区）
  J 行内 style 中的陈旧印刷风格

输出：reports/deep_audit.json（逐篇证据），控制台汇总。
"""

import os, re, sys, json, html
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_WHITELIST = set("""
html head body meta title link style script noscript template
nav header footer main article section aside div span p
h1 h2 h3 h4 h5 h6 ul ol li dl dt dd
a img figure figcaption picture source video audio iframe canvas svg
path circle rect line polyline polygon ellipse g defs use text tspan
lineargradient stop clippath mask pattern symbol marker
radialgradient filter fedropshadow fegaussianblur feoffset feblend fecolormatrix
animate animatetransform animatemotion switch foreignobject desc
table thead tbody tfoot tr th td caption col colgroup
strong em b i u s strike del ins mark small sub sup q cite abbr code pre kbd samp var
blockquote form input button label select option textarea fieldset legend datalist output progress meter
details summary time ruby rt rp wbr br hr base object param embed track map area slot
""".split())

INSTITUTIONS = [
    "麦肯锡", "McKinsey", "德勤", "Deloitte", "普华永道", "PwC", "波士顿咨询", "BCG",
    "Gartner", "SHRM", "盖洛普", "Gallup", "微软", "Microsoft", "领英", "LinkedIn",
    "IDC", "Mercer", "美世", "埃森哲", "Accenture", "光辉国际", "Korn Ferry",
    "斯坦福", "Stanford", "麻省理工", "MIT", "哈佛", "Harvard", "ADP",
    "EU AI Act", "欧盟", "Workday", "SAP", "甲骨文", "Oracle",
    "世界经济论坛", "WEF", "OECD", "国际劳工组织", "ILO",
    "Meta", "谷歌", "Google", "亚马逊", "Amazon", "Anthropic", "OpenAI",
    "字节", "腾讯", "阿里", "百度", "京东", "美团", "华为",
    "Bain", "贝恩", "Prosci", "Forrester", "Indeed", "Glassdoor", "Bersin",
    "人社部", "工信部", "国家统计局",
]

HARD_NUM = re.compile(r"(\d+(?:\.\d+)?\s*(?:%|倍|个百分点|pp))|(\d{1,3}(?:,\d{3}){1,})")

# 自述方法参数：工具/自测页在说明自己的计分规则时会自然出现数字，
# 这些数字的品牌自己就是责任人，不应要求外部信源。
SELF_METHOD = re.compile(
    r"(本自测|本工具|本模型|本清单|本手册|我们把|我们将|我们建议|我们采用|"
    r"等权|权重|阈值|计分区间|打分区间|经验切分|自评|评分标准|每个维度|五个维度|七个要素)")

PLACEHOLDERS = [
    (r"\{\{[^}]{0,40}\}\}", "模板占位符 {{}}"),
    (r"\bTODO\b", "TODO"),
    (r"\bFIXME\b", "FIXME"),
    (r"待补(?:充|写)?", "待补充"),
    (r"敬请期待", "敬请期待"),
    (r"lorem ipsum", "lorem"),
    (r"\bXXX+\b", "XXX 占位"),
    (r"示例文案", "示例文案"),
    (r"占位(?:符|文本|内容)", "占位文本"),
    (r"内容待(?:定|更新)", "内容待定"),
    (r"此处(?:省略|添加)", "此处省略"),
    (r"马上(?:上线|推出|更新)", "马上上线"),
]


# 非页面产物：不是给人看的落地页，不参与标题/正文/信源等页面级检查。
# 曾经的教训：templates/ 构建模板片断与搜索引擎验证文件被判 indexable，
# 凭空造出 10 条假 HIGH（缺 h1/缺 title/资源 404/JSON-LD 不可解析），
# 掩盖了真实问题。分类缺陷必须修在源头，不靠人工每次过滤噪声。
NONPAGE_DIRS = {"templates"}
VERIFY_FILE = re.compile(
    r"^(?:baidu_verify_|google[0-9a-f]{8,}|sogou|shenma|360|360cn|yandex_|naver_)"
    r".*\.html$", re.I)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.classes = {}
        self.resources = []

    def handle_starttag(self, tag, attrs):
        ln = self.getpos()[0]
        self.tags.append((tag, ln))
        d = dict(attrs)
        for tok in re.split(r"\s+", (d.get("class") or "").strip()):
            if tok and tok not in self.classes:
                self.classes[tok] = ln
        for k, v in d.items():
            if not v:
                continue
            if tag == "link" and k == "href" and "stylesheet" in (d.get("rel") or ""):
                self.resources.append(("css", v, ln))
            elif tag == "script" and k == "src":
                self.resources.append(("js", v, ln))
            elif tag == "img" and k == "src":
                self.resources.append(("img", v, ln))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def build_css_class_set():
    defined = set()
    cssdir = os.path.join(ROOT, "assets", "css")
    if os.path.isdir(cssdir):
        for fn in sorted(os.listdir(cssdir)):
            if fn.endswith(".css"):
                t = open(os.path.join(cssdir, fn), encoding="utf-8", errors="ignore").read()
                defined |= set(re.findall(r"\.(-?[A-Za-z_][\w-]*)", t))

    jsdir = os.path.join(ROOT, "assets", "js")
    if os.path.isdir(jsdir):
        for dirpath, _, files in os.walk(jsdir):
            for fn in files:
                if fn.endswith(".js"):
                    t = open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore").read()
                    defined |= set(re.findall(r"[.\"'\s]([a-z][a-z0-9]*(?:-[a-z0-9]+)+)[\"'\s.:,]", t))

    for dirpath, _, files in os.walk(ROOT):
        if "/.git" in dirpath or "/node_modules" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".html"):
                continue
            t = open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore").read()
            for st in re.findall(r"<style[^>]*>(.*?)</style>", t, re.S | re.I):
                defined |= set(re.findall(r"\.(-?[A-Za-z_][\w-]*)", st))
            for sc in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", t, re.S | re.I):
                defined |= set(re.findall(r"[.\"'\s]([a-z][a-z0-9]*(?:-[a-z0-9]+)+)[\"'\s.:,]", sc))
    return defined


def head_field(t, name):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']' + re.escape(name) + r'["\'][^>]*>', t, re.I)
    if not m:
        return None
    m2 = re.search(r'content=["\']([^"\']*)["\']', m.group(0), re.I)
    return html.unescape(m2.group(1)).strip() if m2 else None


def jsonld_blocks(t):
    out = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         t, re.S | re.I):
        try:
            out.append((line_of(t, m.start(1)), json.loads(m.group(1).strip())))
        except Exception as e:
            out.append((line_of(t, m.start(1)), "__PARSE_FAIL__:" + str(e)))
    return out


def flatten_nodes(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from flatten_nodes(v)
    elif isinstance(o, list):
        for v in o:
            yield from flatten_nodes(v)


def visible_text(seg):
    seg = re.sub(r"<!--.*?-->", " ", seg, flags=re.S)
    seg = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", seg, flags=re.S | re.I)
    seg = re.sub(r"<[^>]+>", " ", seg)
    return re.sub(r"\s+", " ", html.unescape(seg)).strip()


def norm(s):
    """比较用归一化：去掉所有空白，避免全角空格/换行造成的伪差异。"""
    return re.sub(r"\s+", "", s or "")


# 正文容器：与 ci/gates 的 extract_article_body 同契约（取首个 <article>），
# 否则会把 ⌘K 搜索浮层、目录栏、页脚文案当成正文，制造假阳性。
def article_scope(t):
    m = re.search(r"<article\b[^>]*>([\s\S]*?)</article>", t, re.S | re.I)
    if m:
        return m.group(1)
    m = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", t, re.S | re.I)
    return m.group(1) if m else t


STRIP_SCOPE = [
    r"<nav\b[\s\S]*?</nav>",
    r"<aside\b[\s\S]*?</aside>",
    r"<footer\b[\s\S]*?</footer>",
    r"<header\b[\s\S]*?</header>",
]


def audit_file(path, css_defined):
    rel = os.path.relpath(path, ROOT)
    t = open(path, encoding="utf-8", errors="ignore").read()
    f = {"file": rel, "issues": []}

    # 非页面产物判定提前：模板内本就含 <!-- PLACEHOLDER_XXX --> 与站点相对路径，
    # 若等资源检查跑完再判 kind，会稳定产出「模板占位符 404」这类假 HIGH。
    top_dir = rel.split(os.sep)[0]
    is_template = top_dir in NONPAGE_DIRS
    is_verify = bool(VERIFY_FILE.match(os.path.basename(rel)))
    is_artifact = is_template or is_verify

    def add(code, sev, msg, ev=None, ln=None):
        f["issues"].append({"code": code, "sev": sev, "msg": msg,
                            "line": ln, "ev": (ev or "")[:220]})

    # ---- A 非白名单标签 ----
    col = Collector()
    try:
        col.feed(t)
    except Exception as e:
        add("A-PARSE", "HIGH", "HTMLParser 解析异常: %s" % e)
    bad = {}
    for tag, ln in col.tags:
        if tag not in TAG_WHITELIST:
            bad.setdefault(tag, ln)
    for tag, ln in sorted(bad.items()):
        add("A-BADTAG", "HIGH", "非白名单标签 <%s>（疑似开标签被截断）" % tag, ln=ln)

    # ---- B CSS 类无定义 ----
    unknown = sorted(c for c in col.classes if c not in css_defined)
    for c in unknown:
        add("B-NOCSS", "MED", "class `%s` 在全部 CSS/JS 中均无定义（组件可能裸奔）" % c,
            ln=col.classes[c])

    # ---- E 资源存在性（模板等非页面产物跳过：占位符本就不可解析为真实路径）----
    if not is_artifact:
        for kind, url, ln in col.resources:
            if url.startswith("/"):
                if not os.path.exists(os.path.join(ROOT, url.lstrip("/"))):
                    add("E-MISSRES", "HIGH", "%s 站内资源不存在: %s" % (kind, url), ln=ln)
            elif url.startswith(("http://", "https://", "//")):
                pass
            else:
                if not os.path.exists(os.path.join(os.path.dirname(path), url)):
                    add("E-MISSRES", "HIGH", "%s 相对资源不存在: %s" % (kind, url), ln=ln)

    # ---- head ----
    tm_ = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
    title = html.unescape(tm_.group(1)).strip() if tm_ else None
    h1m = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S | re.I)
    h1 = visible_text(h1m.group(1)) if h1m else None
    desc = head_field(t, "description")
    og_t = head_field(t, "og:title")
    og_u = head_field(t, "og:url")
    og_img = head_field(t, "og:image")
    og_type = head_field(t, "og:type")
    og_pub = head_field(t, "article:published_time")
    tw_t = head_field(t, "twitter:title")
    cm = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*>', t, re.I)
    canon = None
    if cm:
        c2 = re.search(r'href=["\']([^"\']+)["\']', cm.group(0))
        canon = c2.group(1) if c2 else None
    robots = head_field(t, "robots")

    f["meta"] = {"title": title, "h1": h1, "desc": desc, "og_title": og_t,
                 "canonical": canon, "robots": robots}

    is_redirect = bool(re.search(r'http-equiv=["\']refresh["\']', t, re.I))
    is_noindex = bool(robots and "noindex" in robots.lower())
    f["kind"] = ("artifact" if is_artifact
                 else "redirect" if is_redirect
                 else "noindex" if is_noindex
                 else "indexable")

    # 构建模板片断与搜索引擎验证文件不是页面，不做任何页面级检查。
    if f["kind"] == "artifact":
        f["meta"]["note"] = ("构建模板片断" if is_template else "搜索引擎验证文件")
        return f

    BRAND = "AIHR数智引擎"

    if f["kind"] == "indexable":
        if not title:
            add("C-NOTITLE", "HIGH", "缺少 <title>")
        if not h1:
            add("C-NOH1", "HIGH", "缺少 <h1>")
        if not desc:
            add("C-NODESC", "HIGH", "缺少 meta description")
        elif not (40 <= len(desc) <= 200):
            add("C-DESCLEN", "LOW", "description 长度 %d 超出 40–200 区间" % len(desc))
        if desc and desc.startswith(("这里是", "本站", "AI 时代组织变革实验室", "提供关于", "欢迎来到")):
            add("C-DESCCORRUPT", "HIGH", "description 以站级样板开头（DESC-CORRUPT）")
        if desc and desc.count(BRAND) > 2:
            add("C-DESCFILL", "MED", "description 堆砌品牌词 >2 次")
        if h1 and og_t and norm(h1) != norm(og_t):
            add("C-OGTITLE", "MED", "og:title 与 h1 不一致\n     h1=%s\n     og=%s" % (h1, og_t))
        if h1 and tw_t and norm(h1) != norm(tw_t):
            add("C-TWTITLE", "MED", "twitter:title 与 h1 不一致\n     twitter=%s" % tw_t)
        if og_t and BRAND in og_t:
            add("C-R16", "MED", "og:title 含品牌后缀（违 R-16）", ev=og_t)
        if title and h1 and not (title == h1 or title == h1 + " | " + BRAND):
            add("C-TITLEH1", "LOW", "<title> 与 h1 关系异常\n     title=%s\n     h1=%s" % (title, h1))
        if og_type == "article" and not og_img:
            add("C-NOOGIMG", "MED", "og:type=article 但缺 og:image")
        if og_img and og_img.startswith("/") and not os.path.exists(os.path.join(ROOT, og_img.lstrip("/"))):
            add("C-OGIMG404", "HIGH", "og:image 文件不存在: %s" % og_img)
        if not canon:
            add("C-NOCANON", "MED", "缺少 canonical")
        elif og_u and canon and og_u.rstrip("/") != canon.rstrip("/"):
            add("C-CANONURL", "MED", "canonical 与 og:url 不一致\n     canon=%s\n     og=%s" % (canon, og_u))

        # ---- D 日期三源 ----
        pubs = set()
        # 只取第一个 <time datetime>（后面的属于推荐卡片/列表项，不是本文发布日）
        mt = re.search(r'<time[^>]*datetime="([^"]+)"', t)
        if mt:
            pubs.add(mt.group(1)[:10])
        for ln, blk in jsonld_blocks(t):
            if blk == "__PARSE_FAIL__" or isinstance(blk, str):
                continue
            for n in flatten_nodes(blk):
                v = n.get("datePublished") if isinstance(n, dict) else None
                if isinstance(v, str):
                    pubs.add(v[:10])
        if og_pub:
            pubs.add(og_pub[:10])
        if len(pubs) > 1:
            add("D-DATE", "HIGH", "日期三源不一致: %s" % sorted(pubs))
        if not pubs and og_type == "article":
            add("D-NODATE", "MED", "文章无任何机器可读发布日期")

        # ---- JSON-LD 健康 ----
        for ln, blk in jsonld_blocks(t):
            if isinstance(blk, str) and blk.startswith("__PARSE_FAIL__"):
                add("D-BADJSONLD", "HIGH", "JSON-LD 不可解析: %s" % blk[14:70], ln=ln)
        lds = []
        for ln, blk in jsonld_blocks(t):
            if isinstance(blk, (dict, list)):
                for n in flatten_nodes(blk):
                    if isinstance(n, dict) and n.get("headline"):
                        lds.append(str(n["headline"]))
        if lds and h1 and not any(norm(h1) == norm(x) for x in lds):
            add("D-LDH1", "MED", "JSON-LD headline 与 h1 不一致\n     ld=%s" % lds[0][:80])

    # ---- 正文 ----
    # 「取首个 <article>」是与 ci/gates 对齐的正文契约，但那只成年文为真：
    # 聚合页（categories/tags 等）首个 <article> 就是第一张卡片，会整段误当作本页正文，
    # 于是把子文章的摘要数字算成本页断言。非文章页改取整页 body 再剥结构件。
    if og_type == "article":
        body = article_scope(t)
    else:
        _m = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", t, re.S | re.I)
        body = _m.group(1) if _m else article_scope(t)
    core = body
    for rx in STRIP_SCOPE:
        core = re.sub(rx, " ", core, flags=re.I)
    for rx in [r'<section class="inline-related[\s\S]*?</section>',
               r'<section class="next-path[\s\S]*?</section>',
               r'<div class="article-footer-qr[\s\S]*?</div>\s*</div>',
               r'<div class="geo-answer-capsule[\s\S]*?</div>',
               r'<nav class="article-toc[\s\S]*?</nav>']:
        core = re.sub(rx, " ", core, flags=re.I)

    # 首个信源块原文（用于机构覆盖比对）
    sm = re.search(r'<section[^>]*class="[^"]*(?:verified-sources|fact-sources)[^"]*"[^>]*>([\s\S]*?)</section>',
                   core, re.I)
    src_block = sm.group(0) if sm else None

    # 判定组：块 = 任一信源容器类名。
    # recognized = 门认的；legacy = 老式类名（ abound对我们 invisible，等于没被任何门看见）
    all_blocks = re.findall(
        r'<section[^>]*class="[^"]*(verified-sources|fact-sources|references|sources-block)'
        r'[^"]*"[^>]*>([\s\S]*?)</section>', core, re.I)

    # 读者看得见的信源，除了标准 section 容器，还有「逐条来源行」用法：
    #   · 对比页每家公司末尾的 <p class="co-src">来源：MIT Technology Review…</p>
    #   · 信号简报每条信号末尾的 <p class="src">来源：Mercer Global Talent Trends…</p>
    # 它们不是 <ul>/<li> 结构，但信源对读者完全可见、可点。
    # I-NUMNOSRC 问的是「读者能不能追溯」，认这些容器；H-* 的结构性断言仍只看 section。
    inline_src = [b for b in re.findall(
        r'<(p|div)\b[^>]*class="[^"]*\b(?:co-src|src)\b[^"]*"[^>]*>([\s\S]*?)</\1>',
        core, re.I)
        if re.match(r"\s*(来源|信源|资料来源|Source)", visible_text(b[1]), re.I)]
    # 自述口径：工具/模型页在脚注里声明「阈值为本框架经验值，非统计抽样」并说明参考来源时，
    # 读者已经知道这些数字由谁负责、怎么来的。此时再要一份外部信源属于形式主义。
    self_declared = bool(re.search(
        r"(索引|阈值|基线|区间|口径)[^。]{0,40}(自研|自行设定|经验阈值|非统计抽样|经验切分)",
        core))
    has_visible_sources = bool(all_blocks) or bool(inline_src) or self_declared

    n_all_items = sum(len(re.findall(r"<li\b", b[1], re.I)) for b in all_blocks)
    recognized = [b for b in all_blocks if b[0].lower() in ("verified-sources", "fact-sources")]
    legacy = [b for b in all_blocks if b[0].lower() not in ("verified-sources", "fact-sources")]
    f["src_items"] = n_all_items
    f["src_blocks"] = len(all_blocks)
    if f["kind"] == "indexable":
        if len(all_blocks) > 1:
            add("H-SRCDUP", "HIGH",
                "正文出现 %d 个信源块（重复渲染「参考信源」标题）" % len(all_blocks))
        if n_all_items > 5:
            add("H-SRCNUM", "MED", "信源条目合计 %d 条 > 5（撞尾页一致性关）" % n_all_items)
        if all_blocks and n_all_items == 0:
            add("H-SRCEMPTY", "HIGH", "信源块存在但 0 条 <li> 条目（门不认）")
        if legacy and not recognized:
            add("H-SRCCLASS", "HIGH",
                "信源容器用了门不识别的类名 class=\"%s\"（%d 条条目对所有质量门不可见）"
                % (legacy[0][0], len(re.findall(r"<li\b", legacy[0][1], re.I))))

    # 硬数字扫描的三条豁免。没有它们，这条检查会稳定给出假 HIGH：
    #  1) 聚合页的 <article class="article-card"> 摘要：数字来自子文章，子文章自带信源块，
    #     在聚合页上再要一份等于要求它复制全库；
    #  2) 段落里的数字只出现在 <a> 链接文字内：那是指向别处的标题/锚文本，不是本页断言；
    #  3) 自述方法参数：自测工具的题量、权重、阈值、等级划分是本产品的设计说明，不是外部事实。
    # 判据必须跟「这是不是一条需要外部负责的定量断言」有因果关系，否则就是在制造噪声。
    core_nocard = re.sub(
        r'<article\b[^>]*class="[^"]*\barticle-card\b[^"]*"[\s\S]*?</article>',
        "", core, flags=re.I)
    core_nocard = re.sub(
        r'<div\b[^>]*class="[^"]*\bcard-excerpt\b[^"]*"[\s\S]*?</div>',
        "", core_nocard, flags=re.I)
    if og_type != "article":
        hard_core = core_nocard
    else:
        hard_core = core

    hard = []
    for m in re.finditer(r"<p[^>]*>([\s\S]*?)</p>", hard_core, re.I):
        seg = visible_text(m.group(1))
        if len(seg) < 25:
            continue
        if not HARD_NUM.search(seg):
            continue
        # 豁免 2：数字只存在于链接文字里
        nolink = visible_text(re.sub(r"<a\b[\s\S]*?</a>", "", m.group(1), flags=re.I))
        if not HARD_NUM.search(nolink):
            continue
        # 豁免 3：自述方法参数
        if SELF_METHOD.search(seg):
            continue
        hard.append((line_of(t, m.start(1)), seg))
    f["hard"] = len(hard)
    if f["kind"] == "indexable" and hard and not has_visible_sources:
        for ln, seg in hard[:3]:
            add("I-NUMNOSRC", "HIGH", "含硬数字且整页无可见信源块", ev=seg, ln=ln)

    if src_block:
        # 只报「机构在同句内带着数字出现」的硬证据，避免把叙事性提及误判为数据引用
        src_text = visible_text(src_block)
        for inst in INSTITUTIONS:
            pat = re.compile(r"[^。<>]{0,80}" + re.escape(inst) + r"[^。]{0,120}")
            hits = [m.group(0) for m in pat.finditer(core)]
            for h in hits:
                if HARD_NUM.search(h) and inst not in src_text:
                    add("H-INSTUNCOVERED", "MED",
                        "「%s」在同一句内带定量出现，信源块却无对应条目" % inst,
                        ev=visible_text(h)[:150])
                    break

    # 示例代码块里的「XXXXX」「lorem ipsum」是教学演示，不是面向读者的占位残留；
    # 扫描前先摘掉 code/pre，避免把别人的示例代码报成自家缺陷。
    body_nocode = re.sub(r"<(code|pre)\b[\s\S]*?</\1>", "", body, flags=re.I)
    for pat, name in PLACEHOLDERS:
        for m in re.finditer(pat, body_nocode, re.I):
            add("F-PLACEHOLDER", "HIGH", "占位残留: %s" % name, ev=m.group(0),
                ln=line_of(t, m.start()))

    seen = set()
    for m in re.finditer(r"<p[^>]*>([\s\S]*?)</p>", core, re.I):
        seg = visible_text(m.group(1))
        if len(seg) < 40:
            continue
        if seg in seen:
            add("G-DUPPARA", "MED", "段落整段重复", ev=seg[:120], ln=line_of(t, m.start(1)))
        else:
            seen.add(seg)

    for m in re.finditer(r'style="[^"]*(?:letter-spacing:\s*[-\d.]+px|text-indent:\s*2em)[^"]*"', t, re.I):
        add("J-INLINESTYLE", "LOW", "行内 style 含陈旧印刷风格属性", ev=m.group(0)[:80],
            ln=line_of(t, m.start()))

    return f


def main():
    print("[1/2] 构建 CSS/JS 类名定义集 ...", flush=True)
    css_defined = build_css_class_set()
    print("      已收录 %d 个已定义类名" % len(css_defined), flush=True)

    files = []
    for dirpath, dirs, fs in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for fn in fs:
            if fn.endswith(".html"):
                files.append(os.path.join(dirpath, fn))
    files.sort()

    results = []
    for i, p in enumerate(files, 1):
        results.append(audit_file(p, css_defined))
        if i % 100 == 0:
            print("      已扫描 %d/%d" % (i, len(files)), flush=True)

    outdir = os.path.join(ROOT, "reports")
    os.makedirs(outdir, exist_ok=True)
    json.dump(results, open(os.path.join(outdir, "deep_audit.json"), "w"),
              ensure_ascii=False, indent=1)

    # B-NOCSS 噪声收敛：只有≥3 页共用的未定义类才算系统性组件缺失；
    # 单页孤例可能是语义钩子或拼写错误，降级为 LOW 并在最后单独列出。
    cls_pages = {}
    for r in results:
        for it in r["issues"]:
            if it["code"] == "B-NOCSS":
                m = re.search(r"`([^`]+)`", it["msg"])
                if m:
                    cls_pages.setdefault(m.group(1), []).append(r["file"])
    for r in results:
        for it in r["issues"]:
            if it["code"] == "B-NOCSS":
                m = re.search(r"`([^`]+)`", it["msg"])
                c = m.group(1) if m else ""
                if len(cls_pages.get(c, [])) < 3:
                    it["sev"] = "LOW"
                    it["msg"] = it["msg"].replace("（组件可能裸奔）", "（单页孤例，可能为语义钩子或拼写）")
    print("\n  未定义类（>=3 页共用 = 系统性组件缺失）：", flush=True)
    systemic = {c: v for c, v in cls_pages.items() if len(v) >= 3}
    if systemic:
        for c, v in sorted(systemic.items(), key=lambda kv: -len(kv[1])):
            print("    %-34s %3d 页  例: %s" % (c, len(v), v[0]))
    else:
        print("    无")

    by_code = {}
    sev_of = {}
    for r in results:
        for it in r["issues"]:
            by_code.setdefault(it["code"], []).append(r["file"])
            sev_of[it["code"]] = it["sev"]

    print("\n" + "=" * 68)
    print("  深度审计：%d 个 HTML" % len(results))
    print("=" * 68)
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    for code, fs in sorted(by_code.items(), key=lambda kv: (order.get(sev_of[kv[0]], 9), -len(kv[1]))):
        sev = sev_of[code]
        flag = {"HIGH": "🔴", "MED": "🟡", "LOW": "⚪"}[sev]
        print("%s %-20s %-5s %4d 文件" % (flag, code, sev, len(fs)))
    print("=" * 68)
    print("  零问题页面：%d / %d" % (sum(1 for r in results if not r["issues"]), len(results)))
    print("  明细：reports/deep_audit.json")


if __name__ == "__main__":
    main()
