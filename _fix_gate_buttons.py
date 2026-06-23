#!/usr/bin/env python3
"""把 resources/index.html 的 gate-trigger 按钮改为 onclick 直接调用 openGate()"""
import re

HTML = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/resources/index.html"

with open(HTML, "r") as f:
    html = f.read()

# 匹配含 data-gate-title 和 data-gate-instruction 的 button 标签
# 用非贪婪匹配，支持单引号或双引号
pattern = re.compile(
    r'<button\b[^>]*\bclass="btn-gate[^"]*"[^>]*>.*?</button>',
    re.DOTALL
)

def replace_button(match):
    tag = match.group(0)
    # 提取 data-gate-title
    m1 = re.search(r'data-gate-title="([^"]*)"', tag)
    # 提取 data-gate-instruction（值含单引号包裹，内部可能有 HTML）
    m2 = re.search(r"data-gate-instruction='([^']*)'", tag)
    title = m1.group(1) if m1 else "获取资源"
    instruction = m2.group(1) if m2 else ""

    # 构建新的 onclick 调用
    # 把 instruction 中的单引号转义为 &#39; 避免与 HTML 属性引号冲突
    instruction_escaped = instruction.replace("'", "&#39;")
    # 把 title 中的双引号转义
    title_escaped = title.replace('"', "&quot;")

    onclick = (
        f"openGate("
        f"decodeURIComponent('{title_escaped}'), "
        f"decodeURIComponent('{instruction_escaped}')"
        f")"
    )
    # 简化：直接用 data 属性 + this，不拼 JS 字符串
    # 更好方案：onclick 中用 this.dataset 读取
    onclick = "openGateFromButton(this)"

    new_tag = tag
    # 删除 data-gate-* 属性，改为 onlick + data 属性保留
    new_tag = re.sub(r'\s*data-gate-title="[^"]*"', '', new_tag)
    new_tag = re.sub(r"\s*data-gate-instruction='[^']*'", '', new_tag)
    new_tag = re.sub(r'\s*class="btn-gate[^"]*"', ' class="btn-gate"', new_tag)
    # 插入 onclick
    new_tag = new_tag.replace('<button', '<button onclick="openGateFromButton(this)"', 1)
    return new_tag

new_html = pattern.sub(replace_button, html)
count = len(pattern.findall(html))
print(f"Matched {count} buttons")

with open(HTML, "w") as f:
    f.write(new_html)
print("HTML updated")
