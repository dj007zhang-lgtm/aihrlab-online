#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D 系列：深色主题渲染审计（F4 缺口补齐）

为什么必须有这个：
  视觉门禁 B1–B14 全是「读 CSS 源码」的静态断言，读不出「计算值」。
  .site-header{background:rgba(255,255,255,0.95)} 在源码层面只是一个硬编码色，
  但在深色主题下它是「浅色文字压白底、导航不可读」的真实可用性缺陷。
  只有真实渲染 + 取 computed style 才能看见。

三条断言（全部可计算，跑得出数字，不是主观判断）：
  D1 浅底残留：深色主题下元素有效背景亮度 > 0.5（明显浅色），与深色主题割裂
  D2 文字对比度：文本与其有效背景对比度 < 4.5（WCAG AA 正文下限）
  D3 边框不可见：border 颜色与自身背景对比度 < 1.2（深色下黑描边消失）

关键实现：
  - 必须走 HTTP（file:// 下 /assets/ 根相对路径解析到文件系统根，全是假缺陷）
  - 有效背景 = 向上遍历祖先取第一个非透明背景（透明背景不能直接跟文字比）
  - 抽样而非全量（430 页 × 2 主题渲染耗时过长），但覆盖全部模板类型

用法:
    python3 scripts/audit_dark_theme.py              # 抽样审计
    python3 scripts/audit_dark_theme.py --pages 20   # 指定抽样数
    python3 scripts/audit_dark_theme.py --self-test  # F5 注入验证
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8765
BASE = "http://127.0.0.1:%d" % PORT

# 扫描范围必须**动态发现**，不能手写栏目清单。
# 教训（E-028 第四次重演）：原先手写的 TEMPLATE_GLOBS 只写了 resources/index.html、
# tools/index.html、glossary/index.html —— 只含索引页不含子页，另漏了 assets/*.html
# 与根级其他页。结果是「120 页抽样」实际只在部分目录里抽，资源页改了也扫不到，
# 「0 缺陷」是没扫到不是干净。改为：遍历站点根取全部 .html，按顶层目录分组保底。
EXCLUDE_DIRS = (".git", "node_modules", "_wip", "_wip_unpublished", "outputs",
                "_aihr_repo_archive")


def discover_pages():
    """按顶层目录分组返回 {目录: [相对路径]}，新增目录自动纳入。"""
    groups = {}
    for dp, dn, fn in os.walk(ROOT):
        rel_dir = os.path.relpath(dp, ROOT)
        if rel_dir == ".":
            rel_dir = "(根)"
        if any(x in rel_dir.split(os.sep) for x in EXCLUDE_DIRS):
            continue
        pages = [os.path.join(rel_dir, f) if rel_dir != "(根)" else f
                 for f in fn if f.endswith(".html")]
        if pages:
            groups.setdefault(rel_dir, []).extend(sorted(pages))
    return groups

JS_PROBE = r"""
() => {
  const lum = (r,g,b) => {
    const f = c => { c/=255; return c<=0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055,2.4); };
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b);
  };
  const parse = s => {
    const m = s.match(/rgba?\(([^)]+)\)/); if(!m) return null;
    const p = m[1].split(',').map(x=>parseFloat(x));
    return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};
  };
  const contrast = (a,b) => {
    const L1 = Math.max(lum(a.r,a.g,a.b), lum(b.r,b.g,b.b));
    const L2 = Math.min(lum(a.r,a.g,a.b), lum(b.r,b.g,b.b));
    return (L1+0.05)/(L2+0.05);
  };
  // 有效背景：向上找第一个不透明（a>0.5）的背景
  const effBg = el => {
    let n = el;
    while (n && n !== document.documentElement.parentNode) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c;
      n = n.parentElement;
    }
    return {r:11,g:12,b:14,a:1}; // 兜底：深色主题 body 底色
  };
  const out = {light_bg:[], contrast:[], invisible_border:[], subtle_border:[]};
  const nodes = document.querySelectorAll('body *');
  for (const el of nodes) {
    const cs = getComputedStyle(el);
    if (cs.display==='none' || cs.visibility==='hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;      // 忽略零尺寸
    const bg = parse(cs.backgroundColor);
    const bgEff = effBg(el);

    // D1 只在深色主题下成立：浅色主题里页面本就该是浅底，
    // 拿同一判据跑浅色会把几百处正常浅底全报成缺陷（实测 435 处误报）。
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark && bg && bg.a > 0.5) {
      const L = lum(bg.r,bg.g,bg.b);
      if (L > 0.5 && r.width*r.height > 20000) {
        out.light_bg.push({
          sel: el.tagName.toLowerCase()+(el.className && typeof el.className==='string'
               ? '.'+el.className.trim().split(/\s+/).slice(0,2).join('.') : ''),
          bg: cs.backgroundColor, area: Math.round(r.width*r.height)
        });
      }
    }
    // D2 文本对比度：只看自己直接持有文本的叶子节点
    const hasText = Array.from(el.childNodes)
      .some(n => n.nodeType===3 && n.textContent.trim().length > 1);
    if (hasText) {
      const fg = parse(cs.color);
      if (fg && fg.a > 0.5) {
        const c = contrast(fg, bgEff);
        const big = parseFloat(cs.fontSize) >= 24;   // 大字号门槛 3:1
        if (c < (big ? 3.0 : 4.5)) {
          out.contrast.push({
            sel: el.tagName.toLowerCase()+(el.className && typeof el.className==='string'
                 ? '.'+el.className.trim().split(/\s+/).slice(0,2).join('.') : ''),
            ratio: Math.round(c*100)/100, color: cs.color,
            bg: 'rgb('+[bgEff.r,bgEff.g,bgEff.b].join(',')+')',
            fs: cs.fontSize,
            text: el.textContent.trim().slice(0,28)
          });
        }
      }
    }
    // D3 边框消失。**仅在深色主题下判为缺陷**：本断言的语义是「深色下边框消失了」。
    // 浅色主题里 #e5e7eb 这类浅灰描边压白底得 1.08，是刻意设计的弱分隔线，不是缺陷
    // （实测浅色 119 处里绝大多数属此类）。但也不隐藏——浅色下改记 subtle_border，
    // 照常打印为 INFO，只是不计入缺陷数。
    const bw = parseFloat(cs.borderTopWidth)||0;
    if (bw > 0) {
      const bc = parse(cs.borderTopColor);
      if (bc && bc.a > 0.5) {
        const c = contrast(bc, bgEff);
        if (c < 1.2) {
          const rec = {
            sel: el.tagName.toLowerCase()+(el.className && typeof el.className==='string'
                 ? '.'+el.className.trim().split(/\s+/).slice(0,2).join('.') : ''),
            ratio: Math.round(c*100)/100, bc: cs.borderTopColor, w: bw
          };
          if (isDark) out.invisible_border.push(rec); else out.subtle_border.push(rec);
        }
      }
    }
  }
  return out;
}
"""


def start_server():
    """起本地 HTTP（必须在站点根，否则 /assets/ 根相对路径全 404 = 假缺陷）"""
    for _ in range(40):
        try:
            import urllib.request
            urllib.request.urlopen(BASE + "/index.html", timeout=1)
            return None
        except Exception:
            time.sleep(0.25)
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


SHELL_RE = re.compile(
    r'<meta[^>]+http-equiv\s*=\s*["\']?refresh["\']?[^>]*>', re.I)


def is_redirect_shell(path):
    """
    跳转壳：noindex + meta refresh + canonical，正文只有一句「已迁移」。
    （项目里这类页用于保留旧 URL 的外链，绝不下线）

    为什么要过滤：Playwright 会跟随 meta refresh，测到的其实是目标页，
    但报告会把缺陷记在壳的 URL 下——定位时会去找一个根本没有该元素的文件。
    实测踩到过：daily-tech-ai-2026-08.html（587 字节，0 个 table）
    却被报出 table/td 缺陷，真实归属是它跳转到的 hub 页。
    """
    try:
        s = open(path, encoding="utf-8").read(4000)
    except Exception:
        return False
    return bool(SHELL_RE.search(s)) and "noindex" in s.lower()


def pick_pages(n):
    import random
    groups = discover_pages()
    # 过滤跳转壳：它们不是内容页，缺陷归目标页，计入会重复且误导定位
    groups = {d: [p for p in ps if not is_redirect_shell(os.path.join(ROOT, p))
                  and "/_" not in p and not p.startswith("_")]
              for d, ps in groups.items()}
    groups = {d: ps for d, ps in groups.items() if ps}
    random.seed(42)
    # 每个顶层目录至少取 1 个（保证模板覆盖），其余随机补齐
    must = []
    for d in sorted(groups):
        must.append(groups[d][0])
    rest = [p for ps in groups.values() for p in ps if p not in must]
    random.shuffle(rest)
    out = must + rest[:max(0, n - len(must))]
    return sorted(set(out))


def page_count():
    """可被审计的页面总数（跳转壳已排除）"""
    return len(pick_pages(10 ** 6))


def audit(pages, theme):
    from playwright.sync_api import sync_playwright
    agg = {"light_bg": [], "contrast": [], "invisible_border": [], "subtle_border": []}
    per_page = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        for rel in pages:
            url = BASE + "/" + rel.replace(os.sep, "/")
            try:
                pg.goto(url, wait_until="load", timeout=25000)
            except Exception as e:
                per_page[rel] = {"error": str(e)[:80]}
                continue
            # 页面可能被 meta refresh / JS 跳转带走：用落地 URL 作为真实归属，
            # 否则缺陷会记在一个根本不含该元素的文件名下
            landed = pg.url
            if landed.startswith(BASE):
                real = landed[len(BASE):].lstrip("/")
                if real and real != rel:
                    per_page[rel] = {"redirected_to": real}
                    rel = real
            if theme == "dark":
                pg.evaluate("document.documentElement.setAttribute('data-theme','dark')")
            pg.wait_for_timeout(350)
            res = pg.evaluate(JS_PROBE)
            per_page[rel] = {k: len(v) for k, v in res.items()}
            for k in agg:
                for item in res[k]:
                    item["page"] = rel
                    agg[k].append(item)
        b.close()
    return agg, per_page


def report(agg, per_page, theme, n):
    scope = "全站 %d 页" % n if n >= page_count() else "抽样 %d 页（覆盖率 %.0f%%）" % (
        n, 100.0 * n / max(1, page_count()))
    print("=" * 78)
    print("深色主题渲染审计（F4）  theme=%s  %s" % (theme, scope))
    print("=" * 78)
    tot = 0
    for code, name, lim in (("light_bg", "D1 浅底残留（背景亮度>0.5，与深色割裂）", 0),
                            ("contrast", "D2 文字对比度 <4.5（WCAG AA）", 0),
                            ("invisible_border", "D3 边框与背景对比度<1.2（深色下消失）", 0)):
        items = agg[code]
        tot += len(items)
        if not items:
            print("PASS  %s  无缺陷" % (code + " " + name))
            continue
        print("FAIL  %s  %d 处" % (code + " " + name, len(items)))
        cnt = Counter((i["page"], i["sel"]) for i in items)
        for (page, sel), c in cnt.most_common(12):
            ex = next(i for i in items if i["page"] == page and i["sel"] == sel)
            extra = ""
            if code == "contrast":
                extra = " ratio=%.2f fg=%s bg=%s fs=%s「%s」" % (
                    ex["ratio"], ex["color"], ex["bg"], ex["fs"], ex.get("text", ""))
            elif code == "light_bg":
                extra = " bg=%s area=%d" % (ex["bg"], ex["area"])
            else:
                extra = " ratio=%.2f bc=%s w=%s" % (ex["ratio"], ex["bc"], ex["w"])
            print("      x%-3d %-34s %s%s" % (c, sel[:34], page[:40], extra))
    # 浅色主题下的弱描边：照常打印但不计入缺陷（刻意设计的分隔线，不是缺陷）
    sb = agg.get("subtle_border", [])
    if sb:
        cnt = Counter((i["page"], i["sel"]) for i in sb)
        print("INFO  subtle_border 弱描边（浅色下刻意的分隔线，不计缺陷）  %d 处" % len(sb))
        for (page, sel), c in cnt.most_common(5):
            ex = next(i for i in sb if i["page"] == page and i["sel"] == sel)
            print("      x%-3d %-34s %s ratio=%.2f bc=%s" % (
                c, sel[:34], page[:40], ex["ratio"], ex["bc"]))
    print("-" * 78)
    print("缺陷合计: %d" % tot)
    return tot


def self_test():
    """
    F5：注入已知缺陷，验证门禁真的能抓到（抓不到 = 装饰性门禁，等同失效）。

    按「注入的特征值」验证，不按「缺陷总数」验证。
    为什么不能数总数：基线里可能本就存在同类缺陷（例如 .site-header 浅底），
    再注入一个同类缺陷总数不变，会假报「未命中」——那是自检本身的假信号。
    """
    from playwright.sync_api import sync_playwright
    # (名称, 注入 JS, 归属检测项)
    # 注入物一律打 __probe 标记，按标记验证——不按总数、不按可能撞车的颜色值。
    # 选色必须真的越界：D1 要 lum>0.5 的亮色（红/蓝都不够亮，只有白/黄这类够）；
    # D3 要「与所在背景同色」的边框（黑框压白底对比度 21:1，本就可见，不算缺陷）。
    cases = [
        ("D1 浅底残留",
         "var d=document.createElement('div');d.className='__probe';"
         "d.style.cssText='width:300px;height:300px;background:#ffffff';"
         "d.textContent='probe';document.body.appendChild(d)",
         "light_bg"),
        ("D2 低对比文字",
         "var d=document.createElement('p');d.className='__probe';"
         "d.style.cssText='color:#777777';d.textContent='probe text here';"
         "document.body.appendChild(d)",
         "contrast"),
        ("D3 边框消失",
         "var d=document.createElement('div');d.className='__probe';"
         "d.style.cssText='width:300px;height:120px;border-top:3px solid #0b0c0e';"
         "document.body.appendChild(d)",
         "invisible_border"),
    ]
    pages = pick_pages(1)
    ok = True
    proc = start_server()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1280, "height": 900})
            url = BASE + "/" + pages[0]
            for name, js, code in cases:
                pg.goto(url, wait_until="load")
                pg.evaluate("document.documentElement.setAttribute('data-theme','dark')")
                pg.wait_for_timeout(300)
                pg.evaluate(js)
                pg.wait_for_timeout(250)
                res = pg.evaluate(JS_PROBE)
                found = any("__probe" in i.get("sel", "") for i in res[code])
                hit = [i for i in res[code] if "__probe" in i.get("sel", "")]
                print("  注入 %-12s -> %-16s 探针捕获 %s"
                      % (name, code, ("命中 OK %s" % hit[0]) if found else "未命中 FAIL"))
                if not found:
                    ok = False
                pg.reload(wait_until="load")
            b.close()
    finally:
        if proc:
            proc.terminate()
    print("自检结论: %s" % ("全部命中，门禁有效" if ok else "存在未命中，门禁失效"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=12)
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--urls", default="",
                    help="逗号分隔的相对路径，定向审计指定页。"
                         "抽样会漏掉只有个位页面用到的组件（实测 30 页抽样的「0 缺陷」"
                         "在 120 页下暴露 17 处），改了具体组件必须用此项定向验证。")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    if a.urls:
        pages = []
        for u in a.urls.split(","):
            u = u.strip().lstrip("/")
            if not u:
                continue
            if not os.path.exists(os.path.join(ROOT, u)):
                print("页面不存在: %s" % u)
                return 2
            if is_redirect_shell(os.path.join(ROOT, u)):
                print("跳过跳转壳（缺陷归属落地页）: %s" % u)
                continue
            pages.append(u)
        if not pages:
            print("无可审计页面")
            return 2
    else:
        pages = pick_pages(a.pages)
    proc = start_server()
    try:
        agg, per_page = audit(pages, a.theme)
    finally:
        if proc:
            proc.terminate()

    if a.json:
        print(json.dumps(agg, ensure_ascii=False, indent=1))
        return 0
    n = report(agg, per_page, a.theme, len(pages))
    print("\n覆盖页面: %s" % ", ".join(pages[:6]) + ("..." if len(pages) > 6 else ""))
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
