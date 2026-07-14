#!/bin/bash
# IndexNow 快捷推送脚本（封装 Python 版）
# Usage: ./submit-indexnow.sh              # 全量推送
#        ./submit-indexnow.sh <url>         # 单条推送
#
# 底层调用: scripts/indexnow_push.py

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Users/andyzhang/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
PUSH_SCRIPT="$SCRIPT_DIR/indexnow_push.py"

if [ ! -f "$PUSH_SCRIPT" ]; then
    echo "❌ 找不到 $PUSH_SCRIPT"
    exit 1
fi

if [ -z "$1" ]; then
    "$PYTHON" "$PUSH_SCRIPT"
else
    "$PYTHON" "$PUSH_SCRIPT" --single "$1"
fi
