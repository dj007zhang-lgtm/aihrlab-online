#!/usr/bin/env python3
# 终版 AI 味文风清理：正文级破折号 + 中文邻半角
# 真实字符覆盖：U+2014(—) / U+2013(–) / ASCII "--" / 双全角"——"
# 保护 <pre>/<code>/<blockquote> 不被误改（占位后还原）
import re, os, sys

EM = chr(0x2014)
EN = chr(0x2013)
HALF = {',': '，', ':': '：', ';': '；', '!': '！', '?': '？',
        '(': '（', ')': '）', '[': '【', ']': '】'}
YEAR = re.compile(r'(\d)\s*[\u2014\u2013]{1,2}\s*(\d)')  # 仅 em/en dash 年份跨度；ASCII - 留给日期/URL


def clean_text(t: str) -> str:
    # 1) 年份跨度（em/en dash 数字间）-> 数字至数字
    t = YEAR.sub(lambda m: m.group(1) + '至' + m.group(2), t)
    # 2) 其余破折号 -> 逗号（ASCII 单连字符 - 不碰，保护日期/URL/复合词）
    t = t.replace(EM, '，').replace(EN, '，').replace('——', '，').replace('--', '，')
    # 2.5) 双破折号会产生双逗号，折叠重复中文标点
    t = re.sub(r'([，。：；！？、]){2,}', r'\1', t)
    # 3) 中文邻半角 -> 全角
    for h, f in HALF.items():
        t = re.sub(r'(?<=[\u4e00-\u9fff])' + re.escape(h), f, t)
        t = re.sub(re.escape(h) + r'(?=[\u4e00-\u9fff])', f, t)
    return t


def clean_body(html: str) -> str:
    # 保护脚本/样式/代码块（JSON-LD、prompt 模板等），其余（含 head 标题与 blockquote 署名）统一清洗
    blocks = []

    def _stash(m):
        blocks.append(m.group(0))
        return f'\x00BLOCK{len(blocks)-1}\x00'

    protected = re.sub(r'<(script|style|pre|code)[^>]*>.*?</\1>', _stash, html, flags=re.S | re.I)
    cleaned = clean_text(protected)
    for i, b in enumerate(blocks):
        cleaned = cleaned.replace(f'\x00BLOCK{i}\x00', b)
    return cleaned


def main():
    files = open('/tmp/aitaste_publish.txt').read().split()
    total_dash = total_hw = 0
    for p in files:
        if not os.path.exists(p):
            print('MISS', p); continue
        html = open(p, encoding='utf-8').read()
        new = clean_body(html)
        if new != html:
            open(p, 'w', encoding='utf-8').write(new)
            # 计数本次改动
            d = new.count(EM) + new.count(EN) + new.count('--') + new.count('——')
            print(f'已清理 {os.path.basename(p)[:-5]}')
        else:
            print(f'无需改 {os.path.basename(p)[:-5]}')
    print('done')


if __name__ == '__main__':
    main()
