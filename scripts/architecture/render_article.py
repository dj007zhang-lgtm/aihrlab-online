# content-first 最小生成器（S0 骨架，不发布）
# 输入：content/articles/*.md + templates/article-shell.html + ci/design-contract.json
# 输出：outputs/architecture-preview/*.html（outputs/ 不进发布清单）
import sys, re, json, pathlib, html as H

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "templates/article-shell.html"
CONTRACT = ROOT / "ci/design-contract.json"
OUT = ROOT / "outputs/architecture-preview"
REQUIRED = ["title", "slug", "date", "canonical", "cluster", "description", "lead", "spine", "counterpoint", "sources", "related"]
EXPECTED = {"{{TITLE}}": 4, "{{DESCRIPTION}}": 3, "{{CANONICAL}}": 2, "{{DATE}}": 3,
            "{{LEAD}}": 1, "{{OG_IMAGE}}": 1, "{{JSONLD}}": 1, "{{BODY}}": 1,
            "{{SPINE_BLOCK}}": 1, "{{COUNTERPOINT_BLOCK}}": 1, "{{SOURCES_BLOCK}}": 1,
            "{{RELATED_BLOCK}}": 1, "{{CLUSTER_BLOCK}}": 1}

def parse_fm(text):
    lines = text.splitlines()
    assert lines[0].strip() == "---", "缺少 frontmatter 起始"
    ends = [i for i in range(1, len(lines)) if lines[i].strip() == "---"]
    assert ends, "缺少 frontmatter 结束"
    e = ends[0]
    fm, cur = {}, None
    for ln in lines[1:e]:
        m = re.match(r"^([a-z_]+)\s*:\s*(.*)$", ln)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if v == "":
                fm[k] = []; cur = k
            elif v.startswith("[") and v.endswith("]"):
                fm[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]; cur = None
            else:
                fm[k] = v.strip().strip("'\""); cur = None
        elif ln.strip().startswith("- ") and cur:
            fm[cur].append(ln.strip()[2:].strip().strip("'\""))
    return fm, "\n".join(lines[e+1:])

def inline(s):
    s = H.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s

def md2html(body):
    out, para = [], []
    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>"); para.clear()
    for raw in body.splitlines():
        ln = raw.rstrip()
        if not ln.strip(): flush(); continue
        if ln.startswith("### "): flush(); out.append("<h3>" + inline(ln[4:]) + "</h3>")
        elif ln.startswith("## "): flush(); out.append("<h2>" + inline(ln[3:]) + "</h2>")
        elif ln.startswith("> "): flush(); out.append("<blockquote><p>" + inline(ln[2:]) + "</p></blockquote>")
        elif ln.startswith("- "): flush(); out.append("<li>" + inline(ln[2:]) + "</li>")
        else: para.append(ln.strip())
    flush()
    res, inul = [], False
    for x in out:
        if x.startswith("<li>"):
            if not inul: res.append("<ul>"); inul = True
            res.append(x)
        else:
            if inul: res.append("</ul>"); inul = False
            res.append(x)
    if inul: res.append("</ul>")
    return "\n".join(res)

def build(md_path):
    fm, body = parse_fm(md_path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if not fm.get(k)]
    assert not missing, "frontmatter 缺必填字段: %s" % missing
    assert CONTRACT.exists(), "缺设计契约"
    shell = SHELL.read_text(encoding="utf-8")
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["typography"]["measure"] == "720px", "契约正文列宽漂移"
    jsonld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": fm["title"], "description": fm["lead"],
        "datePublished": fm["date"], "mainEntityOfPage": fm["canonical"],
        "author": {"@type": "Organization", "name": "AIHR数智引擎"},
        "publisher": {"@type": "Organization", "name": "AIHR数智引擎"}
    }
    rep = {
        "{{TITLE}}": fm["title"], "{{DESCRIPTION}}": fm["description"],
        "{{CANONICAL}}": fm["canonical"], "{{DATE}}": fm["date"], "{{LEAD}}": fm["lead"],
        "{{OG_IMAGE}}": "https://www.aihrlab.online/assets/images/banners/%s.webp" % fm["slug"],
        "{{JSONLD}}": json.dumps(jsonld, ensure_ascii=False, indent=2),
        "{{BODY}}": md2html(body),
        "{{SPINE_BLOCK}}": '<div class="insight-box"><strong>本文判断</strong>：' + inline(fm["spine"]) + "</div>",
        "{{COUNTERPOINT_BLOCK}}": '<section class="counterpoint"><h2>对撞项</h2><p>' + inline(fm["counterpoint"]) + "</p></section>",
        "{{SOURCES_BLOCK}}": '<section class="verified-sources"><h2>参考信源</h2><ul>' + "".join("<li>" + inline(x) + "</li>" for x in fm["sources"]) + "</ul></section>",
        "{{RELATED_BLOCK}}": "<!-- RELATED_PLACEHOLDER: Gate10 要求链接文字逐字复制目标 H1，全量迁移时由链接图解析填入 -->",
        "{{CLUSTER_BLOCK}}": '<div class="insight-box">本文收录于 <a href="/hub/%s.html">专题枢纽（由 cluster-map 解析真实 H1）</a></div>' % fm["cluster"],
    }
    for k, v in rep.items():
        assert shell.count(k) == EXPECTED[k], ("模板占位次数漂移", k, shell.count(k), EXPECTED[k])
        shell = shell.replace(k, v)
    assert "{{" not in shell, "存在未替换占位符"
    assert set(EXPECTED) == set(rep), "契约与模板占位集合不一致"
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / (fm["slug"] + ".html")
    dest.write_text(shell, encoding="utf-8")
    return dest, fm

if __name__ == "__main__":
    args = sys.argv[1:] or sorted(str(p) for p in (ROOT / "content/articles").glob("*.md"))
    for a in args:
        dest, fm = build(pathlib.Path(a))
        print("OK  %s -> %s (%d bytes) | spine=%s" % (pathlib.Path(a).name, dest.relative_to(ROOT), len(dest.read_bytes()), fm["spine"][:24]))
