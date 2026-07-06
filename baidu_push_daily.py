#!/usr/bin/env python3
"""百度API每日URL推送脚本"""

import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import sys
from datetime import date

SITEMAP_PATH = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/sitemap.xml"
LOG_PATH = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/baidu_push_log.json"
API_URL = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"
MAX_PUSH = 10

# 1. 解析 sitemap 提取所有 URL 并去重
ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
tree = ET.parse(SITEMAP_PATH)
root = tree.getroot()

sitemap_urls = []
for url_elem in root.findall("s:url/s:loc", ns):
    loc = url_elem.text.strip()
    if loc not in sitemap_urls:
        sitemap_urls.append(loc)

print(f"📋 Sitemap 中共有 {len(sitemap_urls)} 个唯一 URL")

# 2. 读取已有推送记录
with open(LOG_PATH, "r", encoding="utf-8") as f:
    log = json.load(f)

pushed_set = set(log["pushed"])
print(f"📊 已推送: {len(pushed_set)} 条")

# 3. 计算未推送的 URL
remaining = [u for u in sitemap_urls if u not in pushed_set]
print(f"⏳ 剩余未推送: {len(remaining)} 条")

if len(remaining) == 0:
    print("✅ 所有 URL 已全部推送完毕！")
    today_str = date.today().isoformat()
    log["history"].append({
        "date": today_str,
        "pushed": 0,
        "failed": 0,
        "remaining_after": 0,
        "status": "ALL_COMPLETE"
    })
    log["total_pushed"] = len(pushed_set)
    log["total_urls"] = len(sitemap_urls)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    sys.exit(0)

# 4. 取前 10 个，逐条推送
to_push = remaining[:MAX_PUSH]
print(f"\n🚀 准备推送 {len(to_push)} 条 URL：")
for i, u in enumerate(to_push):
    print(f"   {i+1}. {u}")

print("\n" + "=" * 60)

success_count = 0
fail_count = 0
over_quota = False

for i, url in enumerate(to_push):
    data = url.encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, method="POST")
    req.add_header("Content-Type", "text/plain")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"✅ [{i+1}/{len(to_push)}] {url}")
            print(f"   响应: {resp_body}")
            
            # 检查是否配额耗尽
            if "over quota" in resp_body.lower():
                print("⚠️  配额已用完，停止推送！")
                over_quota = True
                break
            
            # 尝试解析 remain 数量
            try:
                resp_json = json.loads(resp_body)
                remain = resp_json.get("remain", "?")
                print(f"   今日剩余配额: {remain}")
                if remain == 0:
                    print(f"   今日配额耗尽（共推送 {success_count + 1} 条）")
            except json.JSONDecodeError:
                pass
            
            success_count += 1
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e.code)
        print(f"❌ [{i+1}/{len(to_push)}] {url} (HTTP {e.code}: {err_body})")
        if "over quota" in str(err_body).lower():
            over_quota = True
            break
        fail_count += 1
    except Exception as e:
        print(f"❌ [{i+1}/{len(to_push)}] {url} ({str(e)})")
        fail_count += 1

# 5. 更新 log
today_str = date.today().isoformat()
new_pushed = to_push[:success_count]

for u in new_pushed:
    if u not in log["pushed"]:
        log["pushed"].append(u)

log["total_pushed"] = len(log["pushed"])
log["total_urls"] = len(sitemap_urls)

new_remaining = len(sitemap_urls) - log["total_pushed"]

history_entry = {
    "date": today_str,
    "pushed": success_count,
    "failed": fail_count,
    "remaining_after": new_remaining
}

if over_quota and success_count == 0:
    history_entry["status"] = "OVER_QUOTA_NO_PUSH"

log["history"].append(history_entry)

with open(LOG_PATH, "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

# 6. 打印结果摘要
print("\n" + "=" * 60)
print("📊 推送结果摘要")
print("=" * 60)
print(f"   推送成功: {success_count} 条")
print(f"   推送失败: {fail_count} 条")
print(f"   累计推送: {log['total_pushed']}/{len(sitemap_urls)} ({log['total_pushed']/len(sitemap_urls)*100:.1f}%)")
print(f"   剩余未推: {new_remaining} 条")
if over_quota:
    print(f"   ⚠️  配额已耗尽")

print("\n✅ 日志已更新到 baidu_push_log.json")
