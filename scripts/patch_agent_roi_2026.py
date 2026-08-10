#!/usr/bin/env python3
"""AI Agent ROI 文章上线收尾（Bash 恢复后运行）。
1) sync-articles.py 重写 article-index.json + 卡片网格（幂等，基于磁盘文章）
2) 补齐 articles/index.html 的 CollectionPage JSON-LD ItemList（幂等）
3) 跑 quality_gate.py --all
4) 通过 GitHub Contents API 推送 5 个文件
幂等：JSON-LD 已含 agent URL 则跳过插入；Contents API 用 GET 取 sha 后 PUT。
"""
import re, json, subprocess, base64, urllib.request, urllib.error, os

def _load_token():
    """Load PAT from gitignored scripts/.github_token or env (never hardcode)."""
    import os as _os
    for cand in (
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".github_token"),
        _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), ".github_token"),
    ):
        if _os.path.exists(cand):
            return open(cand, encoding="utf-8").read().strip()
    return _os.environ.get("AIHR_GITHUB_TOKEN") or _os.environ.get("GITHUB_TOKEN") or ""


TOKEN = _load_token()
REPO = "dj007zhang-lgtm/aihrlab-online"
BRANCH = "main"
API = f"https://api.github.com/repos/{REPO}/contents"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # site-migrated

SLUG = "ai-agent-roi-reality-2026"
URL = f"https://www.aihrlab.online/articles/{SLUG}.html"
TITLE = "Agent ROI现实检验：80%说赚，88%未投产"


def run_sync():
    r = subprocess.run(["python3", "scripts/sync-articles.py"], cwd=ROOT,
                       capture_output=True, text=True)
    print("[SYNC]", "ok" if r.returncode == 0 else r.stderr[:300])


def patch_jsonld():
    p = os.path.join(ROOT, "articles/index.html")
    h = open(p, encoding="utf-8").read()
    # articles/index.html 含多个 itemListElement（BreadcrumbList 2项 + CollectionPage 79项
    # + data-category 等误匹配）。用括号配对定位每个数组，取 ListItem 数最多者（= CollectionPage）。
    best, best_cnt, best_close, best_arr = None, -1, None, ""
    for m in re.finditer(r'"itemListElement"', h):
        idx = m.start()
        start = h.find('[', idx)
        depth = 0
        i = start
        while i < len(h):
            if h[i] == '[':
                depth += 1
            elif h[i] == ']':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        arr = h[start + 1:i]
        cnt = arr.count('"@type": "ListItem"')
        if cnt > best_cnt:
            best_cnt, best_close, best_arr = cnt, i, arr
    if best_cnt <= 0:
        print("[JSON-LD] no itemListElement found, abort"); return
    if SLUG in best_arr:
        print("[JSON-LD] already in CollectionPage, skip"); return
    positions = [int(x) for x in re.findall(r'"position":\s*(\d+)', best_arr)]
    newpos = max(positions) + 1
    item = (f',{{"@type": "ListItem", "position": {newpos}, '
            f'"name": {json.dumps(TITLE, ensure_ascii=False)}, '
            f'"url": {json.dumps(URL, ensure_ascii=False)}}}')
    h = h[:best_close] + item + h[best_close:]
    open(p, "w", encoding="utf-8").write(h)
    print(f"[JSON-LD] inserted at position {newpos}; total items {best_cnt + 1}")


def quality_gate():
    r = subprocess.run(["python3", "scripts/quality_gate.py", "--all"], cwd=ROOT,
                       capture_output=True, text=True)
    print(f"[QUALITY GATE exit {r.returncode}]")
    out = r.stdout if r.stdout else r.stderr
    print(out[-1800:])


def api(method, path, data=None):
    req = urllib.request.Request(f"{API}/{path}", method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "aihr-sync")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def push():
    files = [f"articles/{SLUG}.html", "assets/js/article-index.json",
             "articles/index.html", "sitemap.xml", "llms-full.txt"]
    msg = "add: AI Agent ROI现实检验长文 + 同步四数据源(含JSON-LD ItemList)"
    for f in files:
        status, resp = api("GET", f + f"?ref={BRANCH}")
        sha = resp.get("sha") if status == 200 else None
        content = open(os.path.join(ROOT, f), "rb").read()
        b64 = base64.b64encode(content).decode("ascii")
        payload = {"message": msg, "content": b64, "branch": BRANCH}
        if sha:
            payload["sha"] = sha
        st, r = api("PUT", f, payload)
        print(f"[{st}] {f}  sha={sha[:8] if sha else 'NEW'}")
        if st not in (200, 201):
            print("   ERR:", json.dumps(r, ensure_ascii=False)[:300])


if __name__ == "__main__":
    run_sync()
    patch_jsonld()
    quality_gate()
    push()
    print("DONE")
