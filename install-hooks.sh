#!/bin/bash
# install-hooks.sh — 安装 Git Hooks（新机器/新克隆后运行一次）
# 用法: bash install-hooks.sh

cd "$(dirname "$0")"
HOOKS_DIR=".git/hooks"

echo "🔧 安装 Git Hooks..."

# 复制 pre-push hook
if [ -f "pre-push-check.sh" ]; then
  cp pre-push-check.sh "$HOOKS_DIR/../../pre-push-check.sh" 2>/dev/null || true
  cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
echo ""
echo "🔍 正在运行推送前质量检查..."
echo ""
$(dirname "$0")/../../pre-push-check.sh "$1" 2>&1
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
  echo ""
  echo "❌ 推送被阻止：质量检查未通过"
  echo "   修复错误后重试，或用 git push --no-verify 跳过（不推荐）"
  echo ""
  exit 1
fi
exit 0
EOF
  chmod +x "$HOOKS_DIR/pre-push"
  echo "  ✓ pre-push hook 已安装"
else
  echo "  ✗ pre-push-check.sh 不存在，请先运行 deploy.sh"
fi

echo ""
echo "✅ 安装完成"
echo ""
echo "现在每次 git push 前都会自动运行质量检查。"
echo "跳过检查（紧急时）: git push --no-verify"
