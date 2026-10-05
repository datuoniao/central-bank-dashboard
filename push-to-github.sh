#!/usr/bin/env bash
# =============================================================
# push-to-github.sh — 用户配好代理后，一键推到 GitHub
#
# 前置：
#   1) 在本机（非受限沙箱）配好代理，且能访问 github.com
#        例：export HTTPS_PROXY=http://127.0.0.1:7890
#            export HTTP_PROXY=http://127.0.0.1:7890
#   2) 已在 GitHub 上建好空仓库（不要勾选 Initialize with README）
#
# 用法：
#   bash push-to-github.sh <你的GitHub用户名> <仓库名> [分支名]
#   例：bash push-to-github.sh zhangsan g4-dashboard main
# =============================================================
set -euo pipefail

USER_NAME="${1:?用法: bash push-to-github.sh <用户名> <仓库名> [分支]}"
REPO="${2:?用法: bash push-to-github.sh <用户名> <仓库名> [分支]}"
BRANCH="${3:-main}"

cd "$(dirname "$0")"

echo "==> 当前分支重命名为 $BRANCH"
git branch -M "$BRANCH"

echo "==> 配置远端 origin"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/${USER_NAME}/${REPO}.git"
else
  git remote add origin "https://github.com/${USER_NAME}/${REPO}.git"
fi

echo "==> 连通性自检（若失败，请确认代理已开启）"
if curl -sS -o /dev/null -w "%{http_code}\n" --max-time 15 https://github.com | grep -qE "200|30[0-9]"; then
  echo "  GitHub 可达 ✓"
else
  echo "  GitHub 不可达 ✗ —— 请先开代理并设置 HTTPS_PROXY/HTTP_PROXY"
  exit 1
fi

echo "==> 推送"
git push -u origin "$BRANCH"

echo ""
echo "完成！接下来："
echo "  1) 仓库 Settings → Actions → General → Workflow permissions 选 'Read and write'"
echo "  2) Settings → Pages → Source 选 'Deploy from a branch'，分支 $BRANCH，目录 / (root)"
echo "  3) 访问 https://${USER_NAME}.github.io/${REPO}/"
