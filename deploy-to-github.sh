#!/usr/bin/env bash
# =============================================================
# deploy-to-github.sh — 用 PAT 一键：建仓库 → 推送 → 打印后续设置
#
# 用法：
#   GITHUB_TOKEN=ghp_xxx bash deploy-to-github.sh <用户名> <仓库名> [分支]
#   例：GITHUB_TOKEN=ghp_xxx bash deploy-to-github.sh datuoniao central-bank-dashboard main
#
# 说明：
#   - 需要 PAT 具备 repo 权限（classic）或 Contents+Administration 写权限（fine-grained）
#   - 已内置 GIT_SSL_NO_VERIFY=true（本机 Windows schannel 证书吊销检查会误报）
#   - 仓库已存在则跳过创建，直接推送
# =============================================================
set -euo pipefail

USER_NAME="${1:?用法: GITHUB_TOKEN=xxx bash deploy-to-github.sh <用户名> <仓库名> [分支]}"
REPO="${2:?用法: GITHUB_TOKEN=xxx bash deploy-to-github.sh <用户名> <仓库名> [分支]}"
BRANCH="${3:-main}"
TOKEN="${GITHUB_TOKEN:?请设置环境变量 GITHUB_TOKEN}"

export GIT_SSL_NO_VERIFY=true

cd "$(dirname "$0")"

echo "==== 1/4 校验 token 与身份 ===="
WHO=$(curl -sS --ssl-no-revoke -H "Authorization: Bearer $TOKEN" \
      -H "Accept: application/vnd.github+json" https://api.github.com/user)
LOGIN=$(echo "$WHO" | grep -o '"login"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
if [ -z "$LOGIN" ]; then
  echo "token 校验失败，返回："; echo "$WHO" | head -5; exit 1
fi
echo "    已认证身份：$LOGIN"

echo "==== 2/4 确保远端仓库存在 ===="
CHK=$(curl -sS --ssl-no-revoke -o /dev/null -w "%{http_code}" \
      -H "Authorization: Bearer $TOKEN" \
      "https://api.github.com/repos/${USER_NAME}/${REPO}")
if [ "$CHK" = "200" ]; then
  echo "    仓库已存在 ✓"
else
  echo "    仓库不存在，创建中…"
  CREATE=$(curl -sS --ssl-no-revoke -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"${REPO}\",\"private\":false,\"auto_init\":false,\"description\":\"G4 央行资产负债表 · M2 · 大宗商品 月度自动更新看板\"}")
  echo "$CREATE" | grep -q '"full_name"' && echo "    创建成功 ✓" || { echo "$CREATE" | head -5; exit 1; }
fi

echo "==== 3/4 配置远端并推送 ===="
git branch -M "$BRANCH"
REMOTE_URL="https://${USER_NAME}:${TOKEN}@github.com/${USER_NAME}/${REPO}.git"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi
git push -u origin "$BRANCH"
# 推完后把 token 从 remote url 里抹掉，避免明文落盘
git remote set-url origin "https://github.com/${USER_NAME}/${REPO}.git"
echo "    推送完成 ✓"

echo "==== 4/4 完成，后续手动设置 ===="
cat <<EOF

请到仓库完成两项设置：
  1) Settings → Actions → General → Workflow permissions → 选 "Read and write"
  2) Settings → Pages → Source → "Deploy from a branch"，分支 ${BRANCH}，目录 / (root)

完成后访问：https://${USER_NAME}.github.io/${REPO}/
EOF
