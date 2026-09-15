#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度API每日URL推送 (2026-09-10 自动化执行).

步骤:
1. 读取 sitemap.xml，提取并去重所有 <loc> URL
2. 读取 baidu_push_log.json 已推送列表
3. 计算剩余未推送 URL (sitemap 中且不在 log.pushed 中，按 unquote 归一化匹配)
4. 取前 10 条逐条 POST 推送 (text/plain)
5. 更新 baidu_push_log.json
6. 剩余为 0 时 history 记 ALL_COMPLETE
7. 打印推送结果
8. over quota 时记录并退出
"""
import json
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

SITEMAP = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/sitemap.xml"
LOG = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/baidu_push_log.json"
API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"

DATE = "2026-09-10"
BATCH = 10


def norm(u):
    return urllib.parse.unquote(u).rstrip("/")


def main():
    # 1. parse sitemap
    tree = ET.parse(SITEMAP)
    root = tree.getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    raw = []
    for loc in root.findall("s:url/s:loc", ns):
        t = (loc.text or "").strip()
        if t:
            raw.append(t)
    seen = set()
    sitemap_urls = []
    for u in raw:
        if u not in seen:
            seen.add(u)
            sitemap_urls.append(u)
    total_urls = len(sitemap_urls)

    # 2. load log
    with open(LOG, "r", encoding="utf-8") as f:
        log = json.load(f)
    pushed = log.get("pushed", [])
    pushed_norm = set(norm(p) for p in pushed)

    # 3. remaining
    remaining = [u for u in sitemap_urls if norm(u) not in pushed_norm]

    print("=" * 56)
    print(f"百度每日推送  {DATE}")
    print("=" * 56)
    print(f"sitemap 去重后 URL 数 : {total_urls}")
    print(f"log.pushed 列表数      : {len(pushed)}")
    print(f"归一化已推送去重数     : {len(pushed_norm)}")
    print(f"剩余未推送 (remaining) : {len(remaining)}")

    if not remaining:
        # 6. ALL_COMPLETE
        log["total_pushed"] = len(pushed)
        log["total_urls"] = total_urls
        rec = {
            "date": DATE,
            "pushed": 0,
            "failed": 0,
            "remaining_after": 0,
            "status": "ALL_COMPLETE",
            "note": "No new URLs to push - all sitemap URLs already in pushed list",
        }
        log.setdefault("history", []).append(rec)
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("\n[ALL_COMPLETE] 全部 sitemap URL 已推送完毕，无新 URL。")
        return

    to_push = remaining[:BATCH]
    print(f"\n取前 {len(to_push)} 条逐条推送:")
    for i, u in enumerate(to_push, 1):
        print(f"  ({i}/{len(to_push)}) {u}")

    pushed_ok = []
    failed = []
    over_quota = False
    quota_msg = None

    for u in to_push:
        data = u.encode("utf-8")
        req = urllib.request.Request(
            API, data=data, headers={"Content-Type": "text/plain"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "ignore")
            try:
                res = json.loads(body)
            except Exception:
                res = {"raw": body}
            msg = json.dumps(res, ensure_ascii=False)
            if isinstance(res, dict):
                if "error" in res or "error_code" in res:
                    # 检测 over quota
                    low = msg.lower()
                    if "over quota" in low or (
                        res.get("error") in (401, 402)
                        and "quota" in low
                    ):
                        over_quota = True
                        quota_msg = msg
                        failed.append((u, msg))
                        print(f"    -> OVER QUOTA: {msg}")
                        break  # 8. 退出，不做其他操作
                    failed.append((u, msg))
                    print(f"    -> FAIL: {msg}")
                else:
                    pushed_ok.append(u)
                    print(f"    -> OK: {msg}")
            else:
                pushed_ok.append(u)
                print(f"    -> OK: {msg}")
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", "ignore")
            low = b.lower()
            if "over quota" in low:
                over_quota = True
                quota_msg = b
                failed.append((u, b))
                print(f"    -> OVER QUOTA (HTTP {e.code}): {b}")
                break
            failed.append((u, b))
            print(f"    -> HTTP FAIL {e.code}: {b}")
        except Exception as e:
            failed.append((u, str(e)))
            print(f"    -> EXC: {e}")

    if over_quota:
        # 8. 记录到 history 并退出，不做任何其他操作
        rec = {
            "date": DATE,
            "pushed": 0,
            "failed": len(failed),
            "remaining_after": len(remaining),
            "status": "OVER_QUOTA_NO_PUSH",
            "note": f"今日百度配额已耗尽: {quota_msg}",
        }
        log.setdefault("history", []).append(rec)
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("\n[OVER QUOTA] 记录到 history 并退出，未更新 pushed 列表。")
        return

    # 5. 更新 log
    for u in pushed_ok:
        pushed.append(u)
    log["pushed"] = pushed
    log["total_pushed"] = len(pushed)
    log["total_urls"] = total_urls
    remaining_after = len(remaining) - len(pushed_ok)
    rec = {
        "date": DATE,
        "pushed": len(pushed_ok),
        "failed": len(failed),
        "remaining_after": remaining_after,
        "status": "ALL_COMPLETE" if remaining_after == 0 else "PARTIAL",
        "note": "Daily incremental push"
        + ("" if not pushed_ok else f"; URLs: {', '.join(pushed_ok)}"),
    }
    log.setdefault("history", []).append(rec)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    # 7. 打印结果
    total_pushed = len(pushed)
    pct = (total_pushed / total_urls * 100) if total_urls else 0
    print("\n" + "=" * 56)
    print("推送结果汇总")
    print("=" * 56)
    print(f"本次推送成功 : {len(pushed_ok)}")
    print(f"本次推送失败 : {len(failed)}")
    print(f"累计已推送   : {total_pushed} / {total_urls}")
    print(f"累计进度     : {pct:.1f}%")
    print(f"剩余还未推送 : {remaining_after}")
    if pushed_ok:
        print(f"\n已推送 URL:")
        for u in pushed_ok:
            print(f"  + {u}")
    print("=" * 56)


if __name__ == "__main__":
    main()
