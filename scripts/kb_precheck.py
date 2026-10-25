#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
站点文章 <-> UncleJ-wiki 知识库 信源校验与反向回流（非阻断）

做什么：
  1. 校验：发布前的文章是否带 fact-sources 信源区块；其中的硬数字能否在知识库
     台账（assets/data_sources.md）找到对应 DATA-xxx；命中 tier3 的源是否被当作主论据。
  2. 回流：文章里「机构 + 报告 + 样本量 + 数字」齐备、但台账尚未收录的信源，
     自动汇总成候选清单，供补登台账——让已发布内容反哺知识库，而不是单向消耗。

为什么非阻断（观察期）：
  站点已有 300+ 篇存量文章，历史信源不可能一夜挂上 DATA-xxx。一上来就阻断
  会导致无法发布。当前阶段只报告、不中止；待存量迁移完成再评估是否升级为阻断门。

用法：
  python3 scripts/kb_precheck.py articles/xxx.html [更多文件]
  python3 scripts/kb_precheck.py --all            # 全站文章（较慢）
  python3 scripts/kb_precheck.py articles/x.html --json

退出码：恒 0（非阻断，仅报告）。异常亦不抛出，保证不破坏 publish.py 的双闸。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(SITE_ROOT, "reports", "kb_precheck-candidates.md")

NUM_RE = re.compile(r"(?<![\w.])\d{1,3}(?:\.\d+)?%")

try:
    import kb_bridge as KB
except Exception:  # 知识库不可达时降级为纯结构校验，绝不阻断发布
    KB = None


def org_tokens(s):
    """从台账的「机构 / 报告」列抽出可比对 token（英文词 + 《前中文串）。"""
    toks = set()
    head = re.split(r"《|（|\(", s)[0]
    for w in re.findall(r"[A-Za-z][A-Za-z&.\-]{2,}", head):
        if len(w) >= 3:
            toks.add(w.lower())
    for w in re.findall(r"[\u4e00-\u9fa5]{2,6}", head):
        toks.add(w)
    return toks


def load_ledger():
    if KB is None:
        return {}
    try:
        rows = KB.parse_ledger()
    except Exception:
        return {}
    out = {}
    for sid, r in rows.items():
        text = " ".join(str(v) for v in r.values())
        out[sid] = {
            "tokens": org_tokens(str(r.get("机构 / 报告", ""))),
            "nums": set(NUM_RE.findall(text)),
            "tier": str(r.get("tier", "")).strip(),
            "org": str(r.get("机构 / 报告", ""))[:40],
        }
    return out


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", s).strip()


# 站点历史上有两套信源区块 class，必须都认，否则大量误报：
#   verified-sources（184 篇，带 verified-sources__item/__link/__meta）
#   fact-sources（58 篇，旧版契约模板）
SOURCE_SECTION_RE = re.compile(
    r'<section class="(?:verified-sources|fact-sources)".*?</section>', re.S)


def extract_fact_sources(html):
    blocks = []
    for m in SOURCE_SECTION_RE.finditer(html):
        # `<li[^>]*>`：verified-sources 的条目带 class 属性，纯 `<li>` 匹配不到
        blocks += [strip_tags(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", m.group(0), re.S)]
    return blocks or None


def extract_body_numbers(html):
    """正文（去 fact-sources）里出现的百分比，用于发现无归属数字。"""
    body = SOURCE_SECTION_RE.sub("", html)
    return set(NUM_RE.findall(strip_tags(body)))


def check_file(path, ledger):
    try:
        html = open(path, encoding="utf-8", errors="ignore").read()
    except Exception as e:
        return {"file": path, "error": str(e)}

    res = {"file": os.path.relpath(path, SITE_ROOT), "has_fact_sources": False,
           "sources": 0, "hit": [], "unregistered": [], "tier3_as_main": [],
           "unattributed": []}

    lis = extract_fact_sources(html)
    if not lis:
        res["has_fact_sources"] = False
        return res
    res["has_fact_sources"] = True
    res["sources"] = len(lis)

    for li in lis:
        nums = set(NUM_RE.findall(li))
        if not nums:
            continue
        low = li.lower()
        matched = None
        for sid, meta in ledger.items():
            if not (nums & meta["nums"]):
                continue
            if any(t in low for t in meta["tokens"]):
                matched = sid
                break
        if matched:
            res["hit"].append({"id": matched, "org": ledger[matched]["org"],
                               "tier": ledger[matched]["tier"], "nums": sorted(nums)[:6]})
            if ledger[matched]["tier"] == "3":
                res["tier3_as_main"].append(matched)
        else:
            # 机构 + 数字齐备但未入台账 → 回流候选
            has_org = bool(re.search(r"[A-Za-z]{3,}|[\u4e00-\u9fa5]{2,}", li))
            has_n = bool(re.search(r"\d[\d,]{2,}|名|位", li))
            res["unregistered"].append({
                "org": li[:60],
                "nums": sorted(nums)[:8],
                "complete": has_org and has_n,
            })

    body_nums = extract_body_numbers(html)
    src_nums = set()
    for li in lis:
        src_nums |= set(NUM_RE.findall(li))
    res["unattributed"] = sorted(body_nums - src_nums)[:10]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    files = a.files
    if a.all or not files:
        adir = os.path.join(SITE_ROOT, "articles")
        files = [os.path.join(adir, f) for f in sorted(os.listdir(adir))
                 if f.endswith(".html") and f != "index.html"]
        if not a.all and not a.files:
            print(__doc__)
            return 0

    ledger = load_ledger()
    results = [check_file(f, ledger) for f in files]

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0

    print("=" * 60)
    print("知识库信源校验（非阻断 · 观察期）")
    print("=" * 60)
    print(f"台账数据源: {len(ledger)} 条" if ledger else "知识库不可达，仅做结构校验")

    no_fs = [r for r in results if not r.get("has_fact_sources")]
    hits = sum(len(r.get("hit", [])) for r in results)
    unreg = [(r["file"], u) for r in results for u in r.get("unregistered", [])]
    t3 = [(r["file"], x) for r in results for x in r.get("tier3_as_main", [])]
    unattr = [(r["file"], n) for r in results for n in r.get("unattributed", [])]

    print(f"扫描 {len(results)} 篇 | 命中台账 {hits} 处 | "
          f"未登记信源 {len(unreg)} 条 | tier3 主论据 {len(t3)} 处 | "
          f"正文无归属数字 {len(unattr)} 处")

    if no_fs:
        print(f"\n[WARN] {len(no_fs)} 篇缺 fact-sources 信源区块（契约第 2 条要求必须带）：")
        for r in no_fs[:5]:
            print("   -", r["file"])
        if len(no_fs) > 5:
            print(f"   ... 另有 {len(no_fs) - 5} 篇")

    if t3:
        print(f"\n[WARN] 命中 tier3（待核）源作主论据 {len(t3)} 处，成稿前应替换或补核验：")
        for f, sid in t3[:5]:
            print(f"   - {f} → {sid}")

    if unattr:
        print(f"\n[WARN] 正文出现但信源区块未逐条列出的数字 {len(unattr)} 处（抽样 10）：")
        print("   口径：数字可能已在正文行内标注机构（如「BCG 调研显示 65%」），")
        print("   本项仅提示未在信源区块逐条列出者，须人工判断是否需补录，不直接判违规。")
        for f, n in unattr[:10]:
            print(f"   - {f} → {n}")

    if unreg:
        print(f"\n[回流候选] {len(unreg)} 条信源机构+数字齐备但台账未收录，建议补登：")
        for f, u in unreg[:8]:
            print(f"   - {u['org'][:52]} | 数字 {','.join(u['nums'][:5])}")
        if len(unreg) > 8:
            print(f"   ... 另 {len(unreg) - 8} 条见 {os.path.relpath(REPORT, SITE_ROOT)}")

    # 候选清单落盘，供回写台账时逐条处理
    try:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        with open(REPORT, "w", encoding="utf-8") as fh:
            fh.write("# 台账补登候选（站点文章反向回流 · 自动生成）\n\n")
            fh.write("> 由 scripts/kb_precheck.py 生成。每条含机构、数字、来源文章；\n")
            fh.write("> 补登 assets/data_sources.md 时须补齐 机构+年份+样本量 n，缺项降级 tier3。\n\n")
            for f, u in unreg:
                fh.write(f"- `{f}` → {u['org']}\n  - 数字：{', '.join(u['nums'])}\n")
    except Exception:
        pass

    print("\n结果：非阻断，发布继续。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[kb_precheck] 异常已忽略（非阻断）: {e}")
        sys.exit(0)
