#!/usr/bin/env python3
"""Baidu daily URL push — 2026-09-11 (automation run)."""
import json
import sys
import urllib.parse
import urllib.request
import datetime
import os

BASE = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
SITEMAP = os.path.join(BASE, "sitemap.xml")
LOG = os.path.join(BASE, "baidu_push_log.json")
API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"
TODAY = "2026-09-11"
LIMIT = 10

# 1. Extract sitemap URLs, dedupe (raw)
with open(SITEMAP, "r", encoding="utf-8") as f:
    raw = f.read()
locs = []
for line in raw.splitlines():
    s = line.strip()
    if "<loc>" in s and "</loc>" in s:
        loc = s.split("<loc>", 1)[1].split("</loc>", 1)[0].strip()
        locs.append(loc)
sitemap_urls = sorted(set(locs))

# 2. Read pushed list
with open(LOG, "r", encoding="utf-8") as f:
    log = json.load(f)
pushed = log.get("pushed", [])

# Normalize helper: unquote to handle encoded/decoded dupes
def norm(u):
    return urllib.parse.unquote(u).rstrip("/")

pushed_norm = set(norm(u) for u in pushed)
sitemap_norm_map = {}
for u in sitemap_urls:
    sitemap_norm_map.setdefault(norm(u), u)  # keep one representative

# 3. Remaining = in sitemap but not in pushed
remaining = [sitemap_norm_map[k] for k in sorted(sitemap_norm_map) if k not in pushed_norm]

total_urls = len(sitemap_norm_map)
already = total_urls - len(remaining)

print(f"[INFO] sitemap unique URLs (normalized): {total_urls}")
print(f"[INFO] already in pushed set: {already}")
print(f"[INFO] remaining to push: {len(remaining)}")
print(f"[INFO] log.total_urls field: {log.get('total_urls')} | log.total_pushed: {log.get('total_pushed')}")

# 8b. ALL_COMPLETE branch
if len(remaining) == 0:
    print("[INFO] No remaining URLs — ALL_COMPLETE")
    entry = {
        "date": TODAY,
        "pushed": 0,
        "failed": 0,
        "remaining_after": 0,
        "status": "ALL_COMPLETE",
        "note": "No new URLs to push - all sitemap URLs already in pushed list",
    }
    log.setdefault("history", []).append(entry)
    log["total_urls"] = total_urls
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print("[DONE] ALL_COMPLETE recorded; no push performed.")
    sys.exit(0)

batch = remaining[:LIMIT]
print(f"[INFO] Pushing first {len(batch)} URLs...")

success_urls = []
failed_urls = []
over_quota = False

for url in batch:
    data = url.encode("utf-8")
    req = urllib.request.Request(API, data=data, headers={"Content-Type": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        # Baidu returns JSON like {"remain":N,"success":M} or error
        try:
            res = json.loads(body)
        except Exception:
            res = {"raw": body}
        print(f"  -> {url}\n     {body.strip()}")
        if isinstance(res, dict):
            if "error" in res:
                # e.g. {"error":401,"message":"..."}
                msg = res.get("message", "")
                if "over quota" in msg.lower():
                    over_quota = True
                failed_urls.append(url)
            else:
                success_urls.append(url)
        else:
            failed_urls.append(url)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")
        print(f"  -> {url}\n     HTTP {e.code}: {err_body.strip()}")
        if "over quota" in err_body.lower():
            over_quota = True
        failed_urls.append(url)
    except Exception as e:
        print(f"  -> {url}\n     EXC: {e}")
        failed_urls.append(url)

    if over_quota:
        # 8. over quota: record and exit, do nothing else
        print("[WARN] Over quota detected — recording and exiting per procedure.")
        entry = {
            "date": TODAY,
            "pushed": len(success_urls),
            "failed": len(failed_urls),
            "remaining_after": len(remaining),
            "status": "OVER_QUOTA",
            "note": "Baidu returned over quota; no further action taken",
        }
        log.setdefault("history", []).append(entry)
        log["total_urls"] = total_urls
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("[DONE] Over-quota exit.")
        sys.exit(0)

# 5. Update log
updated_pushed = list(pushed)
for u in success_urls:
    updated_pushed.append(u)
log["pushed"] = updated_pushed
log["total_pushed"] = len(updated_pushed)
log["total_urls"] = total_urls

remaining_after = len(remaining) - len(success_urls)
status = "ALL_COMPLETE" if remaining_after == 0 else "PARTIAL"
entry = {
    "date": TODAY,
    "pushed": len(success_urls),
    "failed": len(failed_urls),
    "remaining_after": remaining_after,
    "status": status,
    "note": "Daily incremental push; URLs: " + ", ".join(success_urls),
}
log.setdefault("history", []).append(entry)

with open(LOG, "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

# 7. Print clear result
pct = (len(updated_pushed) / total_urls * 100) if total_urls else 0
print("\n==================== PUSH RESULT ====================")
print(f"Date              : {TODAY}")
print(f"Pushed this run   : {len(success_urls)}")
print(f"Failed this run   : {len(failed_urls)}")
print(f"Total pushed      : {len(updated_pushed)}")
print(f"Total sitemap URL : {total_urls}")
print(f"Cumulative %      : {pct:.1f}%")
print(f"Remaining after   : {remaining_after}")
print(f"Status            : {status}")
print("=====================================================")
