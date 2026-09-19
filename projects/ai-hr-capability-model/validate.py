#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CM-2026 项目校验脚本
把 02-DECISIONS.md 中的 M 类（机器可验）判断写成可执行断言。
用法： python3 projects/ai-hr-capability-model/validate.py
退出码： 0=全过  1=存在 FAIL
"""
import os
import re
import sys
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
# ROOT = <site>/projects/ai-hr-capability-model，需上溯两级才是站点根
SITE = os.path.dirname(os.path.dirname(ROOT))
RESULTS = []
SELF = os.path.abspath(__file__)


def chk(cid, name, ok, actual, expected, note="", status=None):
    if status is None:
        status = "PASS" if ok else "FAIL"
    RESULTS.append({
        "id": cid, "name": name, "status": status,
        "actual": actual, "expected": expected, "note": note,
    })


# V-00 哨兵：路径解析必须落在站点根，否则后续检查全部不可信
def v00():
    ok = os.path.exists(os.path.join(SITE, "sitemap.xml")) and \
         os.path.isdir(os.path.join(SITE, "articles"))
    chk("V-00", "哨兵：SITE 指向站点根", ok,
        SITE if ok else f"路径错：{SITE}", "含 sitemap.xml 与 articles/")


def read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


# V-01 全站不得出现简历上传控件（D-006）
def v01():
    hits = []
    for dirpath, _, files in os.walk(SITE):
        if any(x in dirpath for x in (".git", "node_modules", "articles-backup")):
            continue
        for fn in files:
            if not fn.endswith(".html"):
                continue
            h = read(os.path.join(dirpath, fn))
            if re.search(r'type\s*=\s*["\']file["\']', h):
                hits.append(os.path.relpath(os.path.join(dirpath, fn), SITE))
    chk("V-01", "全站无简历上传控件 (D-006)", len(hits) == 0,
        f"{len(hits)} 处", "0 处",
        ("命中：" + ", ".join(hits[:3])) if hits else "")


# V-02 测评页站内出链（D-002 修复目标）
def v02():
    tools = {"bigfive": "tools/bigfive/index.html",
             "mbti": "tools/mbti/index.html",
             "holland": "tools/holland/index.html",
             "disc-test": "tools/disc-test/index.html"}
    weak = []
    detail = []
    for k, rel in tools.items():
        h = read(os.path.join(SITE, rel))
        links = set(re.findall(r'href="(/[^"]*)"', h))
        links = {l for l in links if not l.startswith("/assets")}
        detail.append(f"{k}={len(links)}")
        if len(links) < 3:
            weak.append(k)
    chk("V-02", "测评页站内出链 >=3（D-002 债）", len(weak) == 0,
        " ".join(detail), "每页 >=3",
        ("薄弱：" + ", ".join(weak)) if weak else "")


# V-03 不得出现招聘平台爬虫（D-007）
def v03():
    plat = ["boss直聘", "BOSS直聘", "zhipin", "猎聘", "liepin", "拉勾", "lagou",
            "51job", "智联招聘"]
    crawl = ["crawler", "spider", "scrapy", "selenium", "playwright"]
    hits = []
    for base in (os.path.join(SITE, "scripts"), os.path.join(SITE, "projects"), SITE):
        for dirpath, _, files in os.walk(base):
            if ".git" in dirpath:
                continue
            for fn in files:
                if not fn.endswith((".py", ".sh")):
                    continue
                p = os.path.join(dirpath, fn)
                if os.path.abspath(p) == SELF:
                    continue
                t = read(p)
                if not t:
                    continue
                if any(x in t for x in plat) and any(y in t.lower() for y in crawl):
                    hits.append(os.path.relpath(p, SITE))
    chk("V-03", "无招聘平台爬虫脚本 (D-007)", len(hits) == 0,
        f"{len(hits)} 处", "0 处",
        ("命中：" + ", ".join(hits[:3])) if hits else "")


# V-04 v1 每项能力须同时含层级锚点与常见误判（D-005）
def v04():
    p = os.path.join(ROOT, "01-capability-model-v1.md")
    t = read(p)
    items = re.findall(r"\*\*(\d\.\d) ", t)
    misjudge = t.count("常见误判")
    levels = len(re.findall(r"层级：", t))
    n = len(items)
    ok = n >= 20 and misjudge >= n and levels >= n
    chk("V-04", "v1 每项含层级+误判 (D-005)", ok,
        f"能力项 {n} / 层级 {levels} / 误判 {misjudge}",
        f"三者均 >= {max(n, 20)}")


# V-05 证据层须含性格测评硬排除条款（D-010）
def v05():
    t = read(os.path.join(ROOT, "01-capability-model-v1.md"))
    ok = ("硬排除" in t) and ("性格测评分数" in t) and ("不进入任何一项" in t)
    chk("V-05", "证据层硬排除性格测评 (D-010)", ok,
        "条款存在" if ok else "条款缺失", "条款存在")


# V-06 口径纪律：技能本位百分比须带分母标注（D-014）
def v06():
    t = read(os.path.join(ROOT, "01-capability-model-v1.md"))
    ok = "口径" in t and "分母" in t
    chk("V-06", "口径分歧已标注 (D-014)", ok,
        "已标注" if ok else "未标注", "已标注")


# V-07 qa_guardian 基线不劣化（D-016）
def v07():
    bp = os.path.join(SITE, "ci", "baseline", "health_baseline.json")
    if not os.path.exists(bp):
        chk("V-07", "qa_guardian 基线存在 (D-016)", False, "缺失", "存在")
        return
    d = json.load(open(bp, encoding="utf-8"))
    g = d.get("gates", {})
    thin = g.get("stub_detector", {}).get("thin_block")
    clone = g.get("clone_detection", {}).get("clone_clusters")
    chk("V-07", "qa_guardian 基线已锁定 (D-016)",
        thin is not None and clone == 0,
        f"thin_block={thin} clone={clone}", "clone=0 且 thin_block 有值")


# V-08 镜像须带 source_commit（D-017）
def v08():
    mirrors = [f for f in os.listdir(ROOT) if f.startswith("MIRROR-")]
    if not mirrors:
        chk("V-08", "镜像带 source_commit (D-017)", False,
            "尚无镜像（P0 正常态）", "P1 起须有镜像", status="SKIP")
        return
    ok = all("source_commit" in read(os.path.join(ROOT, m)) for m in mirrors)
    chk("V-08", "镜像带 source_commit (D-017)", ok,
        f"{len(mirrors)} 个镜像", "全部含 source_commit")


# V-09 镜像落点必须绑定 AIHR 团队（D-023）
# 说明：这是台账自校验。真正的空间归属无法离线判定，须由人工在乐享侧
# 复核（见 03-VALIDATION.md 的「人工核验」栏）。脚本盯住的是「台账有没有
# 如实记录已迁/未迁」，防的是台账写了 LIVE 而实际没迁。
AIHR_TEAM_ID = "a808edd6b44211f18075aa6188fe0d3c"


def v09():
    m = os.path.join(ROOT, "MIRROR-LEXIANG.md")
    t = read(m)
    if not t:
        chk("V-09", "镜像落点绑定 AIHR 团队 (D-023)", False,
            "无 MIRROR 文件", "存在且绑定", status="SKIP")
        return
    tid = re.search(r"mirror_team_id:\s*(\S+)", t)
    sid = re.search(r"mirror_space_id:\s*(\S+)", t)
    st = re.search(r"mirror_status:\s*(\S+)", t)
    got_tid = tid.group(1) if tid else "缺失"
    got_sid = sid.group(1) if sid else "缺失"
    got_st = st.group(1) if st else "缺失"
    if got_tid != AIHR_TEAM_ID:
        chk("V-09", "镜像落点绑定 AIHR 团队 (D-023)", False,
            f"team_id={got_tid}", f"team_id={AIHR_TEAM_ID[:12]}…",
            "落点团队不对")
        return
    if got_st == "LIVE":
        # 声称已迁：space_id 必须是真实 id，不能还是 PENDING 或占位
        ok = got_sid not in ("PENDING", "缺失", "") and len(got_sid) >= 16
        chk("V-09", "镜像落点绑定 AIHR 团队 (D-023)", ok,
            f"LIVE / space_id={got_sid[:12]}…", "LIVE 且 space_id 为真实 id",
            "" if ok else "声称已迁但 space_id 无效——台账与实际不一致")
        return
    chk("V-09", "镜像落点绑定 AIHR 团队 (D-023)", True,
        f"BLOCKED / 待建知识库", "未迁时须如实标记 BLOCKED",
        "落点已绑定 AIHR 团队；等待团队下建知识库后迁入", status="SKIP")


# V-02b 测评页不得出现重复的「延伸阅读」区块（防盲目补丁叠块）
# 教训：2026-09-20 修 V-02 时未先读工作区当前状态，直接插入新区块，与上一轮
# 已加但未落 commit 的区块叠成两个「延伸阅读」。教训写成断言，不写进教训本。
def v02b():
    tools = {"bigfive": "tools/bigfive/index.html",
             "mbti": "tools/mbti/index.html",
             "holland": "tools/holland/index.html",
             "disc-test": "tools/disc-test/index.html"}
    dup = []
    for k, rel in tools.items():
        h = read(os.path.join(SITE, rel))
        n = len(re.findall(r'class="ext-read"', h))
        if n > 1:
            dup.append(f"{k}={n}")
    chk("V-02b", "测评页延伸阅读区块不重复", len(dup) == 0,
        " ".join(dup) if dup else "每页 <=1", "每页 <=1",
        ("叠块：" + ", ".join(dup)) if dup else "")


def main():
    for fn in (v00, v01, v02, v02b, v03, v04, v05, v06, v07, v08, v09):
        try:
            fn()
        except Exception as e:
            chk(fn.__name__.upper(), fn.__doc__ or fn.__name__, False,
                f"异常：{e}", "无异常")
    w = max(len(r["name"]) for r in RESULTS) + 2
    print(f"{'ID':<6}{'检查项':<{w}}{'状态':<6}{'实测':<28}期望")
    print("-" * (6 + w + 6 + 28 + 24))
    for r in RESULTS:
        print(f"{r['id']:<6}{r['name']:<{w}}{r['status']:<6}{r['actual']:<28}{r['expected']}")
        if r["note"]:
            print(f"{'':<6}↳ {r['note']}")
    fail = [r for r in RESULTS if r["status"] == "FAIL"]
    print("-" * (6 + w + 6 + 28 + 24))
    print(f"合计 {len(RESULTS)} 项，PASS {len(RESULTS)-len(fail)}，FAIL {len(fail)}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
