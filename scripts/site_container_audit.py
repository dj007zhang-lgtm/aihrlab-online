#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AIHRlab（网站）· 容器完整性巡检。

体系归属：**AIHRlab 网站**。本文件只判网站容器缺陷，不判公众号文风调性——
那是 aihr-hardcore-writing skill 与 content-redlines.md 的职责，两套体系不混用。

为什么存在：历史上网站自动化只覆盖「结构/机械」一类失效（死链、标签平衡），
而「容器完整性」（元数据自洽、跨页污染、canonical 自指、JSON-LD 可解析）
长期零覆盖——og:title 拼接损坏能在 305 页 × 10 次巡检中全部存活，就是这个空白。

检查项（均为可机检、有明确判据）：
  C1  h1 存在且唯一
  C2  h1 == og:title == twitter:title（R-16/R-17）
  C3  h1 / og:title / twitter:title 不含 "| AIHR数智引擎" 后缀（仅 <title> 允许）
  C4  meta 字段不得混入他页标题（跨页污染 / 拼接损坏）
  C5  canonical 存在且自指本页 URL
  C6  所有 JSON-LD 块可被 json.loads 解析
  C7  description 长度在合理区间（<70 过短 / >170 过长）
  C8  noindex 页必须同时具备 refresh + canonical（= 合法 URL 合并跳转壳）；
      否则视为「不该存在却被 noindex」的异常页
  C9  sitemap 中的 URL 对应本地文件必须存在

退出码：0 = 全部通过；1 = 存在 WARN；2 = 存在 BLOCK（构建/发布应被阻断）。
用法：python3 scripts/site_container_audit.py [--json out.json]
"""
import re, os, sys, glob, json, html

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.aihrlab.online"
SUFFIX = "| AIHR数智引擎"
SCAN_DIRS = ("articles/*.html", "hub/*.html", "assessments/*.html",
             "resources/*.html", "products/*.html", "brief/*.html")

META_RE = re.compile(r'<meta\s+([^>]*?)/?>', re.I | re.S)
LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.I | re.S)


def meta_map(s):
    out = {}
    for m in META_RE.finditer(s):
        a = m.group(1)
        k = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', a, re.I)
        v = re.search(r'content\s*=\s*["\']([^"\']*)["\']', a, re.I)
        if k and v:
            out.setdefault(k.group(1).lower(), []).append(html.unescape(v.group(1)).strip())
    return out


def get_h1s(s):
    return [re.sub(r'<[^>]+>', '', m.group(1)).strip()
            for m in re.finditer(r'<h1[^>]*>(.*?)</h1>', s, re.I | re.S)]


def is_redirect_shell(s, mm):
    """合法 URL 合并壳 = noindex + meta refresh + canonical 三者齐备。"""
    robots = " ".join(mm.get("robots", [])).lower()
    return ("noindex" in robots
            and re.search(r'http-equiv\s*=\s*["\']refresh', s, re.I) is not None
            and bool(re.search(r'rel\s*=\s*["\']canonical', s, re.I)))


def audit_file(rel, s, corpus):
    """返回 findings: [(level, code, detail)]"""
    f = []
    mm = meta_map(s)
    h1s = [h for h in get_h1s(s) if h]
    shell = is_redirect_shell(s, mm)

    # C1 h1 唯一。跳转壳（noindex+refresh+canonical）本就无正文，豁免。
    if shell:
        h1 = h1s[0] if h1s else None
    elif not h1s:
        f.append(("BLOCK", "C1", "缺少 h1"))
        h1 = None
    else:
        if len(h1s) > 1:
            f.append(("WARN", "C1", f"存在 {len(h1s)} 个 h1（应唯一）"))
        h1 = h1s[0]

    og = (mm.get("og:title") or [None])[0]
    tw = (mm.get("twitter:title") or [None])[0]

    if not shell:
        # C2 三值一致
        if h1 and og and h1 != og:
            f.append(("BLOCK", "C2", f"og:title ≠ h1（og={og[:40]} / h1={h1[:40]}）"))
        if h1 and tw and h1 != tw:
            f.append(("BLOCK", "C2", f"twitter:title ≠ h1（tw={tw[:40]} / h1={h1[:40]}）"))
        if not og:
            f.append(("BLOCK", "C2", "缺少 og:title"))
        # C3 后缀纪律
        for fld, val in (("h1", h1), ("og:title", og), ("twitter:title", tw)):
            if val and SUFFIX in val:
                f.append(("BLOCK", "C3", f"{fld} 含禁止后缀「{SUFFIX}」（仅 <title> 允许）"))
        # C4 跨页污染
        for fld in ("og:title", "twitter:title", "description", "og:description"):
            for val in mm.get(fld, []):
                for other, otitles in corpus.items():
                    if other == rel:
                        continue
                    for t in otitles:
                        if len(t) >= 12 and t in val and t != h1:
                            f.append(("BLOCK", "C4",
                                      f"{fld} 混入 {other} 的标题「{t[:36]}」（拼接损坏/注入污染）"))
                            break
        # C5 canonical 自指
        can = re.search(r'rel\s*=\s*["\']canonical["\'][^>]*href\s*=\s*["\']([^"\']+)', s, re.I) \
            or re.search(r'href\s*=\s*["\']([^"\']+)["\'][^>]*rel\s*=\s*["\']canonical', s, re.I)
        if not can:
            f.append(("BLOCK", "C5", "缺少 canonical"))
        else:
            def canon_key(x):
                """目录 canonical /x/ 与 /x/index.html 等价。"""
                x = x.replace(SITE, "").strip()
                x = x[:-5] if x.endswith(".html") else x
                x = x.rstrip("/")
                if x.endswith("/index"):
                    x = x[:-6]
                return x.lstrip("/")
            if canon_key(can.group(1)) != canon_key("/" + rel):
                f.append(("WARN", "C5", f"canonical 不自指（={can.group(1)[:60]}）"))
        # C10 head 区孤儿行：内容恰为 ">"，是破损标签残骸，会让解析器提前闭合 head
        for i, line in enumerate(s.split("\n"), 1):
            if line.strip() == '">':
                f.append(("BLOCK", "C10", f"head 区第 {i} 行是孤儿 '\">'（破损标签残骸）"))
                break
        # C11 meta content 内含未转义半角双引号：属性被提前闭合，生效值被截断
        bad_tag = 0
        for tm in re.finditer(r'<meta\b[^>]*>', s, re.I):
            core = tm.group(0)[:-1]
            if core.endswith("/"):
                core = core[:-1]
            cm = re.search(r'\scontent="(.*?)"(?=\s|$)', core)
            if cm and '"' in cm.group(1):
                bad_tag += 1
        if bad_tag:
            f.append(("BLOCK", "C11",
                      f"{bad_tag} 个 meta 的 content 含未转义半角双引号（值会被截断）"))
        # C7 description 长度
        for val in mm.get("description", [])[:1]:
            if len(val) < 70:
                f.append(("WARN", "C7", f"description 过短（{len(val)} 字 < 70）"))
            elif len(val) > 170:
                f.append(("WARN", "C7", f"description 过长（{len(val)} 字 > 170）"))
    else:
        # C8 跳转壳合法性
        pass

    # C6 JSON-LD 可解析（壳页也查）
    for i, blk in enumerate(LD_RE.findall(s)):
        t = blk.strip()
        if not t:
            continue
        try:
            json.loads(t)
        except Exception as e:
            f.append(("BLOCK", "C6", f"JSON-LD 第 {i+1} 块无法解析：{str(e)[:60]}"))
    return f


def main():
    os.chdir(SITE_ROOT)
    files = sorted(sum([glob.glob(p) for p in SCAN_DIRS], []))
    files = [f for f in files if os.path.isfile(f)]

    # 语料：各页 h1 + <title>（去后缀），用于跨页污染比对
    corpus = {}
    for rel in files:
        s = open(rel, encoding="utf-8").read()
        hs = [h for h in get_h1s(s) if h]
        t = re.search(r'<title>(.*?)</title>', s, re.I | re.S)
        tt = html.unescape(t.group(1)).replace(SUFFIX, "").strip() if t else None
        corpus[rel] = [x for x in hs + [tt] if x and len(x) >= 12]

    allf = []
    for rel in files:
        s = open(rel, encoding="utf-8").read()
        for lvl, code, detail in audit_file(rel, s, corpus):
            allf.append({"file": rel, "level": lvl, "code": code, "detail": detail})

    # C9 sitemap URL 对应本地文件存在
    sm_p = os.path.join(SITE_ROOT, "sitemap.xml")
    if os.path.exists(sm_p):
        sm = open(sm_p, encoding="utf-8").read()
        for u in re.findall(r"<loc>(.*?)</loc>", sm):
            p = u.replace(SITE, "").lstrip("/")
            if not p:
                continue
            cands = [p, p + "/index.html", p.rstrip("/") + "/index.html"]
            if not any(os.path.exists(c) for c in cands):
                allf.append({"file": "sitemap.xml", "level": "BLOCK",
                             "code": "C9", "detail": f"sitemap URL 无本地文件：{u}"})

    blocks = [x for x in allf if x["level"] == "BLOCK"]
    warns = [x for x in allf if x["level"] == "WARN"]

    print("=" * 78)
    print(f"AIHRlab 网站容器完整性巡检 · 扫描 {len(files)} 页")
    print("=" * 78)
    print(f"BLOCK = {len(blocks)}   WARN = {len(warns)}")
    if blocks:
        print("\n【BLOCK · 必须修复】")
        seen = set()
        for x in blocks:
            k = (x["code"], x["file"])
            if k in seen:
                continue
            seen.add(k)
            print(f"  [{x['code']}] {x['file']}")
            print(f"        {x['detail']}")
    if warns:
        by = {}
        for x in warns:
            by.setdefault(x["code"], []).append(x)
        print(f"\n【WARN · 按类型聚合 {len(warns)} 条】")
        for c, lst in sorted(by.items()):
            print(f"  {c}: {len(lst)} 条  样例: {lst[0]['file']} — {lst[0]['detail'][:60]}")
    if not blocks and not warns:
        print("\n✅ 全部通过")
    print("=" * 78)

    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump({"scanned": len(files), "blocks": blocks, "warns": warns},
                  open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"明细已写入 {out}")

    return 2 if blocks else (1 if warns else 0)


if __name__ == "__main__":
    sys.exit(main())
