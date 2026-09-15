#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性证据核验：对 monitor 的正见补强信号做带上下文的真实性复核（owner verification）。"""
import os, re, glob

ART = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/articles"

def body_text(slug):
    p = os.path.join(ART, slug + ".html")
    if not os.path.exists(p): return ""
    h = open(p, encoding="utf-8", errors="ignore").read()
    m = re.search(r"<article\b[^>]*>(.*?)</article>", h, re.S | re.I)
    b = m.group(1) if m else h
    b = re.sub(r"<(script|style)\b.*?</\1>", " ", b, flags=re.S | re.I)
    b = re.sub(r"<[^>]+>", " ", b)
    return re.sub(r"\s+", " ", b).strip()

# 1) 页面已迁移 stub 计数
stubs = []
for f in glob.glob(os.path.join(ART, "*.html")):
    t = open(f, encoding="utf-8", errors="ignore").read()
    if "页面已迁移" in t:
        stubs.append(os.path.basename(f))
print(f"[1] '页面已迁移' stub 总数：{len(stubs)}")
for s in stubs[:30]: print("    ", s)

# 2) 虚构具名场景
FAB = re.compile(r"(小张|小王|小李|小赵|小刘|小陈|小杨|小黄|小周|小吴|小孙|小胡|某员工|某HR|某经理|某主管|某同事|某总监|王经理|李总|张总|刘总|陈总|赵总|周总)")
print("\n[2] 虚构具名场景核验：")
for slug in ["hr-90-days-after-ai-org-change-2026", "human-ai-equation"]:
    t = body_text(slug)
    for m in FAB.finditer(t):
        i = m.start(); print(f"  {slug}: …{t[max(0,i-25):i+25]}…")

# 3) 推测写死（抽样带上下文）
SPEC = re.compile(r"(必将|必定|一定会|毫无疑问会|注定会|必然导致|必然带来|一定会被|毫无疑问将|势必将|必然会|无可避免地(?:被|将)|注定(?:被|要))")
print("\n[3] 推测写死核验（每篇最多2处上下文）：")
for slug in ["mckinsey-2026-ai-automation-sector-impact","xiaomi-2026-org-evolution",
             "2026-hr-transformation-chief-architect","ai-rebuild-training-coach-2026",
             "anthropic-engineer-three-stages","ai-native-human-agent-contract-2026",
             "anthropic-best-ai-company","ai-evaluation-split-2026",
             "ai-hr-2026-midyear-three-signals","from-company-to-intelligent-organization"]:
    t = body_text(slug)
    hits = list(SPEC.finditer(t))[:2]
    if hits:
        print(f"  ▶ {slug}")
        for m in hits:
            i = m.start(); print(f"      …{t[max(0,i-30):i+30]}…")

# 4) 营销腔
MKT = re.compile(r"(必看|干货满满|保姆级|一文搞懂|彻底搞懂|强烈推荐|不得不看|绝绝子|封神|yyds|宝藏(?:干货|方法|攻略|清单)|速收藏|码住|建议转发|无脑冲|闭眼入|神器)")
print("\n[4] 营销腔核验：")
t = body_text("hr-bigfive-recruitment-screening")
for m in MKT.finditer(t):
    i = m.start(); print(f"  hr-bigfive-recruitment-screening: …{t[max(0,i-25):i+25]}…")
