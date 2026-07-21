#!/usr/bin/env python3
"""
内链断裂批量修复（Broken Internal Link Repair）

修复策略：
1. 明确拼写错误/近似slug → 修正为正确文件名
2. URL编码中文文件名 → 改用原始中文
3. 幽灵文章（计划了但从未创建的slug）→ 替换为最接近的已存在文章或删除

运行后需人工复核替换是否语义合理。
"""

import os
import re
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLES_DIR = os.path.join(SITE_ROOT, "articles")

# ============================================================
# 修复映射表：错误slug → 正确slug（None表示删除该链接）
# ============================================================
REPAIR_MAP = {
    # === 类型1: 拼写错误 / 近似slug ===
    'ai-silent-signals.html': 'ai-silent-org-signals.html',
    'kpi-physical-failure.html': 'kpi-failure-ai-org-restructure.html',

    # === 类型2: URL编码中文文件名 → 原始中文（特殊处理）===

    # === 类型3: 幽灵文章（从未创建）→ 最接近的已存在文章 ===
    # 「AI时代组织进化：从科层制到网络化」→ 从公司到智能组织（主题最近）
    'ai-era-org-evolution.html': 'from-company-to-intelligent-organization.html',
    # 「AI+HR：从效率工具到战略伙伴」→ HR转型首席架构师
    'ai-hr-transformation.html': '2026-hr-transformation-chief-architect.html',
    # 「AI时代HR transformation」→ 同上（另一拼写变体）
    'ai-era-hr-transformation.html': '2026-hr-transformation-chief-architect.html',
    # 「阿里ATH×AGI组织重构」→ 阿里AI组织变革
    'alibaba-ath-agi-organization.html': 'alibaba-ai-org-restructuring-2026.html',
    # 「AI组织进化：中国大厂样本」→ 中国AI组织三条路线
    'ai-org-evolution-china-bigtech.html': 'china-ai-org-three-routes.html',

    # === 类型4: 无合适替代，删除链接 ===
    'digital-management-four-actions.html': None,   # 数字化管理四部曲(不存在)
    'amazon-layoff-lesson.html': None,              # 亚马逊裁员教训(不存在)
}

# URL编码中文文件名的修复（特殊处理）
def repair_url_encoded_chinese(content):
    """修复 href 中使用 URL 编码中文文件名的问题"""
    import urllib.parse
    # 匹配 /articles/AI%E8%A3%81... 格式
    def replace_encoded(match):
        full_match = match.group(0)
        href_val = match.group(1)
        try:
            decoded = urllib.parse.unquote(href_val)
            # 如果解码后文件存在，使用解码后的版本
            if os.path.exists(os.path.join(SITE_ROOT, decoded.lstrip('/'))):
                return f'href="{decoded}"'
        except:
            pass
        return full_match

    # 匹配 href="/articles/AI%XX..." 或 href=AI%XX...
    content = re.sub(
        r'href="(.*?AI[%0-9A-F][%0-9A-F].*?\.html)"',
        replace_encoded,
        content
    )
    return content


def repair_file(fpath):
    """修复单个文件中的断裂内链"""
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    original = content
    changes = []

    # 1. 修复映射表中的 slug
    for bad_slug, good_slug in REPAIR_MAP.items():
        pattern = f'href="([^"]*{re.escape(bad_slug)})"'
        def make_replacer(good):
            def replacer(m):
                old_href = m.group(1)
                if good is None:
                    # 删除整个 <li><a>...</a></li>
                    return ''
                # 替换 slug 部分
                new_href = old_href.replace(bad_slug, good)
                return f'href="{new_href}"'
            return replacer

        new_content = re.sub(pattern, make_replacer(good_slug), content)
        if new_content != content:
            count = len(re.findall(pattern, content))
            action = '删除' if good_slug is None else f'→ {good_slug}'
            changes.append(f"  {bad_slug} [{action}] ×{count}")
            content = new_content

    # 2. 修复 URL 编码中文文件名
    content = repair_url_encoded_chinese(content)
    if content != original:
        # 检查是否有变化
        pass

    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        return changes
    return None


def main():
    print("=" * 60)
    print("  内链断裂批量修复")
    print("=" * 60)

    total_fixes = 0
    fixed_files = []

    # 扫描 articles/ 下所有 .html（排除 index.html 和重定向桩）
    for fname in sorted(os.listdir(ARTICLES_DIR)):
        if not fname.endswith('.html'):
            continue
        if fname == 'index.html':
            continue
        fpath = os.path.join(ARTICLES_DIR, fname)

        # 跳过重定向桩页
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            head = f.read(1024)
        if 'http-equiv="refresh"' in head:
            continue

        changes = repair_file(fpath)
        if changes:
            total_fixes += len(changes)
            fixed_files.append((fname, changes))
            print(f"\n📄 {fname}:")
            for c in changes:
                print(c)

    # 也处理 seo-monitor.html
    seo_monitor = os.path.join(SITE_ROOT, 'seo-monitor.html')
    if os.path.exists(seo_monitor):
        changes = repair_file(seo_monitor)
        if changes:
            total_fixes += len(changes)
            fixed_files.append(('seo-monitor.html', changes))
            print(f"\n📄 seo-monitor.html:")
            for c in changes:
                print(c)

    print(f"\n{'=' * 60}")
    print(f"  共修复 {len(fixed_files)} 个文件，{total_fixes} 处变更")
    print("=" * 60)


if __name__ == "__main__":
    main()
