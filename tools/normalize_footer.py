#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尾页(footer)一致性归一化引擎 v2 —— 合并多相关区块版。

Canonical 尾页模板（位于 </article> 内、正文之后，强制顺序）：
  [相关阅读]  .related-reading  <h3>相关阅读</h3> + <ul><li><a>...</a></li></ul>  (合并全部相关链接)
  [关注CTA]   .article-footer-qr  (类样式，剥 inline；统一 CTA 文案)
  [参考来源]  .references  <h3>参考来源</h3> + <ul>...</ul>   (仅对有来源的文章)

归一化规则：
  1. 删除 </article> 之后的孤儿「相关推荐」区块（一页两套相关阅读的 bug）。
  2. 收集全站该文所有相关链接：.related-reading / .article-related+.related-grid / 孤儿相关推荐，
     去重、相对路径转绝对(/articles/...)，保留首个 5 条 → 合并为单一 .related-reading。
  3. 删除 .article-related / .related-grid / 孤儿相关推荐 等冗余相关区块（仅保留合并后的 .related-reading）。
  4. QR 块统一为类样式，剥 inline style，统一 CTA 文案。
  5. references 块统一 class=.references、标题=参考来源（合并 source-note/source/article-sources）。
  6. 强制排列顺序：相关阅读 → QR → 参考来源。
  7. 幂等：已符合 canon 的文章不改动。

用法：
  python3 tools/normalize_footer.py --dry
  python3 tools/normalize_footer.py
"""
import re, glob, os, sys

ART_DIR = 'articles'
QR_CANON = '''<div class="article-footer-qr">
  <img decoding="async" loading="lazy" alt="AIHR数智引擎公众号二维码" src="/assets/images/qrcode-wechat.webp" width="160" height="160">
  <p>关注公众号，获取 AI 时代 HR 变革一手分析</p>
</div>'''

REF_CLASSES = r'(?:references|source-note|source|article-sources)'
STUB_RE = re.compile(r'http-equiv="refresh"')

# 相关区块匹配（覆盖 section/div 容器）——仅用于【读取】链接，不删除
REL_BLOCK_PATS = [
    r'<section[^>]*class="[^"]*related-reading[^"]*"[^>]*>.*?</section>',
    r'<div[^>]*class="[^"]*related-reading[^"]*"[^>]*>.*?</div>',
    r'<div[^>]*class="[^"]*article-related[^"]*"[^>]*>.*?</div>',
    r'<section[^>]*class="[^"]*article-related[^"]*"[^>]*>.*?</section>',
    r'<div[^>]*class="[^"]*related-grid[^"]*"[^>]*>.*?</div>',
]

# 孤儿相关推荐区块的【精确】签名（仅出现在 </article> 之后，用于安全删除，绝不波及全局页脚）
ORPHAN_PATS = [
    r'<section class="related-articles">.*?</section>',
    r'<section style="margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var\(--line\);">.*?</section>',
]

def norm_url(u):
    u = u.strip()
    if u.startswith('/') or u.startswith('http') or u.startswith('#'):
        return u
    if u.endswith('.html') and '/' not in u:
        return '/articles/' + u
    return u

def cap_links(links, cap=5):
    """保留首个 cap 条；若术语词典(glossary)链接会被截断则保住它。"""
    if len(links) <= cap:
        return links
    head = links[:cap]
    if any('glossary' in u for u, _ in head):
        return head
    gloss = [(u, t) for u, t in links if 'glossary' in u]
    if gloss:
        head[-1] = gloss[0]
    return head

def collect_related_links(html):
    """收集全文中所有相关链接 (url,title)，去重，相对转绝对。"""
    links = []
    seen = set()
    for pat in REL_BLOCK_PATS + ORPHAN_PATS:
        for m in re.finditer(pat, html, re.S):
            block = m.group(0)
            for am in re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
                url = am.group(1).strip()
                title = re.sub(r'<[^>]+>', '', am.group(2)).strip()
                if not title or not url:
                    continue
                url = norm_url(url)
                if url not in seen:
                    seen.add(url)
                    links.append((url, title))
    return links

def extract_ref_inner(region):
    m = re.search(r'(?:<div|<section)[^>]*class="[^"]*' + REF_CLASSES + r'[^"]*"[^>]*>.*?</(?:div|section)>', region, re.S)
    if not m:
        return ''
    ul = re.search(r'<ul[^>]*>.*?</ul>', m.group(0), re.S)
    if ul:
        return ul.group(0)
    ol = re.search(r'<ol[^>]*>.*?</ol>', m.group(0), re.S)
    return ol.group(0) if ol else ''

def strip_blocks(html):
    """移除 html 中所有 QR / 相关区块 / references 块（head 用，安全精确）。"""
    html = re.sub(r'<div class="article-footer-qr"[^>]*>.*?</div>', '', html, flags=re.S)
    # 仅用精确签名删孤儿，避免波及 head 内其他 section
    for pat in [p for p in REL_BLOCK_PATS if '相关推荐' not in p]:
        html = re.sub(pat, '', html, flags=re.S)
    html = re.sub(r'(?:<div|<section)[^>]*class="[^"]*' + REF_CLASSES + r'[^"]*"[^>]*>.*?</(?:div|section)>', '', html, flags=re.S)
    return html

def remove_orphan(tail):
    """仅从 </article> 之后的 tail 安全删除孤儿相关推荐区块（精确签名）。"""
    for pat in ORPHAN_PATS:
        tail = re.sub(pat, '', tail, flags=re.S)
    return tail

def normalize(html):
    if STUB_RE.search(html):
        return html, False, 'stub'
    ae = html.rfind('</article>')
    if ae == -1:
        return html, False, 'no-article(工具页)'
    head = html[:ae]
    tail = html[ae:]  # </article> + 全局页脚 + scripts

    # 收集（含孤儿）
    links = collect_related_links(html)
    links = cap_links(links, 5)
    ref_inner = extract_ref_inner(head)

    # 重建 canon 尾页
    parts = []
    if links:
        items = '\n'.join(f'          <li><a href="{u}">{t}</a></li>' for u, t in links)
        parts.append('<section class="related-reading">\n        <h3>相关阅读</h3>\n        <ul>\n' + items + '\n        </ul>\n      </section>')
    parts.append(QR_CANON)
    if ref_inner:
        parts.append('<section class="references"><h3>参考来源</h3>' + ref_inner + '</section>')
    canon = '\n'.join(parts)

    # 从 head 移除旧尾页块
    new_head = strip_blocks(head)
    new_head = new_head.rstrip()
    if new_head.endswith('</section>') or new_head.endswith('</div>'):
        new_head += '\n'
    # tail 仅安全删除孤儿相关推荐（精确签名，绝不波及全局页脚）
    new_tail = remove_orphan(tail)
    new_html = new_head + '\n' + canon + '\n' + new_tail

    # 校验：确保全局页脚关键标记仍在
    if 'site-footer' in html and 'site-footer' not in new_html:
        return html, False, '⚠全局页脚丢失-已放弃'
    changed = new_html != html
    return new_html, changed, f'links={len(links)} ref={"Y" if ref_inner else "N"}'

def main():
    dry = '--dry' in sys.argv
    files = sorted(glob.glob(os.path.join(ART_DIR, '*.html')))
    total = changed = skipped = 0
    reports = []
    for f in files:
        html = open(f, encoding='utf-8').read()
        new_html, ch, note = normalize(html)
        stem = os.path.splitext(os.path.basename(f))[0]
        total += 1
        if ch:
            changed += 1
            reports.append(f'  ✓ {stem}  [{note}]')
            if not dry:
                open(f, 'w', encoding='utf-8').write(new_html)
        else:
            skipped += 1
            reports.append(f'  - {stem}  跳过: {note}')
    print(f"=== 尾页归一化 v2 {'[DRY-RUN]' if dry else '[已执行]'} ===")
    print(f"扫描 {total} 篇 | 改动 {changed} | 跳过 {skipped}")
    for r in reports:
        print(r)

if __name__ == '__main__':
    main()
