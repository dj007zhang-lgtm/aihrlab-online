#!/usr/bin/env python3
"""
百度API URL批量推送工具
用法: python3 baidu_push.py
配置: 修改下面的 SITE 和 TOKEN
"""

import os
import sys
import time
import urllib.request
import urllib.error

# ============ 配置 ============
SITE = "https://www.aihrlab.online"
TOKEN = "bpollEnMfPbbn9Ng"
SITE_DIR = "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated"
BATCH_SIZE = 10  # 每批推送数量（百度限制，保守设10避免超限）
# =================================


def collect_urls():
    """收集所有需要推送的URL"""
    urls = [
        f"{SITE}/",
        f"{SITE}/about.html",
        f"{SITE}/articles.html",
        f"{SITE}/resources/",
    ]

    articles_dir = os.path.join(SITE_DIR, "articles")
    if os.path.exists(articles_dir):
        for fname in sorted(os.listdir(articles_dir)):
            if fname.endswith('.html'):
                urls.append(f"{SITE}/articles/{fname}")

    return urls


def push_urls(urls):
    """通过百度API推送URL列表"""
    api_url = f"http://data.zz.baidu.com/urls?site={SITE}&token={TOKEN}"
    
    data = "\n".join(urls).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "text/plain"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode("utf-8")
            return result
    except urllib.error.HTTPError as e:
        return f'{{"error":{e.code},"message":"{e.reason}"}}'


def main():
    all_urls = collect_urls()
    total = len(all_urls)
    print(f"共 {total} 个URL待推送\n")

    # 分批推送
    batches = [all_urls[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    total_success = 0
    total_remain = 0

    for i, batch in enumerate(batches, 1):
        print(f"--- 第 {i}/{len(batches)} 批 ({len(batch)} 个URL) ---")
        result = push_urls(batch)
        print(f"响应: {result}")

        # 解析结果
        try:
            import json
            info = json.loads(result)
            if "success" in info:
                total_success += info["success"]
            if "remain" in info:
                total_remain = info["remain"]
                if info["remain"] == 0:
                    print("\n⚠️ 今日配额已用完，停止推送")
                    break
        except (json.JSONDecodeError, KeyError):
            pass

        # 批次间间隔，避免触发频率限制
        if i < len(batches):
            time.sleep(2)

    print(f"\n{'='*40}")
    print(f"本次推送完成:")
    print(f"  成功: {total_success} 个")
    print(f"  剩余配额: {total_remain}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
