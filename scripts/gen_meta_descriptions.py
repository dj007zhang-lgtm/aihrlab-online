#!/usr/bin/env python3
"""
批量补全 meta description（Bing 警告「Meta description 太短」）

策略：
- 文章页：抽取正文首段（真实、唯一、非模板填充），截断到 70-155 字符
- 落地/枢纽/对比页：用 CURATED 字典中的人工精选文案
- 抽取失败：回退到「标题核心 + 品牌后缀」

健壮性：
- description 标签检测顺序无关（兼容 content=.. name= 与 name=.. content=）
- 自动去重：同一页面多个 description 标签 → 保留最优（最长且≥70）或重生成，确保唯一
- 兜底不生成破碎文案（取完整首段，不截断到半句）

跳过：重定向桩页、搜索引擎验证文件、404.html、sitemap。幂等，可重跑。
用法：
  python3 scripts/gen_meta_descriptions.py --dry-run
  python3 scripts/gen_meta_descriptions.py --apply
"""
import os
import re
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_LEN = 70
MAX_LEN = 155

# 落地/枢纽/对比/工具页：人工精选 description（按相对路径，均 ≥80 字）
CURATED = {
    "index.html":
        "AIHR数智引擎——AI 时代 HR 转型与大厂组织变革的深度分析平台。硬核长文拆解大厂 AI 组织范式，权威测评工具矩阵，以及连接人才与企业的策展桥梁，帮你建立 AI 组织竞争力。",
    "about.html":
        "AIHR数智引擎——专注 AI 时代 HR 转型与大厂组织变革的深度分析平台。以原创硬核内容、权威测评工具与策展桥梁，助力 HR 从业者与业务管理者建立 AI 组织竞争力。",
    "bridge/index.html":
        "AI 转型人才策展桥梁：企业缺 AI 人才、人才找 AI 转型企业，提交意图由主理人人工撮合。AIHR数智引擎用品牌信任而非算法匹配，连接双边真实需求。",
    "tools/index.html":
        "AIHR数智引擎在线测评工具矩阵：MBTI、DISC、大五人格、DRI 成熟度与 AI 风险自评，用经过验证的权威量表帮你读懂人才与组织的真实状态。",
    "products/dri-toolkit.html":
        "DRI 落地指南工具包：从概念到执行的完整方法论与可直接套用的模板，帮你的团队厘清责任归属、消灭模糊决策，让组织真正转起来。",
    "resources/index.html":
        "AIHR数智引擎资源库：模板、研究报告与工具指南一站式获取，服务 HR 与业务管理者把 AI 组织变革从理念落到可执行的日常动作。",
    "hub/ai-org-transformation.html":
        "AI 组织变革大厂范式拆解：微软、谷歌、Meta、亚马逊、字节、腾讯如何重构 AI 时代组织，27 篇深度文章串成一张全景综述地图。",
    "compare/bigtech-ai-org-transformation-2026.html":
        "六家科技巨头 2025–2026 AI 组织变革路径对比：AI 一号位、核心部门、重组动作一文看清，并提炼对 HR 与组织设计的可执行启示。",
    "glossary/index.html":
        "AI+HR 术语词典：20 个关键概念的定义、对 HR 的意义与风险边界，附权威文章内链，帮你在 AI 组织变革的话语体系里不迷路。",
    "tools/dri-quiz.html":
        "DRI 角色成熟度自测：10 道题快速评估你的团队责任归属是否清晰，定位模糊决策的根源，并给出可直接落地的改进建议。AIHR数智引擎出品。",
    "assets/dq-evaluation.html":
        "DQ 评估打分卡：从数据质量维度衡量岗位被 AI 替代的风险，帮你客观判断哪些工作该交给 AI、哪些必须由人守住。AIHR数智引擎测评工具。",
    "assets/ai-transformation-maturity.html":
        "AI 转型落地成熟度自评表：从战略、组织、人才、数据四个维度给企业的 AI 落地程度打分，输出差距清单与行动优先级。AIHR数智引擎出品。",
}

# 顺序无关匹配 <meta ... name="description" ...>
DESC_TAG_RE = re.compile(r'<meta\b[^>]*\bname\s*=\s*["\']description["\'][^>]*>', re.I)
# 抽取 content（引号配对回溯，兼容内容内含单引号）
CONTENT_RE = re.compile(r'content\s*=\s*(["\'])(.*?)\1', re.I)


def _clean(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", "'").replace("&#39;", "'").replace("&nbsp;", " ")
                .replace("&ensp;", " ").replace("&emsp;", " "))
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace('"', "'")  # meta 用双引号包裹，去掉内部双引号
    return text


def _title_core(c):
    m = re.search(r"<title>([^<]+)</title>", c)
    if not m:
        return ""
    core = m.group(1).split("|")[0].strip()
    if " - " in core:
        core = core.split(" - ")[0].strip()
    return core


def _extract_lead(c):
    """抽取正文首段（完整段落，非半句），截断到 MAX_LEN"""
    region = c
    i = region.find("</header>")
    if i > 0:
        region = region[i:]
    j = region.find("<footer")
    if j > 0:
        region = region[:j]
    for marker in ["related-reading", "article-footer", "note-box"]:
        k = region.find(marker)
        if k > 0:
            region = region[:k]
    paras = re.findall(r"<p[^>]*>(.*?)</p>", region, re.S | re.I)
    for p in paras:
        txt = _clean(p)
        if len(txt) >= 40:
            return txt[:MAX_LEN]
    return ""


def _generate(rel, c):
    if rel in CURATED:
        g = CURATED[rel]
        if len(g) < MIN_LEN:  # 兜底：curated 偏短则补长，避免回归到「太短」
            g = (g + " AIHR数智引擎深度分析 AI 时代组织变革与 HR 转型。")[:MAX_LEN]
        return g
    lead = _extract_lead(c)
    if lead:
        if len(lead) >= MIN_LEN:
            return lead
        # 首段偏短：补干净的品牌后缀，确保达标（lead 已是完整段落，不会破碎）
        padded = lead + "——AIHR数智引擎深度分析 AI 时代组织变革与 HR 转型实战路径。"
        return padded[:MAX_LEN]
    core = _title_core(c)
    # 兜底模板加长，确保即便标题很短也达标
    base = ("AIHR数智引擎——%s。我们专注 AI 时代 HR 转型与大厂组织变革的深度分析，"
            "提供硬核长文、权威测评工具与策展桥梁，帮你建立 AI 组织竞争力。") % core
    return base[:MAX_LEN]


def process(apply=False):
    changed = []
    for root, dirs, files in os.walk(SITE_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for fn in files:
            if not fn.endswith(".html"):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, SITE_ROOT)
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                c = fh.read()
            # 跳过：重定向桩页 / 验证文件 / 404 / sitemap
            if "http-equiv=\"refresh\"" in c:
                continue
            if any(x in rel for x in ["404.html", "sitemap", ".txt"]):
                continue
            base = os.path.basename(rel)
            if any(x in base for x in ["baidu_", "google", "BingSiteAuth", "verify"]):
                continue

            tags = list(DESC_TAG_RE.finditer(c))
            existing = []
            for t in tags:
                cm = CONTENT_RE.search(t.group(0))
                if cm:
                    existing.append(cm.group(1).strip())

            # 决策最终 content
            good_existing = [e for e in existing if len(e) >= MIN_LEN]
            if good_existing:
                final = max(good_existing, key=len)  # 保留原有优质 description
                action = "去重保留" if len(existing) > 1 else "无变动"
            else:
                final = _generate(rel, c)
                action = "生成/替换"

            if not apply:
                changed.append((rel, len(existing), len(final), action,
                                existing[0][:30] if existing else ""))
                continue

            # 单标签且已充足：跳过，避免无谓重写
            if action == "无变动":
                continue

            # 写入：移除所有 description 标签，确保唯一
            c2 = DESC_TAG_RE.sub("", c)
            c2 = re.sub(r"(</title>)", f'\\1\n<meta name="description" content="{final}">',
                        c2, count=1)
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(c2)
            changed.append((rel, len(existing), len(final), action, existing[0][:30] if existing else ""))
    return changed


def main():
    dry = "--dry-run" in sys.argv
    changed = process(apply=not dry)
    dup = [x for x in changed if x[1] > 1]
    print(f"{'【DRY-RUN】' if dry else '【写入】'} 处理 {len(changed)} 个页面"
          f"（其中重复标签 {len(dup)} 个将去重）\n")
    for rel, n_exist, newlen, action, old in sorted(changed):
        flag = "🔁" if n_exist > 1 else ("✏️" if action != "无变动" else "·")
        print(f"  {flag} [{action}] 现有{n_exist}→最终{newlen}字  {rel}")
    if not dry and changed:
        print(f"\n✅ 完成：{len(changed)} 个页面已确保唯一且充足的描述")


if __name__ == "__main__":
    main()
