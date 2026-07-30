#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标题一致性检测（Title Consistency Check）
========================================
目的：在质量门里装上"眼睛"，专门捕捉此前反复出现、但旧质量门看不见的基础 bug：

  1. 标题截断（title 是 og:title / H1 的前半截）
     —— 写文/模板写入时把 <title> 截成半句，导致 SERP 展示残缺、排名信号打折。
        判定：title_core 是 og_core / h1 的【严格前缀】（且明显更短）= 物理截断 → FAIL。
        注：若 title 与 og 只是措辞不同（非前缀关系），属正常变体，仅 WARN。

  2. 引号污染（中文内容里混入 HTML 实体或英文双引号）
     —— `&amp;quot;`（双重转义，永远错误）、`&quot;`、`"` 出现在可见文本中，
        渲染成乱码或英文引号，破坏中文排版与信任感。统一应使用「」。
        检测范围限定在可见文本元素：<title> / <meta description> / og:title /
        og:description / <h1> / <h2> / 卡片 <h3> / inline-related 链接文字。
        属性值里的合法引号不在检测范围（避免误报）。

  3. 标题超长（> 28 字，移动端 SERP 会被截断）
     —— 但规则升级：超长标题必须"重写保留原意"，禁止物理截断。
        本脚本只报超长，是否"重写而非截断"由人工/AI 在修复时保证（见 README 注释）。

用法：
  python3 scripts/check_title_consistency.py            # 全站扫描
  python3 scripts/check_title_consistency.py articles/x.html  # 单文件
返回：发现任意 FAIL 则 exit 1，否则 exit 0。
"""

import os
import re
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 品牌后缀（从 title / og:title 中剥离后再比较）
BRAND_SUFFIXES = ["| AIHR数智引擎", "|AIHR数智引擎", "| AIHR", "|AIHR", " | AIHR数智引擎"]

# 标题长度上限（移动端 SERP 不截断）
TITLE_MAX = 28

# 可见文本元素抽取规则
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
DESC_RE = re.compile(r'name=["\']description["\'][^>]*?content=(["\'])(.*?)\1', re.S | re.I)
OG_TITLE_RE = re.compile(r'property=["\']og:title["\'][^>]*?content=(["\'])(.*?)\1', re.S | re.I)
OG_DESC_RE = re.compile(r'property=["\']og:description["\'][^>]*?content=(["\'])(.*?)\1', re.S | re.I)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S | re.I)
H3_CARD_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S | re.I)
INLINE_LINK_RE = re.compile(r'<a[^>]*href=["\']/articles/([^"\']+)["\'][^>]*>(.*?)</a>', re.S | re.I)


def _strip_tags(s):
    """去掉 HTML 标签，保留可见文本。"""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def _strip_brand(s):
    """剥离品牌后缀。"""
    if not s:
        return ""
    t = s.strip()
    for suf in BRAND_SUFFIXES:
        if t.endswith(suf):
            t = t[: -len(suf)].strip()
    # 兜底：以 | 或 - 分割取主标题
    t = t.split("|")[0].strip()
    if " - " in t:
        t = t.split(" - ")[0].strip()
    return t.strip()


def _norm(s):
    """归一化用于比较：去空白、去所有引号（中英文），避免引号边界误判。"""
    s = re.sub(r"\s+", "", s or "")
    for q in ['"', '"', '"', "「", "」", "'", "'", "‘", "’"]:
        s = s.replace(q, "")
    return s


def _is_midword_chop(shorter, longer):
    """判断 shorter 是否是 longer 的【词中截断】。

    采用子串包含（而非仅前缀）+ 引号归一化，覆盖三类截断：
      ① 前缀截断（"AI正在系统性优" ⊂ H1）
      ② 引号边界截断（"系统性「" ⊂ H1，引号被归一化后命中）
      ③ 子串截断（标题取了 H1 中段，如 "在 AI 时代，活成组织的首席架" ⊂ H1）
    只有断在词中间（下一字符续词）才判截断；断在标点/空格=合法短标题。
    """
    ns, nl = _norm(shorter), _norm(longer)
    if not (ns and nl) or len(ns) >= len(nl):
        return False
    if len(ns) < 8:  # 过短子串易误匹配，跳过
        return False
    idx = nl.find(ns)
    if idx == -1:
        return False
    after = nl[idx + len(ns): idx + len(ns) + 1]
    # 下一字符是 CJK 汉字 / 数字 / 字母 = 续词 = 截断；标点/空格 = 合法短语边界
    return bool(re.match(r"[\u4e00-\u9fff0-9a-zA-Z]", after))


def _extract_h1(content):
    """健壮抽取 H1（兼容旧模板中 H1 嵌套在 .article-header 内、或带属性的情况）。"""
    m = H1_RE.search(content)
    if m:
        return _strip_tags(m.group(1))
    return ""


def check_file(path):
    """返回该文件的 issue 列表；每条为 (level, msg)，level ∈ {'FAIL','WARN'}。"""
    issues = []
    rel = os.path.relpath(path, SITE_ROOT)

    # 验证文件 / 重定向桩 / 404 / 模板（含 PLACEHOLDER，非发布页）豁免
    base = os.path.basename(path)
    if any(x in base for x in ["baidu_", "google", "BingSiteAuth", "verify"]) or "404" in base:
        return issues
    if "templates/" in rel:
        return issues
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        content = fh.read()
    if 'http-equiv="refresh"' in content:
        return issues

    # ---------- 1. 标题截断检测（词中截断才算，合法短标题不误杀）----------
    tm = TITLE_RE.search(content)
    title_full = tm.group(1).strip() if tm else ""
    title_core = _strip_brand(title_full)

    ogm = OG_TITLE_RE.search(content)
    og_core = _strip_brand(ogm.group(2).strip()) if ogm else ""

    h1 = _extract_h1(content)

    # 词中截断判定：title_core 是 h1 / og_core 的前缀，且断在词中间
    for label, longer in [("H1", h1), ("og:title", og_core)]:
        if not longer:
            continue
        if _is_midword_chop(title_core, longer):
            issues.append((
                "FAIL",
                f"{rel}: <title> 被截断成 {label} 的词中前半截 "
                f"—— title「{title_core}」 vs {label}「{longer}」",
            ))
            break  # 一处截断足以判定，避免重复

    # 偏离 WARN：title 与 og 既不相等、也非前缀关系（可能不一致，需人工核对）
    if og_core and title_core and _norm(title_core) != _norm(og_core):
        nt, no = _norm(title_core), _norm(og_core)
        if not (no.startswith(nt) or nt.startswith(no)):
            issues.append((
                "WARN",
                f"{rel}: <title> 与 og:title 措辞不一致（非截断，需核对是否同源）"
                f" —— title「{title_core}」 vs og「{og_core}」",
            ))

    # ---------- 2. 标题超长 ----------
    if 0 < len(title_core) > TITLE_MAX:
        issues.append((
            "FAIL",
            f"{rel}: 核心标题超长（{len(title_core)}字 > {TITLE_MAX}）"
            f" —— 必须【重写】保留原意，禁止物理截断: 「{title_core}」",
        ))

    # ---------- 3. 引号污染（可见文本）----------
    # 双重转义永远错误
    for m in re.finditer(r"&amp;quot;", content):
        issues.append(("FAIL", f"{rel}: 发现双重转义 &amp;quot;（永远错误，应改为「」）"))
        break

    # 在可见文本元素里检测 &quot; 与英文双引号
    def _check_visible_text(tag_name, text):
        if not text:
            return
        if "&quot;" in text:
            issues.append(("FAIL", f"{rel}: {tag_name} 含 &quot; 实体（应改为「」）: 「{text[:40]}」"))
        # 英文直双引号（排除中文引号「」"" 与书名号）
        if '"' in text:
            issues.append(("FAIL", f"{rel}: {tag_name} 含英文双引号 \"（应改为「」）: 「{text[:40]}」"))

    _check_visible_text("<title>", title_full)
    dm = DESC_RE.search(content)
    if dm:
        _check_visible_text("meta description", dm.group(2))
    if ogm:
        _check_visible_text("og:title", ogm.group(2))
    ogdm = OG_DESC_RE.search(content)
    if ogdm:
        _check_visible_text("og:description", ogdm.group(2))
    for h in H1_RE.findall(content):
        _check_visible_text("<h1>", _strip_tags(h))
    for h in H2_RE.findall(content):
        _check_visible_text("<h2>", _strip_tags(h))
    for h in H3_CARD_RE.findall(content):
        _check_visible_text("卡片<h3>", _strip_tags(h))
    for href, ltext in INLINE_LINK_RE.findall(content):
        _check_visible_text(f"延伸阅读链接({href})", _strip_tags(ltext))

    return issues


def main():
    args = sys.argv[1:]
    files = []
    if args:
        for a in args:
            p = a if os.path.isabs(a) else os.path.join(SITE_ROOT, a)
            if os.path.exists(p):
                files.append(p)
    else:
        for root, dirs, fs in os.walk(SITE_ROOT):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
            for f in fs:
                if f.endswith(".html"):
                    files.append(os.path.join(root, f))

    all_issues = []
    for p in sorted(files):
        all_issues.extend(check_file(p))

    fails = [i for i in all_issues if i[0] == "FAIL"]
    warns = [i for i in all_issues if i[0] == "WARN"]

    print("=" * 60)
    print("  标题一致性检测 (Title Consistency Check)")
    print("=" * 60)
    if not all_issues:
        print("  🟢 未发现标题截断 / 引号污染 / 超长问题")
    else:
        if fails:
            print(f"\n  ❌ FAIL × {len(fails)}")
            for _, m in fails:
                print(f"    • {m}")
        if warns:
            print(f"\n  ⚠️  WARN × {len(warns)}")
            for _, m in warns:
                print(f"    • {m}")
    print("=" * 60)
    print(f"  扫描文件: {len(files)} | FAIL: {len(fails)} | WARN: {len(warns)}")
    print("=" * 60)

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
