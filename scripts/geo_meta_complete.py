#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo_meta_complete.py — 补全 GEO 答案元数据 (short-answer / answer-for)
基于 GA4 数据: 99.5% 首访用户 = AI 引擎发现型流量, 需最大化可被引用字段。

规则:
- short-answer: 若缺失, 从正文首段首句提取 (不编造, 用文章自身内容)
- answer-for:   若缺失或为空标签, 设为 "voice-search; generative-ai" (与现有 34 篇一致)
- 幂等: 重跑产生 0 改动
- 跳过: 桩页 / 非文章页
"""
import glob, re, os, sys

ARTICLES_DIR = "articles"
ANSWER_FOR_DEFAULT = "voice-search; generative-ai"

def is_stub(html):
    return ("页面已迁移" in html) or ("http-equiv" in html.lower())

def extract_short_answer(html):
    """从正文首段提取首句作为 short-answer (合法提取, 非编造)。"""
    # 定位正文起点: v2 在 </header> 后, v1 在 </h1> 后
    h1end = html.find("</h1>")
    if h1end == -1:
        m = re.search(r"</header>", html)
        h1end = m.end() if m else 0
    body = html[h1end:]
    # 优先取首个无 class 的纯 <p> (跳过 alert/update 类)
    pm = re.search(r"<p>(.*?)</p>", body, re.DOTALL)
    if not pm:
        pm = re.search(r"<p[^>]*>(.*?)</p>", body, re.DOTALL)
    if not pm:
        return None
    raw = pm.group(1)
    txt = re.sub(r"<[^>]+>", "", raw)
    txt = re.sub(r"\s+", " ", txt).strip()
    # 过滤导航/导读式开场句 (非实质答案)
    if re.match(r"^(读完本文|本文你将|你将获得|点击|关注|订阅|欢迎)", txt):
        # 再取下一个纯 <p>
        pm2 = re.search(r"<p>(.*?)</p>", body[pm.end():], re.DOTALL)
        if pm2:
            txt = re.sub(r"<[^>]+>", "", pm2.group(1))
            txt = re.sub(r"\s+", " ", txt).strip()
    if not txt:
        return None
    txt = re.sub(r"\s+", " ", txt).strip()
    if not txt:
        return None
    # 取首句 (到第一个句号/问号/叹号)
    m2 = re.search(r"^.{1,100}?[。？！]", txt)
    if m2:
        ans = m2.group(0).strip()
    else:
        ans = txt[:100].strip()
    ans = ans.strip("「」\"' ")
    return ans if ans else None

def set_meta(html, name, value):
    """设置 <meta name="X" content="V">, 顺序无关; 缺失则插入 og:title 后, 空标签则补 content。"""
    pat = re.compile(r'<meta[^>]*name="%s"[^>]*>' % re.escape(name))
    m = pat.search(html)
    if m:
        tag = m.group(0)
        if re.search(r'content="[^"]+"', tag):
            return html, False  # 已有有效值
        # 空标签或空 content -> 替换整条
        new_tag = '<meta name="%s" content="%s">' % (name, value)
        return pat.sub(lambda x: new_tag, html, count=1), True
    # 缺失 -> 插入到 og:title 之后
    og = re.search(r'(<meta[^>]*property="og:title"[^>]*>)', html)
    if og:
        insert_pos = og.end()
        return html[:insert_pos] + '\n    <meta name="%s" content="%s">' % (name, value) + html[insert_pos:], True
    # fallback: head 内
    head = re.search(r'(<head[^>]*>)', html, re.IGNORECASE)
    if head:
        return html[:head.end()] + '\n    <meta name="%s" content="%s">' % (name, value) + html[head.end():], True
    return html, False

def main():
    apply = "--apply" in sys.argv
    dry = not apply
    changed = 0
    for f in sorted(glob.glob(os.path.join(ARTICLES_DIR, "*.html"))):
        html = open(f, encoding="utf-8").read()
        if is_stub(html):
            continue
        new_html = html
        did = False
        # short-answer
        sa = re.search(r'<meta[^>]*name="short-answer"[^>]*>', new_html)
        sa_ok = sa and re.search(r'content="[^"]+"', sa.group(0))
        if not sa_ok:
            ans = extract_short_answer(new_html)
            if ans:
                new_html, c = set_meta(new_html, "short-answer", ans)
                did = did or c
        # answer-for
        af = re.search(r'<meta[^>]*name="answer-for"[^>]*>', new_html)
        af_ok = af and re.search(r'content="[^"]+"', af.group(0))
        if not af_ok:
            new_html, c = set_meta(new_html, "answer-for", ANSWER_FOR_DEFAULT)
            did = did or c
        if did:
            changed += 1
            if dry:
                slug = os.path.basename(f)
                print(f"  [will fix] {slug}")
            else:
                open(f, "w", encoding="utf-8").write(new_html)
    print(f"\n{'APPLY' if apply else 'DRY-RUN'}: {changed} articles need/will change")
    if not dry:
        print("已写入。")

if __name__ == "__main__":
    main()
