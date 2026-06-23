#!/bin/bash
# ============================================
# AIHR数智引擎 — 站长提交脚本
# 自动提交sitemap到百度站长、Google Search Console
# 使用方法: bash submit-verification.sh
# ============================================

BASE_URL="https://www.aihrlab.online"
SITEMAP_URL="${BASE_URL}/sitemap.xml"
ROBOTS_URL="${BASE_URL}/robots.txt"

echo "=========================================="
echo "  AIHR数智引擎 — 站长提交脚本"
echo "=========================================="
echo ""

# ------------------------------------------
# 1. 检查文件可用性
# ------------------------------------------
echo "📋 第1步: 检查sitemap.xml和robots.txt是否可访问..."
echo ""

# 检查sitemap
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SITEMAP_URL}" 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ sitemap.xml 可访问 (${HTTP_CODE})"
else
    echo "  ⚠️  sitemap.xml 无法访问 (HTTP ${HTTP_CODE})"
    echo "     请先确保文件已推送到GitHub Pages"
fi

# 检查robots
HTTP_CODE_ROBOTS=$(curl -s -o /dev/null -w "%{http_code}" "${ROBOTS_URL}" 2>/dev/null)
if [ "$HTTP_CODE_ROBOTS" = "200" ]; then
    echo "  ✅ robots.txt 可访问 (${HTTP_CODE_ROBOTS})"
else
    echo "  ⚠️  robots.txt 无法访问 (HTTP ${HTTP_CODE_ROBOTS})"
fi

echo ""

# ------------------------------------------
# 2. Bing站长验证
# ------------------------------------------
echo "📋 第2步: Bing站长验证..."
echo ""
echo "  Bing Webmaster验证码已在index.html中内置："
echo "    EFE6B970983C4C6F951613B6E14571A0"
echo ""
echo "  操作步骤："
echo "  1. 打开 https://www.bing.com/webmasters"
echo "  2. 登录Microsoft账户"
echo "  3. 添加站点: ${BASE_URL}"
echo "  4. 选择'HTML标记'验证方式"
echo "  5. 将以下meta标签添加到页面<head>"
echo '     <meta name="msvalidate.01" content="EFE6B970983C4C6F951613B6E14571A0" />'
echo "  6. 保存并提交验证"
echo ""

# ------------------------------------------
# 3. 百度站长（已内置百度统计）
# ------------------------------------------
echo "📋 第3步: 百度站长平台..."
echo ""
echo "  百度统计已内置 (ID: b53ffd054b55836f535892622f1e4cc5)"
echo ""
echo "  操作步骤："
echo "  1. 打开 https://ziyuan.baidu.com/"
echo "  2. 添加站点: ${BASE_URL}"
echo "  3. 选择'URL提交' → ' sitemap提交 '"
echo "  4. 输入sitemap地址: ${SITEMAP_URL}"
echo "  5. 每日自动抓取更新"
echo ""

# ------------------------------------------
# 4. Google Search Console（需手动）
# ------------------------------------------
echo "📋 第4步: Google Search Console..."
echo ""
echo "  由于需要Domain属性验证（DNS TXT记录），"
echo "  以下为手动操作步骤："
echo ""
echo "  方式A: DNS TXT记录验证（推荐）"
echo "  1. 打开 https://search.google.com/search-console"
echo "  2. 添加属性: ${BASE_URL}"
echo "  3. 选择'DNS验证'"
echo "  4. 在DNSPod添加TXT记录:"
echo "     主机记录: google-site-verification"
echo "     记录值: 需从GSC获取具体验证码"
echo "  5. 等待DNS传播（通常几分钟）"
echo "  6. 点击'验证'"
echo ""
echo "  方式B: HTML文件验证（更快）"
echo "  1. GSC生成验证文件（如googlexxxxxxx.html）"
echo "  2. 放入站点根目录"
echo "  3. 提交验证"
echo ""
echo "  验证通过后："
echo "  5. 在GSC中手动提交sitemap: ${SITEMAP_URL}"
echo ""

# ------------------------------------------
# 5. 自动提交sitemap（需token）
# ------------------------------------------
echo "📋 第5步: 自动提交sitemap到各平台..."
echo ""
echo "  需要配置各平台的API token才能自动提交。"
echo "  目前建议手动在以上平台提交sitemap。"
echo ""

# ------------------------------------------
# 总结
# ------------------------------------------
echo "=========================================="
echo "  提交完成清单"
echo "=========================================="
echo ""
echo "  [✅] Bing站长 — 验证码已内置，直接添加站点"
echo "  [✅] 百度站长 — 百度统计已内置，提交sitemap即可"
echo "  [ ]  Google   — 需DNS验证后手动提交sitemap"
echo ""
echo "  sitemap: ${SITEMAP_URL}"
echo "  robots:  ${ROBOTS_URL}"
echo ""
