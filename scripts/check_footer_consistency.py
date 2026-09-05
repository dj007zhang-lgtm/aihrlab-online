#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尾页一致性校验（质量门第 8 关）。

检查每篇内容文章（含 </article> 且非重定向桩页）的尾页是否符合 canonical 规范：
  1. 相关阅读：.related-reading 出现 0 或 1 次（不多套）；无 .article-related / .related-grid 冗余块。
  2. 无孤儿「相关推荐」区块（</article> 之后不应有相关推荐 section）。
  3. QR 块：.article-footer-qr 若存在，不得含 inline style=；CTA 文案为规范文案。
  4. 参考信源：若存在参考块，class 必须为 .references，标题必须为「参考信源」（不得用 source-note/source/article-sources/数据来源/参考来源）。
  5. 排列顺序：相关阅读 → QR → 参考来源（三者皆有时）。

返回非 0 退出码表示存在不一致（供质量门阻断）。
"""
import re, glob, os, sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(SITE_ROOT, 'articles')
CANON_QR_COPY = '关注公众号，获取 AI 时代 HR 变革一手分析'

def check_file(fpath):
    rel = os.path.relpath(fpath, SITE_ROOT)
    issues = []
    if 'http-equiv="refresh"' in open(fpath, encoding='utf-8', errors='ignore').read():
        return issues  # 桩页豁免
    h = open(fpath, encoding='utf-8', errors='ignore').read()
    ae = h.rfind('</article>')
    if ae == -1:
        return issues  # 工具页/非标准容器豁免
    region = h[:ae]
    tail = h[ae:]

    # 1) related-reading 数量
    rr = len(re.findall(r'class="[^"]*related-reading[^"]*"', region))
    if rr > 1:
        issues.append(f"{rel}: .related-reading 出现 {rr} 次（应 ≤1）")
    # 2) 冗余相关块
    if re.search(r'class="[^"]*article-related[^"]*"', region):
        issues.append(f"{rel}: 残留 .article-related 冗余相关块")
    if re.search(r'class="[^"]*related-grid[^"]*"', region):
        issues.append(f"{rel}: 残留 .related-grid 冗余相关块")
    # 3) 孤儿相关推荐
    if '相关推荐' in tail:
        issues.append(f"{rel}: </article> 之后存在孤儿「相关推荐」区块")

    # 4) QR 块
    qr_m = re.search(r'<div class="article-footer-qr"([^>]*)>', region)
    if qr_m:
        if 'style=' in qr_m.group(1):
            issues.append(f"{rel}: .article-footer-qr 含 inline style（应统一用类样式）")
        qp = re.search(r'<div class="article-footer-qr"[^>]*>.*?<p>(.*?)</p>', region, re.S)
        if qp:
            copy = re.sub(r'<[^>]+>', '', qp.group(1)).strip()
            if copy != CANON_QR_COPY:
                issues.append(f"{rel}: QR CTA 文案非规范（「{copy}」）")

    # 5) references 块
    if re.search(r'class="[^"]*(?:source-note|article-sources)[^"]*"', region):
        issues.append(f"{rel}: 参考块仍用旧 class（应统一 .references）")
    if re.search(r'class="[^"]*references[^"]*"', region):
        # 标题必须是 参考信源（用户 2026-09-05 定调：统一叫参考信源，露出 ≤5 条）
        rm = re.search(r'class="[^"]*references[^"]*"[^>]*>.*?<h[23][^>]*>(.*?)</h[23]>', region, re.S)
        if rm:
            title = re.sub(r'<[^>]+>', '', rm.group(1)).strip()
            if title != '参考信源':
                issues.append(f"{rel}: 参考块标题为「{title}」（应为「参考信源」）")
    # 6) 统一参考信源检查（覆盖 .references / .fact-sources / .verified-sources / .sources）
    def _extract_tag_block(html, start_idx):
        """提取从 start_idx 处的开标签到其匹配闭合标签之间的完整块。

        关键修复（2026-09-05）：原实现用 `'/' in next_tag` 判断自闭合，但
        `<a href="https://...">` 的 URL 含 `/` 会被误判为自闭合，导致后续的
        `</a>` 多减一层 stack、区块提前闭合、<li> 计数偏少——造成「参考信源露出
        >5 条」的漏判（false negative）。现改为仅当标签以 `/` 结尾才视为自闭合。
        """
        tag_end = html.find('>', start_idx) + 1
        stack = 1
        i = tag_end
        while i < len(html) and stack > 0:
            if html[i] == '<':
                if html.startswith('</', i):
                    close_end = html.find('>', i) + 1
                    stack -= 1
                    i = close_end
                elif html.startswith('<!', i) or html.startswith('<?', i):
                    i = html.find('>', i) + 1
                else:
                    gt = html.find('>', i)
                    next_tag = html[i+1:gt]
                    is_void = next_tag.lower().split()[0] in ('meta', 'link', 'img', 'br', 'hr', 'input', 'source')
                    is_selfclose = next_tag.rstrip().endswith('/')
                    if not is_void and not is_selfclose:
                        stack += 1
                    i = gt + 1
            else:
                i += 1
        return html[start_idx:i]

    source_patterns = [
        ('references', r'<section[^>]*class="[^"]*references[^"]*"[^>]*>'),
        ('fact-sources', r'<section[^>]*class="[^"]*fact-sources[^"]*"[^>]*>'),
        ('verified-sources', r'<section[^>]*class="[^"]*verified-sources[^"]*"[^>]*>'),
        ('sources', r'<div[^>]*class="[^"]*\bsources\b[^"]*"[^>]*>'),
    ]
    for cls_name, pat in source_patterns:
        for m in re.finditer(pat, region, re.S):
            block = _extract_tag_block(region, m.start())
            # 标题必须是 参考信源
            hm = re.search(r'<h[23][^>]*>(.*?)</h[23]>', block, re.S)
            if hm:
                title = re.sub(r'<[^>]+>', '', hm.group(1)).strip()
                if title != '参考信源':
                    issues.append(f"{rel}: {cls_name} 参考块标题为「{title}」（应为「参考信源」）")
            # 条目数 ≤5
            n_li = len(re.findall(r'<li[ >]', block))
            if n_li > 5:
                issues.append(f"{rel}: {cls_name} 参考信源露出 {n_li} 条（应 ≤5 条）")

    # 7) 顺序（三者皆有时）
    ri = region.find('class="related-reading"')
    qi = region.find('<div class="article-footer-qr"')
    si = region.find('class="references"')
    present = [x for x in [(ri,'R'),(qi,'Q'),(si,'S')] if x[0] != -1]
    present.sort()
    order = ''.join(n for _, n in present)
    if {'R', 'Q', 'S'}.issubset(set(order)) and order != 'RQS':
        issues.append(f"{rel}: 尾页顺序为 {order}（应为 RQS）")

    return issues

def main():
    files = sorted(glob.glob(os.path.join(ART_DIR, '*.html')))
    all_issues = []
    for f in files:
        all_issues += check_file(f)
    if all_issues:
        print(f"❌ 尾页一致性检查失败：{len(all_issues)} 处")
        for i in all_issues[:50]:
            print(f"  • {i}")
        sys.exit(1)
    print(f"✅ 尾页一致性检查通过：{len(files)} 篇内容文章均符合 canonical 规范")
    sys.exit(0)

if __name__ == '__main__':
    main()
