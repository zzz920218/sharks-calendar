#!/bin/bash
# 一条命令上线：创建 GitHub 仓库 + 推送代码 + 首次生成 ics
#   ./setup_repo.sh ghp_xxx            # token 需勾选 public_repo（或 repo），可选 gist
#   ./setup_repo.sh ghp_xxx my-repo    # 自定义仓库名
set -euo pipefail

TOKEN="${1:-}"
REPO="${2:-sharks-calendar}"
[ -z "$TOKEN" ] && { echo "用法: ./setup_repo.sh <github-token> [repo-name]"; exit 1; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

api() { curl -sS --tlsv1.2 -H "Authorization: Bearer $TOKEN" -H "User-Agent: sharks-calendar" \
        -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" "$@"; }

echo "· 校验 token"
OWNER=$(api https://api.github.com/user | python3 -c "import json,sys;print(json.load(sys.stdin).get('login',''))")
[ -z "$OWNER" ] && { echo "✗ token 无效"; exit 1; }
SCOPES=$(curl -sS --tlsv1.2 -D - -o /dev/null -H "Authorization: Bearer $TOKEN" https://api.github.com/user \
         | tr -d '\r' | awk -F': ' 'tolower($1)=="x-oauth-scopes"{print $2}' | tr -d ' ')
echo "  账号: ${OWNER}   权限: ${SCOPES:-none}"
case ",$SCOPES," in
  *,public_repo,*|*,repo,*) : ;;
  *) echo "✗ token 缺少 public_repo / repo 权限"; exit 1;;
esac

echo "· 创建仓库 ${OWNER}/${REPO} - public, 已存在则复用"
CODE=$(api -o /tmp/repo_create.json -w "%{http_code}" -X POST \
  -d "{\"name\":\"$REPO\",\"description\":\"上海大鲨鱼 2026-2027 赛季 CBA 赛程日历（每日自动同步 CBA 官网）\",\"private\":false,\"has_issues\":false,\"has_wiki\":false,\"auto_init\":false}" \
  https://api.github.com/user/repos)
case "$CODE" in
  201) echo "  已创建";;
  422) echo "  仓库已存在，复用";;
  *)   echo "✗ 创建失败 HTTP $CODE：$(head -c 200 /tmp/repo_create.json)"; exit 1;;
esac

echo "· 本地生成一次 ics"
python3 refresh.py >/dev/null

echo "· 提交并推送"
if [ ! -d .git ]; then
  git init -q -b main
fi
git -c user.name="sharks-calendar" -c user.email="sharks@users.noreply.github.com" add -A
git -c user.name="sharks-calendar" -c user.email="sharks@users.noreply.github.com" \
    commit -q -m "feat: 上海大鲨鱼 2026-2027 赛程日历（每日自动同步）" || echo "  （无改动）"
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$OWNER/$REPO.git"
git push -q "https://x-access-token:$TOKEN@github.com/$OWNER/$REPO.git" main

RAW="https://raw.githubusercontent.com/$OWNER/$REPO/main/public/shanghai-sharks-2026-2027.ics"
echo
echo "✓ done: https://github.com/${OWNER}/${REPO}"
echo "  订阅地址（webcal）："
echo "  ${RAW/https:\/\//webcal://}"
echo
echo "  页面：https://github.com/$OWNER/$REPO/actions   ← 每天 06:15（北京时间）自动跑"
