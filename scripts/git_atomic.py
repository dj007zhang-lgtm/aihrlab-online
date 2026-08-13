#!/usr/bin/env python3
# scripts/git_atomic.py
# Atomic multi-file commit to GitHub via the Git Data API.
#
# WHY: the old publish flow used the Contents API `PUT` per file, which created
# one commit per file. A multi-file publish (article + sitemap + index + json
# + llms-full) left intermediate commits where sitemap did NOT yet contain the
# just-pushed article -> the CI quality gate (Gate 11: URL consistency) failed on
# those intermediate commits and emailed a failure every run.
#
# FIX (Plan 1): build ONE commit that contains ALL changed files at once via
#   POST git/blobs  -> POST git/trees (base_tree) -> POST git/commits -> PATCH git/refs
# so main is never observed in an inconsistent state. CI triggers exactly once,
# on a complete commit, and passes.
#
# Usage (as a module):
#   import git_atomic
#   sha = git_atomic.atomic_commit(["articles/x.html", "sitemap.xml"], "msg")
#   git_atomic.atomic_commit(files, "msg", dry_run=True)   # builds objects, no ref update
#   git_atomic.verify_remote(["articles/x.html"], needle="geo-answer-capsule")
import os, base64, json, time, socket, urllib.request, urllib.error

REPO = "dj007zhang-lgtm/aihrlab-online"
BRANCH = "main"
GIT = f"https://api.github.com/repos/{REPO}/git"
CONTENTS = f"https://api.github.com/repos/{REPO}/contents"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # site-migrated


def _load_token():
    """Load the GitHub PAT without committing it to the repo.

    Resolution order:
      1. env AIHR_GITHUB_TOKEN (or GITHUB_TOKEN)
      2. gitignored local file scripts/.github_token (raw token, one line)
      3. gitignored scripts/.env  with line  AIHR_GITHUB_TOKEN=...
    Hardcoding the token in source triggered GitHub push-protection (secret
    scanning) and blocked every publish — never put it back here.
    """
    env = os.environ.get("AIHR_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if env and env.strip():
        return env.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(here, ".github_token"),
        os.path.join(os.path.dirname(here), ".github_token"),
        os.path.join(here, ".env"),
    ):
        if os.path.exists(cand):
            try:
                for line in open(cand, encoding="utf-8"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == "AIHR_GITHUB_TOKEN":
                            return v.strip()
                    else:
                        return line  # plain raw-token file
            except Exception:
                pass
    raise RuntimeError(
        "GitHub token not found. Set AIHR_GITHUB_TOKEN env var, or create "
        "scripts/.github_token (gitignored) containing the raw token."
    )


TOKEN = _load_token()


# Transient errors worth retrying: GitHub flakiness / proxy drops on large
# blob POSTs, plus 5xx. Also 400/429: the sandbox egress proxy occasionally
# injects a spurious 400 (or GitHub rate-limits 429) mid-batch after a burst of
# API calls; the same request re-POSTed seconds later succeeds (verified: all
# 189 blobs re-created fine). Blob/tree/commit are content-addressed or
# parent-linked, so re-POSTing identical content is idempotent — a retry reuses
# the same sha or creates an orphan object that is simply garbage-collected.
# Safe to retry. (A genuinely malformed request still fails after _MAX_RETRIES.)
_RETRYABLE_HTTP = {400, 408, 409, 422, 429, 500, 502, 503, 504}
_MAX_RETRIES = 6


def _req(method, path, body=None):
    url = f"{GIT}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", "aihr-sync")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    last_err = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = e
            try:
                body_txt = e.read().decode("utf-8", "ignore")
            except Exception:
                body_txt = ""
            if e.code in _RETRYABLE_HTTP:
                print(f"    [retry HTTP {e.code}] {method} {path} "
                      f"attempt {attempt}/{_MAX_RETRIES}: {body_txt[:160]}")
                if attempt < _MAX_RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                # final attempt: surface the real server message
                raise RuntimeError(
                    f"GitHub API {e.code} on {method} {path}: {body_txt}"
                ) from e
            # non-retryable (400/401/403/404) — fail fast with body
            # 2026-08-13 补强：写类端点 404 最常见根因是 token 缺 scope
            # （只勾 workflow 漏勾 repo → blob/tree/commit 全 404；
            #  只勾 repo 漏勾 workflow → .github/workflows/* 写 404）。
            # 把 cryptic 404 翻成人话，避免再次出现"发了错 token 还以为是代理抖动"。
            hint = ""
            if e.code == 404 and ("blobs" in path or "trees" in path
                                  or "commits" in path or "refs/heads" in path):
                hint = ("（疑似 token 缺 repo 写 scope；若路径在 .github/workflows/ 下"
                        "还需 workflow scope。请在 GitHub 重新生成 PAT 并勾选"
                        " repo(或 public_repo) + workflow）")
            raise RuntimeError(
                f"GitHub API {e.code} on {method} {path}: {body_txt}{hint}"
            ) from e
        except (urllib.error.URLError, socket.timeout, ConnectionError,
                TimeoutError) as e:
            last_err = e
            print(f"    [retry net {type(e).__name__}] {method} {path} "
                  f"attempt {attempt}/{_MAX_RETRIES}: {e}")
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_err


def get_base():
    """Return (head_commit_sha, base_tree_sha) for BRANCH."""
    ref = _req("GET", f"refs/heads/{BRANCH}")
    commit_sha = ref["object"]["sha"]
    commit = _req("GET", f"commits/{commit_sha}")
    return commit_sha, commit["tree"]["sha"]


def create_blob(content_bytes):
    b64 = base64.b64encode(content_bytes).decode()
    resp = _req("POST", "blobs", {"content": b64, "encoding": "base64"})
    return resp["sha"]


def verify_token_scopes():
    """发布前 scope 预检：探测 token 是否具备 repo 写 scope。

    根因（2026-08-13 低级失误）：用户重新生成 PAT 时只勾了 workflow，漏勾 repo，
    导致 POST blobs 稳定 404；当时错误信息只有 'GitHub API 404' 无 scope 提示，
    误判为代理抖动，浪费多轮。本函数把这件事变成发布前的确定性预检。

    做法：向 blobs 端点 POST 一个极小探针 blob。
      - 201 且返回 sha  → repo 写 scope OK（探针 blob 未被任何 tree/commit 引用，
        GitHub 自动 GC，无副作用）；
      - 404            → 确定性缺 repo scope，返回 (False, 人话提示)；
      - 其他异常（含代理偶发抖动）→ 返回 (None, 提示)，不阻断，让真实写操作暴露真相，
        避免把代理 404 误判成 scope 缺失而误杀合法发布。
    """
    marker = base64.b64encode(b"__aihr_scope_probe__").decode()
    try:
        r = _req("POST", "blobs", {"content": marker, "encoding": "base64"})
        if isinstance(r, dict) and "sha" in r:
            return True, "token 具备 repo 写 scope（workflow 文件写操作由真实提交暴露）"
        return False, f"probe blob 返回异常结构: {r!r}"
    except RuntimeError as e:
        if "404" in str(e):
            return False, ("token 缺 repo 写 scope（POST blobs 返回 404）。"
                           "请在 GitHub 重新生成 PAT 并勾选 repo(或 public_repo)；"
                           "若还要提交 .github/workflows/* 还需 workflow scope")
        return None, f"scope 预检未定性（{e}），继续由真实写操作判定"


def atomic_commit(local_rel_paths, message, dry_run=False, verbose=True):
    """Create ONE commit containing ALL given files (new or updated).

    Files are read from disk at ROOT/<rel>. Unchanged files are inherited from
    the base tree automatically. With dry_run=True the blob/tree/commit objects
    are created on the server but the branch ref is NOT updated (safe verify).
    Returns the new commit sha.
    """
    if not local_rel_paths:
        print("  [atomic] no files to commit")
        return None
    # 发布前 scope 预检：确定性缺 repo scope 直接拦下，避免中途静默 404。
    ok, msg = verify_token_scopes()
    if ok is False:
        raise RuntimeError(f"[发布预检失败] {msg}")
    elif ok is None:
        print(f"  [warn] {msg}")
    commit_sha, base_tree_sha = get_base()
    if verbose:
        print(f"  [atomic] base {commit_sha[:8]} tree {base_tree_sha[:8]}")
    tree_entries = []
    for rel in local_rel_paths:
        p = os.path.join(ROOT, rel)
        content = open(p, "rb").read()
        blob_sha = create_blob(content)
        tree_entries.append({
            "path": rel,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha,
        })
        if verbose:
            print(f"  blob {rel} ({len(content)} bytes) -> {blob_sha[:8]}")
    # Chunked tree creation.
    # ROOT CAUSE (2026-08-13): the sandbox egress proxy returns HTTP 404 on
    # large tree POST bodies (the 226-file publish 404'd on `POST trees`, while
    # a 2-entry tree POST succeeded). GitHub's Git Data tree API accepts a
    # base_tree, so we build the final tree incrementally in small batches:
    # each batch POSTs a tree whose base_tree is the previous batch's sha. The
    # result is identical to a single large tree, but every POST body stays
    # small enough for the proxy. Blob/tree/commit are content-addressed or
    # parent-linked, so re-POSTing is idempotent and safe to retry.
    CHUNK = 25
    cur_base = base_tree_sha
    final_tree_sha = base_tree_sha
    for i in range(0, len(tree_entries), CHUNK):
        chunk = tree_entries[i:i + CHUNK]
        resp = _req("POST", "trees", {"base_tree": cur_base, "tree": chunk})
        cur_base = resp["sha"]
        final_tree_sha = cur_base
        if verbose:
            print(f"  tree chunk {i // CHUNK + 1} "
                  f"({len(chunk)} files) -> {cur_base[:8]}")
    new_commit = _req("POST", "commits", {
        "message": message,
        "tree": final_tree_sha,
        "parents": [commit_sha],
    })
    new_sha = new_commit["sha"]
    if dry_run:
        print(f"  [DRY-RUN] created orphan commit {new_sha[:8]} "
              f"({len(tree_entries)} files); ref NOT updated")
        return new_sha
    _req("PATCH", f"refs/heads/{BRANCH}", {"sha": new_sha, "force": False})
    print(f"  [atomic] pushed {new_sha[:8]} ({len(tree_entries)} files) -> {BRANCH}")
    return new_sha


def verify_remote(rel_paths, needle=None):
    """Fetch remote files via Contents API; return dict rel -> bool/err."""
    out = {}
    for rel in rel_paths:
        try:
            req = urllib.request.Request(f"{CONTENTS}/{rel}?ref={BRANCH}")
            req.add_header("Authorization", f"Bearer {TOKEN}")
            req.add_header("User-Agent", "aihr-sync")
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            txt = base64.b64decode(d["content"]).decode("utf-8", "ignore")
            out[rel] = (needle is None) or (needle in txt)
        except Exception as e:
            out[rel] = f"ERR {e}"
    return out


if __name__ == "__main__":
    # Self-test: prove the API chain works without mutating main.
    sha = atomic_commit(["sitemap.xml"], "DRY-RUN self test", dry_run=True)
    print("self-test commit:", sha)
