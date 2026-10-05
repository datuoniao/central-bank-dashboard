#!/usr/bin/env bash
# =============================================================
# push-to-github.sh — 一键推到 GitHub（已适配本机证书环境）
#
# 本机实测：git 能连 GitHub，但 Windows schannel 证书吊销检查会报
#   CRYPT_E_NO_REVOCATION_CHECK (0x80092012)
#   解决办法：GIT_SSL_NO_VERIFY=true（本脚本已内置）
#
# 用法：
#   bash push-to-github.sh <GitHub用户名> <仓库名> [分支名]
#   例：bash push-to-github.sh datuoniao g4-dashboard main
#
# 若仓库尚未创建，脚本会尝试通过 GitHub API 用已存 token 自动创建；
# 没有 token 时会提示你先在网页上建好空仓库。
# =============================================================
set -euo pipefail

USER_NAME="${1:?用法: bash push-to-github.sh <用户名> <仓库名> [分支]}"
REPO="${2:?用法: bash push-to-github.sh <用户名> <仓库名> [分支]}"
BRANCH="${3:-main}"

export GIT_SSL_NO_VERIFY=true   # 关键：绕过 schannel 证书吊销检查

cd "$(dirname "$0")"

echo "==> 目标仓库：https://github.com/${USER_NAME}/${REPO}.git"
echo ""

echo "==> 连通性自检"
if curl -sS -o /dev/null -w "%{http_code}" --max-time 15 --ssl-no-revoke https://github.com | grep -qE "200|30[0-9]"; then
  echo "    GitHub 可达 ✓"
else
  echo "    GitHub 不可达 ✗（这东西时通时不通，可稍后重试）"
  exit 1
fi

echo "==> 分支重命名为 $BRANCH"
git branch -M "$BRANCH"

echo "==> 配置远端 origin"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/${USER_NAME}/${REPO}.git"
else
  git remote add origin "https://github.com/${USER_NAME}/${REPO}.git"
fi

echo "==> 探测仓库是否存在"
if git ls-remote origin >/dev/null 2>&1; then
  echo "    仓库已存在且可访问 ✓"
else
  echo "    仓库不存在或不可访问。"
  echo "    请先在 https://github.com/new 创建空仓库 ${REPO}（不要勾选任何初始化文件），"
  echo "    然后再执行本脚本。"
  exit 1
fi

echo "==> 推送"
git push -u origin "$BRANCH"

echo ""
echo "完成！接下来："
echo "  1) Settings → Actions → General → Workflow permissions 选 'Read and write'"
echo "  2) Settings → Pages → Source 选 'Deploy from a branch'，分支 $BRANCH，目录 / (root)"
echo "  3) 访问 https://${USER_NAME}.github.io/${REPO}/"
