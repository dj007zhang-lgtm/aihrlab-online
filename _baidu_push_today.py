import json, re, urllib.parse, urllib.request, datetime

BASE = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
SM = f"{BASE}/sitemap.xml"
LOG = f"{BASE}/baidu_push_log.json"
API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"

# 1. Extract & dedupe sitemap URLs (preserve order)
with open(SM, encoding="utf-8") as f:
    sm = f.read()
locs = re.findall(r"<loc>(.*?)</loc>", sm)
sitemap = []
seen = set()
for u in locs:
    if u not in seen:
        seen.add(u)
        sitemap.append(u)

# 2. Load log
with open(LOG, encoding="utf-8") as f:
    log = json.load(f)
pushed = log["pushed"]
pushed_norm = {urllib.parse.unquote(p) for p in pushed}

# 3. Remaining (in sitemap, not in log)
remaining = [u for u in sitemap if urllib.parse.unquote(u) not in pushed_norm]
total = len(sitemap)
print(f"Sitemap unique URLs: {total}")
print(f"Already pushed (normalized): {len(pushed_norm)}")
print(f"Remaining to push: {len(remaining)}")

batch = remaining[:10]
print(f"\nToday's batch ({len(batch)}):")
for u in batch:
    print("  -", u)

# 4. Push one by one
pushed_today = []
failed_today = []
over_quota = False

for url in batch:
    data = url.encode("utf-8")
    req = urllib.request.Request(API, data=data, method="POST",
                                 headers={"Content-Type": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        print(f"\n[POST] {url}\n  -> {body}")
        j = json.loads(body)
        if "error" in j:
            failed_today.append((url, body))
        else:
            pushed_today.append(url)
            # avoid literal/normalized dupes
            if url not in pushed and urllib.parse.unquote(url) not in pushed_norm:
                pushed.append(url)
                pushed_norm.add(urllib.parse.unquote(url))
            if j.get("error", 0) == "over quota" or "over quota" in body:
                over_quota = True
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        print(f"\n[POST] {url}\n  -> HTTP {e.code}: {err}")
        failed_today.append((url, f"HTTP {e.code}: {err}"))
        if "over quota" in err:
            over_quota = True
    if over_quota:
        print("\n*** OVER QUOTA detected. Recording and exiting. ***")
        break

# 5. Update log
remaining_after = len(remaining) - len(pushed_today)
today = datetime.date.today().isoformat()

if over_quota:
    log["history"].append({
        "date": today,
        "pushed": len(pushed_today),
        "failed": len(failed_today),
        "remaining_after": remaining_after,
        "status": "OVER_QUOTA",
        "note": "Today's quota exhausted (over quota) before completing batch. No further action taken."
    })
else:
    log["total_pushed"] = log.get("total_pushed", 0) + len(pushed_today)
    hist = {
        "date": today,
        "pushed": len(pushed_today),
        "failed": len(failed_today),
        "remaining_after": remaining_after,
    }
    if remaining_after == 0:
        hist["status"] = "ALL_COMPLETE"
        hist["note"] = "All sitemap URLs pushed."
    log["history"].append(hist)

with open(LOG, "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

# 6. Result print
print("\n" + "="*50)
print("PUSH RESULT")
print("="*50)
print(f"Pushed today : {len(pushed_today)}")
print(f"Failed today : {len(failed_today)}")
if failed_today:
    for u, e in failed_today:
        print(f"   FAIL {u}: {e}")
pct = len(pushed_norm) / total * 100 if total else 100
print(f"Remaining    : {remaining_after}")
print(f"Cumulative   : {len(pushed_norm)}/{total} unique sitemap URLs ({pct:.1f}%)")
if over_quota:
    print("STATUS: OVER_QUOTA - exited, no other action performed.")
elif remaining_after == 0:
    print("STATUS: ALL_COMPLETE - all sitemap URLs pushed.")
else:
    print(f"STATUS: PARTIAL - {remaining_after} URLs remain for future pushes.")
