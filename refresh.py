#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日自动同步入口：

1. 从 CBA 官网抓取上海久事全部比赛（季前赛 / 常规赛 / 俱乐部杯 / 季后赛）
2. 生成 matches.json（快照）与 shanghai-sharks-2026-2027.ics（日历）
3. 如配置了 GitHub Gist（config.json 或环境变量 GIST_ID + GITHUB_TOKEN），顺带推送公网订阅源

用法：
  python3 refresh.py            # 正常同步
  python3 refresh.py --offline  # 只用现有 matches.json 重新渲染 ics
"""
import datetime as dt
import json
import os
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

import build_ics          # noqa: E402
import fetch_matches      # noqa: E402

SNAPSHOT = "matches.json"
PUBLIC = "public"
ICS = os.path.join(PUBLIC, "shanghai-sharks-2026-2027.ics")
LOG = "refresh.log"


def log(msg: str):
    line = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    # 日志只留最近 500 行
    with open(LOG, encoding="utf-8") as f:
        rows = f.readlines()[-500:]
    with open(LOG, "w", encoding="utf-8") as f:
        f.writelines(rows)


def load_config():
    path = os.path.join(HERE, "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def push_gist(config):
    """可选：把 ics 推到 GitHub Gist，得到公网 webcal 订阅地址。"""
    gist_id = os.environ.get("GIST_ID") or config.get("gist_id")
    token = (os.environ.get("GIST_TOKEN") or os.environ.get("GITHUB_TOKEN")
             or os.environ.get("GH_TOKEN") or config.get("github_token"))
    if not (gist_id and token):
        return None
    filename = config.get("gist_filename") or os.path.basename(ICS)
    payload = {
        "files": {
            filename: {"content": open(ICS, encoding="utf-8").read()}
        }
    }
    p = subprocess.run(
        ["curl", "-sS", "-X", "PATCH",
         "-H", f"Authorization: token {token}",
         "-H", "Accept: application/vnd.github+json",
         "-d", json.dumps(payload),
         f"https://api.github.com/gists/{gist_id}"],
        capture_output=True, text=True)
    if p.returncode != 0:
        log(f"[gist] 推送失败：{p.stderr.strip()[:200]}")
        return None
    try:
        resp = json.loads(p.stdout)
        # 订阅要用「不带 commit hash」的固定地址，避免每次更新后 URL 变化
        raw_url = config.get("raw_url") or resp["files"][filename]["raw_url"]
        log(f"[gist] 已更新：{raw_url}")
        return raw_url
    except Exception:                              # noqa: BLE001
        log(f"[gist] 响应异常：{p.stdout[:200]}")
        return None


def write_status(ok, matches, extra=None):
    status = {
        "last_run": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": ok,
        "matches": matches,
        "ics": ICS,
    }
    if extra:
        status.update(extra)
    with open("status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)


def main():
    offline = "--offline" in sys.argv
    os.makedirs(PUBLIC, exist_ok=True)
    config = load_config()
    try:
        if offline:
            with open(SNAPSHOT, encoding="utf-8") as f:
                snapshot = json.load(f)
            log(f"[sync] 离线模式，沿用 {SNAPSHOT}（{len(snapshot['matches'])} 场）")
        else:
            snapshot = fetch_matches.main(SNAPSHOT)
            log(f"[sync] 抓取完成：{snapshot['counts']} 合计 {len(snapshot['matches'])} 场")
        build_ics.build(snapshot, ICS)
        raw = push_gist(config)
        write_status(True, len(snapshot["matches"]), {"gist_raw": raw} if raw else None)
        log("[sync] 完成")
        return 0
    except Exception as exc:                       # noqa: BLE001
        log(f"[sync] 失败：{exc}")
        log(traceback.format_exc().strip().splitlines()[-1])
        write_status(False, 0, {"error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
