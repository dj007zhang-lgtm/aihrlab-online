#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 meta description 中的「标题复读 / 半截句」残留。

上一步 repair_meta_descriptions.py 取的是正文首段，而这些文章的首段是模板生成的
「<标题>？<标题>的核心洞察：……」结构，导致描述里塞进了自我提问与重复标题。

本脚本对已修复页面做后处理：
  - 若描述中在句中再次出现本篇 h1，截掉从复读处开始的尾巴；
  - 清理悬挂逗号、连续标点；
  - 保证仍 >=50 汉字，不足则保留原值不动。
"""
import os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r"[\u4e00-\u9fff]")
DESC_RE = re.compile(r'(<meta\s+name="description"\s+content=")([^"]*)(")')


def clean(desc, h1):
    if h1 and len(h1) >= 6:
        i = desc.find(h1)
        # 只在「非开头」位置出现才算复读（开头复用标题是允许的强意图写法）
        if i > 3:
            head = desc[:i].strip()
            if len(HAN.findall(head)) >= 50:
                desc = head
    desc = re.sub(r"\s+", " ", desc)
    desc = re.sub(r"^[，、；：\s]+", "", desc)          # 悬挂标点
    desc = re.sub(r"[，、；：]\s*$", "", desc)
    desc = re.sub(r"，,|,,|。。", lambda m: m.group(0)[0], desc)
    desc = re.sub(r"，\s*，", "，", desc)
    return desc.strip()


def main():
    touched = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "articles", "*.html"))):
        html = open(f, encoding="utf-8").read()
        if 'http-equiv="refresh"' in html:
            continue
        m = DESC_RE.search(html)
        if not m:
            continue
        cur = m.group(2)
        h1m = re.search(r"<h1>(.*?)</h1>", html, re.S)
        h1 = re.sub(r"<[^>]+>", "", h1m.group(1)).strip() if h1m else ""
        new = clean(cur, h1)
        if new == cur:
            continue
        if len(HAN.findall(new)) < 50:
            print(f"  KEEP(不足50字) {os.path.basename(f)}")
            continue
        html = DESC_RE.sub(lambda x: x.group(1) + new + x.group(3), html, count=1)
        open(f, "w", encoding="utf-8").write(html)
        touched += 1
        print(f"  CLEANED {os.path.basename(f)}")
        print(f"    - {cur[:70]}")
        print(f"    + {new[:70]}")
    print(f"\nSummary: cleaned={touched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
