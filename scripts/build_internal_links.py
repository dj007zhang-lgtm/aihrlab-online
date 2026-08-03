#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内部链接工程（BCD · 索引/排名/权威/跳出率 四目标合一）

策略：
- 以「他文标题」+「策划概念锚点」为链接源，向 零内链 / 稀疏内链 文章注入 contextual ilink。
- 链接格式严格对齐现有约定：<a href="/articles/slug.html" class="ilink">锚文本</a>
- 仅注入文章正文区（<article ...> 至 <div class="article-footer-qr">），避开导航/页脚/已存在的链接/标签内。
- 每篇上限 3 条；已有 >=2 条的不动。
- 重定向桩页（含 http-equiv=refresh / window.location.replace）跳过。

用法：
  python3 scripts/build_internal_links.py            # 执行
  python3 scripts/build_internal_links.py --dry-run  # 仅报告将改哪些文件
"""
import os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, 'articles')

# ---------- 策划概念锚点（高价值跨集群链接，人工审定） ----------
# 短语 -> slug。仅当该短语出现在目标正文时才注入。
CONCEPT_ANCHORS = {
    "AI原生组织": "ai-native-org-hr-2026.html",
    "大厂AI组织": "big-tech-ai-org-2026.html",
    "大厂AI组织变革": "big-tech-ai-org-2026.html",
    "AI裁员": "ai-layoff-to-rebuild-hr-stand-firm.html",
    "中层管理": "ai-flatten-org-middle-managers-2026.html",
    "中层管理者": "ai-flatten-org-middle-managers-2026.html",
    "组织扁平化": "ai-flatten-org-middle-managers-2026.html",
    "技能型组织": "ai-skills-based-org-2026.html",
    "人机协作": "human-ai-equation.html",
    "人机协作方程式": "human-ai-equation.html",
    "招聘算法偏见": "ai-recruitment-selection-guide-2026.html",
    "AI面试官": "ai-hiring-fairness-compliance-2026.html",
    "大五人格": "hr-bigfive-recruitment-screening.html",
    "行为风格测试": "disc-style-test-2026.html",
    "数字员工": "hr-digital-employee-2026.html",
    "GEO": "ai-citation-geo-playbook-2026.html",
    "被引用": "ai-citation-geo-playbook-2026.html",
    "情境管理": "bytedance-context-management-ai-agent.html",
    "智能组织": "from-company-to-intelligent-organization.html",
    "组织僵化": "ai-era-org-rigidity.html",
    "ROI现实检验": "ai-agent-roi-reality-2026.html",
    "AI Agent": "frontier-firm-ai-agent-2026.html",
    "治理鸿沟": "ai-governance-gap-hr-2026.html",
    "技能重构": "ai-talent-profile-reconstruction-2026.html",
    "人才画像": "ai-talent-profile-reconstruction-2026.html",
    "AI组织": "ai-hr-org-cluster.html",
}

MAX_PER_ARTICLE = 3


def read(f):
    return open(f, encoding='utf-8', errors='ignore').read()


def write(f, t):
    open(f, 'w', encoding='utf-8').write(t)


def clean_title(t):
    m = re.search(r'<title>(.*?)</title>', t, re.S)
    if not m:
        return ''
    return m.group(1).split(' | ')[0].strip()


def is_stub(t):
    return 'http-equiv="refresh"' in t or 'window.location.replace' in t


def body_region(t):
    """返回 (region_start, region_end) 指向 <article ...> 正文到页脚 QR 之前。"""
    m = re.search(r'<article[^>]*>', t)
    if not m:
        return None
    start = m.end()
    end = t.find('<div class="article-footer-qr">')
    if end == -1:
        end = len(t)
    return start, end


def already_linked_here(t, idx, phrase):
    """判断 phrase 在 idx 处是否已在 <a> 内或刚被链接。"""
    pre = t[max(0, idx - 80):idx]
    # 若前面 80 字符里存在未闭合的 '<'（即在标签内），跳过
    last_gt = pre.rfind('>')
    last_lt = pre.rfind('<')
    if last_lt > last_gt:
        return True  # 在标签内
    # 若前面紧跟 href= 说明在链接内
    if 'href=' in pre[last_gt + 1:]:
        return True
    post = t[idx + len(phrase):idx + len(phrase) + 12]
    if post.startswith('</a>'):
        return True
    # 关键修复：检查从文档开头到 idx 的 <a 开标签数是否多于 </a> 闭标签数
    # （即当前是否处于某个 <a> 的内部——防止嵌套链接）
    opens = t[:idx].count('<a ')
    closes = t[:idx].count('</a>')
    if opens > closes:
        return True
    return False


def inject_first(t, phrase, href):
    """在正文区首次出现的 phrase 处注入 ilink；返回 (new_text, injected_bool)。"""
    br = body_region(t)
    if not br:
        return t, False
    s, e = br
    region = t[s:e]
    idx = region.find(phrase)
    while idx != -1:
        abs_idx = s + idx
        if not already_linked_here(t, abs_idx, phrase):
            repl = f'<a href="/articles/{href}" class="ilink">{phrase}</a>'
            return t[:abs_idx] + repl + t[abs_idx + len(phrase):], True
        idx = region.find(phrase, idx + 1)
    return t, False


def target_h1(slug):
    """读取目标文章的 H1（用于前缀守卫：避免锚文本是目标 H1 的前半截）。"""
    p = os.path.join(ART, slug)
    if not os.path.exists(p):
        return ''
    t = read(p)
    m = re.search(r'<h1[^>]*>(.*?)</h1>', t, re.S)
    return re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ''


def main():
    dry = '--dry-run' in sys.argv
    files = sorted(glob.glob(os.path.join(ART, '*.html')))

    # 建立 标题 -> slug 映射（用于标题级交叉链接）
    title_map = {}
    meta = {}
    for f in files:
        t = read(f)
        if is_stub(t):
            continue
        ct = clean_title(t)
        if len(ct) >= 8 and ct not in ('页面已迁移',):
            slug = os.path.basename(f)
            title_map[ct] = slug
            meta[f] = {'slug': slug, 'title': ct}

    # 目标 H1 缓存（前缀守卫用）
    h1_cache = {}

    def is_prefix_of_target(phrase, slug):
        if slug not in h1_cache:
            h1_cache[slug] = target_h1(slug)
        h1 = h1_cache[slug]
        if not h1:
            return False
        return h1.startswith(phrase)

    changed = []
    for f in files:
        if os.path.basename(f) == 'index.html':
            continue  # 列表页，非文章
        t = read(f)
        if is_stub(t):
            continue
        cur = t.count('class="ilink"')
        if cur >= 2:
            continue  # 已有足够内链
        need = MAX_PER_ARTICLE - cur
        if need <= 0:
            continue

        # 候选：(phrase, slug)
        cands = []
        seen_href = set()
        # 1) 标题级：他文标题出现在本正文
        for ct, slug in title_map.items():
            if slug == os.path.basename(f):
                continue
            if slug in seen_href:
                continue
            if ct in t and not is_prefix_of_target(ct, slug):
                cands.append((ct, slug))
                seen_href.add(slug)
        # 2) 概念锚点
        for phrase, slug in CONCEPT_ANCHORS.items():
            if slug == os.path.basename(f):
                continue
            if slug in seen_href:
                continue
            if phrase in t and not is_prefix_of_target(phrase, slug):
                cands.append((phrase, slug))
                seen_href.add(slug)

        new_t = t
        added = 0
        for phrase, slug in cands:
            if added >= need:
                break
            new_t, ok = inject_first(new_t, phrase, slug)
            if ok:
                added += 1
        if added > 0:
            if not dry:
                write(f, new_t)
            changed.append((os.path.basename(f), cur, cur + added))

    print(f"{'DRY-RUN ' if dry else ''}内部链接工程：改动 {len(changed)} 个文件")
    for fn, a, b in changed:
        print(f"  {fn}: {a} -> {b} ilinks")
    return changed


if __name__ == '__main__':
    main()
