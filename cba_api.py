#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CBA 官网（www.cbaleague.com）数据接口的只读客户端。

三个后端：
  * PORTAL  portal-server.cbaleague.com    门户赛程（明文 JSON，含 stadium / 赛区）
  * DATA    data-server.cbaleague.com     数据站（AES-128-ECB 加密响应，含轮次/比分）
  * CUP     club-cup-server.cbaleague.com 俱乐部杯（同一套接口 + 杯赛 matchTypeId）

加密响应用系统自带 openssl 解密，无需第三方库。
"""
import base64
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

PORTAL = "https://portal-server.cbaleague.com"
DATA = "https://data-server.cbaleague.com"
CUP = "https://club-cup-server.cbaleague.com"

KEY_HEX = "uVayqL4ONKjFbVzQ".encode().hex()      # 数据站前端硬编码的 AES-128 key

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Origin": "https://www.cbaleague.com",
    "Accept": "application/json, text/plain, */*",
    "isEncrypt": "encrypt",
}


def _decrypt(text: str):
    try:
        ct = base64.b64decode(json.loads(text)) if text.lstrip().startswith('"') else base64.b64decode(text)
        p = subprocess.run(["openssl", "enc", "-d", "-aes-128-ecb", "-K", KEY_HEX],
                           input=ct, capture_output=True)
        if p.returncode == 0:
            return p.stdout.decode("utf-8", "replace")
    except Exception:                                   # noqa: BLE001
        pass
    return text


def request(host: str, path: str, params=None, data=None, retries: int = 3, timeout: int = 30):
    url = host + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = None if data is None else json.dumps(data).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=dict(HEADERS))
        req.add_header("Referer", "https://www.cbaleague.com/")
        if body is not None:
            req.add_header("Content-Type", "application/json;charset=UTF-8")
        try:
            raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
            return json.loads(_decrypt(raw))
        except Exception as exc:                        # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("CBA 接口请求失败 %s%s -> %s" % (host, path, last))


def get(host, path, params=None):
    return request(host, path, params=params)


def post(host, path, payload, params=None):
    return request(host, path, params=params, data=payload)


# ---------------------------------------------------------------- 便捷封装
def team_list():
    return get(DATA, "/api/teams/teamList")


def team_schedule(host, team_id: int, season: int, match_type_id: int, page_size: int = 100):
    """球队在某赛事类型下的全部场次（含 round / 主客 / 比分）。"""
    out, page = [], 1
    while True:
        r = post(host, "/api/team-match-datas/team-child-schedule",
                 {"teamId": team_id, "season": season, "matchTypeId": match_type_id},
                 {"pageNumber": page, "pageSize": page_size})
        recs = r.get("records", []) if isinstance(r, dict) else (r or [])
        out.extend(recs)
        total = r.get("total") if isinstance(r, dict) else len(out)
        if not recs or len(out) >= (total or 0):
            return out
        page += 1


def portal_schedules():
    """门户全量赛程（一个请求拿到全联盟所有场次）。"""
    r = get(PORTAL, "/home/home_schedules")
    return r.get("data", []) if isinstance(r, dict) else (r or [])


def schedules_of_day(host, day: str):
    return get(host, "/api/schedules/day", {"day": day, "auto": 1})
