#!/usr/bin/env python3
"""
统一修复所有文章页面的模板和排版问题
=====================================

问题清单：
1. Type A (25篇): 旧的 site-header 双层嵌套结构
2. Type B (12篇): 引用不存在的 article.css
3. Type C (47篇): 结构OK但缺少部分CSS类
4. 全部文章: favicon路径、统计代码不一致

修复方案：
1. 统一 header 为标准格式（基于 index.html 的结构）
2. 统一 CSS 为 style.min.css（唯一CSS文件）
3. 删除 article.css 引用（文件不存在）
4. 补充缺失的 CSS 类到 style.min.css
5. 统一 favicon 路径
6. 确保统计代码完整
"""

import os
import re
import json
from pathlib import Path

SITE_DIR = Path('/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated')
ARTICLES_DIR = SITE_DIR / 'articles'
CSS_FILE = SITE_DIR / 'assets/css/style.min.css'

# ============================================================
# 标准导航栏HTML（基于index.html，适配articles目录相对路径）
# ============================================================
STANDARD_HEADER = '''<header class="site-header">
    <div class="container">
      <a href="../index.html" class="site-logo" aria-label="AIHR数智引擎首页">
        <img src="../assets/images/avatar.png" class="logo-icon" alt="AIHR数智引擎" width="28" height="28">
        AIHR<span class="logo-dot">数智引擎</span>
      </a>
      <button class="nav-toggle" aria-label="打开导航菜单">&#9776;</button>
      <nav class="site-nav" aria-label="主导航">
        <a href="../index.html">首页</a>
        <a href="./index.html" class="active" aria-current="page">全部文章</a>
        <a href="../resources/index.html">资源库</a>
        <a href="../about.html">关于</a>
        <button class="nav-search-btn" data-open-search aria-label="搜索文章">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <span>搜索</span>
        </button>
      </nav>
    </div>
  </header>'''

# 标准favicon块
STANDARD_FAVICON = '''<link rel="icon" type="image/png" sizes="32x32" href="../assets/images/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="../assets/images/favicon-16x16.png">
  <link rel="apple-touch-icon" href="../assets/images/apple-touch-icon.png">
  <link rel="shortcut icon" href="../assets/images/favicon-32x32.png" type="image/png">'''

# GA4 统计代码
GA4_CODE = '''<script async src="https://www.googletagmanager.com/gtag/js?id=G-BWLGRVRRGN"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-BWLGRVRRGN');
  </script>'''

# 百度统计代码  
BAIDU_CODE = '''<script>
    var _hmt = _hmt || [];
    (function() {
      var hm = document.createElement("script");
      hm.src = "https://hm.baidu.com/hm.js?b53ffd054b55836f535892622f1e4cc5";
      var s = document.getElementsByTagName("script")[0];
      s.parentNode.insertBefore(hm, s);
    })();
  </script>'''

# 缺失的CSS规则（追加到style.min.css）
MISSING_CSS_RULES = """
/* ===== 统一补充：文章详情页缺失类 ===== */
.article-content-wrapper{max-width:760px;margin:0 auto;padding:2rem 1.5rem}
.article-detail{max-width:760px;margin:0 auto;padding:2rem 1.5rem}
.breadcrumb{font-size:.85rem;color:#666;margin-bottom:1.5rem;padding:.8rem 0}
.breadcrumb a{color:#2c5ea8;text-decoration:none}
.breadcrumb a:hover{text-decoration:underline}
.breadcrumb .separator{margin:0 .4rem;color:#999}
"""


def fix_article_file(filepath):
    """修复单个文章文件"""
    content = filepath.read_text(encoding='utf-8', errors='ignore')
    original = content
    filename = filepath.name
    
    changes = []
    
    # ---- 1. 统一CSS引用：只保留 style.min.css ----
    # 删除 article.css 引用
    if 'article.css' in content:
        content = re.sub(
            r'\s*<link\s+rel=["\']stylesheet["\'][^>]*article\.css["\'][^>]*>',
            '',
            content
        )
        changes.append("删除article.css引用")
    
    # 将 style.css 替换为 style.min.css
    if re.search(r'href=["\'][^"\']*style\.css["\'](?!.*min)', content):
        content = re.sub(
            r'href=["\']([^"\']*)(style\.css)["\']',
            lambda m: f'href="../assets/css/style.min.css"' if 'min' not in m.group(1) else m.group(0),
            content
        )
        # 更精确的替换
        content = re.sub(
            r'href=["\']\.\./assets/css/style\.css["\'](?!"")',
            'href="../assets/css/style.min.css"',
            content
        )
        content = re.sub(
            r'href=["\']\./assets/css/style\.css["\'](?!"")',
            'href="../assets/css/style.min.css"',
            content
        )
        changes.append("CSS统一为style.min.css")
    
    # 确保有 style.min.css 引用
    if 'style.min.css' not in content:
        # 在 </head> 前插入
        content = content.replace('</head>', '  <link rel="stylesheet" href="../assets/css/style.min.css">\n</head>')
        changes.append("添加style.min.css引用")
    
    # ---- 2. 统一Header结构 ----
    
    # 情况A：有 <header class="site-header"> 但结构是旧的（带 header-inner 或 logo图片在错误位置）
    if '<header class="site-header">' in content or '<header class=site-header>' in content:
        # 找到从 <header 到对应的 </header> 的完整内容
        # 替换整个 header 块为标准格式
        
        # 用正则匹配并替换 header 部分
        header_pattern = r'<header[^>]*class=["\']?site-header["\']?[^>]*>.*?</header>'
        new_content = re.sub(header_pattern, STANDARD_HEADER, content, flags=re.DOTALL)
        if new_content != content:
            content = new_content
            changes.append("替换旧site-header为新格式")
    
    # 情况B：有 <nav class="site-nav"> 直接作为body第一个子元素（Type B/C格式）
    # 这种格式也需要统一 - 改为包含在 site-header 中
    elif re.search(r'<body\s*>\s*\n\s*<nav\s+class=["\']site-nav["\']', content):
        # 将独立的 nav 包裹在标准 header 中
        nav_pattern = r'(<body\s*>)\s*(\n\s*<nav\s+class=["\']site-nav["\'][^>]*>.*?</nav>)'
        
        def replace_nav(match):
            return match.group(1) + '\n  ' + STANDARD_HEADER + '\n'
        
        new_content = re.sub(nav_pattern, replace_nav, content, flags=re.DOTALL)
        if new_content != content:
            content = new_content
            changes.append("将独立site-nav包裹进标准site-header")
    
    # ---- 3. 统一Favicon ----
    # 删除所有旧的 favicon/icon link
    icon_pattern = r'\s*<link\s+(?:rel=["\'](?:icon|shortcut icon|apple-touch-icon)["\'][^>]*|type=["\']image/png["\'][^>]*|(?:sizes|href)=["\'][^"\']*["\'])+[^>]*>*'
    # 更简单的方式：删除所有含 avatar.png 的icon和 shortcut icon 行
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        stripped = line.strip()
        # 移除旧favicon行（指向avatar.png的或重复的icon）
        if ('rel="icon"' in line or 'rel="shortcut icon"' in line or 'rel="apple-touch-icon"' in line):
            if 'avatar.png' in line or 'favicon-' not in line:
                continue  # 跳过旧的/错误的favicon行
        new_lines.append(line)
    content = '\n'.join(new_lines)
    
    # 确保有正确的favicon（在viewport之后）
    if 'favicon-32x32.png' not in content:
        content = content.replace(
            '<meta name="viewport"',
            STANDARD_FAVICON + '\n  <meta name="viewport"',
            1
        )
        changes.append("添加标准favicon")
    
    # ---- 4. 确保统计代码存在 ----
    has_ga4 = 'G-BWLGRVRRGN' in content
    has_baidu = 'b53ffd054b55836f535892622f1e4cc5' in content
    
    if not has_ga4:
        # 在 </head> 前添加
        content = content.replace('</head>', GA4_CODE + '\n</head>')
        changes.append("添加GA4统计代码")
    
    if not has_baidu:
        # 在 </head> 前添加（在GA4之后）
        content = content.replace('</head>', BAIDU_CODE + '\n</head>')
        changes.append("添加百度统计代码")
    
    # ---- 5. 修复 main 内容区域class ----
    # 统一使用 article-main 或确保有合适的容器
    if 'class="main-content"' in content and 'class="article-main"' not in content:
        content = content.replace('class="main-content"', 'class="article-main"', 1)
        changes.append("main-content → article-main")
    
    # 如果有 article-detail 容器但没有正确包装
    if 'class="article-detail"' in content and 'class="container"' in content:
        content = content.replace('class="article-detail container"', 'class="article-detail"')
        changes.append("移除article-detail上的多余container类")
    
    # 写回文件
    if content != original or changes:
        filepath.write_text(content, encoding='utf-8')
        return changes
    return []


def add_missing_css_rules():
    """向 style.min.css 追加缺失的CSS规则"""
    css_content = CSS_FILE.read_text(encoding='utf-8')
    
    if '.article-content-wrapper' not in css_content:
        css_content += MISSING_CSS_RULES
        CSS_FILE.write_text(css_content, encoding='utf-8')
        print(f"  ✅ 已向 style.min.css 补充 {len(MISSING_CSS_RULES.strip().split(chr(10)))} 条CSS规则")
        return True
    else:
        print("  ⏭️  style.min.css 已包含所需规则，跳过")
        return False


def main():
    print("=" * 65)
    print("  AIHR数智引擎 — 文章页面统一修复脚本")
    print("=" * 65)
    print()
    
    # Step 1: 先修复 CSS
    print("Step 1/3: 检查并修复 style.min.css 缺失规则")
    print("-" * 45)
    css_changed = add_missing_css_rules()
    print()
    
    # Step 2: 扫描并修复所有文章
    print("Step 2/3: 扫描并修复所有文章页面")
    print("-" * 45)
    
    html_files = sorted([f for f in ARTICLES_DIR.glob('*.html') if f.name != 'index.html'])
    
    stats = {'fixed': 0, 'unchanged': 0, 'total_changes': 0}
    details = []
    
    for filepath in html_files:
        changes = fix_article_file(filepath)
        if changes:
            stats['fixed'] += 1
            stats['total_changes'] += len(changes)
            details.append((filepath.name, changes))
        else:
            stats['unchanged'] += 1
    
    print(f"  总计: {len(html_files)} 篇文章")
    print(f"  已修复: {stats['fixed']} 篇")
    print(f"  无需修改: {stats['unchanged']} 篇")
    print(f"  总修改项: {stats['total_changes']} 项")
    print()
    
    # 显示修改详情
    if details:
        print("  修改详情（前20篇）:")
        for fname, changes in details[:20]:
            change_str = ', '.join(changes[:3])
            if len(changes) > 3:
                change_str += f' (+{len(changes)-3})'
            print(f"    📄 {fname:50s} → {change_str}")
        if len(details) > 20:
            print(f"    ... 还有 {len(details)-20} 篇")
    print()
    
    # Step 3: 验证
    print("Step 3/3: 验证修复结果")
    print("-" * 45)
    
    errors = []
    
    # 检查是否还有引用不存在的article.css
    remaining_article_css = []
    for f in html_files:
        c = f.read_text(encoding='utf-8', errors='ignore')
        if 'article.css' in c:
            remaining_article_css.append(f.name)
    
    if remaining_article_css:
        errors.append(f"仍有 {len(remaining_article_css)} 篇引用不存在的article.css")
        for n in remaining_article_css[:5]:
            errors.append(f"  - {n}")
    
    # 检查是否还有旧的site-header双层嵌套
    remaining_old_header = []
    for f in html_files:
        c = f.read_text(encoding='utf-8', errors='ignore')
        if 'class="header-inner"' in c:
            remaining_old_header.append(f.name)
    
    if remaining_old_header:
        errors.append(f"仍有 {len(remaining_old_header)} 篇保留旧的header-inner结构")
        for n in remaining_old_header[:5]:
            errors.append(f"  - {n}")
    
    # 验证CSS括号平衡
    css = CSS_FILE.read_text(encoding='utf-8')
    if css.count('{') != css.count('}'):
        errors.append(f"⚠️ CSS括号不平衡: open={css.count('{')} close={css.count('}')}")
    else:
        print(f"  ✅ CSS括号平衡 ({css.count('{')} 对)")
    
    if errors:
        print("  ⚠️ 发现以下问题:")
        for e in errors:
            print(f"    {e}")
    else:
        print("  ✅ 所有检查通过!")
    
    print()
    print("=" * 65)
    print("  修复完成! 请运行 git diff 查看变更，确认后提交推送。")
    print("=" * 65)


if __name__ == '__main__':
    main()
