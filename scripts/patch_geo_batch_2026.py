#!/usr/bin/env python3
# scripts/patch_geo_batch_2026.py
# Batch 4 GEO capsule injection for articles lacking one, prioritized by in-link weight.
# SEO/GEO intent: extend .geo-answer-capsule (Bing citation + ranking recovery lever) to
# high in-link articles that still lack it. Capsule BLUF is extracted from the article's
# OWN content (key-insight block or first <p>), so nothing is fabricated.
#
# Publish is ATOMIC: all injected articles + the sitemap land in ONE commit
# (git_atomic.atomic_commit), so the CI quality gate never sees a half-applied state.
#
# Usage:
#   python3 scripts/patch_geo_batch_2026.py            # dry-run plan
#   python3 scripts/patch_geo_batch_2026.py --apply    # inject + bump sitemap + atomic push
#   python3 scripts/patch_geo_batch_2026.py --apply --dry-run  # inject-on-disk skipped, chain test only
import os, re, sys, json
import git_atomic

ROOT = git_atomic.ROOT
ART = os.path.join(ROOT, "articles")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
TODAY = "2026-07-31"
N = 15  # batch size


def slug_of(path):
    return os.path.splitext(os.path.basename(path))[0]


def read(p):
    return open(p, encoding="utf-8").read()


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def has_capsule(html):
    return "geo-answer-capsule" in html


def inlink_weight(slug, all_html):
    pat = re.compile(r"/articles/" + re.escape(slug) + r"\.html")
    return sum(len(pat.findall(h)) for s, h in all_html.items() if s != slug)


def extract_bluf(html):
    # 1) key-insight first <p>
    m = re.search(r'<div class="key-insight".*?<p>(.*?)</p>', html, re.DOTALL)
    if m:
        t = strip_tags(m.group(1))
        if len(t) > 20:
            return t
    # 2) first <p> after </header> (skip subtitle by requiring length)
    m = re.search(r"</header>.*?(<p[^>]*>(.*?)</p>)", html, re.DOTALL)
    if m:
        t = strip_tags(m.group(2))
        if len(t) > 20:
            return t
    # 3) first <p> after <h1>
    m = re.search(r"</h1>.*?(<p[^>]*>(.*?)</p>)", html, re.DOTALL)
    if m:
        t = strip_tags(m.group(2))
        if len(t) > 20:
            return t
    return ""


def build_capsule(bluf):
    bluf = bluf.strip()
    if len(bluf) > 92:
        cut = bluf[:92]
        bluf = cut.rstrip("，。、；：") + "…"
    return (
        '\n    <div class="geo-answer-capsule">\n'
        '      <p class="geo-answer-capsule__label">核心结论</p>\n'
        f'      <p class="geo-answer-capsule__text">{bluf}</p>\n'
        '    </div>\n'
    )


def bump_sitemap(slug):
    sm = read(SITEMAP)
    loc = f"https://www.aihrlab.online/articles/{slug}.html"
    idx = sm.find(f"<loc>{loc}</loc>")
    if idx == -1:
        return
    end = sm.find("</url>", idx)
    block = sm[idx:end]
    if "<lastmod>" in block:
        block2 = re.sub(r"<lastmod>.*?</lastmod>", f"<lastmod>{TODAY}</lastmod>", block)
    else:
        block2 = block.replace("</loc>", f"</loc>\n    <lastmod>{TODAY}</lastmod>")
    sm = sm[:idx] + block2 + sm[end:]
    open(SITEMAP, "w", encoding="utf-8").write(sm)


def main():
    apply = "--apply" in sys.argv
    dry = "--dry-run" in sys.argv
    files = [os.path.join(ART, f) for f in os.listdir(ART) if f.endswith(".html")]
    all_html = {slug_of(f): read(f) for f in files}
    rows = []
    for f in files:
        s = slug_of(f)
        h = all_html[s]
        if has_capsule(h):
            continue
        rows.append((inlink_weight(s, all_html), s, extract_bluf(h)))
    rows.sort(reverse=True)
    print(f"=== capsule-less articles: {len(rows)} (showing top {N}) ===")
    plan = []
    for w, s, bluf in rows[:N]:
        print(f"  [{w:3}] {s}\n         bluf={bluf[:60]!r}")
        plan.append({"slug": s, "inlink": w, "bluf": bluf})

    if not apply:
        json.dump(plan, open("/tmp/geo_batch_plan.json", "w"), ensure_ascii=False, indent=2)
        print("\n[DRY-RUN] plan written to /tmp/geo_batch_plan.json — rerun with --apply to inject+push")
        return

    changed = []
    for w, s, bluf in rows[:N]:
        if not bluf:
            print(f"  skip {s} (no bluf extracted)")
            continue
        p = os.path.join(ART, s + ".html")
        h = all_html[s]
        cap = build_capsule(bluf)
        if "</header>" in h:
            h = h.replace("</header>", "</header>" + cap, 1)
        else:
            m = re.search(r"(<h1[^>]*>.*?</h1>)", h, re.DOTALL)
            if not m:
                print(f"  skip {s} (no inject point)"); continue
            h = h.replace(m.group(1), m.group(1) + cap, 1)
        if not dry:
            open(p, "w", encoding="utf-8").write(h)
        changed.append(s)
        if not dry:
            bump_sitemap(s)
        print(f"  injected capsule -> {s}")

    if changed:
        commit_files = ["sitemap.xml"] + [f"articles/{s}.html" for s in changed]
        git_atomic.atomic_commit(
            commit_files,
            f"geo capsule batch: {len(changed)} articles (atomic)",
            dry_run=dry)
        if not dry:
            res = git_atomic.verify_remote(
                [f"articles/{s}.html" for s in changed[:5]],
                needle="geo-answer-capsule")
            print("\n=== remote verify ===")
            for k, v in res.items():
                print(f"  {k}: capsule={v}")
    print(f"\n[APPLY] done. {len(changed)} articles changed." + (" (dry-run)" if dry else ""))


if __name__ == "__main__":
    main()
