#!/usr/bin/env python3
"""补齐缺失的 <meta property="article:published_time">。

为什么需要它：datePublished / 日期真相源优先级链（memory 已固化）
    <time datetime>  →  JSON-LD datePublished  →  git 首次提交日期  →  mtime(保底，禁用)
OG 层缺失 published_time 时，同步/归档脚本会退到最后一级，造成「sync 日期污染」。
本脚本按同一条优先级链回填 OG 层，让链在第一/二级就命中。

纪律：
  - 幂等：已有 article:published_time 的页面直接跳过，重复运行结果相同。
  - 只读默认：不带 --apply 时只报告，不落盘。
  - 不许编造：四级全拿不到日期就跳过并报告（计入 SKIP），绝不猜日期。
  - 不改 Generator 产物之外的语义：只插入一行 meta。

用法:
  python3 scripts/backfill_published_time.py            # 报告
  python3 scripts/backfill_published_time.py --apply    # 落盘
"""
import subprocess, sys, os, re, glob

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()
REMOTE = "origin/main"

PUB_RE = re.compile(r'article:published_time')
TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
JSONLD_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
OG_TYPE_RE = re.compile(r'^(\s*)<meta property="og:type" content="article">\s*$', re.M)
OG_LOCALE_RE = re.compile(r'^(\s*)<meta property="og:locale"[^>]*>\s*$', re.M)
OG_URL_RE = re.compile(r'^(\s*)<meta property="og:url"[^>]*>\s*$', re.M)
# 跳转壳判定：noindex + meta refresh(+canonical)。这类页面是刻意存在的 URL 合并壳，
# 不是内容页，禁止改写（记忆铁律：noindex 页先判「是不是跳转壳」，不按字数定性）。
REFRESH_RE = re.compile(r'<meta[^>]+http-equiv="refresh"[^>]*>', re.I)
NOINDEX_RE = re.compile(r'<meta[^>]+name="robots"[^>]*noindex', re.I)

ISO_DATE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')


def norm_date(raw: str):
    """把各种日期写法归一成 YYYY-MM-DD；带时间的保留到秒并附 +08:00。"""
    if not raw:
        return None
    raw = raw.strip()
    m = ISO_DATE.match(raw)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (2020 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    date_part = "%04d-%02d-%02d" % (y, mo, d)
    t = re.search(r'T(\d{2}):(\d{2})(:(\d{2}))?', raw)
    if t:
        hh, mm, ss = int(t.group(1)), int(t.group(2)), int(t.group(4) or 0)
        return "%sT%02d:%02d:%02d+08:00" % (date_part, hh, mm, ss)
    return date_part


def git_first_commit_date(rel: str):
    """git 首次提交日期（--diff-filter=A）。先查本地 HEAD 历史，再查远程 main。"""
    for ref in ("HEAD", REMOTE):
        try:
            out = subprocess.run(
                ["git", "log", ref, "--diff-filter=A", "--format=%aI", "--", rel],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            ).stdout.strip().split("\n")
            if out and out[-1]:
                return norm_date(out[-1])
        except Exception:
            continue
    return None


def pick_date(path: str, head: str, full: str):
    """按真相源优先级取日期，返回 (date, source)。"""
    m = TIME_RE.search(full)
    if m:
        d = norm_date(m.group(1))
        if d:
            return d, "time[datetime]"
    m = JSONLD_RE.search(full)
    if m:
        d = norm_date(m.group(1))
        if d:
            return d, "jsonld.datePublished"
    d = git_first_commit_date(path)
    if d:
        return d, "git first-commit"
    return None, None


def insert_point(content: str):
    """返回插入位置（行末之后）与缩进。

    锚点优先级：紧跟社交/meta 区块，避免插到 head 中间把 description 与 og 割裂。
      og:type → og:locale → og:url → og:title → og:description → og:image
      → og:site_name → twitter:card → twitter:*
    找不到任何 og/twitter 行则返回 None（由调用方跳过，不猜位置）。
    """
    patterns = [
        r'^(\s*)<meta property="og:type"[^>]*>\s*$',
        r'^(\s*)<meta property="og:locale"[^>]*>\s*$',
        r'^(\s*)<meta property="og:url"[^>]*>\s*$',
        r'^(\s*)<meta property="og:title"[^>]*>\s*$',
        r'^(\s*)<meta property="og:description"[^>]*>\s*$',
        r'^(\s*)<meta property="og:image"[^>]*>\s*$',
        r'^(\s*)<meta property="og:site_name"[^>]*>\s*$',
        r'^(\s*)<meta name="twitter:card"[^>]*>\s*$',
        r'^(\s*)<meta (?:property|name)="twitter:[^"]*"[^>]*>\s*$',
    ]
    head_zone = content[:200000]
    for pat in patterns:
        rx = re.compile(pat, re.M)
        matches = list(rx.finditer(head_zone))
        if matches:
            m = matches[-1]
            line_end = content.find("\n", m.end())
            if line_end == -1:
                line_end = len(content)
            return line_end + 1, m.group(1)
    # 兜底：head 是压缩单行（meta 全挤在一行，无行级锚点）→ 插到 </head> 之前。
    idx = content.find("</head>")
    if idx > 0 and idx < 200000:
        return idx, "  "
    return None, None


def main():
    apply = "--apply" in sys.argv
    targets = sorted(glob.glob(os.path.join(ROOT, "articles", "*.html")))
    stats = {"have": 0, "filled": 0, "skip_nodate": 0, "redirect_shell": 0,
             "no_anchor": 0}
    by_source = {}
    locations = {}
    changes = []
    problems = []

    for p in targets:
        rel = os.path.relpath(p, ROOT)
        full = open(p, "r", encoding="utf-8", errors="ignore").read()
        head = full[:200000]
        if PUB_RE.search(head):
            stats["have"] += 1
            continue
        if REFRESH_RE.search(head) and NOINDEX_RE.search(head):
            stats["redirect_shell"] += 1
            continue
        date, src = pick_date(rel, head, full)
        if not date:
            stats["skip_nodate"] += 1
            continue
        idx, indent = insert_point(full)
        if idx is None:
            stats["no_anchor"] += 1
            problems.append(rel)
            continue
        tag = '%s<meta property="article:published_time" content="%s">\n' % (indent, date)
        if tag in full:
            stats["have"] += 1
            continue
        new = full[:idx] + tag + full[idx:]
        if PUB_RE.search(new[:200000]) is None:
            problems.append(rel)
            continue
        changes.append((rel, tag.strip()))
        by_source[src] = by_source.get(src, 0) + 1
        locations[os.path.dirname(rel)] = locations.get(os.path.dirname(rel), 0) + 1
        stats["filled"] += 1
        if apply:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(new)

    print("=" * 62)
    print("article:published_time 回填   模式: %s" % ("APPLY（已落盘）" if apply else "DRY-RUN（只读报告）"))
    print("=" * 62)
    print("  扫描 articles/*.html        : %d" % len(targets))
    print("  已具备 published_time       : %d" % stats["have"])
    print("  本次补齐                    : %d" % stats["filled"])
    print("  四级真源全无 → 跳过(不猜)   : %d" % stats["skip_nodate"])
    print("  跳转壳 → 按铁律不改          : %d" % stats["redirect_shell"])
    print("  找不到 og 锚点 → 未处理      : %d" % stats["no_anchor"])
    print("\n日期来源分布：")
    for k, v in sorted(by_source.items(), key=lambda x: -x[1]):
        print("  %-24s %d" % (k, v))
    if problems:
        print("\n⚠️  处理失败（需人工）:")
        for r in problems[:20]:
            print("  ", r)
    if changes and not apply:
        print("\n样例（前 8 条）：")
        for rel, tag in changes[:8]:
            print("  %-52s %s" % (rel, tag))
    if not apply and stats["filled"]:
        print("\n→ 确认无误后加 --apply 落盘")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
