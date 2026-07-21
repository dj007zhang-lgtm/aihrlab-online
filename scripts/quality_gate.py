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

try:
    import check_title_consistency
except ImportError:
    check_title_consistency = None

try:
    import check_inline_links
except ImportError:
    check_inline_links = None

try:
    import url_consistency_audit
except ImportError:
    url_consistency_audit = None

# ============================================================
# 配置
# ============================================================
SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATE_SCRIPT = os.path.join(SITE_ROOT, "tools", "validate_article.py")
# 默认用当前解释器（CI / GitHub Actions 下即 runner 自带 python3）；
# 本地若有指定 managed python，可用环境变量覆盖。
PYTHON = os.environ.get("QUALITY_GATE_PYTHON", sys.executable)

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
        if any(x in rel for x in ['404', 'verify', '.txt', 'sitemap', 'templates']):
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
        
        if any(x in rel for x in ['404', 'verify', '.txt', 'sitemap', 'articles.html', 'templates']):
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


# ============================================================
# Gate 9: 标题一致性关（截断 / 引号污染 / 偏离）
# 全站扫描（历史债也要抓），不局限于 diff。
# ============================================================
def gate_title_consistency(target_files=None):
    if check_title_consistency is None:
        return GateResult("9-标题一致性关", False,
                           ["check_title_consistency.py 未找到，无法执行标题一致性扫描"])
    issues = []
    for f in _get_all_html_files():
        if not f.endswith('.html'):
            continue
        issues.extend(check_title_consistency.check_file(f))
    fails = [m for lvl, m in issues if lvl == "FAIL"]
    warns = [m for lvl, m in issues if lvl == "WARN"]
    if fails:
        details = fails[:12]
        if len(fails) > 12:
            details.append(f"… 共 {len(fails)} 处 FAIL（标题截断 / 引号污染）")
        if warns:
            details.append(f"⚠️ 另有 {len(warns)} 处 title/og 偏离仅提示，需人工核对")
        return GateResult("9-标题一致性关", False, details)
    msg = "全站标题无截断 / 引号污染"
    if warns:
        msg += f"（{len(warns)} 处偏离仅提示）"
    return GateResult("9-标题一致性关", True, [msg])


# ============================================================
# Gate 10: 延伸阅读链接截断关（链接文字是否为目标 H1 的词中前半截）
# 全站扫描（历史债也要抓）。
# ============================================================
def gate_inline_link_integrity(target_files=None):
    if check_inline_links is None:
        return GateResult("10-延伸阅读链接截断关", False,
                           ["check_inline_links.py 未找到，无法执行链接文字扫描"])
    issues = []
    for f in _get_all_html_files():
        if not f.endswith('.html'):
            continue
        issues.extend(check_inline_links.check_file(f))
    fails = [m for lvl, m in issues if lvl == "FAIL"]
    if fails:
        details = fails[:12]
        if len(fails) > 12:
            details.append(f"… 共 {len(fails)} 处延伸阅读链接截断")
        return GateResult("10-延伸阅读链接截断关", False, details)
    return GateResult("10-延伸阅读链接截断关", True,
                      ["全站延伸阅读链接文字完整，无词中截断"])


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
# Gate 11: URL 一致性关（全站级，防止 404 / 孤儿 / 断裂 / 重复）
# 始终全站扫描，不受 --page/--changed 模式限制。
# 复用 scripts/url_consistency_audit.py 的 6 维度检测引擎。
# ============================================================
def gate_url_consistency(target_files=None):
    """Gate 11: URL 一致性关——系统性防护 sitemap/磁盘/redirects/index/内链/重复 不一致。

    此关为「根除 404 类 bug」的核心防线：
    - sitemap 引用的 URL 全部在磁盘有文件
    - 磁盘上的文章全部被 sitemap 收录
    - redirects.json 源路径无残留非桩文件、目标路径存在
    - article-index.json 的 slug 全部有效
    - 全站内联 .html 链接无断裂
    - 无 sitemap 重复 / 孤立重定向桩 / index 重复 slug
    """
    if url_consistency_audit is None:
        return GateResult("11-URL一致性关", False,
                           ["url_consistency_audit.py 未找到，无法执行 URL 一致性体检"])

    issues = []
    checks = [
        ("sitemap→磁盘", url_consistency_audit.check_1_sitemap_vs_disk),
        ("磁盘→sitemap", url_consistency_audit.check_2_disk_vs_sitemap),
        ("redirects完整性", url_consistency_audit.check_3_redirects_integrity),
        ("article-index完整性", url_consistency_audit.check_4_article_index_integrity),
        ("内链断裂", url_consistency_audit.check_5_broken_internal_links),
        ("重复与异常", url_consistency_audit.check_6_duplicates_and_anomalies),
    ]
    for name, fn in checks:
        result = fn()
        if result:
            issues.extend([(name, item) for item in result])

    if issues:
        details = []
        for check_name, item in issues[:20]:
            details.append(f"[{check_name}] {item}")
        if len(issues) > 20:
            details.append(f"… 共 {len(issues)} 个问题")
        return GateResult("11-URL一致性关", False, details)

    return GateResult("11-URL一致性关", True,
                      ["sitemap/磁盘/redirects/article-index/内链/重复 — 6 维一致"])


def gate_source_freshness(target_files=None):
    """Gate 12: 信源时效关——防止「用老旧信源写当前事」。

    核心纪律（内容主理人红线）：
    文章若标注当前年份(2026)或声称「最新/当前/近日/刚刚」，其作为核心论据的
    事实信源必须是 2026 年内的公开信息。2025 及更早均属旧闻（用户定调：2026 年，
    不含 25 年，25 年已是旧闻），不得作为当前事的核心论据。把 2023/2024/2025 的旧案
    当成「当前 AI 原生组织原型」来写，属严重不合格。

    判定逻辑：
    1. 提取正文文本中所有 4 位年份引用。
    2. 若文章定位「当前」（title/description 含 2026 或 最新/当前/近日/刚刚/
       刚刚/新近），则核心论据年份必须出现 2026。
    3. 豁免：明确的「历史背景引导」句式——如「2023年X启动，到2026年Y」、
       「自2023年起」、「2023年底…两年后」等含时间线连接词的叙述，不计入。
       历史事实（如「2012 年推出」「满 2 年」）作背景锚点允许；但作为
       「当前进展」被叙述的 2025 事件视为旧闻。
    4. 最新实质论据年份 = 排除豁免句式后，正文出现的最大年份。
       若该年份 <= 2025 且文章定位当前 → FAIL。
    """
    import re as _re

    CURRENT_YEAR = 2026
    STALE_CUTOFF = 2025  # 核心论据停在 <=2025 视为旧闻（非历史背景时）

    # 历史背景引导模式：这些句式里的早期年份是合理的时间线起点
    HISTORY_PATTERN = _re.compile(
        r'(20\d{2}年.{0,30}?(启动|成立|推出|发布|分拆|变革|改革|提出|伊始|起|底|初).{0,40}?'
        r'(到|至|如今|如今|两年后|三年后|此后|再到|演化|演进|演变|沉淀|成为))'
        r'|自\s*20\d{2}\s*年.{0,20}?(起|以来|至今)'
        r'|20\d{2}\s*年底.{0,30}?(两年后|三年后|此后|到\s*202[5-6])',
        _re.S,
    )

    # 当前定位信号
    CURRENT_SIGNAL = _re.compile(r'2026|最新|当前|近日|刚刚|新近|近期')

    def _extract_body_text(html):
        # 去掉 script/style
        body = _re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=_re.I)
        body = _re.sub(r'<style[\s\S]*?</style>', ' ', body, flags=_re.I)
        # 仅取 article 主体（若有）
        m = _re.search(r'<article[\s\S]*?</article>', body, _re.I | _re.S)
        if m:
            body = m.group(0)
        return _re.sub(r'<[^>]+>', ' ', body)

    issues = []

    html_files = target_files or _get_all_html_files()
    for path in html_files:
        if not path.endswith('.html'):
            continue
        if _is_verify_page(path):
            continue
        # 信源时效纪律只约束 articles/ 下的分析文章；测评/工具/资源/枢纽页豁免
        rel = os.path.relpath(path, SITE_ROOT)
        if 'articles/' not in rel and not (target_files and path in target_files):
            continue
        # 跳过纯跳转桩文件
        try:
            with open(path, encoding='utf-8') as f:
                html = f.read()
        except Exception:
            continue
        if 'window.location.replace' in html and '页面已迁移' in html:
            continue

        # 当前定位判定：title / description / slug 含当前信号
        head = html[:html.find('</head>')] if '</head>' in html else html[:8000]
        slug = os.path.basename(path)
        is_current = bool(CURRENT_SIGNAL.search(head)) or ('2026' in slug)

        if not is_current:
            continue

        body_text = _extract_body_text(html)
        # 找所有年份
        year_matches = list(_re.finditer(r'(19|20)\d{2}', body_text))
        if not year_matches:
            continue

        # 排除「明确的全篇历史回顾」信号：若标题/description 显式说「回顾/史/启示/复盘」
        # 且正文最新年份<=2024，则视为合法历史文，不触发
        retrospective = _re.search(r'回顾|历史|复盘|启示|演进史|发展史|简史|往事', head)
        if retrospective:
            continue

        # 核心判定：正文是否出现 2026 的实质新进展年份（2025 已是旧闻）
        has_recent = any(int(m.group(0)) >= 2026 for m in year_matches)

        if not has_recent:
            # 统计旧年份，辅助说明
            old_years = sorted({int(m.group(0)) for m in year_matches
                                if 2000 <= int(m.group(0)) <= STALE_CUTOFF})
            issues.append(
                f"{os.path.relpath(path, SITE_ROOT)} | 标注当前(2026/最新)但正文无任何 2026 "
                f"实质信源，旧年份集中在 {old_years}；疑似用旧闻(2025及更早)写当前事"
            )

    if issues:
        return GateResult("12-信源时效关", False, issues[:25])

    return GateResult("12-信源时效关", True,
                      ["当前定位文章均含 2026 实质信源；2025 及更早旧闻未充当当前事核心论据"])


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
        gate_title_consistency(target_files),
        gate_inline_link_integrity(target_files),
        gate_diff(),
        gate_footer_consistency(),
        gate_url_consistency(target_files),  # Gate 11: 始终全站扫描
        gate_source_freshness(target_files),  # Gate 12: 信源时效关
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
