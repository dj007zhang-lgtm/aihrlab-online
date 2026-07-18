#!/usr/bin/env python3
"""
主理人质量门（Quality Gate）
用法:
  python3 scripts/quality_gate.py              # 检查当前工作区 vs HEAD
  python3 scripts/quality_gate.py --all        # 全站扫描（不限于 diff）
  python3 scripts/quality_gate.py --page articles/xxx.html  # 检查单页

任何 push 前必须通过此脚本。输出质量报告。
"""

import os
import sys
import re
import json
import subprocess
from datetime import datetime

# 让质量门能复用内链扫描引擎（同目录）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import check_broken_links
except ImportError:
    check_broken_links = None

try:
    import check_h1
except ImportError:
    check_h1 = None

# ============================================================
# 配置
# ============================================================
SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATE_SCRIPT = os.path.join(SITE_ROOT, "tools", "validate_article.py")
PYTHON = "/Users/andyzhang/.workbuddy/binaries/python/versions/3.13.12/bin/python3"

# 质量门结果
class GateResult:
    def __init__(self, name, passed, details=None):
        self.name = name
        self.passed = passed
        self.details = details or []
    
    def __bool__(self):
        return self.passed
    
    def report(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        lines = [f"  [{status}] {self.name}"]
        for d in self.details:
            lines.append(f"    • {d}")
        return "\n".join(lines)


# ============================================================
# Gate 1: 内链完整性关（最前置硬关卡）
# ============================================================
def gate_link_integrity(target_files=None):
    """内链完整性关：阻断任何会引入 404 的改动。
    跨文件检查（链接在 A 指向 B），始终全站扫描。
    """
    if check_broken_links is None:
        return GateResult("1-内链完整性关", False,
                           ["check_broken_links.py 未找到，无法执行链接扫描"])

    broken = check_broken_links.find_broken_links(SITE_ROOT)
    orphans = check_broken_links.find_sitemap_orphans(SITE_ROOT)

    if broken or orphans:
        details = []
        if broken:
            details.append(f"断裂内部链接 {len(broken)} 处（Google/Bing 会返回 404）：")
            by_src = {}
            for b in broken:
                by_src.setdefault(b["source"], []).append(b["href"])
            for src, hrefs in sorted(by_src.items()):
                details.append(f"  📄 {src} → {', '.join(hrefs)}")
        if orphans:
            details.append(f"sitemap 孤儿 URL {len(orphans)} 个（指向不存在文件）：")
            for o in orphans:
                details.append(f"  → {o}")
        return GateResult("1-内链完整性关", False, details)

    return GateResult("1-内链完整性关", True,
                      ["全站无断裂内部链接；sitemap 无孤儿 URL"])


# ============================================================
# Gate 2: 结构关（复用 validate_article.py）
# ============================================================
def gate_structure(target_files=None):
    """HTML 结构完整性检查"""
    issues = []
    if not os.path.exists(VALIDATE_SCRIPT):
        return GateResult("2-结构关", False, [f"validate_article.py 不存在: {VALIDATE_SCRIPT}"])
    
    cmd = [PYTHON, VALIDATE_SCRIPT, SITE_ROOT]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    
    # Parse output for errors
    error_lines = [l.strip() for l in output.split('\n') 
                   if '❌' in l or 'ERROR' in l.upper() or 'FAIL' in l.upper()]
    if error_lines:
        issues.extend(error_lines[:10])  # Cap at 10
    
    # Also check for "All files OK"
    all_ok = 'All files OK' in output or len(issues) == 0
    return GateResult("2-结构关", all_ok, issues if issues else ["全站结构校验通过"])


# ============================================================
# Gate 3: H1 完整性关（可复用引擎 check_h1）
# ============================================================
def gate_h1_integrity(target_files=None):
    """H1 完整性关：内容/工具页必须有顶级 <h1>（页面主题声明，SEO/可访问性必需）。
    跨文件结构性检查，始终全站扫描；重定向桩/404/验证文件按设计豁免。
    """
    if check_h1 is None:
        return GateResult("3-H1完整性关", False,
                           ["check_h1.py 未找到，无法执行 H1 扫描"])

    missing = check_h1.find_missing_h1(SITE_ROOT)
    if missing:
        details = [f"缺 H1 的内容页 {len(missing)} 个（搜索引擎无法识别页面主题）："]
        for m in missing:
            cand = m["candidate"] or "❌无 headline/title"
            details.append(f"  📄 {m['file']}  →  候选标题: {cand[:50]}")
        return GateResult("3-H1完整性关", False, details)

    return GateResult("3-H1完整性关", True,
                      ["全站内容/工具页均有 H1（重定向桩/404/验证文件已豁免）"])


# ============================================================
# Gate 4: 视觉关（关键 HTML/CSS 元素检测）
# ============================================================
def gate_visual(target_files=None):
    """视觉层关键元素检查：CSS链接、字体加载、无裸文本块等"""
    issues = []
    checked = 0
    
    files_to_check = target_files or _get_all_html_files()
    
    for fpath in files_to_check:
        rel = os.path.relpath(fpath, SITE_ROOT)
        
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        
        checked += 1
        
        # Check 1: Has CSS link（豁免重定向桩页：旧 slug 极简跳转页有意不含 CSS）
        has_css = bool(re.search(r'(stylesheet|\.css)', content, re.I))
        is_redirect = 'http-equiv="refresh"' in content
        if not has_css and fpath.endswith('.html') and not _is_verify_page(fpath) and not is_redirect:
            issues.append(f"{rel}: 缺少 CSS 链接")
        
        # Check 2: Double logo detection (AIHR logo appearing in both nav + body)
        # Normal: nav(1) + footer(1) = 2. Warn if >= 3 (actual duplicate)
        logo_in_body = re.findall(r'>\s*AIHR\s*数智引擎\s*<', content)
        if len(logo_in_body) >= 3 and 'index.html' not in rel and 'about.html' not in rel:
            issues.append(f"{rel}: ⚠️ 双 logo ({len(logo_in_body)} 处，正常应为2处)")
        
        # Check 3: Has viewport meta (mobile) — 豁免重定向桩页与验证文件
        has_viewport = bool(re.search(r'viewport', content, re.I))
        is_redirect = 'http-equiv="refresh"' in content
        if not has_viewport and fpath.endswith('.html') and not _is_verify_page(fpath) and not is_redirect:
            issues.append(f"{rel}: 缺少 viewport meta 标签")
        
        # Check 4: Has title (豁免搜索引擎验证文件)
        if not _is_verify_page(fpath):
            has_title = bool(re.search(r'<title>.+?</title>', content, re.S))
            if not has_title:
                issues.append(f"{rel}: 缺少 <title>")
    
    if issues:
        return GateResult("4-视觉关", False, issues)
    return GateResult("4-视觉关", True, [f"已检查 {checked} 个页面，无视觉层异常"])


# ============================================================
# Gate 4: 品味关（排版层级/色块堆砌检测）
# ============================================================
def gate_taste(target_files=None):
    """设计品味检查：排版层级、less-is-more、无 SaaS Landing 风"""
    issues = []
    checked = 0
    
    files_to_check = target_files or _get_all_html_files()
    
    for fpath in files_to_check:
        if not fpath.endswith('.html'):
            continue
        rel = os.path.relpath(fpath, SITE_ROOT)
        
        # Skip non-content pages
        if any(x in rel for x in ['404', 'verify', '.txt', 'sitemap']):
            continue
            
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        
        checked += 1
        
        # Check 1: Inline style blocks that look like emergency patches
        inline_styles = re.findall(r'<style>(.*?)</style>', content, re.DOTALL)
        total_inline_css = sum(len(s) for s in inline_styles)
        # v2 article template（templates/article-v2.html）的完整内联样式约 5500 字符，属设计标准非临时修补
        is_v2_template = any('--font-serif' in s or '.article-header .cat' in s for s in inline_styles)
        if total_inline_css > 6000 and 'tools/' not in rel and 'bridge/' not in rel and not is_v2_template:
            issues.append(f"{rel}: 行内 style 过长 ({total_inline_css}字符)，可能为临时修补")
        
        # Check 2: 核心标题长度 > 28 字（忽略品牌后缀「| AIHR数智引擎」）
        tm = re.search(r'<title>([^<]+)</title>', content)
        if tm:
            full = tm.group(1).strip()
            core = full.split('|')[0].strip()
            if ' - ' in core:
                core = core.split(' - ')[0].strip()
            tlen = len(core)
            if tlen > 28:
                issues.append(f"{rel}: 核心标题超长 ({tlen}字): '{core[:30]}...'")
        
        # Check 3: Description starts with template residue
        dm = re.search(r'name=["\']description["\'][^>]*content=["\']([^"\']+)"', content)
        if dm:
            desc = dm.group(1)
            if desc.startswith('搜索') or desc.startswith('section:nth-child') or len(desc) < 30:
                issues.append(f"{rel}: description 为模板残留或过短 ({len(desc)}字)")
        
        # Check 4: 空 div 链（tools/bridge 为 JS 运行时填充，豁免）
        if 'tools/' not in rel and 'bridge/' not in rel:
            empty_divs = re.findall(r'<div[^>]*>\s*</div>', content)
            if len(empty_divs) > 15:
                issues.append(f"{rel}: 大量空 div ({len(empty_divs)}个)，疑似未填充的布局骨架")
    
    if issues:
        return GateResult("5-品味关", False, issues)
    return GateResult("5-品味关", True, [f"已检查 {checked} 个页面，无品味问题"])


# ============================================================
# Gate 5: SEO 关
# ============================================================
def gate_seo(target_files=None):
    """SEO 完整性检查：description / OG / Schema"""
    issues = []
    checked = 0
    
    files_to_check = target_files or _get_all_html_files()
    
    for fpath in files_to_check:
        if not fpath.endswith('.html'):
            continue
        rel = os.path.relpath(fpath, SITE_ROOT)
        
        if any(x in rel for x in ['404', 'verify', '.txt', 'sitemap', 'articles.html']):
            continue

        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        
        if 'http-equiv="refresh"' in content:  # 重定向桩页，不检查 SEO 元数据
            continue
        if _is_verify_page(fpath):  # 搜索引擎验证文件，不检查 SEO 元数据
            continue
        
        checked += 1
        
        # Check description
        descs = re.findall(r'name=["\']description["\']', content, re.I)
        if len(descs) == 0:
            issues.append(f"{rel}: 缺少 meta description")
        elif len(descs) > 1:
            issues.append(f"{rel}: ⚠️ 多个 description 标签 ({len(descs)}个)")
        else:
            # 引号配对回溯，兼容 description 内容内含单引号（如 'AI要取代HR'）
            dm = re.search(r'name=["\']description["\'][^>]*?content=(["\'])(.*?)\1', content, re.S)
            if dm:
                val = dm.group(2)
                if val.startswith('搜索'):
                    issues.append(f"{rel}: description 为模板残留")
                elif len(val) < 50:
                    issues.append(f"{rel}: description 偏短 ({len(val)}字)")
        
        # Check OG tags
        has_og_title = bool(re.search(r'og:title', content))
        has_og_desc = bool(re.search(r'og:description', content))
        has_og_image = bool(re.search(r'og:image', content))
        if not (has_og_title and has_og_desc and has_og_image) and 'articles/' in rel:
            missing = []
            if not has_og_title: missing.append('og:title')
            if not has_og_desc: missing.append('og:description')
            if not has_og_image: missing.append('og:image')
            issues.append(f"{rel}: 缺少 OG 标签: {', '.join(missing)}")
    
    if issues:
        return GateResult("6-SEO关", False, issues)
    return GateResult("6-SEO关", True, [f"已检查 {checked} 个页面，SEO 元数据完整"])


# ============================================================
# Gate 6: Diff 关
# ============================================================
def gate_diff():
    """Git diff 摘要——强制我读实际改动"""
    try:
        result = subprocess.run(
            ["git", "-C", SITE_ROOT, "diff", "--stat", "HEAD"],
            capture_output=True, text=True, timeout=15
        )
        stat = result.stdout.strip()
        
        result2 = subprocess.run(
            ["git", "-C", SITE_ROOT, "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=15
        )
        changed_files = [f.strip() for f in result2.stdout.strip().split('\n') if f.strip()]
        
        details = [
            f"变更文件数: {len(changed_files)}",
            f"变更摘要:\n{stat}",
        ]
        
        # Warn on large batch edits
        if len(changed_files) > 20:
            details.append(f"⚠️ 批量编辑超过20文件({len(changed_files)})，建议抽样验证!")
        
        return GateResult("7-Diff关", True, details)
    except Exception as e:
        return GateResult("7-Diff关", False, [f"无法读取 git diff: {e}"])


def gate_footer_consistency():
    """Gate 8: 尾页一致性关——阻断尾页结构回归（相关阅读/QR/参考来源 的样式、类、顺序、重复）。
    复用 scripts/check_footer_consistency.py。"""
    script = os.path.join(SITE_ROOT, 'scripts', 'check_footer_consistency.py')
    try:
        r = subprocess.run([sys.executable, script], capture_output=True, text=True, cwd=SITE_ROOT, timeout=120)
        lines = [l for l in (r.stdout + r.stderr).strip().splitlines() if l.strip()]
        if r.returncode == 0:
            return GateResult("8-尾页一致性关", True, lines[:1] or ["尾页一致性校验通过"])
        return GateResult("8-尾页一致性关", False, lines[:10] or ["尾页一致性校验未通过"])
    except Exception as e:
        return GateResult("8-尾页一致性关", False, [f"无法运行尾页校验脚本: {e}"])


# ============================================================
# Helpers
# ============================================================

def _get_all_html_files():
    results = []
    for root, dirs, files in os.walk(SITE_ROOT):
        # Skip .git, node_modules, etc.
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        for f in files:
            if f.endswith('.html'):
                results.append(os.path.join(root, f))
    return results


def _is_verify_page(path):
    basename = os.path.basename(path)
    return any(x in basename for x in ['baidu_', 'google', 'BingSiteAuth', 'verify'])


def _get_changed_files():
    """Get files changed since last commit"""
    try:
        result = subprocess.run(
            ["git", "-C", SITE_ROOT, "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=15
        )
        files = []
        base = SITE_ROOT
        for f in result.stdout.strip().split('\n'):
            f = f.strip()
            if f and f.endswith('.html'):
                full = os.path.join(base, f)
                if os.path.exists(full):
                    files.append(full)
        return files
    except Exception:
        return None


# ============================================================
# Main
# ============================================================

def run_quality_gate(mode="changed"):
    print("=" * 60)
    print(f"  主理人质量门 (Quality Gate)")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  模式: {mode}")
    print("=" * 60)
    
    # Determine which files to check
    target_files = None
    if mode == "changed":
        target_files = _get_changed_files()
        if target_files:
            print(f"\n📋 检测到 {len(target_files)} 个变更文件\n")
        else:
            print("\n📋 未检测到变更文件，执行全站扫描\n")
            mode = "all"
    
    if mode == "all":
        target_files = None
    elif mode == "single" and len(sys.argv) > 2:
        target_file = sys.argv[2]
        if os.path.isabs(target_file):
            target_files = [target_file]
        else:
            target_files = [os.path.join(SITE_ROOT, target_file)]
    
    # Run all gates（内链完整性为第1关，最前置；H1 完整性为第3关，结构性检查）
    gates = [
        gate_link_integrity(target_files),
        gate_structure(target_files),
        gate_h1_integrity(target_files),
        gate_visual(target_files),
        gate_taste(target_files),
        gate_seo(target_files),
        gate_diff(),
        gate_footer_consistency(),
    ]
    
    # Report
    print()
    for g in gates:
        print(g.report())
        print()
    
    # Summary
    all_passed = all(g.passed for g in gates)
    failed_count = sum(1 for g in gates if not g.passed)
    
    print("=" * 60)
    if all_passed:
        print("  🟢 质量门全部通过 — 可以 push")
    else:
        print(f"  🔴 质量门未通过 — {failed_count}/{len(gates)} 关失败")
        print("  ❌ 请修复以上问题后再 push")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    mode = "changed"
    if "--all" in sys.argv:
        mode = "all"
    elif "--page" in sys.argv:
        mode = "single"
    
    sys.exit(run_quality_gate(mode))
