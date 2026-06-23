#!/bin/bash
# pre-push-check.sh — 推送前质量门禁
# 用法: ./pre-push-check.sh [main|staging]
# 放到 site-migrated/ 目录，chmod +x 后执行

set -e
cd "$(dirname "$0")"

BRANCH=${1:-main}
ERRORS=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  AIHR Lab — Pre-push Quality Gate"
echo "  Target branch: $BRANCH"
echo "=========================================="
echo ""

# ── 1. CSS 语法检查 ────────────────────────────
echo "[1/7] CSS 语法检查..."

if [ ! -f "assets/css/style.min.css" ]; then
  echo -e "  ${RED}✗ style.min.css 不存在${NC}"
  ERRORS=$((ERRORS + 1))
else
  MIN_SIZE=$(wc -c < assets/css/style.min.css)
  if [ "$MIN_SIZE" -lt 1000 ]; then
    echo -e "  ${RED}✗ style.min.css 只有 $MIN_SIZE bytes，可能为空或被截断${NC}"
    ERRORS=$((ERRORS + 1))
  else
    # 检查大括号平衡
    OPEN=$(tr -cd '{' < assets/css/style.min.css | wc -c)
    CLOSE=$(tr -cd '}' < assets/css/style.min.css | wc -c)
    if [ "$OPEN" -ne "$CLOSE" ]; then
      echo -e "  ${RED}✗ style.min.css 大括号不平衡！open=$OPEN close=$CLOSE${NC}"
      ERRORS=$((ERRORS + 1))
    else
      echo -e "  ${GREEN}✓ style.min.css OK ($MIN_SIZE bytes, braces balanced $OPEN/$CLOSE)${NC}"
    fi
  fi
fi

# ── 2. JSON 文件有效性 ─────────────────────────
echo ""
echo "[2/7] JSON 文件检查..."

for f in assets/js/article-index.json; do
  if [ -f "$f" ]; then
    if python3 -c "import json; json.load(open('$f'))" 2>/dev/null; then
      CNT=$(python3 -c "import json; print(len(json.load(open('$f'))))" 2>/dev/null || echo "?")
      echo -e "  ${GREEN}✓ $f 有效 JSON ($CNT 条记录)${NC}"
    else
      echo -e "  ${RED}✗ $f JSON 语法错误！${NC}"
      python3 -c "import json; json.load(open('$f'))" 2>&1 | head -3
      ERRORS=$((ERRORS + 1))
    fi
  fi
done

# ── 3. 引用不存在的图片 ─────────────────────────
echo ""
echo "[3/7] 图片引用检查..."

BROKEN=0
for html in $(find . -name "*.html" -not -path "./node_modules/*"); do
  for img in $(grep -oP 'src="\K[^"]+\.(png|jpg|jpeg|svg|webp)[^"]*' "$html" 2>/dev/null | grep -v "^http" | grep -v "^//" | grep -v "^data:"); do
    # 转为绝对路径
    dir=$(dirname "$html")
    # 去除查询参数
    img_clean=$(echo "$img" | sed 's/?.*//')
    if [ ! -f "$dir/$img_clean" ] && [ ! -f "$img_clean" ]; then
      echo -e "  ${YELLOW}⚠ $html 引用了不存在的图片: $img${NC}"
      BROKEN=$((BROKEN + 1))
    fi
  done
done
if [ "$BROKEN" -eq 0 ]; then
  echo -e "  ${GREEN}✓ 所有图片引用有效${NC}"
else
  echo -e "  ${YELLOW}⚠ 发现 $BROKEN 个可能损坏的图片引用（警告，不阻断）$NC"
fi

# ── 4. HTML 文件引用 CSS/JS 存在性 ──────────────
echo ""
echo "[4/7] CSS/JS 引用检查..."

BROKEN_REF=0
for html in $(find . -name "*.html" -not -path "./node_modules/*"); do
  for ref in $(grep -oP '(href|src)="\K[^"]+\.(css|js)[^"]*' "$html" 2>/dev/null | grep -v "^http" | grep -v "^//"); do
    ref_clean=$(echo "$ref" | sed 's/?.*//')
    dir=$(dirname "$html")
    if [ ! -f "$dir/$ref_clean" ] && [ ! -f "$ref_clean" ]; then
      echo -e "  ${RED}✗ $html 引用了不存在的文件: $ref${NC}"
      BROKEN_REF=$((BROKEN_REF + 1))
    fi
  done
done
if [ "$BROKEN_REF" -eq 0 ]; then
  echo -e "  ${GREEN}✓ 所有 CSS/JS 引用有效${NC}"
else
  ERRORS=$((ERRORS + BROKEN_REF))
fi

# ── 5. 重复/冲突的搜索 UI ───────────────────────
echo ""
echo "[5/7] 搜索功能冲突检查..."

for html in $(find . -name "*.html" -not -path "./node_modules/*"); do
  # 检查是否有内联搜索 HTML（会与 search.js 动态创建冲突）
  if grep -q 'id="search-overlay"' "$html" && grep -q 'search\.js' "$html"; then
    echo -e "  ${YELLOW}⚠ $html 同时包含内联搜索 HTML 和 search.js（可能冲突）${NC}"
  fi
  # 检查搜索按钮是否有对应的 JS 选择器支持
  if grep -q 'search-toggle' "$html" && [ -f "assets/js/search.js" ]; then
    if ! grep -q 'search-toggle' "assets/js/search.js"; then
      echo -e "  ${RED}✗ $html 使用 .search-toggle 但 search.js 未注册该选择器${NC}"
      ERRORS=$((ERRORS + 1))
    fi
  fi
done
if [ $? -eq 0 ]; then
  echo -e "  ${GREEN}✓ 搜索功能无冲突${NC}"
fi

# ── 6. 本地服务器渲染测试 ───────────────────────
echo ""
echo "[6/7] 本地渲染测试（启动服务器）..."

# 杀掉占用 8080 的进程
kill $(lsof -i :8080 -t) 2>/dev/null || true
sleep 1

# 启动服务器（后台）
python3 -m http.server 8080 --bind 127.0.0.1 > /dev/null 2>&1 &
SERVER_PID=$!
sleep 2

# 检查关键页面 HTTP 状态码
PAGES="index.html about.html articles/ resources/"
for page in $PAGES; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/$page" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    echo -e "  ${GREEN}✓ http://localhost:8080/$page → $HTTP_CODE${NC}"
  else
    echo -e "  ${RED}✗ http://localhost:8080/$page → $HTTP_CODE${NC}"
    ERRORS=$((ERRORS + 1))
  fi
done

# 检查 CSS 是否真的被浏览器解析（通过检查响应内容，非 0 字节）
CSS_SIZE=$(curl -s -o /dev/null -w "%{size_download}" "http://localhost:8080/assets/css/style.min.css")
if [ "$CSS_SIZE" -gt 1000 ]; then
  echo -e "  ${GREEN}✓ style.min.css 服务正常 ($CSS_SIZE bytes)${NC}"
else
  echo -e "  ${RED}✗ style.min.css 服务异常（只有 $CSS_SIZE bytes）${NC}"
  ERRORS=$((ERRORS + 1))
fi

# 停止服务器
kill $SERVER_PID 2>/dev/null || true

# ── 7. Git 变更摘要 ─────────────────────────────
echo ""
echo "[7/7] Git 变更摘要..."

if git diff --quiet && git diff --cached --quiet; then
  echo -e "  ${YELLOW}⚠ 没有已暂存的变更（先 git add）${NC}"
else
  echo "  已暂存文件："
  git diff --cached --stat | head -10
fi

# ── 结果 ────────────────────────────────────────
echo ""
echo "=========================================="
if [ "$ERRORS" -eq 0 ]; then
  echo -e "  ${GREEN}✅ 质量门禁通过，可以推送${NC}"
  echo "=========================================="
  echo ""
  echo "  执行推送："
  echo "    git push origin $BRANCH"
  echo ""
  exit 0
else
  echo -e "  ${RED}❌ 质量门禁失败，发现 $ERRORS 个错误${NC}"
  echo -e "  ${RED}  请修复后再推送！${NC}"
  echo "=========================================="
  echo ""
  exit 1
fi
