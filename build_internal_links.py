#!/usr/bin/env python3
"""
全站内部链接矩阵构建脚本
功能: 基于文章标题关键词匹配，为每篇文章生成「相关阅读」推荐
"""

import os, re, json
from collections import Counter
from pathlib import Path

ARTICLES_DIR = Path(__file__).parent / "articles"


def extract_title(html_path):
    """从HTML文件中提取标题"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 尝试从 og:title 或 <title> 或 <h1> 提取
    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', content)
    if m:
        return m.group(1).replace(' | AIHR数智引擎', '').replace(' - AIHR数智引擎', '').strip()
    m = re.search(r'<title>([^<]*)</title>', content)
    if m:
        return m.group(1).replace(' | AIHR数智引擎', '').replace(' - AIHR数智引擎', '').strip()
    m = re.search(r'<h1[^>]*>([^<]+)</h1>', content)
    if m:
        return m.group(1).strip()
    return html_path.stem


def tokenize(text):
    """简单的中文分词（基于2-gram）"""
    # 英文字母数字视为整体
    tokens = []
    i = 0
    while i < len(text):
        if text[i].isalnum() and text[i].isascii():
            # 英文字母数字连续片段
            j = i
            while j < len(text) and text[j].isalnum() and text[j].isascii():
                j += 1
            tokens.append(text[i:j].lower())
            i = j
        elif '\u4e00' <= text[i] <= '\u9fff':
            # 中文2-gram
            if i + 1 < len(text) and '\u4e00' <= text[i+1] <= '\u9fff':
                tokens.append(text[i:i+2])
            i += 1
        else:
            i += 1
    return tokens


def is_redirect_page(content):
    """检测是否为重定向页面"""
    return 'http-equiv="refresh"' in content[:500]


def build_article_index():
    """扫描所有文章，建立标题/关键词索引（排除重定向页）"""
    articles = {}
    skipped = []
    for fpath in sorted(ARTICLES_DIR.glob("*.html")):
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 跳过重定向页面
        if is_redirect_page(content):
            skipped.append(fpath.name)
            continue
        
        title = extract_title(fpath)
        # 提取 h2 标题作为关键词补充
        h2s = re.findall(r'<h2[^>]*>([^<]+)</h2>', content)
        # 提取 meta description
        desc = ''
        m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', content)
        if m:
            desc = m.group(1)
        
        # 合并标题+h2+描述作为全文特征
        full_text = title + ' ' + ' '.join(h2s[:5]) + ' ' + desc
        tokens = tokenize(full_text)
        
        articles[fpath.name] = {
            'title': title,
            'tokens': Counter(tokens),
            'path': fpath.name,
            'url': f'/articles/{fpath.name}'
        }
    
    if skipped:
        print(f"  跳过 {len(skipped)} 个重定向页面: {', '.join(skipped)}")
    
    return articles


def compute_similarity(tokens_a, tokens_b):
    """计算两篇文章的相似度（基于共同token数量）"""
    common = set(tokens_a.keys()) & set(tokens_b.keys())
    if not common:
        return 0.0
    # 加权：高频token权重更高
    score = sum(
        min(tokens_a[t], tokens_b[t]) 
        for t in common
    )
    # 归一化
    norm = (sum(tokens_a.values()) * sum(tokens_b.values())) ** 0.5
    return score / norm if norm > 0 else 0.0


def gen_related_links(articles, top_n=4):
    """为每篇文章生成相关文章推荐"""
    related = {}
    filenames = list(articles.keys())
    
    for fn in filenames:
        scores = []
        for other_fn in filenames:
            if fn == other_fn:
                continue
            sim = compute_similarity(articles[fn]['tokens'], articles[other_fn]['tokens'])
            if sim > 0:
                scores.append((sim, articles[other_fn]))
        
        # 取top N
        scores.sort(key=lambda x: x[0], reverse=True)
        related[fn] = [item[1] for item in scores[:top_n]]
    
    return related


def inject_related_links(articles, related):
    """将相关阅读HTML注入到每篇文章中"""
    count = 0
    for fn, recs in related.items():
        fpath = ARTICLES_DIR / fn
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除旧的 related-reading 区块（如果存在），确保不会重复
        content = re.sub(
            r'\s*<!-- 相关阅读 -->\s*<section class="related-reading">.*?</section>\s*',
            '',
            content,
            flags=re.DOTALL
        )
        
        # 验证无自引用
        recs = [r for r in recs if r['path'] != fn]
        if len(recs) < 4:
            print(f"  WARN {fn}: only {len(recs)} valid recommendations after filtering")
        
        # 生成相关阅读HTML
        links_html = '\n'.join([
            f'          <li><a href="{r["url"]}">{r["title"]}</a></li>'
            for r in recs
        ])
        
        related_html = f'''
      <!-- 相关阅读 -->
      <section class="related-reading">
        <h3>相关阅读</h3>
        <ul>
{links_html}
        </ul>
      </section>
'''
        
        # 注入到 </article> 之前
        if '</article>' in content:
            content = content.replace('</article>', related_html + '    </article>')
        else:
            # 备选：注入到 <footer> 之前
            m = re.search(r'(    <footer[^>]*>)', content)
            if m:
                content = content.replace(m.group(1), related_html + m.group(1))
        
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        count += 1
        print(f"  OK {fn}: +{len(recs)} related links")
    
    return count


def main():
    print("=== 构建内部链接矩阵 ===\n")
    
    print("[1/3] 扫描文章，提取特征...")
    articles = build_article_index()
    print(f"  共 {len(articles)} 篇文章\n")
    
    # 打印关键词分布
    print("  Top关键词分布:")
    all_tokens = Counter()
    for a in articles.values():
        all_tokens.update(a['tokens'])
    for token, count in all_tokens.most_common(15):
        print(f"    {token}: {count}")
    print()
    
    print("[2/3] 计算文章相似度，生成推荐...")
    related = gen_related_links(articles)
    print(f"  每篇推荐 {len(list(related.values())[0])} 篇相关文章\n")
    
    print("[3/3] 注入「相关阅读」HTML...")
    inject_related_links(articles, related)
    
    print(f"\n✅ 完成！共处理 {len(articles)} 篇文章")


if __name__ == '__main__':
    main()
