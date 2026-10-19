# 上海大鲨鱼 2026-2027 赛季 · 赛程日历（GitHub Actions 每日自动同步）

数据每天由 **GitHub Actions** 从 CBA 官网（cbaleague.com）抓取、重新生成 `.ics` 并提交回本仓库，
**不需要任何服务器、也不需要自己的电脑开机**。

- 覆盖：季前赛 + 常规赛 46 轮（含已完赛比分）+ 俱乐部杯（小组赛；淘汰赛公布后自动加入）+ 季后赛（公布后自动加入）
- 时间以 UTC 存储，手机按定位时区自动换算；未赛场次带 8 小时前 / 30 分钟前两条提醒
- 已完赛场次保留并显示比分，不再提醒

## 订阅地址

```
webcal://raw.githubusercontent.com/zzz920218/sharks-calendar/main/public/shanghai-sharks-2026-2027.ics
```

在 iPhone / iPad / Mac 的 **Safari** 里打开 → 「订阅」→「添加」，订阅会通过 iCloud 同步到同一 Apple ID 的所有设备。

网页直接查看：https://raw.githubusercontent.com/zzz920218/sharks-calendar/main/public/shanghai-sharks-2026-2027.ics

## 自动更新

`.github/workflows/update-calendar.yml`：

| 项 | 值 |
|---|---|
| 触发 | 每天 **22:15 UTC = 北京 06:15**（GitHub 可能延迟几分钟）+ 手动 `workflow_dispatch` |
| 步骤 | `refresh.py` 抓取 → 生成 `public/shanghai-sharks-2026-2027.ics` → 自动 commit & push |
| 权限 | 仅用仓库内置 `GITHUB_TOKEN`（`contents: write`），不需要任何 secret |
| 成本 | public 仓库的 Actions 免费、无限量（单次约 30 秒） |

想立刻跑一次：仓库页 → **Actions** → `update-calendar` → **Run workflow**。

## 可选：让旧的 Gist 订阅链接也继续更新

如果你还留着早期的 gist 订阅地址，希望它跟着一起更新（这样不用重新订阅）：

1. 仓库 **Settings → Secrets and variables → Actions → New repository secret**
2. Name 填 `GIST_TOKEN`，Value 填一个勾选了 **gist** 权限的 classic token
3. 之后每次 Actions 跑完都会顺带 PATCH 那条 gist（`GIST_ID` 已写在 workflow 里）

不加也没关系：仓库里的 raw 地址本身就是完整的订阅源。

## 目录结构

```
refresh.py            一键同步：抓取 → 生成 ics →（可选）更新 gist → 写 status.json / refresh.log
fetch_matches.py      抓取并合并上海队全部比赛 → matches.json
build_ics.py          matches.json → public/shanghai-sharks-2026-2027.ics
venues.py             场馆映射（多主场球队按日期/主场序号切换）
cba_api.py            CBA 官网三个后端的只读客户端（含 AES-128-ECB 响应解密，用系统 openssl）
setup_repo.sh         一条命令创建仓库并推送（本地首次初始化用）
public/…ics           订阅文件（由 Actions 每日更新）
matches.json          赛程快照（便于 diff 审查）
status.json           最近一次同步结果
```

## 本地手动跑

```bash
python3 refresh.py            # 抓取 + 生成
python3 refresh.py --offline  # 不联网，仅用现有 matches.json 重渲染
```
