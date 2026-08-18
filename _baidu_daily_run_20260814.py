#!/usr/bin/env python3
"""百度API每日URL推送 - 自动化任务执行脚本"""
import json
import os
import re
import urllib.request
import urllib.error
from urllib.parse import unquote, quote

SITE = "https://www.aihrlab.online"
TOKEN = "bpollEnMfPbbn9Ng"
SITE_DIR = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
SITEMAP = os.path.join(SITE_DIR, "sitemap.xml")
LOG_FILE = os.path.join(SITE_DIR, "baidu_push_log.json")
API_URL = f"http://data.zz.baidu.com/urls?site={SITE}&token={TOKEN}"
BATCH = 10
TODAY = "2026-08-14"


def extract_sitemap_urls(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    locs = re.findall(r"<loc>(.*?)</loc>", content, re.DOTALL)
    # 去重（保留顺序）
    seen = set()
    unique = []
    for u in locs:
        u = u.strip()
        if not u or u in seen:
            continue
        seen.add(u)
        unique.append(u)
    return unique


def normalize(url):
    """归一化用于比对：先 unquote 再统一编码（quote 默认安全字符集）。"""
    return unquote(url).strip().rstrip("/")


def push_single(url):
    """单条 URL POST 推送，返回 (success:bool, raw:str)"""
    data = url.encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "text/plain"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return True, raw
    except urllib.error.HTTPError as e:
        return False, f'{{"error":{e.code},"message":"{e.reason}"}}'
    except Exception as e:
        return False, f'{{"error":"exception","message":"{str(e)}"}}'


def main():
    # 1. sitemap URLs
    sm_urls = extract_sitemap_urls(SITEMAP)
    print(f"[1] sitemap 提取到 {len(sm_urls)} 个唯一 URL")

    # 2. 已推送列表
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log = json.load(f)
    pushed = log.get("pushed", [])
    pushed_norm = {normalize(u) for u in pushed}
    print(f"[2] 日志已推送条目 {len(pushed)} 个（归一化 {len(pushed_norm)} 个）")

    # 3. 剩余未推送
    remaining = [u for u in sm_urls if normalize(u) not in pushed_norm]
    print(f"[3] 剩余未推送 URL 数：{len(remaining)}")

    # 6. 剩余为 0 -> ALL_COMPLETE
    if len(remaining) == 0:
        print(">>> 剩余为 0，全部推送完毕，记录 ALL_COMPLETE 并退出")
        log.setdefault("history", []).append({
            "date": TODAY,
            "pushed": 0,
            "failed": 0,
            "remaining_after": 0,
            "status": "ALL_COMPLETE",
            "note": "所有 sitemap URL 已推送完毕，无新增"
        })
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"\n[结果] 推送 0 条 / 失败 0 条 / 累计进度 100% (ALL_COMPLETE)")
        return

    # 4. 取前 10 条，逐条推送
    batch = remaining[:BATCH]
    print(f"[4] 取前 {len(batch)} 条逐条推送：")
    success_urls = []
    failed_urls = []
    over_quota = False
    for i, url in enumerate(batch, 1):
        ok, raw = push_single(url)
        print(f"  {i:2d}. {url}\n      -> {raw}")
        try:
            info = json.loads(raw)
        except Exception:
            info = {}
        # 8. over quota 检测
        if not ok and ("over quota" in raw.lower() or info.get("error") == "over quota"):
            over_quota = True
        if ok and "success" in info and info["success"] > 0:
            success_urls.append(url)
        else:
            # 单条失败（非 over quota 整体退出情形，仍计入失败）
            if not (ok and "success" in info and info["success"] > 0):
                failed_urls.append(url)
        if over_quota:
            print("      >>> 检测到 over quota，停止后续推送")
            break

    pushed_count = len(success_urls)
    failed_count = len(failed_urls)

    # 8. over quota 处理：记录并重写日志后退出，不做其他操作
    if over_quota:
        log.setdefault("history", []).append({
            "date": TODAY,
            "pushed": pushed_count,
            "failed": failed_count,
            "remaining_after": len(remaining),
            "status": "OVER_QUOTA_NO_PUSH",
            "note": "今日百度配额已用完，未继续推送"
        })
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"\n[结果] OVER_QUOTA — 推送 {pushed_count} 条 / 失败 {failed_count} 条，已退出")
        return

    # 5. 更新日志
    new_pushed = list(pushed)
    for u in success_urls:
        if normalize(u) not in {normalize(x) for x in new_pushed}:
            new_pushed.append(u)
    remaining_after = len(remaining) - pushed_count
    log["pushed"] = new_pushed
    log["total_pushed"] = log.get("total_pushed", 0) + pushed_count
    log["total_urls"] = len(sm_urls)
    log.setdefault("history", []).append({
        "date": TODAY,
        "pushed": pushed_count,
        "failed": failed_count,
        "remaining_after": remaining_after,
        "status": "ALL_COMPLETE" if remaining_after == 0 else "PARTIAL"
    })

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    # 7. 打印清晰结果
    total_unique = len(sm_urls)
    covered = total_unique - remaining_after
    pct = (covered / total_unique * 100) if total_unique else 0
    print(f"\n{'='*48}")
    print(f"[结果] 推送成功 {pushed_count} 条 / 失败 {failed_count} 条")
    print(f"       剩余未推送 {remaining_after} 条")
    print(f"       累计覆盖 {covered}/{total_unique} 唯一 URL = {pct:.1f}%")
    print(f"       total_pushed 累计 = {log['total_pushed']}")
    print(f"{'='*48}")


if __name__ == "__main__":
    main()
