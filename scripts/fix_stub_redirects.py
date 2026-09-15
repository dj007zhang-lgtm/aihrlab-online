#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 17 个 noindex 跳转桩页造成的死链漏斗。

问题：
  这些 URL 早已 noindex，但仍被站内 ~57 处「延伸阅读 / 相关链接」引用，
  且跳转目标统一为通用列表页 /articles/。读者点「延伸阅读」落到列表页而非
  承诺的正文 —— 既浪费内部链接权重，也是跳出率居高不下的机械成因之一。

修复两件事：
  1) 站内所有指向桩页的链接，直接改写到语义正确的真文 URL（零跳转让易经 real page）。
  2) 桩页自身的 refresh / canonical 同步改为真文 URL，兜住外部来的旧链接。

幂等：目标已存在则跳过；目标文件不存在则拒绝改写并报告。
"""
import os, re, glob, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# stub file -> 语义正确的归位目标（均已核验存在）
MAP = {
    "2026-big-tech-ai-org-restructure-rigidity.html": "/articles/big-tech-ai-org-2026.html",
    "AI裁员7飙到40你的公司在做减法还是乘法.html": "/hub/ai-layoff-restructuring.html",
    "ai-layoff-2026-manager-redefine.html": "/articles/ai-layoff-to-rebuild-hr-stand-firm.html",
    "ai-layoff-230k-regret.html": "/articles/ai-layoff-regret.html",
    "ai-layoff-subtraction-vs-multiplication.html": "/hub/ai-layoff-restructuring.html",
    "ai-layoff-subtraction.html": "/hub/ai-layoff-restructuring.html",
    "bytedance-160b-campus-recruit.html": "/articles/bytedance-160b-ai-org.html",
    "bytedance-7000-campus-7000interns.html": "/articles/bytedance-campus-7000.html",
    "bytedance-doubao-org-engineer-2026.html": "/articles/bytedance-doubao-org-engine-2026.html",
    "dingtalk-ceo-change.html": "/articles/dingtalk-ceo-change-control-vs-empowerment.html",
    "kpi-failure.html": "/articles/kpi-failure-ai-org-restructure.html",
    "mckinsey-6-percent-trust-architecture.html": "/articles/mckinsey-2026-organization-report.html",
    "meta-ai-layoffs-middle-managers.html": "/articles/meta-ai-optimizes-middle-managers.html",
    "microsoft-anthropic-org-restructuring-ai-era.html": "/articles/microsoft-anthropic-ai-org-restructure.html",
    "microsoft-openai-decoupling.html": "/articles/microsoft-ai-decoupling.html",
    "tencent-2800-huoshui.html": "/articles/tencent-huoshui-internal-mobility.html",
    "unitree-ipo-org-design.html": "/articles/unitree-ipo-org-analysis.html",
}

# 只替换 href/src 中出现的引用，避免误伤文本叙述
REF_RE_CACHE = {}


def ref_patterns(stub):
    """返回 (raw, encoded) 两种引用形态，用于稳妥匹配。"""
    if stub in REF_RE_CACHE:
        return REF_RE_CACHE[stub]
    raw = "/articles/" + stub
    enc = "/articles/" + urllib.parse.quote(stub)
    pats = []
    for form in {raw, enc}:
        pats.append((re.compile(re.escape(form)), form))
    REF_RE_CACHE[stub] = pats
    return pats


def target_exists(target_rel):
    p = os.path.join(ROOT, target_rel.lstrip("/"))
    return os.path.exists(p)


def main():
    # 1) 校验目标全部存在，否则拒绝执行
    bad = [t for t in MAP.values() if not target_exists(t)]
    if bad:
        print("ABORT：以下目标不存在，拒绝改写：")
        for b in bad:
            print("   ", b)
        return 1

    # 2) 收集全站可能被影响的 HTML / JSON 文件
    files = []
    for pat in ("*.html", "*/*.html", "assets/js/*.json", "*.txt", "llms*.txt"):
        files.extend(glob.glob(os.path.join(ROOT, pat)))
    files = sorted(set(files))

    changed_files, total_refs = 0, 0
    per_stub = {k: 0 for k in MAP}

    for path in files:
        base = os.path.basename(path)
        try:
            html = open(path, encoding="utf-8").read()
        except Exception:
            continue
        orig = html
        for stub, target in MAP.items():
            if base == stub:
                continue  # 桩页自身在第 3 步处理
            for rx, _ in ref_patterns(stub):
                html, n = rx.subn(target, html)
                if n:
                    per_stub[stub] += n
                    total_refs += n
        if html != orig:
            open(path, "w", encoding="utf-8").write(html)
            changed_files += 1
            rel = os.path.relpath(path, ROOT)
            print(f"  LINKS_FIXED  {rel}")

    print(f"\n内链改写：{total_refs} 处，涉及 {changed_files} 个文件")

    # 3) 桩页自身：rewrite refresh / canonical 到真文
    stub_fixed = 0
    for stub, target in MAP.items():
        p = os.path.join(ROOT, "articles", stub)
        if not os.path.exists(p):
            print("  STUB_MISSING", stub)
            continue
        s = open(p, encoding="utf-8").read()
        o = s
        s = re.sub(r'(http-equiv="refresh" content="0;\s*url=)[^"]*"', r'\g<1>' + target + '"', s)
        s = re.sub(r'(<link rel="canonical" href=")[^"]*"', r'\g<1>' + target + '"', s)
        # 跳转提示文案中的目标链接
        s = re.sub(r'(href="/articles/")(?=[^"]*")', target, s, count=1)
        if s != o:
            open(p, "w", encoding="utf-8").write(s)
            stub_fixed += 1
            print(f"  STUB_TARGET_FIXED  {stub} -> {target}")

    print(f"\n桩页兜底跳转修正：{stub_fixed} 个")
    print("\n=== 每个桩页的内链收敛情况 ===")
    for stub, n in per_stub.items():
        print(f"  {n:>3} 处  {stub}  ->  {MAP[stub]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
