import json, re, subprocess, urllib.parse, sys, datetime

BASE = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
SITEMAP = f"{BASE}/sitemap.xml"
LOG = f"{BASE}/baidu_push_log.json"
API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"
TODAY = datetime.date.today().isoformat()

# 1. parse sitemap locs, dedupe preserving order
with open(SITEMAP, encoding="utf-8") as f:
    sml = f.read()
locs = re.findall(r"<loc>(.*?)</loc>", sml)
seen = set()
sitemap_urls = []
for u in locs:
    if u not in seen:
        seen.add(u)
        sitemap_urls.append(u)

# 2. read pushed log
with open(LOG, encoding="utf-8") as f:
    log = json.load(f)
pushed = log.get("pushed", [])

# normalize for comparison (unquote both sides to handle encoded/decoded dupes)
pushed_norm = set(urllib.parse.unquote(p) for p in pushed)
sitemap_norm = {urllib.parse.unquote(u): u for u in sitemap_urls}  # keep canonical sitemap form

# 3. compute remaining (in sitemap, not in pushed)
remaining = [sitemap_norm[n] for n in sitemap_norm if n not in pushed_norm]

print(f"[INFO] sitemap unique URLs: {len(sitemap_urls)}")
print(f"[INFO] pushed entries: {len(pushed)} (normalized distinct: {len(pushed_norm)})")
print(f"[INFO] remaining unpushed: {len(remaining)}")

if not remaining:
    print("[INFO] remaining=0 -> ALL_COMPLETE, no API call needed")
    log["history"].append({
        "date": TODAY,
        "pushed": 0,
        "failed": 0,
        "remaining_after": 0,
        "status": "ALL_COMPLETE",
        "note": "No new URLs to push - all sitemap URLs already in pushed list"
    })
    log["total_urls"] = len(sitemap_urls)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print("[DONE] ALL_COMPLETE logged, log updated")
    sys.exit(0)

# 4. take first 10
batch = remaining[:10]

today_pushed = 0
today_failed = 0
failed_urls = []
over_quota = False
remain_after = None

for url in batch:
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "20", "-H", "Content-Type: text/plain",
             "--data-binary", url, API],
            capture_output=True, text=True, timeout=25
        )
        out = (r.stdout or "").strip()
        print(f"  push -> {url}\n    resp: {out}")
        try:
            resp = json.loads(out)
        except Exception:
            resp = {}
        if "remain" in resp:
            remain_after = resp["remain"]
        if "error" in resp:
            err = resp.get("error", "")
            if "over quota" in err.lower() or "quota" in err.lower():
                over_quota = True
                today_failed += 1
                failed_urls.append(url)
                break
            else:
                today_failed += 1
                failed_urls.append(url)
        else:
            today_pushed += 1
            pushed.append(url)
    except Exception as e:
        print(f"  ERROR pushing {url}: {e}")
        today_failed += 1
        failed_urls.append(url)

# 5/6. update log
log["total_pushed"] = len(pushed)
log["total_urls"] = len(sitemap_urls)

remaining_after_count = len(remaining) - today_pushed

if over_quota:
    log["history"].append({
        "date": TODAY,
        "pushed": today_pushed,
        "failed": today_failed,
        "remaining_after": remaining_after_count,
        "status": "OVER_QUOTA_NO_PUSH" if today_pushed == 0 else "PARTIAL",
        "note": "百度今日配额已用完 (over quota)，退出"
    })
else:
    status = "ALL_COMPLETE" if remaining_after_count == 0 else "PARTIAL"
    hist = {
        "date": TODAY,
        "pushed": today_pushed,
        "failed": today_failed,
        "remaining_after": remaining_after_count,
        "status": status,
        "note": "All sitemap URLs pushed." if status == "ALL_COMPLETE" else "Daily incremental push"
    }
    if remain_after is not None:
        hist["baidu_remain"] = remain_after
    log["history"].append(hist)

with open(LOG, "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

# 7. print clear summary
print("\n===== 百度API每日推送结果 =====")
print(f"日期: {TODAY}")
print(f"推送成功: {today_pushed} 条")
print(f"推送失败: {today_failed} 条")
if failed_urls:
    print(f"失败URL: {failed_urls}")
print(f"本次新增/总 sitemap 唯一 URL: {len(sitemap_urls)}")
print(f"累计已推送(pushed条数): {len(pushed)}")
print(f"剩余未推送: {remaining_after_count} 条")
pct = (len(pushed) / len(sitemap_urls) * 100) if sitemap_urls else 100
print(f"累计进度: {len(pushed)}/{len(sitemap_urls)} ({pct:.1f}%)")
if remain_after is not None:
    print(f"百度API剩余配额(remain): {remain_after}")
if over_quota:
    print("[WARN] 今日配额已用完，已退出")
print("==============================")
