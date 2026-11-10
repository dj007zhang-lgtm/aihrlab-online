#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设计契约等价核验（S1，2026-11-10）——从「装饰性骨架」改为发布链上的真实消费者。

旧版（S0）依赖 outputs/architecture-preview/*.html 与 articles/<slug>.html 同时存在，
这两个文件从没进过生产链，直接运行必然 assert 失败，也没有任何代码调用它 = 装饰品。
现改为只读现网真相源：

  1. ci/design-contract.json 的每个数值，必须能在 assets/css/style.css 的权威段找到对应声明；
  2. 契约禁令（字体 / 断点 / 重复定义棘轮）由脚本逐条实查；
  3. B9 真实重复定义组数必须与 ci/visual-baseline.json 的基线对得上（只降不升）；
  4. style.css → style.min.css 必须经 build_css.py 同步；
  5. content/articles/*.md 的 frontmatter 必须含判断密度结构字段（spine / counterpoint / sources）。

任一不符 exit 2。--self-test 注入 6 类已知缺陷，逐条验证对应检查项会 FAIL。

被 scripts/publish.py 的 STEP 2.9 调用，是契约与核验器唯一的生产消费者。
"""
import sys, os, re, json, pathlib, tempfile, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_visual_quality as A  # noqa: E402

CONTRACT = ROOT / "ci/design-contract.json"
CSS = ROOT / "assets/css/style.css"
MIN_CSS = ROOT / "assets/css/style.min.css"
BASELINE = ROOT / "ci/visual-baseline.json"
MD_DIR = ROOT / "content/articles"
REQUIRED = ["title", "slug", "date", "canonical", "cluster", "description",
            "lead", "spine", "counterpoint", "sources", "related"]

BODY_SEL = ".article-body,.article-content-wrapper"
PARA_SEL = ".article-body p,.article-content p,.article-content-wrapper p"
HEAD_SEL = "h1,h2,h3,h4,h5,h6"


def rule_body(css, selector):
    """按精确选择器串取规则体；找不到返回 None（不猜、不模糊匹配）。"""
    i = css.find(selector + "{")
    if i < 0:
        return None
    j = i + len(selector)
    k = css.find("}", j)
    return None if k < 0 else css[j + 1:k]


def media_breakpoints(css):
    """只取宽度断点，排除 prefers-reduced-motion / print 等非宽度媒体查询。"""
    out = set()
    for head in re.findall(r"@media[^{]+", css):
        out.update(int(x) for x in re.findall(r"max-width\s*:\s*(\d+)px", head))
    return out


def html_files():
    files = []
    for dp, dn, fn in os.walk(ROOT):
        if any(x in dp for x in (".git", "node_modules", "_wip", "outputs",
                                 "_aihr_repo_archive", "_wip_unpublished")):
            continue
        files += [os.path.join(dp, f) for f in fn if f.endswith(".html")]
    return files


def b9_metric(css_path):
    """按页面实际加载组合计算的重复定义绝对组数（与 F4 的 B9 同一口径）。"""
    css_files = [os.path.join(A.ROOT, r) for r in A.CSS_SOURCES]
    css_files = [p for p in css_files if os.path.normpath(p) != os.path.normpath(str(CSS))]
    css_files.append(str(css_path))
    tokens = A.read_root_tokens(css_files)
    return A.check_conflicts_per_page(css_files, html_files(), tokens)["metric"]


def fm_keys(path):
    """抽取 frontmatter 顶层键名（不做 YAML 解析，只认冒号起始行）。"""
    s = pathlib.Path(path).read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n([\s\S]*?)\n---", s)
    if not m:
        return set()
    return set(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_-]*)\s*:", m.group(1)))


def run_checks(contract_path, css_path, baseline_path, md_dir, run_build=True):
    c = json.loads(pathlib.Path(contract_path).read_text(encoding="utf-8"))
    css = pathlib.Path(css_path).read_text(encoding="utf-8")
    base = json.loads(pathlib.Path(baseline_path).read_text(encoding="utf-8"))
    t = c.get("typography", {})
    lay = c.get("layout", {})
    rows = []

    def add(name, ok, detail=""):
        rows.append((name, bool(ok), detail))

    add("P1 契约版本", c.get("version") == "1.0.0", "version=%r" % c.get("version"))

    body = rule_body(css, BODY_SEL)
    add("P2 正文字号", bool(body) and ("font-size:%s" % t.get("body_font_size")) in body,
        "期望 %s，权威段=%r" % (t.get("body_font_size"), (body or "")[:90]))
    add("P3 正文行高", bool(body) and ("line-height:%s" % t.get("body_line_height")) in body,
        "期望 %s" % t.get("body_line_height"))
    add("P4 正文行宽", bool(body) and ("max-width:%s" % t.get("measure")) in body,
        "期望 %s" % t.get("measure"))

    para = rule_body(css, PARA_SEL)
    add("P5 正文左对齐", bool(para) and ("text-align:%s" % t.get("align")) in para
        and "text-align:justify" not in para, "期望 left，禁 justify")

    head = rule_body(css, HEAD_SEL)
    add("P6 标题字距契约", bool(head) and "letter-spacing:0 !important" in head,
        "中文标题字距必须 0 且不可被页内 style 覆写")
    add("P7 标题字体 token", "--font-heading-cjk:" in css
        and bool(head) and "font-family:var(--font-heading-cjk)" in head,
        "中文衬线必须走 token，不落页内")

    steps = len(re.findall(r"--fs-\d+\s*:", css))
    add("P8 type scale 档数", steps == t.get("type_scale", {}).get("steps"),
        "契约 %s / 实测 %d" % (t.get("type_scale", {}).get("steps"), steps))
    html = rule_body(css, "html")
    anchor = t.get("type_scale", {}).get("anchor_px")
    add("P9 根字号锚点", bool(html) and ("font-size:%spx" % anchor) in html,
        "期望 %spx" % anchor)

    bps = media_breakpoints(css)
    declared = set(lay.get("breakpoints", []))
    add("P10 断点集合一致", bps == declared,
        "契约 %s / 实测 %s" % (sorted(declared), sorted(bps)))
    add("P10b 断点数不增", len(bps) <= lay.get("max_breakpoints", 0),
        "实测 %d / 上限 %s" % (len(bps), lay.get("max_breakpoints")))

    font_issues = []
    for p in (css_path, MIN_CSS):
        s = pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
        if re.search(r"@font-face|fonts\.googleapis\.com|\.woff2?\b", s):
            font_issues.append(os.path.basename(str(p)))
    add("P11 字体红线", not font_issues, "命中 %s" % font_issues)

    metric = b9_metric(css_path)
    b9base = base.get("B9")
    add("P12 B9 棘轮未漂移", isinstance(b9base, int)
        and A.baseline_verdict(metric, b9base) == "PASS",
        "实测 %d / 基线 %s" % (metric, b9base))

    if run_build:
        r = subprocess.run([sys.executable, "scripts/build_css.py", "--check"],
                           cwd=str(ROOT), capture_output=True, text=True)
        add("P13 构建同步", r.returncode == 0, (r.stdout + r.stderr).strip()[:120])
    else:
        add("P13 构建同步", True, "self-test 跳过")

    mds = sorted(pathlib.Path(md_dir).glob("*.md")) if pathlib.Path(md_dir).exists() else []
    req = set(REQUIRED)
    miss = ["%s 缺 %s" % (m.name, ",".join(sorted(req - fm_keys(m))))
            for m in mds if req - fm_keys(m)]
    add("P14 MD 判断密度结构", not miss, "；".join(miss[:4]) or "%d 篇 MD 全字段齐备" % len(mds))

    forb = c.get("forbidden", [])
    add("P15 契约不写死数量", any("visual-baseline.json" in x for x in forb)
        and not any("个重复" in x for x in forb),
        "重复定义数值只能引用基线账本")
    return rows


def self_test():
    """注入 6 类已知缺陷，逐条验证对应检查项会 FAIL（F5：自动化自身有效性）。"""
    print("== 自检：注入已知缺陷，验证契约核验器会 FAIL ==")
    tmp = pathlib.Path(tempfile.mkdtemp())
    pristine_css = CSS.read_text(encoding="utf-8")
    pristine_contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def prepare():
        cp = tmp / "contract.json"
        sp = tmp / "style.css"
        cp.write_text(json.dumps(pristine_contract, ensure_ascii=False, indent=1), encoding="utf-8")
        sp.write_text(pristine_css, encoding="utf-8")
        return cp, sp

    def check_fails(name, mutate, target):
        cp, sp = prepare()
        mutate(cp, sp)
        rows = run_checks(cp, sp, BASELINE, MD_DIR, run_build=False)
        hit = [r for r in rows if r[0].startswith(target) and not r[1]]
        print("  %-22s %-5s → %s" % (name, target, "抓到" if hit else "漏掉"))
        return bool(hit)

    def m_font_size(cp, sp):
        c = json.loads(cp.read_text(encoding="utf-8"))
        c["typography"]["body_font_size"] = "13px"
        cp.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")

    def m_letter(cp, sp):
        sp.write_text(pristine_css.replace("letter-spacing:0 !important",
                                          "letter-spacing:-0.02em", 1), encoding="utf-8")

    def m_duplicate(cp, sp):
        sp.write_text(pristine_css + "\n.zz-probe{color:red}\n.zz-probe{color:blue}\n",
                      encoding="utf-8")

    def m_font(cp, sp):
        sp.write_text(pristine_css + "\n@font-face{font-family:X;src:url(x.woff2)}\n",
                      encoding="utf-8")

    def m_breakpoint(cp, sp):
        c = json.loads(cp.read_text(encoding="utf-8"))
        c["layout"]["breakpoints"] = [520, 768, 1024]
        cp.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")

    def m_md():
        cp, sp = prepare()
        d = tmp / "md_bad"
        d.mkdir(exist_ok=True)
        (d / "x.md").write_text("---\ntitle: X\n---\n\n正文\n", encoding="utf-8")
        rows = run_checks(cp, sp, BASELINE, d, run_build=False)
        hit = [r for r in rows if r[0].startswith("P14") and not r[1]]
        print("  %-22s %-5s → %s" % ("MD 缺 spine/counterpoint", "P14", "抓到" if hit else "漏掉"))
        return bool(hit)

    cases = [
        ("正文字号漂移", m_font_size, "P2"),
        ("标题字距契约被撤销", m_letter, "P6"),
        ("新增一组重复定义", m_duplicate, "P12"),
        ("外链字体红线", m_font, "P11"),
        ("断点集合漂移", m_breakpoint, "P10"),
    ]
    ok = all(check_fails(*x) for x in cases)
    ok = m_md() and ok
    shutil.rmtree(tmp, ignore_errors=True)
    print("自检结论：", "6/6 全部命中" if ok else "存在漏检（核验器不可用）")
    return 0 if ok else 2


def main():
    if "--self-test" in sys.argv:
        return self_test()
    rows = run_checks(CONTRACT, CSS, BASELINE, MD_DIR)
    print("设计契约等价核验（S1 · 现网真相源）")
    print("=" * 72)
    for name, ok, detail in rows:
        print(("PASS " if ok else "FAIL ") + name + (("  " + detail[:130]) if detail and not ok else ""))
    bad = [r for r in rows if not r[1]]
    print("=" * 72)
    print("核验：%d 项，%d 项异常" % (len(rows), len(bad)))
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
