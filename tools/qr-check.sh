#!/bin/bash
# 二维码完整性检查 - 每次部署前执行
# 规则：每篇真实文章必须有且仅有1个 article-footer-qr，无 article-qrcode 残留

set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

echo "=== 二维码完整性检查 ==="

for f in "$DIR"/articles/*.html; do
    fname=$(basename "$f")
    
    # 跳过 index.html
    [ "$fname" = "index.html" ] && continue
    
    content=$(cat "$f")
    
    # 跳过跳转页（301 redirect）
    echo "$content" | grep -q 'meta http-equiv="refresh"' && continue
    
    # 检查旧式 article-qrcode（不应出现）
    aq_count=$(echo "$content" | grep -o 'article-qrcode' | wc -l | tr -d ' ')
    if [ "$aq_count" -gt 0 ]; then
        echo "❌ $fname: 发现 $aq_count 个旧式 article-qrcode（应删除）"
        ERRORS=$((ERRORS + 1))
    fi
    
    # 检查 article-footer-qr 数量（应恰好1个，只统计HTML元素）
    af_count=$(echo "$content" | grep -o '<div class="article-footer-qr"' | wc -l | tr -d ' ')
    if [ "$af_count" -ne 1 ]; then
        echo "❌ $fname: article-footer-qr 数量=$af_count（应为1）"
        ERRORS=$((ERRORS + 1))
    fi
    
    # 检查 footer-contact 中是否有QR图片（不应有）
    if echo "$content" | grep -A 3 'footer-contact' | grep -q '<img.*qr'; then
        echo "❌ $fname: footer-contact 中仍有QR图片（应删除）"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
if [ "$ERRORS" -eq 0 ]; then
    echo "✅ 通过：所有文章二维码符合规范"
    exit 0
else
    echo "❌ 失败：共 $ERRORS 个问题需要修复"
    exit 1
fi
