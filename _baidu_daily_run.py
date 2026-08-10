#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度API每日URL推送（自动化任务）
- 读取 sitemap.xml 去重 URL
- 读取 baidu_push_log.json 已推送列表
- 计算剩余（归一化 unquote 比对）
- 取前 10 条逐条 POST 百度 API
- 更新日志：pushed / total_pushed / total_urls / history
- over quota 则记录并退出
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
SITEMAP = os.path.join(BASE, "sitemap.xml")
LOG = os.path.join(BASE, "baidu_push_log.json")

API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"
HEADERS = {"Content-Type": "text/plain"}
TODAY = date.today().isoformat()
MAX_PUSH = 10


def load_sitemap_urls():
    with open(SITEMAP, "r", encoding="utf-8") as f:
        content = f.read()
    import re
    locs = re.findall(r"<loc>([^<]+)</loc>", content)
    # 去重（保留原始顺序，原样保留编码/解码形式）
    seen = set()
    out = []
    for u in locs:
        u = u.strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def norm(u):
    return urllib.parse.unquote(u.strip())


def load_log():
    with open(LOG, "r", encoding="utf-8") as f:
        return json.load(f)


def push_one(url):
    req = urllib.request.Request(API, data=url.encode("utf-8"), headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        return body
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"


def main():
    sitemap_urls = load_sitemap_urls()
    log = load_log()
    pushed = log.get("pushed", [])

    pushed_norm = set(norm(u) for u in pushed)
    remaining = [u for u in sitemap_urls if norm(u) not in pushed_norm]

    print(f"[INFO] sitemap 唯一 URL 数: {len(sitemap_urls)}")
    print(f"[INFO] log pushed 条目数: {len(pushed)}")
    print(f"[INFO] 剩余未推送 URL 数: {len(remaining)}")

    if not remaining:
        print("[INFO] 剩余为 0，全部推送完毕。记录 ALL_COMPLETE。")
        log.setdefault("history", []).append({
            "date": TODAY,
            "pushed": 0,
            "failed": 0,
            "remaining_after": 0,
            "status": "ALL_COMPLETE",
            "note": "所有 sitemap URL 已推送完毕"
        })
        log["total_urls"] = len(sitemap_urls)
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"[DONE] 累计进度: {len(pushed_norm)}/{len(sitemap_urls)} 唯一 URL (100.0%)")
        return

    batch = remaining[:MAX_PUSH]
    print(f"[INFO] 本次推送批次（前 {len(batch)} 条）:")
    for u in batch:
        print(f"   - {u}")

    success_urls = []
    failed_urls = []
    over_quota = False
    baidu_remain = None
    baidu_success = None

    for url in batch:
        raw = push_one(url)
        print(f"[API] {url}\n      -> {raw.strip()}")
        # 判断返回
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None

        if "over quota" in raw.lower():
            over_quota = True
            print("[WARN] 百度返回 over quota，配额已用完。停止推送。")
            break

        if parsed is not None:
            baidu_remain = parsed.get("remain", baidu_remain)
            baidu_success = parsed.get("success", baidu_success)
            if parsed.get("success", 0) > 0:
                success_urls.append(url)
            else:
                failed_urls.append((url, raw.strip()))
        else:
            # 非 JSON（可能是错误文本）
            failed_urls.append((url, raw.strip()))

    # 更新日志
    for u in success_urls:
        if norm(u) not in pushed_norm:
            pushed.append(u)
            pushed_norm.add(norm(u))

    if success_urls:
        log["total_pushed"] = log.get("total_pushed", 0) + len(success_urls)
    log["total_urls"] = len(sitemap_urls)

    remaining_after = len([u for u in sitemap_urls if norm(u) not in pushed_norm])

    if over_quota:
        log.setdefault("history", []).append({
            "date": TODAY,
            "pushed": len(success_urls),
            "failed": len(failed_urls),
            "remaining_after": remaining_after,
            "status": "OVER_QUOTA_NO_PUSH",
            "note": "百度今日配额已用完 (over quota)，停止推送"
        })
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("\n" + "=" * 50)
        print(f"推送结果（今日配额耗尽）:")
        print(f"  推送成功: {len(success_urls)} 条")
        print(f"  推送失败: {len(failed_urls)} 条")
        print(f"  剩余未推送: {remaining_after} 条")
        print(f"  已记录 OVER_QUOTA，退出。")
        print("=" * 50)
        return

    rec = {
        "date": TODAY,
        "pushed": len(success_urls),
        "failed": len(failed_urls),
        "remaining_after": remaining_after,
    }
    if remaining_after == 0:
        rec["status"] = "ALL_COMPLETE"
        rec["note"] = "所有 sitemap URL 已推送完毕"
    else:
        rec["status"] = "PARTIAL"
    if baidu_remain is not None:
        rec["baidu_remain"] = baidu_remain
    if baidu_success is not None:
        rec["baidu_success"] = baidu_success
    if failed_urls:
        rec["failed_urls"] = [u for u, _ in failed_urls]

    log.setdefault("history", []).append(rec)

    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    total_unique = len(sitemap_urls)
    pct = (len(pushed_norm) / total_unique * 100) if total_unique else 0
    print("\n" + "=" * 50)
    print(f"推送结果:")
    print(f"  推送成功: {len(success_urls)} 条")
    print(f"  推送失败: {len(failed_urls)} 条")
    print(f"  剩余未推送: {remaining_after} 条")
    print(f"  累计进度: {len(pushed_norm)}/{total_unique} 唯一 URL ({pct:.1f}%)")
    if baidu_remain is not None:
        print(f"  百度 API remain: {baidu_remain}")
    if failed_urls:
        print(f"  失败明细:")
        for u, r in failed_urls:
            print(f"    - {u}: {r}")
    print("=" * 50)


if __name__ == "__main__":
    main()
