# -*- coding: utf-8 -*-
"""
title_standards.py — 标题长度 SEO/GEO 健康区间（单一真相源 / Single Source of Truth）
================================================================================

⚠️ 历史教训（2026-08-10）：
   本站曾长期把「标题 ≤ 28 字」作为硬 FAIL 阈值，藏在与 SEO 无关的 gate_taste
   （品味关）与 check_title_consistency 等多处，且以「魔法数字 28」硬编码进 7 个脚本、
   无任何出处注释。该阈值是 AI 自定的「品味偏好」，与 SEO/GEO 事实相悖：
     - Google / Bing SERP 标题可显示约 60 字符；
     - Bing WMT 反馈本站 20 个页面「标题过短」、37 个「描述过短」。
   结果：门是倒置的——通过的恰是 SEO 有害的（过短），被拦的反而是 SEO 合理的（30–35 字）。
   多次 SEO/GEO 优化轮次都打在「技术/可发现性/可信度」层，从未审计这个分散的假设。

✅ 防复发规则（写进质量门纪律）：
   所有标题长度校验脚本【必须】引用本模块，禁止在各自文件里再硬编码 28 / 40 / 60。
   若需调整区间，只改这里一处，并同步 reports/ 留痕。

健康区间：
   < TITLE_MIN (15)   过短：无搜索意图承诺（soft fail / WARN，不硬阻断）
   TITLE_MIN–TITLE_WARN (15–40)  健康（推荐区间）
   TITLE_WARN–TITLE_MAX (41–60)  偏长：SERP 可能截断（仅 WARN，不阻断）
   > TITLE_MAX (60)   过长：SERP 必被截断（hard fail）
"""
TITLE_MIN = 15   # 过短阈值（无搜索意图承诺）
TITLE_WARN = 40  # 软上限（SERP 可能截断，仅提示）
TITLE_MAX = 60   # 硬上限（SERP 必截断）


def classify(n):
    """返回标题长度分类：'short' | 'ok' | 'warn' | 'long'。"""
    if n < TITLE_MIN:
        return 'short'
    if n > TITLE_MAX:
        return 'long'
    if n > TITLE_WARN:
        return 'warn'
    return 'ok'
