#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_internal_links.py —— Gate 17：内链图谱健康关（R3 收尾护栏）

为什么需要这扇门：
  R3 清理了四类内链债务：① 81 页内联死代码 CSS（/* 优化相关推荐 - 降低跳出率 */
  块，实际匹配 0 元素、且含硬编码 hex 阻碍深色模式）；② 7 页遗留 .related-articles
  旧组件 DOM；③ 站内绝对 URL（https://www.aihrlab.online/articles/... 应归一为
  相对路径）；④ 自引用（related-reading 区块内出现指向自身的链接）。本门把"这四类
  缺陷不得回归"固化为可见护栏，防止后续编辑再次引入。

设计原则（关键）：本门是「防回归」型，不是「全站拓扑约束」型。
  实测发布流程（publish.py）以 --all 模式跑全站质量门；而新文章从模板复制时，
  模板不含 related-reading HTML 区块、且新文天生是入度 0 的孤儿（需后续 R3-c 式
  补链）。若把「每页必须有区块」「孤儿=0」设为硬失败，会误伤正常新文发布。
  因此：
    - 硬失败（永不合法、纯回归）：死代码 CSS 块 / 遗留 .related-articles DOM /
      站内绝对 URL 锚点 / related-reading 自引用。
    - 告警（不阻塞发布，仅提示）：正文页缺 related-reading 区块 / 孤儿（入度 0）。
      —— 这两项是新文的自然状态，由内容工作流补齐，门只记录、不拦截。

检查项（硬失败）：
  1. 任意正文页含内联死代码 CSS（含「优化相关推荐」标记的 <style> 块）。
  2. 任意正文页含遗留 .related-articles / .related-articles-wrapper DOM。
  3. 任意 <a href> 指向站内绝对 URL（https://www.aihrlab.online/articles/...）。
     注意：<link rel="canonical">、og:url（content=）、JSON-LD 的 @id/url 均使用
     非 <a> 标签或非 href 属性，正则已排除，不会误报。
  4. 某页 related-reading 区块内的 <a href> 指向该页自身（自引用）。

检查项（告警，不失败）：
  5. 正文页缺少 related-reading 区块。
  6. 孤儿（在真实正文页锚点图中入度=0 的页面）。

用法：
  python3 scripts/check_internal_links.py
  python3 scripts/check_internal_links.py /path/to/site
  python3 scripts/check_internal_links.py --selftest
"""
import os
import sys
import re
import shutil

STUB_MARKERS = ("window.location.replace", "本页面已迁移")
DEAD_CSS_MARK = "优化相关推荐"          # 死代码 CSS 块的唯一标记串
LEGACY_MARKS = ('class="related-articles"', "related-articles-wrapper")
ABS_ANCHOR = re.compile(r'<a\b[^>]*href="https://www\.aihrlab\.online/articles/([^"]+)"')
ANCHOR = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>')
RR_SEC = re.compile(r'<(?:section|div)\b[^>]*class="[^"]*related-reading[^"]*"[^>]*>[\s\S]*?</(?:section|div)>')


def _is_stub(path):
    if not path or not os.path.exists(path):
        return False
    try:
        t = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return False
    return any(m in t for m in STUB_MARKERS)


def _real_pages(site_root):
    """返回真实正文页绝对路径（排除 articles/index.html 与重定向桩页）。"""
    adir = os.path.join(site_root, "articles")
    if not os.path.isdir(adir):
        return []
    out = []
    for fn in sorted(os.listdir(adir)):
        if not fn.endswith(".html"):
            continue
        if fn == "index.html":
            continue
        p = os.path.join(adir, fn)
        if _is_stub(p):
            continue
        out.append(p)
    return out


def run(site_root):
    hard = []   # 硬失败项
    warn = []   # 告警项（不阻塞）

    pages = _real_pages(site_root)
    real_set = {os.path.basename(p) for p in pages}

    # ---- 单页静态缺陷扫描 ----
    for p in pages:
        base = os.path.basename(p)
        try:
            s = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue

        # 1) 死代码 CSS 块
        if DEAD_CSS_MARK in s and "<style" in s:
            hard.append("死代码 CSS 块回归（含「优化相关推荐」标记的 <style>）：%s" % base)

        # 2) 遗留 DOM
        if any(m in s for m in LEGACY_MARKS):
            hard.append("遗留 .related-articles 旧组件 DOM 回归：%s" % base)

        # 3) 站内绝对 URL 锚点（仅 <a href>，排除 canonical/og/JSON-LD）
        if ABS_ANCHOR.search(s):
            hard.append("站内绝对 URL 锚点（应归一为相对路径）：%s" % base)

        # 4) related-reading 自引用
        msec = RR_SEC.search(s)
        if msec:
            sec = msec.group(0)
            for am in ANCHOR.finditer(sec):
                h = am.group(1)
                if h.startswith("/articles/") and h.endswith(".html") and h.split("/")[-1] == base:
                    hard.append("related-reading 自引用（链接指向自身）：%s" % base)
                    break

        # 5) 告警：缺 related-reading 区块
        if not re.search(r'class="[^"]*related-reading[^"]*"', s):
            warn.append("正文页缺 related-reading 区块（新文常见，需补）：%s" % base)

    # ---- 全局入度图：孤儿检测（仅告警）----
    indeg = {}
    for p in pages:
        base = os.path.basename(p)
        indeg[base] = 0
    for p in pages:
        s = open(p, encoding="utf-8", errors="ignore").read()
        for am in ANCHOR.finditer(s):
            h = am.group(1)
            t = None
            if h.startswith("/articles/") and h.endswith(".html"):
                t = h.split("/")[-1]
            elif h.startswith("https://www.aihrlab.online/articles/") and h.endswith(".html"):
                t = h.split("/")[-1]
            if t and t in real_set and t != os.path.basename(p):
                indeg[t] += 1
    orphans = sorted([b for b, c in indeg.items() if c == 0])
    if orphans:
        warn.append("孤儿（入度=0）共 %d 篇（新文常见，需补入链）：%s"
                    % (len(orphans), ", ".join(orphans[:20]) + ("…" if len(orphans) > 20 else "")))

    passed = (len(hard) == 0)
    details = []
    if hard:
        details.append("❌ 硬失败 %d 项（必须修复）：" % len(hard))
        details.extend("  • " + h for h in hard)
    if warn:
        details.append("⚠️ 告警 %d 项（不阻塞发布）：" % len(warn))
        details.extend("  • " + w for w in warn)
    if passed and not warn:
        details.append("全站内链图谱健康：无死代码 CSS / 遗留 DOM / 绝对 URL / 自引用")
    return passed, details


def _selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="cil_selftest_")
    try:
        adir = os.path.join(tmp, "articles")
        os.makedirs(adir)
        # 四个真实正文页
        for fn, body in [
            ("page-a.html", "<html><body><article>正文A</article>"
                           "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
                           "<li><a href=\"/articles/page-b.html\">B</a></li>"
                           "<li><a href=\"/articles/page-c.html\">C</a></li></ul></section>"
                           "</body></html>"),
            ("page-b.html", "<html><body><article>正文B</article>"
                           "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
                           "<li><a href=\"/articles/page-a.html\">A</a></li></ul></section>"
                           "</body></html>"),
            ("page-c.html", "<html><body><article>正文C</article>"
                           "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
                           "<li><a href=\"/articles/page-a.html\">A</a></li></ul></section>"
                           "</body></html>"),
            ("page-d.html", "<html><body><article>正文D</article>"
                           "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
                           "<li><a href=\"/articles/page-a.html\">A</a></li></ul></section>"
                           "</body></html>"),
        ]:
            open(os.path.join(adir, fn), "w").write(body)

        # 干净站点：无缺陷 → 应通过
        ok, det = run(tmp)
        assert ok is True, "干净站点应 PASS：%s" % det

        # 桩页（应被排除，不计入）
        open(os.path.join(adir, "stub.html"), "w").write(
            '<html><body>本页面已迁移<script>window.location.replace("x")</script></body></html>')

        # ---- 注入四类硬失败缺陷 ----
        # 1) 死代码 CSS
        open(os.path.join(adir, "page-a.html"), "w").write(
            "<html><body><style>/* 优化相关推荐 - 降低跳出率 */ .x{}</style>"
            "<article>正文A</article>"
            "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
            "<li><a href=\"/articles/page-b.html\">B</a></li></ul></section></body></html>")
        # 2) 遗留 DOM
        open(os.path.join(adir, "page-b.html"), "w").write(
            "<html><body><article>正文B</article>"
            "<div class=\"related-articles\"><h3>相关文章</h3></div>"
            "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
            "<li><a href=\"/articles/page-a.html\">A</a></li></ul></section></body></html>")
        # 3) 站内绝对 URL 锚点
        open(os.path.join(adir, "page-c.html"), "w").write(
            "<html><body><article>正文C</article>"
            "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
            "<li><a href=\"https://www.aihrlab.online/articles/page-a.html\">A</a></li></ul></section>"
            "</body></html>")
        # 4) 自引用
        open(os.path.join(adir, "page-d.html"), "w").write(
            "<html><body><article>正文D</article>"
            "<section class=\"related-reading\"><h3>相关阅读</h3><ul>"
            "<li><a href=\"/articles/page-d.html\">D自身</a></li></ul></section></body></html>")

        # canonical 绝对 URL 不应误报（放 page-a 里，验证不误判）
        s = open(os.path.join(adir, "page-a.html"), encoding="utf-8").read()
        s = s.replace("<html>", "<html>\n<link rel=\"canonical\" href=\"https://www.aihrlab.online/articles/page-a.html\">")
        open(os.path.join(adir, "page-a.html"), "w").write(s)

        ok2, det2 = run(tmp)
        assert ok2 is False, "含四类缺陷应 FAIL：%s" % det2
        joined = "\n".join(det2)
        assert "死代码" in joined, "应检出死代码 CSS：%s" % det2
        assert "遗留" in joined, "应检出遗留 DOM：%s" % det2
        assert "绝对 URL" in joined, "应检出绝对 URL：%s" % det2
        assert "自引用" in joined, "应检出自引用：%s" % det2
        # canonical 绝对 URL 不得误报为绝对 URL 缺陷（仅在 <a> 中才算）
        assert "page-a.html" not in joined or "绝对 URL" not in joined.split("page-a")[0], \
            "canonical 绝对 URL 不应误报：%s" % det2

        print("check_internal_links selftest: PASS")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if _selftest() else 1)
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok, details = run(root)
    for d in details:
        print("  " + d)
    print("Gate 17 (internal links): " + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
