#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 matches.json 渲染成 iCalendar 订阅文件（格式对齐 Dallas Mavericks 的 ECAL 订阅：
UTC 存储时间、LOCATION、DESCRIPTION、双提醒）。已完赛场次保留，并写入比分与胜负。
"""
import json
import sys

CN_NUM = "〇一二三四五六日"


def esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line: str) -> str:
    """75 字节折行（续行空格开头），不切断 UTF-8 字符与 \\n / \\, 转义对。"""
    units, i = [], 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line):
            units.append(line[i:i + 2])
            i += 2
        else:
            units.append(line[i])
            i += 1
    chunks, cur, limit = [], "", 75
    for u in units:
        if len(cur.encode("utf-8")) + len(u.encode("utf-8")) > limit:
            chunks.append(cur)
            cur, limit = u, 74
        else:
            cur += u
    chunks.append(cur)
    return "\r\n".join([chunks[0]] + [" " + c for c in chunks[1:]])


def human_date(date_str: str) -> str:
    y, m, d = date_str.split("-")
    return f"{int(y)} 年 {int(m)} 月 {int(d)} 日"


def competition_label(m) -> str:
    comp = m["competition"]
    if comp == "常规赛":
        return "常规赛"
    if comp == "季后赛":
        return "季后赛"
    if comp == "季前赛":
        return "季前赛"
    if comp == "俱乐部杯淘汰赛":
        return "俱乐部杯·淘汰赛"
    return "俱乐部杯·小组赛"


def short_tag(m) -> str:
    comp = m["competition"]
    if comp == "常规赛":
        return ""
    if comp == "季前赛":
        return "季前赛·"
    if comp == "俱乐部杯淘汰赛":
        return "俱乐部杯淘汰赛·"
    return "俱乐部杯·"


def summary_of(m) -> str:
    tag = short_tag(m)
    side = "主场" if m["is_home"] else "客场"
    if m["status"] == "final" and m["us_score"] is not None and m["them_score"] is not None:
        if m["is_home"]:
            body = f'{m["us"]} {m["us_score"]}-{m["them_score"]} {m["them"]}'
        else:
            body = f'{m["them"]} {m["them_score"]}-{m["us_score"]} {m["us"]}'
        return f'🏀 {body}（{tag}{side}·{m["result"]}）'
    if m["is_home"]:
        return f'🏀 {m["us"]} vs {m["them"]}（{tag}{side}）'
    return f'🏀 {m["them"]} vs {m["us"]}（{tag}{side}）'


def description_of(m, generated_at) -> str:
    lines = []
    head = f'CBA 2026-2027 赛季{competition_label(m)}'
    if m["round_text"]:
        head += f' {m["round_text"]}'
    if m["stage"] and m["stage"] not in ("季后赛",):
        head += f'（{m["stage"]}）'
    lines.append(head)
    if m["status"] == "final" and m["us_score"] is not None:
        if m["is_home"]:
            score = f'{m["us"]} {m["us_score"]}-{m["them_score"]} {m["them"]}'
        else:
            score = f'{m["them"]} {m["them_score"]}-{m["us_score"]} {m["us"]}'
        lines.append(f'最终比分：{score}，上海{"主场" if m["is_home"] else "客场"}{m["result"]}')
    else:
        lines.append(f'{m["us"]}{"主场" if m["is_home"] else "客场"}对阵{m["them"]}')
    lines.append(f'比赛场馆：{m["venue"]}（{m["city"]}）')
    lines.append(f'开球时间：北京时间 {human_date(m["date_local"])} {m["time_local"]}')
    lines.append("本日历时间以 UTC 存储，手机/电脑会按所在时区自动换算成本地时间。")
    lines.append("赛程、比分每日自动同步自 CBA 官网（cbaleague.com），如有调整以官方为准。")
    lines.append(f"最后同步：{generated_at}")
    lines.append(f'官方比赛页：{m["source_url"]}')
    return "\n".join(lines)


def event_of(m, generated_at, dtstamp) -> str:
    uid = f'cba-{m["schedule_id"]}@shanghai-sharks'
    lines = [
        "BEGIN:VEVENT",
        "LAST-MODIFIED:00010101T000000Z",
        f"DTSTAMP:{dtstamp}",
        f"LOCATION:{esc(m['venue'] + ', ' + m['city'])}",
        f"DTSTART:{m['start_utc']}",
        f"DTEND:{m['end_utc']}",
        f"SUMMARY:{esc(summary_of(m))}",
        "TRANSP:TRANSPARENT",
        "SEQUENCE:0",
        f"UID:{uid}",
        "PRIORITY:5",
        "X-MICROSOFT-CDO-IMPORTANCE:1",
        "CLASS:PUBLIC",
        f"DESCRIPTION:{esc(description_of(m, generated_at))}",
    ]
    if m["status"] != "final":       # 已完赛的场次不再提醒
        lines += [
            "BEGIN:VALARM", "TRIGGER:-PT8H", "ACTION:DISPLAY",
            "DESCRIPTION:Reminder", "END:VALARM",
            "BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY",
            "DESCRIPTION:Reminder", "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return "\r\n".join(fold(l) for l in lines)


def build(snapshot: dict, out_path: str):
    matches = snapshot["matches"]
    generated = snapshot.get("generated_at_local", "")
    counts = snapshot.get("counts", {})
    desc = (f'上海久事大鲨鱼 2026-2027 赛季全部比赛（季前赛、常规赛、俱乐部杯、季后赛），'
            f'含对阵、场馆、开球时间与比分；每日自动同步自 CBA 官网。'
            f'最后同步 {generated}')
    header = [
        "BEGIN:VCALENDAR",
        "PRODID:-//E-DIARY//E-DIARY 1.0//EN",
        "VERSION:2.0",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:上海大鲨鱼 2026-2027 赛季",
        f"X-WR-CALDESC:{esc(desc)}",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "CALSCALE:GREGORIAN",
    ]
    dtstamp = snapshot.get("generated_at", "").replace("-", "").replace(":", "")
    body = [event_of(m, generated, dtstamp) for m in matches]
    ics = ("\r\n".join(fold(h) for h in header) + "\r\n"
           + "\r\n".join(body) + "\r\nEND:VCALENDAR\r\n")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write(ics)
    print(f"[build] {len(body)} 个日程 -> {out_path} ({len(ics.encode())} bytes) {counts}")
    return out_path


if __name__ == "__main__":
    snap_path = sys.argv[1] if len(sys.argv) > 1 else "matches.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "public/shanghai-sharks-2026-2027.ics"
    with open(snap_path, encoding="utf-8") as f:
        build(json.load(f), out)
