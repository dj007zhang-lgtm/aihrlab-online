#!/usr/bin/env python3
"""
H1 完整性扫描（主理人质量门可复用引擎）

作用：
  - 扫描全站所有 .html 文件，区分「内容/工具页」与「基础设施页」
  - 内容/工具页必须含有至少一个顶级 <h1>（页面主题声明，SEO/可访问性必需）
  - 基础设施页豁免：重定向桩页、404.html、搜索引擎验证文件（本就无需 H1）

分类规则（与 quality_gate._is_verify_page 保持一致）：
  - 重定向桩页: 正文含 http-equiv="refresh"（旧 slug 极简跳转页）
  - 404.html: 文件名结尾
  - 验证文件: 文件名含 baidu_ / google / BingSiteAuth / verify
  - 其余 .html 视为内容/工具页，要求有 H1

用法：
  python3 scripts/check_h1.py              # 打印扫描报告 + 退出码(0=全部有H1,1=有缺失)
  python3 scripts/check_h1.py --json       # 输出 JSON（供自动化/质量门调用）
  from check_h1 import find_missing_h1
"""

import os
import re
import sys
import json

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_redirect_stub(content):
    """旧 slug 软重定向桩页：含 meta refresh 跳转，有意不含 H1/canonical"""
    return 'http-equiv="refresh"' in content


def _is_verify_file(basename):
    """搜索引擎站点验证文件（仅含验证哈希，无需 H1）"""
    return any(x in basename for x in ['baidu_', 'google', 'BingSiteAuth', 'verify'])


def _classify(fpath, content):
    """返回 ('content'|'infra', reason)"""
    basename = os.path.basename(fpath)
    if _is_redirect_stub(content):
        return 'infra', 'redirect-stub'
    if basename == '404.html' or basename.endswith('404.html'):
        return 'infra', '404-page'
    if _is_verify_file(basename):
        return 'infra', 'verify-file'
    if 'design-system' in fpath:  # 设计系统规范文档（assets/design-system.html）非内容页，豁免 H1 要求
        return 'infra', 'design-system-spec'
    return 'content', 'content-page'


def _candidate_title(content):
    """从 JSON-LD headline 或 <title> 取候选标题，供修复时参考"""
    hl = re.search(r'"headline":\s*"([^"]+)"', content)
    if hl:
        return hl.group(1)
    tm = re.search(r'<title>(.*?)</title>', content, re.S)
    if tm:
        return tm.group(1).strip()
    return None


def find_missing_h1(site_root=SITE_ROOT):
    """返回缺失 H1 的内容/工具页列表：[{'file','reason','candidate'}]"""
    missing = []
    for root, dirs, files in os.walk(site_root):
        # Skip .git, node_modules, etc.
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        for fn in files:
            if not fn.endswith('.html'):
                continue
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
            except Exception:
                continue
            kind, reason = _classify(fpath, content)
            if kind != 'content':
                continue
            if not re.search(r'<h1[ >]', content):
                missing.append({
                    'file': os.path.relpath(fpath, site_root),
                    'reason': reason,
                    'candidate': _candidate_title(content),
                })
    return missing


def count_all(site_root=SITE_ROOT):
    """返回统计：content 有H1 / content 缺H1 / infra 豁免"""
    content_ok = 0
    content_missing = 0
    infra = 0
    for root, dirs, files in os.walk(site_root):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        for fn in files:
            if not fn.endswith('.html'):
                continue
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
            except Exception:
                continue
            kind, _ = _classify(fpath, content)
            if kind == 'infra':
                infra += 1
            elif re.search(r'<h1[ >]', content):
                content_ok += 1
            else:
                content_missing += 1
    return content_ok, content_missing, infra


def main():
    as_json = "--json" in sys.argv
    missing = find_missing_h1(SITE_ROOT)
    content_ok, content_missing, infra = count_all(SITE_ROOT)

    if as_json:
        print(json.dumps({
            "missing_h1": missing,
            "missing_count": len(missing),
            "content_ok": content_ok,
            "content_missing": content_missing,
            "infra_exempt": infra,
        }, ensure_ascii=False, indent=2))
        sys.exit(1 if missing else 0)

    print("=" * 60)
    print("  H1 完整性扫描 (check_h1)")
    print("=" * 60)
    print(f"\n  内容/工具页有 H1: {content_ok}")
    if content_missing:
        print(f"  内容/工具页缺 H1: {content_missing}  ⚠️")
    else:
        print(f"  内容/工具页缺 H1: 0  ✅")
    print(f"  基础设施豁免(桩/404/验证文件): {infra}")

    if missing:
        print(f"\n❌ 以下内容页缺少 <h1>（需修复）：\n")
        for m in missing:
            cand = f"  候选标题: {m['candidate'][:50]}" if m['candidate'] else "  候选标题: ❌无 headline/title"
            print(f"  📄 {m['file']}")
            print(cand)
    else:
        print("\n✅ 全站内容页 H1 完整")

    print("\n" + "=" * 60)
    print(f"  结论: {'🔴 发现 ' + str(len(missing)) + ' 个缺 H1 内容页' if missing else '🟢 全部健康'}")
    print("=" * 60)
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
