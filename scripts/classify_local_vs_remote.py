#!/usr/bin/env python3
"""本地 vs 远程 main 的一致性分类（只统计「可发布」文件：tracked + untracked-not-ignored）。

判定:
  NEW      本地有且未被 .gitignore 忽略，远程没有
  SAME     本地与远程 blob 一致
  DIFFER   本地与远程 blob 不同
  REMOTE_ONLY  远程有、本地没有（本地快照落后）

DIFFER 再做 diff 分型，判断改动是否只落在「预期区域」:
      head-meta : <meta ...> / <title> / <link ...> 行
      next-path : next-path 区块内部
  其余落到 UNSAFE，需人工确认后才能进发布批次。

只读，不改动仓库任何文件。
用法: python3 scripts/classify_local_vs_remote.py
"""
import subprocess, sys, os, hashlib, csv, re, difflib
from collections import Counter

REMOTE = os.environ.get("REMOTE_REF", "origin/main")


def run(args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


REPO = run(["git", "rev-parse", "--show-toplevel"]).strip()


def git_blob_sha(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


print("[1/5] 读取远程 %s tree ..." % REMOTE, file=sys.stderr)
remote = {}
for entry in run(["git", "ls-tree", "-r", "-z", REMOTE]).split("\0"):
    if not entry:
        continue
    meta, path = entry.split("\t", 1)
    mode, typ, sha = meta.split()
    if typ == "blob":
        remote[path] = sha
print("    远程 blob: %d" % len(remote), file=sys.stderr)

print("[2/5] 列出可发布候选（tracked + untracked-not-ignored）...", file=sys.stderr)
candidates = set(
    p for p in run(["git", "ls-files", "-co", "--exclude-standard"]).split("\n") if p
)
print("    候选: %d" % len(candidates), file=sys.stderr)

print("[3/5] 本地 / 远程 blob 比对 ...", file=sys.stderr)
rows = []
for rel in sorted(candidates):
    full = os.path.join(REPO, rel)
    if not os.path.isfile(full):
        continue
    data = open(full, "rb").read()
    sha = git_blob_sha(data)
    r = remote.get(rel)
    rows.append({
        "path": rel,
        "status": "NEW" if r is None else ("SAME" if r == sha else "DIFFER"),
        "bytes": len(data),
    })

remote_only = sorted(p for p in remote if p not in {r["path"] for r in rows})

print("[4/5] DIFFER 文件 diff 分型（直读远程 blob，不经 index）...", file=sys.stderr)
META_LINE = re.compile(r"^\s*<(meta|title|link)\b")
NEXT_PATH = re.compile(r"next-path")
SAFE_HEAD = re.compile(r"^<!--" )  # 注释行/标记行一律视为预期改写区
row_by_path = {r["path"]: r for r in rows}

cache_dir = os.path.join(REPO, ".git", "classify-cache")
os.makedirs(cache_dir, exist_ok=True)


def remote_text(path: str) -> str:
    """直读远程 blob 文本；不依赖 index/HEAD 状态。"""
    sha = remote[path]
    cp = os.path.join(cache_dir, sha)
    if not os.path.exists(cp):
        with open(cp, "wb") as fh:
            fh.write(subprocess.run(["git", "cat-file", "blob", sha],
                                    capture_output=True, check=True).stdout)
    return open(cp, "r", encoding="utf-8", errors="replace").read()


for rel in [r["path"] for r in rows if r["status"] == "DIFFER"]:
    kinds = Counter()
    samples = []
    if not rel.endswith((".html", ".xml", ".json", ".py", ".md", ".js", ".css", ".txt")):
        row_by_path[rel]["verdict"] = "REVIEW-binary"
        continue
    old = remote_text(rel).split("\n")
    new = open(os.path.join(REPO, rel), "r", encoding="utf-8", errors="replace").read().split("\n")
    for line in difflib.unified_diff(old, new, n=0, lineterm=""):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line[:1] not in "+-":
            continue
        body = line[1:]
        stripped = body.strip()
        if META_LINE.match(body) or NEXT_PATH.search(body) or stripped in ('">', '" >', '<!--NEXT_PATH_START-->', '<!--NEXT_PATH_END-->', '</ol>') or SAFE_HEAD.search(stripped):
            kinds["meta-or-nextpath"] += 1
        elif body.strip() == "":
            kinds["blank"] += 1
        else:
            kinds["UNSAFE"] += 1
            if len(samples) < 3:
                samples.append(line.strip()[:160])
    if kinds["UNSAFE"]:
        verdict = "UNSAFE"
    elif kinds["meta-or-nextpath"]:
        verdict = "SAFE-meta-nextpath"
    else:
        verdict = "SAFE-blank-only"
    row_by_path[rel]["verdict"] = verdict
    row_by_path[rel]["samples"] = " || ".join(samples)

print("[5/5] 输出 ...", file=sys.stderr)
out = os.path.join(REPO, "outputs", "local-vs-remote-main.csv")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["path", "status", "verdict", "bytes", "samples"])
    w.writeheader()
    for r in rows:
        w.writerow({
            "path": r["path"],
            "status": r["status"],
            "verdict": r.get("verdict", ""),
            "bytes": r["bytes"],
            "samples": r.get("samples", ""),
        })

c = Counter(r["status"] for r in rows)
print("\n=== 汇总（可发布集合）===")
for k in ("SAME", "DIFFER", "NEW"):
    print("  %-8s %d" % (k, c.get(k, 0)))
print("  REMOTE_ONLY(本地缺失) %d" % len(remote_only))

v = Counter(r.get("verdict") for r in rows if r["status"] == "DIFFER")
print("\n=== DIFFER 分型 ===")
for k, n in v.most_common():
    print("  %-22s %d" % (k, n))

print("\n=== UNSAFE 明细 ===")
for r in rows:
    if r.get("verdict") == "UNSAFE":
        print("  %s" % r["path"])
        if r.get("samples"):
            print("      %s" % r["samples"][:300])

if remote_only:
    print("\n=== REMOTE_ONLY 明细 ===")
    for p in remote_only:
        print("  %s" % p)

print("\n明细: %s" % out)
