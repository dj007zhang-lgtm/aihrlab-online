#!/usr/bin/env python3
"""百度API每日URL推送 - 单次执行脚本（取前10个未推送URL逐条POST）。"""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date

ROOT = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
SITEMAP = f"{ROOT}/sitemap.xml"
LOG = f"{ROOT}/baidu_push_log.json"
API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"
TODAY = date.today().isoformat()

def extract_locs(path):
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    locs = re.findall(r"<loc>(.*?)</loc>", txt, re.S)
    # 去重，保持顺序
    seen = set()
    out = []
    for u in locs:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out

def norm(u):
    return urllib.parse.unquote(u).rstrip("/")

def main():
    sitemap_urls = extract_locs(SITEMAP)
    with open(LOG, "r", encoding="utf-8") as f:
        log = json.load(f)

    pushed = set(log.get("pushed", []))
    pushed_norm = {norm(u) for u in pushed}

    remaining = [u for u in sitemap_urls if norm(u) not in pushed_norm]
    total_urls = len(set(norm(u) for u in sitemap_urls))

    print(f"== 百度每日推送 {TODAY} ==")
    print(f"sitemap 唯一 URL 数: {total_urls}（原始 <loc> {len(sitemap_urls)} 条，去重后 {total_urls}）")
    print(f"已推送集合(归一化): {len(pushed_norm)}")
    print(f"剩余未推送(归一化比对): {len(remaining)}")

    if len(remaining) == 0:
        print("剩余为 0 —— 全部 sitemap URL 已推送完毕。")
        log.setdefault("history", []).append({
            "date": TODAY,
            "pushed": 0,
            "failed": 0,
            "remaining_after": 0,
            "status": "ALL_COMPLETE",
            "note": "No new URLs to push - all sitemap URLs already in pushed list"
        })
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("已写入 history（ALL_COMPLETE）。任务结束。")
        return

    batch = remaining[:10]
    print(f"\n取前 {len(batch)} 条进行推送:")
    for u in batch:
        print(f"  - {u}")

    success = []
    failed = []
    over_quota = False
    quota_msg = None

    for u in batch:
        data = u.encode("utf-8")
        req = urllib.request.Request(API, data=data, method="POST")
        req.add_header("Content-Type", "text/plain")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
        except Exception as e:
            body = f"ERROR: {e}"
        print(f"\nPOST {u}\n  响应: {body}")

        if "over quota" in body.lower():
            over_quota = True
            quota_msg = body
            failed.append(u)
            print("  ⚠️ 今日配额已用尽 (over quota)。")
            break

        # 百度成功返回含 success 字段；失败返回 error 字段
        try:
            rj = json.loads(body)
        except Exception:
            rj = {}
        if "error" in rj:
            failed.append(u)
            print(f"  ❌ 失败: {rj.get('message','')}")
        else:
            success.append(u)
            print("  ✅ 成功")

    # 更新日志
    if over_quota:
        log.setdefault("history", []).append({
            "date": TODAY,
            "pushed": len(success),
            "failed": len(failed),
            "remaining_after": len(remaining) - len(success),
            "status": "OVER_QUOTA_NO_PUSH",
            "note": f"over quota: {quota_msg}"
        })
        # 仍写入已成功的URL
        for u in success:
            if u not in pushed:
                log["pushed"].append(u)
        log["total_pushed"] = len(log["pushed"])
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("\n⚠️ 今日配额已用完，记录到 history 并退出，不做任何其他操作。")
        return

    for u in success:
        if u not in pushed:
            log["pushed"].append(u)

    remaining_after = len(remaining) - len(success)
    log["total_pushed"] = len(log["pushed"])

    status = "ALL_COMPLETE" if remaining_after == 0 else "PARTIAL"
    log.setdefault("history", []).append({
        "date": TODAY,
        "pushed": len(success),
        "failed": len(failed),
        "remaining_after": remaining_after,
        "status": status,
        "note": "All sitemap URLs pushed successfully" if status == "ALL_COMPLETE" else "Daily incremental push"
    })
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"\n== 推送结果 ==")
    print(f"本次推送成功: {len(success)} 条")
    print(f"本次推送失败: {len(failed)} 条")
    print(f"剩余未推送(本次后): {remaining_after} 条")
    if success:
        pct = (len(set(norm(u) for u in log['pushed'])) / total_urls) * 100
        print(f"累计进度: {len(set(norm(u) for u in log['pushed']))}/{total_urls} 唯一 URL ({pct:.1f}%)")
    print(f"状态: {status}")

if __name__ == "__main__":
    main()
