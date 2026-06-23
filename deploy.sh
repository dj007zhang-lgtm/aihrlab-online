#!/bin/bash
# deploy.sh — 标准化部署流程
# 用法:
#   ./deploy.sh new-feature     # 新建功能分支并开始工作
#   ./deploy.sh commit "描述"   # 提交并推送到功能分支
#   ./deploy.sh merge           # 合并到 main 并推送（自动跑质量检查）
#   ./deploy.sh abort           # 放弃当前功能分支的修改

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

BRANCH_FILE=".current-feature-branch"

case "$1" in

  new-feature)
    if [ -z "$2" ]; then
      echo "用法: ./deploy.sh new-feature <分支名>"
      echo "示例: ./deploy.sh new-feature add-article-23"
      exit 1
    fi
    BRANCH="feature/$2"
    git checkout main
    git pull origin main
    git checkout -b "$BRANCH"
    echo "$BRANCH" > "$BRANCH_FILE"
    echo -e "${GREEN}✓ 已创建功能分支: $BRANCH${NC}"
    echo -e "${YELLOW}  现在可以安全地修改文件，不会影响 main${NC}"
    ;;

  commit)
    if [ ! -f "$BRANCH_FILE" ]; then
      echo -e "${RED}✗ 没有活跃的功能分支。先运行: ./deploy.sh new-feature <名称>${NC}"
      exit 1
    fi
    BRANCH=$(cat "$BRANCH_FILE")
    MSG="${2:-自动提交}"
    git add -A
    git commit -m "$MSG" || echo "(没有变更需要提交)"
    git push origin "$BRANCH"
    echo -e "${GREEN}✓ 已推送到 $BRANCH${NC}"
    ;;

  preview)
    # 本地预览（不推送）
    echo "启动本地预览服务器: http://localhost:8080"
    echo "按 Ctrl+C 停止"
    python3 -m http.server 8080 --bind 127.0.0.1
    ;;

  merge)
    if [ ! -f "$BRANCH_FILE" ]; then
      echo -e "${RED}✗ 没有活跃的功能分支${NC}"
      exit 1
    fi
    BRANCH=$(cat "$BRANCH_FILE")
    
    echo -e "${YELLOW}▶ 运行质量门禁...${NC}"
    bash pre-push-check.sh main
    if [ $? -ne 0 ]; then
      echo -e "${RED}✗ 质量检查失败，合并已取消${NC}"
      exit 1
    fi
    
    echo -e "${YELLOW}▶ 合并到 main...${NC}"
    git checkout main
    git merge "$BRANCH"
    git push origin main
    git branch -d "$BRANCH"
    rm -f "$BRANCH_FILE"
    echo -e "${GREEN}✓ 已合并到 main 并推送，功能分支已删除${NC}"
    echo -e "${GREEN}  GitHub Pages 将在 1-3 分钟内自动部署${NC}"
    ;;

  abort)
    if [ ! -f "$BRANCH_FILE" ]; then
      echo "没有活跃的功能分支"
      exit 1
    fi
    BRANCH=$(cat "$BRANCH_FILE")
    git checkout main
    git branch -D "$BRANCH" 2>/dev/null || true
    rm -f "$BRANCH_FILE"
    echo -e "${YELLOW}已放弃功能分支 $BRANCH${NC}"
    ;;

  status)
    if [ -f "$BRANCH_FILE" ]; then
      BRANCH=$(cat "$BRANCH_FILE")
      echo -e "当前功能分支: ${GREEN}$BRANCH${NC}"
      git status --short
    else
      echo "当前在 main 分支"
      git status --short
    fi
    ;;

  *)
    echo "AIHR Lab — 部署工作流"
    echo ""
    echo "用法:"
    echo "  ./deploy.sh new-feature <名称>    # 新建功能分支"
    echo "  ./deploy.sh commit \"描述\"        # 提交到功能分支"
    echo "  ./deploy.sh preview              # 本地预览"
    echo "  ./deploy.sh merge                # 质量检查 → 合并 → 推送"
    echo "  ./deploy.sh abort                # 放弃当前功能分支"
    echo "  ./deploy.sh status               # 查看当前状态"
    echo ""
    echo "推荐工作流:"
    echo "  1. ./deploy.sh new-feature add-article-23"
    echo "  2. (修改文件...)"
    echo "  3. ./deploy.sh preview  # 本地确认效果"
    echo "  4. ./deploy.sh commit \"新增文章：AI重写组织逻辑\""
    echo "  5. ./deploy.sh merge    # 自动检查 → 合并 → 上线"
    ;;
esac
