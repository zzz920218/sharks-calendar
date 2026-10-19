#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 CBA 官网（www.cbaleague.com 及其数据/杯赛后端）中「上海久事（大鲨鱼）」的全部比赛，
合并成一个快照 matches.json，供 build_ics.py 生成日历。

覆盖：季前赛 + 常规赛 46 轮 + 俱乐部杯（小组赛/第二阶段/淘汰赛）+ 季后赛（官方公布后自动出现）。
场馆优先用官方返回值，缺失时回退 venues.py 的人工核定映射。
"""
import datetime as dt
import json
import sys

import cba_api
import venues

TEAM_ID = 29125
TEAM_NAME = "上海久事"
SEASON = 2026                      # 2026-2027 赛季
GAME_SECONDS = 2 * 3600            # 日历事件时长（与示例订阅一致：2 小时）

# 常规赛三阶段
PHASES = [(1, 8, "第一阶段"), (9, 34, "第二阶段"), (35, 46, "第三阶段")]

MATCH_TYPE_NAME = {1: "常规赛", 2: "季后赛", 3: "季前赛"}


def parse_dt(date_str, time_str="00:00"):
    """北京时间字符串 -> datetime"""
    t = (time_str or "00:00").strip()
    if len(t) == 5:
        t += ":00"
    return dt.datetime.strptime(f"{date_str} {t}", "%Y-%m-%d %H:%M:%S")


def utc_stamp(local_dt: dt.datetime) -> str:
    return (local_dt - dt.timedelta(hours=8)).strftime("%Y%m%dT%H%M%SZ")


def phase_of(round_no):
    if not round_no:
        return ""
    for lo, hi, name in PHASES:
        if lo <= int(round_no) <= hi:
            return name
    return ""


def build_record(*, sid, competition, stage, round_no, date_local, time_local,
                 is_home, us, them, them_id, venue, city, status,
                 us_score=None, them_score=None, source="", score_home_away=None):
    """组装统一结构的比赛记录。score_home_away=(主队分, 客队分)"""
    local = parse_dt(date_local, time_local)
    if score_home_away and score_home_away[0] is not None and score_home_away[1] is not None:
        host_score, guest_score = score_home_away
        us_score = host_score if is_home else guest_score
        them_score = guest_score if is_home else host_score
        status = "final"
    result = None
    if us_score is not None and them_score is not None and status == "final":
        result = "胜" if us_score > them_score else "负"

    round_text = ""
    if competition.startswith("常规赛") and round_no:
        round_text = f"第 {round_no} 轮"
    elif competition.startswith("季后赛") and round_no:
        round_text = f"季后赛第 {round_no} 轮"

    return {
        "schedule_id": sid,
        "competition": competition,
        "stage": stage,
        "round": round_no,
        "round_text": round_text,
        "date_local": local.strftime("%Y-%m-%d"),
        "time_local": local.strftime("%H:%M"),
        "start_utc": utc_stamp(local),
        "end_utc": utc_stamp(local + dt.timedelta(seconds=GAME_SECONDS)),
        "is_home": bool(is_home),
        "us": us,
        "them": them,
        "them_id": them_id,
        "venue": venue,
        "city": city,
        "status": status,
        "us_score": us_score,
        "them_score": them_score,
        "result": result,
        "source": source,
        "source_url": f"https://www.cbaleague.com/data/#/matchDetail/{sid}",
    }


# --------------------------------------------------------------- 常规赛 / 季前赛 / 季后赛
def collect_league():
    rows = cba_api.portal_schedules()
    if not rows:
        raise RuntimeError("门户赛程接口返回空数据")

    # 计算每支球队的主场序号（用于新疆“前 4 个主场”这类规则）
    home_counter = {}
    home_index = {}
    for r in sorted(rows, key=lambda x: (x.get("dates") or "", x.get("time") or "")):
        hid = r.get("HomeTeamID")
        if hid is None:
            continue
        home_counter[hid] = home_counter.get(hid, 0) + 1
        home_index[r.get("ScheduleID")] = home_counter[hid]

    records = []
    for r in rows:
        hid, vid = r.get("HomeTeamID"), r.get("VisitingTeamID")
        if TEAM_ID not in (hid, vid):
            continue
        type_id = r.get("ScheduleTypeID")
        competition = MATCH_TYPE_NAME.get(type_id)
        if competition is None:            # 全明星等不关心
            continue
        is_home = hid == TEAM_ID
        date_local = r.get("dates") or ""
        time_local = r.get("time") or ""
        if not date_local:
            continue
        round_no = r.get("Round")
        group = (r.get("GroupName") or "").strip()

        if competition == "常规赛":
            stage = phase_of(round_no)
            host_id = hid
            v, c = venues.home_venue(host_id, date_local, home_index.get(r.get("ScheduleID"), 1))
        elif competition == "季后赛":
            stage = "季后赛"
            v, c = venues.home_venue(hid, date_local, home_index.get(r.get("ScheduleID"), 99))
        else:                               # 季前赛（赛会制）
            stage = group or "季前赛"
            v, c = venues.preseason_venue(group)

        official = (r.get("stadium") or "").strip()
        if official:                        # 官方已公布场馆，优先
            v = official
            if not c or c == "待定":
                c = ""

        records.append(build_record(
            sid=r.get("ScheduleID"),
            competition=competition,
            stage=stage,
            round_no=round_no,
            date_local=date_local,
            time_local=time_local,
            is_home=is_home,
            us=r.get("HomeTeamName") if is_home else r.get("VisitingTeamName"),
            them=r.get("VisitingTeamName") if is_home else r.get("HomeTeamName"),
            them_id=vid if is_home else hid,
            venue=v, city=c,
            status="final" if r.get("Status") == 4 else "scheduled",
            score_home_away=(r.get("HomeTeamScore"), r.get("VisitingTeamScore")),
            source="portal",
        ))

    # 季后赛：门户暂无赛程时，用数据站补齐（官方公布后自动出现）
    if not any(x["competition"] == "季后赛" for x in records):
        try:
            for x in cba_api.team_schedule(cba_api.DATA, TEAM_ID, SEASON, 2):
                st = x.get("scheduleTime") or ""
                if len(st) < 16:
                    continue
                date_local, time_local = st[:10], st[11:16]
                is_home = x.get("type") == 0
                records.append(build_record(
                    sid=x.get("scheduleId"),
                    competition="季后赛",
                    stage="季后赛",
                    round_no=x.get("round"),
                    date_local=date_local, time_local=time_local,
                    is_home=is_home,
                    us=TEAM_NAME, them=x.get("acrossTeamName"), them_id=x.get("acrossTeamId"),
                    venue=venues.home_venue(
                        int(x.get("homeTeamId") or 0) if is_home else int(x.get("acrossTeamId") or 0),
                        date_local, 99)[0],
                    city=venues.home_venue(
                        int(x.get("homeTeamId") or 0) if is_home else int(x.get("acrossTeamId") or 0),
                        date_local, 99)[1],
                    status="final" if x.get("points") is not None else "scheduled",
                    us_score=x.get("points"), them_score=x.get("acrossPoints"),
                    source="data",
                ))
        except Exception as exc:            # noqa: BLE001
            print(f"[warn] 季后赛赛程暂不可用：{exc}", file=sys.stderr)
    return records


# --------------------------------------------------------------- 俱乐部杯
def collect_cup():
    records = []
    group_cache = {}

    def group_of(sid, date_local):
        if date_local not in group_cache:
            try:
                group_cache[date_local] = {
                    d.get("scheduleId"): (d.get("groupName") or "")
                    for d in cba_api.schedules_of_day(cba_api.CUP, date_local)
                }
            except Exception:               # noqa: BLE001
                group_cache[date_local] = {}
        return group_cache[date_local].get(sid, "")

    for mtid in (14, 62, 15):               # 小组赛 / 小组赛第二阶段 / 淘汰赛
        try:
            rows = cba_api.team_schedule(cba_api.CUP, TEAM_ID, SEASON, mtid)
        except Exception as exc:            # noqa: BLE001
            print(f"[warn] 俱乐部杯 matchTypeId={mtid} 抓取失败：{exc}", file=sys.stderr)
            continue
        for x in rows:
            st = x.get("scheduleTime") or ""
            if len(st) < 16:
                continue
            date_local, time_local = st[:10], st[11:16]
            sid = x.get("scheduleId")
            is_home = x.get("type") == 0
            them_id = x.get("acrossTeamId")
            group = group_of(sid, date_local)
            if mtid == 15:
                competition, stage = "俱乐部杯淘汰赛", "淘汰赛"
                v, c = venues.cup_venue(group, date_local)
            else:
                competition = "俱乐部杯小组赛"
                stage = f"{group}" if group else ("小组赛第二阶段" if mtid == 62 else "小组赛")
                v, c = venues.cup_venue(group, date_local)
            records.append(build_record(
                sid=sid, competition=competition, stage=stage, round_no=None,
                date_local=date_local, time_local=time_local, is_home=is_home,
                us=TEAM_NAME, them=x.get("acrossTeamName"), them_id=them_id,
                venue=v, city=c,
                status="final" if x.get("points") is not None else "scheduled",
                us_score=x.get("points"), them_score=x.get("acrossPoints"),
                source="cup",
            ))
    return records


# --------------------------------------------------------------- 合并
def merge(*groups):
    by_id = {}
    for group in groups:
        for rec in group:
            key = rec["schedule_id"] or f'{rec["date_local"]}-{rec["them_id"]}'
            if key in by_id:                # 已有记录时只补空字段
                old = by_id[key]
                for k, v in rec.items():
                    if old.get(k) in (None, "", "待定") and v not in (None, "", "待定"):
                        old[k] = v
            else:
                by_id[key] = dict(rec)
    out = list(by_id.values())
    out.sort(key=lambda r: (r["date_local"], r["time_local"], r["schedule_id"] or 0))
    return out


def main(out_path="matches.json"):
    league = collect_league()
    cup = collect_cup()
    matches = merge(league, cup)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at_local": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "team": {"id": TEAM_ID, "name": TEAM_NAME, "season": "2026-2027"},
        "source": "https://www.cbaleague.com/",
        "counts": {},
        "matches": matches,
    }
    counts = {}
    for m in matches:
        counts[m["competition"]] = counts.get(m["competition"], 0) + 1
    payload["counts"] = counts
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[fetch] {len(matches)} 场 -> {out_path}  {counts}")
    return payload


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "matches.json")
