#!/usr/bin/env python3
"""
IndexNow 推送脚本 — aihrlab.online 专用
用法:
  python3 indexnow_push.py              # 推送全部 sitemap URL（默认上限 10000/天）
  python3 indexnow_push.py --single <url>  # 推送单条 URL
  python3 indexnow_push.py --batch <url1> <url2> ...  # 推送指定列表
  python3 indexnow_push.py --key          # 显示当前密钥

支持引擎: Bing / Yandex / Naver（通过 Bing 端点聚合分发）

密钥验证: 搜索引擎会 GET {host}/{key_file} 验证所有权，
         本脚本自动在网站根目录生成该文件。
"""

import sys
import os
import json
import re
import urllib.request
import urllib.error

# ============================================================
# 配置（发布新文章后无需改这里）
# ============================================================
HOST = "www.aihrlab.online"
SITE_URL = f"https://{HOST}"

# 密钥文件名（放于网站根目录供搜索引擎 GET 验证）
KEY_FILENAME = "indexnow-key.txt"
KEY_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    KEY_FILENAME,
)

# Sitemap 路径（相对于本脚本的上级目录 = site-migrated/）
SITEMAP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sitemap.xml",
)

# IndexNot API 端点（Bing 是主入口，会转发给 Yandex/Naver）
INDEXNOW_ENDPOINTS = [
    ("Bing", "https://api.indexnow.org/indexnow"),
    # 备用：如上方不可用可切换
    # ("Bing-alt", "https://www.bing.com/indexnow"),
]

# 单次提交最大 URL 数（IndexNot 协议限制）
MAX_URLS_PER_SUBMISSION = 10000


def ensure_key_exists():
    """确保密钥文件存在；不存在则生成并写入"""
    if os.path.exists(KEY_FILE_PATH):
        with open(KEY_FILE_PATH, "r") as f:
            key = f.read().strip()
        if key:
            return key

    import uuid
    key = str(uuid.uuid4())
    os.makedirs(os.path.dirname(KEY_FILE_PATH), exist_ok=True)
    with open(KEY_FILE_PATH, "w") as f:
        f.write(key)
    print(f"已生成新 IndexNow 密钥 → {KEY_FILE_PATH}")
    print(f"⚠️  请确保 git commit 包含 {KEY_FILENAME} 并 push 到 GitHub Pages 根目录")
    return key


def get_sitemap_urls():
    """从 sitemap.xml 提取全部 URL"""
    if not os.path.exists(SITEMAP_PATH):
        print(f"ERROR: sitemap.xml 不存在 → {SITEMAP_PATH}")
        sys.exit(1)

    with open(SITEMAP_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    urls = re.findall(r"<loc>(.*?)</loc>", content)
    # 只保留本站 URL
    urls = [u for u in urls if HOST in u]
    return urls


def build_payload(key, url_list):
    """构建 IndexNow JSON payload"""
    return {
        "host": HOST,
        "key": key,
        "keyLocation": f"{SITE_URL}/{KEY_FILENAME}",
        "urlList": url_list,
    }


def submit(payload, label=""):
    """提交到所有配置的端点"""
    encoded = json.dumps(payload).encode("utf-8")
    all_ok = True

    for name, endpoint in INDEXNOW_ENDPOINTS:
        req = urllib.request.Request(
            endpoint,
            data=encoded,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                print(f"  ✅ {name}: HTTP {resp.status} — {len(payload['urlList'])} URLs")
                if body.strip():
                    print(f"     响应: {body[:200]}")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            print(f"  ❌ {name}: HTTP {e.code} {e.reason}")
            if detail:
                print(f"     详情: {detail}")
            all_ok = False
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            all_ok = False

    return all_ok


def main():
    key = ensure_key_exists()

    if len(sys.argv) < 2:
        # 默认模式：推送全部 sitemap URL
        print(f"=== IndexNow 全量推送: {HOST} ===")
        urls = get_sitemap_urls()
        if not urls:
            print("ERROR: sitemap 中未找到有效 URL")
            sys.exit(1)

        # 截断至协议上限
        urls = urls[:MAX_URLS_PER_SUBMISSION]
        payload = build_payload(key, urls)
        ok = submit(payload)
        sys.exit(0 if ok else 1)

    elif sys.argv[1] == "--key":
        print(f"IndexNow Key: {key}")
        print(f"Key Location: {SITE_URL}/{KEY_FILENAME}")

    elif sys.argv[1] == "--single":
        if len(sys.argv) < 3:
            print("Usage: indexnow_push.py --single <url>")
            sys.exit(1)
        url = sys.argv[2]
        if not url.startswith("http"):
            url = f"{SITE_URL}/{url.lstrip('/')}"
        print(f"=== IndexNow 单条推送 ===")
        payload = build_payload(key, [url])
        ok = submit(payload)
        sys.exit(0 if ok else 1)

    elif sys.argv[1] == "--batch":
        raw_urls = sys.argv[2:]
        if not raw_urls:
            print("Usage: indexnow_push.py --batch <url1> <url2> ...")
            sys.exit(1)
        urls = []
        for u in raw_urls:
            if not u.startswith("http"):
                u = f"{SITE_URL}/{u.lstrip('/')}"
            urls.append(u)
        print(f"=== IndexNow 批量推送 ({len(urls)} 条) ===")
        payload = build_payload(key, urls)
        ok = submit(payload)
        sys.exit(0 if ok else 1)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
