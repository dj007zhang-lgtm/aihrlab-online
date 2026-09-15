#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度API每日URL推送 — 2026-09-15
遵循 automation-1782717616380 既定流程：
1. 读取 sitemap.xml，提取所有 loc URL 并去重
2. 读取 baidu_push_log.json 获取已推送列表
3. 计算剩余未推送 URL（sitemap 中但不在 log 中，unquote 归一化匹配）
4. 取前 10 条逐条 POST 推送（Content-Type: text/plain）
5. 更新 log：追加成功 URL、更新 total_pushed / total_urls、history 追加今日记录
6. 剩余为 0 → history 记录 ALL_COMPLETE；over quota → 记录并退出
"""
import json
import urllib.parse
import urllib.request
import sys
import os
from xml.etree import ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
SITEMAP = os.path.join(BASE, "sitemap.xml")
LOGPATH = os.path.join(BASE, "baidu_push_log.json")
API = "http://data.zz.baidu.com/urls?site=https://www.aihrlab.online&token=bpollEnMfPbbn9Ng"
TODAY = "2026-09-15"
BATCH = 10

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def norm(u):
    """归一化：unquote + 去末尾斜杠，用于匹配（sitemap 编码 vs log 解码重复）。"""
    u = urllib.parse.unquote(u).strip()
    return u.rstrip("/")


def load_sitemap():
    tree = ET.parse(SITEMAP)
    root = tree.getroot()
    seen = set()
    urls = []
    for url in root.iter(NS + "url"):
        loc = url.find(NS + "loc")
        if loc is not None and loc.text:
            t = loc.text.strip()
            if t not in seen:
                seen.add(t)
                urls.append(t)
    return urls


def main():
    sitemap_urls = load_sitemap()
    with open(LOGPATH, "r", encoding="utf-8") as f:
        log = json.load(f)
    pushed = log.get("pushed", [])

    pushed_set = {norm(p) for p in pushed}
    remaining = [u for u in sitemap_urls if norm(u) not in pushed_set]

    total_urls = len(sitemap_urls)
    print(f"[1] sitemap 去重后 URL 数: {total_urls}")
    print(f"[2] 已推送列表条目数: {len(pushed)} (归一化去重 {len(pushed_set)})")
    print(f"[3] 剩余未推送 URL 数: {len(remaining)}")
    if len(remaining) == 0:
        log["history"].append({
            "date": TODAY, "pushed": 0, "failed": 0,
            "remaining_after": 0, "status": "ALL_COMPLETE",
            "note": "所有 sitemap URL 已推送完毕"
        })
        log["total_urls"] = total_urls
        log["total_pushed"] = len(pushed)
        with open(LOGPATH, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print("[6] 剩余为 0 → 记录 ALL_COMPLETE，已退出。")
        return

    batch = remaining[:BATCH]
    print(f"[4] 取前 {len(batch)} 条推送:")
    for u in batch:
        print(f"    - {u}")

    success_urls = []
    failed = 0
    over_quota = False
    quota_msg = ""
    for u in batch:
        data = u.encode("utf-8")
        req = urllib.request.Request(API, data=data, method="POST")
        req.add_header("Content-Type", "text/plain")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8").strip()
            try:
                j = json.loads(body)
            except Exception:
                j = {"raw": body}
            if isinstance(j, dict) and j.get("error"):
                msg = j.get("message", "")
                if "over quota" in msg.lower() or "quota" in msg.lower():
                    over_quota = True
                    quota_msg = msg
                    failed += 1
                    print(f"    [QUOTA] {u} → {msg}")
                    break
                else:
                    failed += 1
                    print(f"    [ERR] {u} → {msg}")
                    continue
            success_urls.append(u)
            print(f"    [OK] {u} → {j}")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "ignore").strip()
            if "over quota" in err.lower():
                over_quota = True
                quota_msg = err
                failed += 1
                print(f"    [QUOTA] {u} → {err}")
                break
            failed += 1
            print(f"    [HTTPERR] {u} → {err}")
        except Exception as e:
            failed += 1
            print(f"    [EXC] {u} → {e}")

    if over_quota:
        log["history"].append({
            "date": TODAY, "pushed": 0, "failed": len(batch),
            "remaining_after": len(remaining), "status": "OVER_QUOTA_NO_PUSH",
            "note": f"百度配额已用完: {quota_msg}"
        })
        log["total_urls"] = total_urls
        with open(LOGPATH, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"[8] 今日配额已用完 (over quota): {quota_msg}")
        print("    已记录到 history，不做任何其他操作，退出。")
        return

    # 追加成功推送的 URL 到 pushed 列表
    for u in success_urls:
        pushed.append(u)
    log["pushed"] = pushed
    log["total_pushed"] = len(pushed)
    log["total_urls"] = total_urls

    remaining_after = len(remaining) - len(success_urls)
    status = "ALL_COMPLETE" if remaining_after == 0 else "PARTIAL"
    log["history"].append({
        "date": TODAY,
        "pushed": len(success_urls),
        "failed": failed,
        "remaining_after": remaining_after,
        "status": status,
        "note": "Daily incremental push; URLs: " + ", ".join(success_urls)
    })
    with open(LOGPATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"\n[结果汇总]")
    print(f"  本次推送成功: {len(success_urls)} 条")
    print(f"  本次失败: {failed} 条")
    print(f"  累计 total_pushed: {log['total_pushed']}")
    print(f"  sitemap 总数: {total_urls}")
    pct = log["total_pushed"] / total_urls * 100 if total_urls else 0
    print(f"  累计进度: {pct:.1f}%")
    print(f"  剩余未推送: {remaining_after} 条 (状态: {status})")


if __name__ == "__main__":
    main()
