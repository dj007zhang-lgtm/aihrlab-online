#!/usr/bin/env python3
"""
Google Indexing API 批量推送脚本
===============================
将 sitemap.xml 中的全部 URL 通过 Google Indexing API 推送给 Google，
加速新域名 aihrlab.online 的收录。

用法：
    1. 将服务帐号 JSON 密钥文件放在脚本同目录，命名为 gsc_service_account.json
    2. 运行：python google_indexing_push.py

配额限制：
    - URL_UPDATED: 200 条/天/站点
    - 脚本内置间隔，避免超限

前置条件：
    - Google Cloud 项目已启用 Indexing API
    - 服务帐号已添加为 GSC 站点所有者
    - 服务帐号 JSON 密钥已下载
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ——— 配置 ———
SCRIPT_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = SCRIPT_DIR / "gsc_service_account.json"
SITEMAP_URL = "https://www.aihrlab.online/sitemap.xml"
LOG_FILE = SCRIPT_DIR / "google_push_log.json"
INDEXING_API_URL = "https://indexing.googleapis.com/v3/urlNotifications:publish"
RATE_LIMIT_SECONDS = 1.0  # 每条请求间隔
REQUEST_TIMEOUT = 30  # 单次请求超时（秒）
DRY_RUN = False  # True = 只打印不发送；False = 真实调用 API


# ——— 工具函数 ———

def load_log():
    """加载推送日志，不存在则返回空字典"""
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"submissions": {}, "daily_count": {}, "last_updated": None}


def save_log(log):
    """保存推送日志"""
    log["last_updated"] = datetime.now().isoformat()
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def fetch_sitemap_urls():
    """从 sitemap.xml 提取全部 URL，过滤掉目录索引页"""
    try:
        req = urllib.request.Request(SITEMAP_URL, headers={"User-Agent": "aihrlab-bot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read().decode("utf-8")
    except Exception as e:
        print(f"❌ 无法获取 sitemap: {e}")
        sys.exit(1)

    root = ET.fromstring(xml_data)
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []

    for url_elem in root.findall(".//ns:url", ns):
        loc = url_elem.find("ns:loc", ns)
        if loc is not None and loc.text:
            url = loc.text.strip()
            # 过滤掉目录索引页
            path = urllib.parse.urlparse(url).path
            if path in ("/articles/", "/products/", "/resources/"):
                continue
            urls.append(url)

    return urls


def build_session():
    """构建已认证的 requests Session（基于 AuthorizedSession，超时可控）"""
    if not CREDENTIALS_FILE.exists():
        print(f"❌ 找不到服务帐号密钥文件: {CREDENTIALS_FILE}")
        print("   请先完成 GSC 服务帐号配置。")
        sys.exit(1)

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession

        credentials = service_account.Credentials.from_service_account_file(
            str(CREDENTIALS_FILE),
            scopes=["https://www.googleapis.com/auth/indexing"],
        )
        session = AuthorizedSession(credentials)
        return session
    except ImportError as e:
        print(f"❌ 缺少依赖库: {e}")
        print("   请运行: pip install google-auth requests")
        sys.exit(1)


def push_url(session, url, retry=2):
    """推送单个 URL 到 Google Indexing API（直接 REST 调用，超时可控）"""
    body = {
        "url": url,
        "type": "URL_UPDATED",
    }

    for attempt in range(retry):
        try:
            resp = session.post(
                INDEXING_API_URL,
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                notified_time = (
                    data.get("urlNotificationMetadata", {})
                    .get("latestUpdate", {})
                    .get("notifyTime", "unknown")
                )
                return True, notified_time, None
            elif resp.status_code == 429:
                return False, None, f"配额耗尽 (429)"
            elif resp.status_code == 403:
                error_body = resp.json()
                error_msg = error_body.get("error", {}).get("message", str(resp.text))
                return False, None, f"权限不足 (403): {error_msg}"
            elif resp.status_code == 404:
                return False, None, f"URL 不在 GSC 中 (404)"
            else:
                return False, None, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            error_str = str(e)
            if attempt < retry - 1:
                wait = 2 ** attempt
                sys.stdout.write(f"超时，{wait}s后重试... ")
                sys.stdout.flush()
                time.sleep(wait)
            else:
                return False, None, f"网络超时 (尝试 {retry} 次): {error_str[:80]}"


def main():
    print("=" * 60)
    print("Google Indexing API — aihrlab.online URL 推送")
    print("=" * 60)

    # 加载日志
    log = load_log()
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = log["daily_count"].get(today, 0)

    print(f"\n📅 日期: {today}")
    print(f"📊 今日已推送: {today_count} 条")
    print(f"📦 每日上限: 200 条 (URL_UPDATED)")
    print(f"🏷️  模式: {'DRY RUN (仅预览)' if DRY_RUN else '正式推送'}")

    if today_count >= 200:
        print("\n⚠️  今日配额已用完，请明天再运行。")
        return

    # 获取 URL 列表
    print(f"\n🔍 正在获取 sitemap: {SITEMAP_URL}")
    urls = fetch_sitemap_urls()
    print(f"✅ 从 sitemap 提取到 {len(urls)} 个 URL")

    # 筛选尚未推送或推送失败的 URL
    remaining = 200 - today_count
    to_push = []
    skipped = 0

    for url in urls:
        if url in log["submissions"]:
            last = log["submissions"][url]
            if last.get("status") == "success":
                skipped += 1
                continue
        to_push.append(url)

    print(f"📋 已成功推送: {skipped} 条（跳过）")
    print(f"📋 待推送: {len(to_push)} 条")

    if len(to_push) > remaining:
        print(f"⚠️  待推送数量超出今日剩余配额，将只推送前 {remaining} 条")
        to_push = to_push[:remaining]

    if not to_push:
        print("\n✨ 所有 URL 均已推送完成！")
        return

    if DRY_RUN:
        print(f"\n🟡 DRY RUN 模式 — 以下 URL 将会被推送：")
        for i, url in enumerate(to_push, 1):
            print(f"  {i:3d}. {url}")
        return

    # 构建认证 Session
    print("\n🔑 正在认证 Google Indexing API...")
    session = build_session()
    print("✅ 认证成功")

    # 逐条推送
    success_count = 0
    fail_count = 0
    quota_exhausted = False

    print(f"\n🚀 开始推送 {len(to_push)} 条 URL...")
    print("-" * 60)

    for i, url in enumerate(to_push, 1):
        now = datetime.now().isoformat()
        sys.stdout.write(f"  [{i:3d}/{len(to_push)}] ")
        sys.stdout.flush()

        ok, result, error = push_url(session, url)

        if ok:
            success_count += 1
            log["submissions"][url] = {
                "status": "success",
                "notified_at": result,
                "pushed_at": now,
            }
            print(f"✅ {url[:70]}")
        else:
            fail_count += 1
            log["submissions"][url] = {
                "status": "failed",
                "error": error,
                "attempted_at": now,
            }
            print(f"❌ {error}")
            if "配额耗尽" in str(error):
                quota_exhausted = True
                break

        # 速率控制
        if i < len(to_push) and not quota_exhausted:
            time.sleep(RATE_LIMIT_SECONDS)

    # 更新每日计数
    log["daily_count"][today] = today_count + success_count
    save_log(log)

    # 汇总
    print("-" * 60)
    print(f"\n📊 本次推送汇总:")
    print(f"  ✅ 成功: {success_count} 条")
    print(f"  ❌ 失败: {fail_count} 条")
    print(f"  📅 今日累计: {today_count + success_count} 条")
    if quota_exhausted:
        remaining_urls = len(to_push) - i
        print(f"  ⚠️  配额耗尽，剩余 {remaining_urls} 条请明天继续")


if __name__ == "__main__":
    main()
