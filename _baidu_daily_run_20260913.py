#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度API每日URL推送 (2026-09-13)
1. 读取 sitemap.xml，提取所有URL并去重
2. 读取 baidu_push_log.json，获取已推送列表
3. 计算剩余未推送URL
4. 取前10条，逐条POST推送
5. 更新 baidu_push_log.json
6. 处理 ALL_COMPLETE / over quota 分支
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

BASE = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
SITEMAP = os.path.join(BASE, "sitemap.xml")
LOG = os.path.join(BASE, "baidu_push_log.json")
API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"

def norm(u):
    """归一化：解码百分号编码，便于编码/解码版本视为同一URL"""
    try:
        return urllib.parse.unquote(u).rstrip("/")
    except Exception:
        return u.rstrip("/")

def extract_sitemap_urls(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    urls = []
    start = 0
    while True:
        i = content.find("<loc>", start)
        if i == -1:
            break
        j = content.find("</loc>", i)
        if j == -1:
            break
        url = content[i + 5:j].strip()
        urls.append(url)
        start = j + 6
    # 去重（保留顺序）
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq

def main():
    today = date.today().isoformat()
    print(f"== 百度每日推送 {today} ==")

    # 1. sitemap
    sm_urls = extract_sitemap_urls(SITEMAP)
    total_urls = len(sm_urls)
    print(f"[1] sitemap URL 总数（去重后）: {total_urls}")

    # 2. log
    with open(LOG, "r", encoding="utf-8") as f:
        log = json.load(f)
    pushed_raw = log.get("pushed", [])
    pushed_norm = {norm(u) for u in pushed_raw}
    print(f"[2] 已推送条目数（log.pushed）: {len(pushed_raw)}")

    # 3. 剩余
    remaining = [u for u in sm_urls if norm(u) not in pushed_norm]
    print(f"[3] 剩余未推送 URL 数: {len(remaining)}")

    # ALL_COMPLETE 分支
    if len(remaining) == 0:
        print("[*] 剩余为 0 —— 全部推送完毕，记录 ALL_COMPLETE 并退出")
        log.setdefault("history", []).append({
            "date": today,
            "pushed": 0,
            "failed": 0,
            "remaining_after": 0,
            "status": "ALL_COMPLETE",
            "note": "No new URLs to push - all sitemap URLs already in pushed list"
        })
        # 同步 total_urls 到当前 sitemap 规模
        log["total_urls"] = total_urls
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"[*] 累计进度: 100.0% (total_pushed={log.get('total_pushed')}/{total_urls})")
        return

    # 4. 取前10条逐一推送
    batch = remaining[:10]
    success_urls = []
    failed_urls = []
    over_quota = False

    for u in batch:
        data = u.encode("utf-8")
        req = urllib.request.Request(API, data=data, method="POST")
        req.add_header("Content-Type", "text/plain")
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "replace")
            # 解析返回
            try:
                res = json.loads(body)
            except Exception:
                res = {}
            if "error" in res:
                err = res.get("error", "")
                if "over quota" in err.lower() or "quota" in err.lower():
                    print(f"    [配额耗尽] {u} -> {body}")
                    over_quota = True
                    failed_urls.append(u)
                    break  # 配额耗尽，停止后续推送
                else:
                    print(f"    [失败] {u} -> {body}")
                    failed_urls.append(u)
            else:
                print(f"    [成功] {u} -> {body.strip()}")
                success_urls.append(u)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            print(f"    [HTTP错误 {e.code}] {u} -> {body}")
            failed_urls.append(u)
        except Exception as e:
            print(f"    [异常] {u} -> {e}")
            failed_urls.append(u)

    # over quota 分支：记录并退出，不做任何其他操作
    if over_quota:
        print("[*] 今日配额已用完 —— 记录 over quota 并退出，不更新 pushed 列表")
        log.setdefault("history", []).append({
            "date": today,
            "pushed": 0,
            "failed": len(failed_urls),
            "remaining_after": len(remaining),
            "status": "OVER_QUOTA_NO_PUSH",
            "note": "今日百度配额已耗尽，未实际推送"
        })
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        return

    # 5. 更新 log
    for u in success_urls:
        log["pushed"].append(u)
    log["total_pushed"] = len(log["pushed"])
    log["total_urls"] = total_urls

    # 重新计算剩余
    pushed_norm_after = {norm(x) for x in log["pushed"]}
    remaining_after = len([u for u in sm_urls if norm(u) not in pushed_norm_after])

    log.setdefault("history", []).append({
        "date": today,
        "pushed": len(success_urls),
        "failed": len(failed_urls),
        "remaining_after": remaining_after,
        "status": "ALL_COMPLETE" if remaining_after == 0 else "PARTIAL",
        "note": "Daily incremental push; URLs: " + ", ".join(success_urls)
    })

    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    # 7 & 8. 打印清晰结果
    pct = (log["total_pushed"] / total_urls * 100) if total_urls else 0
    print("\n========== 推送结果 ==========")
    print(f"本次推送成功 : {len(success_urls)} 条")
    print(f"本次推送失败 : {len(failed_urls)} 条")
    print(f"累计 total_pushed : {log['total_pushed']}")
    print(f"sitemap 总 URL : {total_urls}")
    print(f"累计进度 : {pct:.1f}%")
    print(f"剩余未推送 : {remaining_after} 条")
    if remaining_after == 0:
        print("状态 : ALL_COMPLETE（全部推送完毕）")
    else:
        print("状态 : PARTIAL（仍有剩余，明继续推）")
    print("==============================")

if __name__ == "__main__":
    main()
