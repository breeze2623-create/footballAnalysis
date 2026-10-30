"""Current-season player report from the football-data skill (sports-skills: ESPN + Understat).

    python fd_player.py --player saka --team arsenal --competition premier-league
    python fd_player.py --player vinicius --team "real madrid" --competition la-liga --last 5
    python fd_player.py --player-id 280555 --team arsenal --competition premier-league

Covers the team's finished matches in the current season of one competition (or the last N):
minutes from the ESPN line-ups and timeline, goals/assists/shots/cards from ESPN, and
xG/xA/xGChain/xGBuildup/key passes plus shot locations from Understat (top-5 European leagues).
Writes outputs/fd-player-<name>-<competition>/ with report.md (Chinese), summary.json,
matches.csv and charts (season shot map, per-match xG/xA). The player is compared with his
team-mates per 90; league-wide percentiles need event data for every team, which is what
sb_player.py --benchmark does on StatsBomb open data.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import fa_common as fc
import fd_match as fd

CACHE_AFTER = timedelta(days=3)
INT_KEYS = ["goals", "penalty_goals", "assists", "shots", "shots_on_target", "key_passes", "yellow_cards", "red_cards"]
FLOAT_KEYS = ["xg", "npxg", "xa", "xg_chain", "xg_buildup"]
UNDERSTAT_KEYS = {"xg", "npxg", "xa", "xg_chain", "xg_buildup", "key_passes", "npxg_xa"}
PER90 = [("goals", "进球"), ("np_goals", "非点球进球"), ("assists", "助攻"), ("shots", "射门"), ("npxg", "npxG"),
         ("xa", "xA"), ("npxg_xa", "npxG + xA"), ("xg_chain", "xGChain"), ("xg_buildup", "xGBuildup"),
         ("key_passes", "关键传球")]
RANKED = ["npxg", "xa", "npxg_xa", "xg_chain", "xg_buildup", "key_passes", "shots"]
LABEL = dict(PER90)


def event_data(fb, name: str, event: dict) -> dict:
    """One sports-skills payload for a finished match; cached once the match is a few days old."""
    eid = str(event["id"])
    path = fc.cache_dir() / "football-data" / f"{name}-{eid}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            path.unlink(missing_ok=True)
    data = fd.call(getattr(fb, name), required=False, event_id=eid)
    start = event.get("start_time")
    settled = bool(start) and datetime.fromisoformat(start.replace("Z", "+00:00")) < datetime.now(timezone.utc) - CACHE_AFTER
    if data and settled and (name != "get_event_xg" or data.get("shots")):
        fc.write_json(path, data)
    return data


def same_person(a: str | None, b: str | None) -> bool:
    return bool(a and b) and (fc.name_matches(a, b) or fc.name_matches(b, a))


def beijing(start: str | None) -> datetime | None:
    if not start:
        return None
    return datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(fd.BEIJING)


def minutes_played(p: dict, timeline: list[dict]) -> tuple[float, bool]:
    """Minutes on the nominal clock (stoppage not counted) and whether the start minute had to be guessed."""
    pid = str(p.get("id"))

    def first(types: tuple[str, ...], key: str) -> float | None:
        return next((float(t["minute"]) for t in timeline if t.get("type") in types and t.get("minute") is not None
                     and str((t.get(key) or {}).get("id")) == pid), None)

    guessed = False
    if p.get("starter"):
        on = 0.0
    elif p.get("subbed_in"):
        on = first(("substitution",), "player_in")
        if on is None:
            on = fd.num(p.get("sub_minute"))
        if on is None:
            on, guessed = 75.0, True
    else:
        return 0.0, False
    ends = [m for m in (first(("substitution",), "player_out"), first(("red_card", "yellow_red_card"), "player"))
            if m is not None]
    end = min(ends + [90.0])
    return max(end - on, 1.0 if on else 0.0), guessed


def match_row(m: dict, p: dict, team_id: str) -> dict:
    ev, timeline = m["event"], m["timeline"]
    us = next(c for c in ev["competitors"] if str(c["team"]["id"]) == str(team_id))
    them = next(c for c in ev["competitors"] if c is not us)
    gf, ga = fd.count(us.get("score")), fd.count(them.get("score"))
    minutes, guessed = minutes_played(p, timeline)
    st = p.get("statistics") or {}
    pid = str(p.get("id"))
    shots = [s for s in m["shots"] if same_person(p.get("name"), (s.get("player") or {}).get("name"))]
    pen_events = [t for t in timeline if t.get("type") in ("penalty_goal", "penalty_missed")
                  and str((t.get("player") or {}).get("id")) == pid]
    xg = fd.num(st.get("xg"))
    if xg is None:
        npxg = None
    elif m["shots"]:
        npxg = xg - sum(float(s.get("xg") or 0) for s in shots if s.get("situation") == "Penalty")
    else:
        npxg = None if pen_events else xg
    when = beijing(ev.get("start_time"))
    return {
        "event_id": str(ev["id"]), "date": f"{when:%Y-%m-%d}" if when else "", "short_date": f"{when:%m-%d}" if when else "",
        "opponent": them["team"]["name"], "venue": "H" if us.get("qualifier") == "home" else "A",
        "score": f"{gf}-{ga}", "result": "W" if gf > ga else "D" if gf == ga else "L",
        "player_id": pid, "player": p.get("name"), "position": p.get("position"),
        "started": bool(p.get("starter")), "minutes": minutes, "minutes_guessed": guessed,
        "understat": m["understat"],
        "goals": fd.count(st.get("totalGoals")) or 0,
        "penalty_goals": sum(t.get("type") == "penalty_goal" for t in pen_events),
        "assists": fd.count(st.get("goalAssists")) or 0,
        "shots": fd.count(st.get("totalShots")) or 0, "shots_on_target": fd.count(st.get("shotsOnTarget")) or 0,
        "xg": xg, "npxg": round(npxg, 4) if npxg is not None else None, "xa": fd.num(st.get("xa")),
        "xg_chain": fd.num(st.get("xg_chain")), "xg_buildup": fd.num(st.get("xg_buildup")),
        "key_passes": fd.count(st.get("key_passes")) if m["understat"] else None,
        "yellow_cards": fd.count(st.get("yellowCards")) or 0, "red_cards": fd.count(st.get("redCards")) or 0,
        "shot_list": [dict(zip(("x", "y"), fd.understat_xy(s["coordinates"])),
                           xg=float(s.get("xg") or 0), outcome="Goal" if s.get("result") == "Goal" else s.get("result"),
                           situation=s.get("situation"), minute=s.get("minute"), opponent=them["team"]["name"])
                      for s in shots if None not in ((s.get("coordinates") or {}).get(k) for k in ("x", "y"))],
    }


def aggregate(rows: list[dict]) -> dict:
    tot: dict = {"apps": len(rows), "starts": sum(r["started"] for r in rows),
                 "minutes": sum(r["minutes"] for r in rows),
                 "minutes_understat": sum(r["minutes"] for r in rows if r["understat"])}
    for k in INT_KEYS + FLOAT_KEYS:
        vals = [r[k] for r in rows if r.get(k) is not None]
        tot[k] = (round(sum(vals), 4) if k in FLOAT_KEYS else int(sum(vals))) if vals else None
    tot["np_goals"] = tot["goals"] - tot["penalty_goals"]
    tot["npxg_xa"] = round(tot["npxg"] + tot["xa"], 4) if tot["npxg"] is not None and tot["xa"] is not None else None
    for k, _ in PER90:
        mins = tot["minutes_understat"] if k in UNDERSTAT_KEYS else tot["minutes"]
        tot[f"{k}_p90"] = round(tot[k] * 90 / mins, 3) if tot.get(k) is not None and mins else None
    np_shots = sum(1 for r in rows for s in r["shot_list"] if s["situation"] != "Penalty")
    tot["np_shots_understat"] = np_shots
    tot["npxg_per_shot"] = round(tot["npxg"] / np_shots, 3) if np_shots and tot["npxg"] is not None else None
    return tot


def resolve_player(args, matches: list[dict], team: str) -> tuple[str, str]:
    seen: dict[str, str] = {}
    for m in matches:
        for p in m["players"]:
            seen.setdefault(str(p.get("id")), p.get("name"))
    if args.player_id:
        if str(args.player_id) not in seen:
            raise SystemExit(f"ESPN player id {args.player_id} is not in {team}'s match squads for these matches")
        return str(args.player_id), seen[str(args.player_id)]
    hits = {pid: name for pid, name in seen.items() if fc.name_matches(args.player, name)}
    exact = {pid: name for pid, name in hits.items() if fc.norm(name) == fc.norm(args.player)}
    hits = exact or hits
    if not hits:
        raise SystemExit(f"no player matching {args.player!r} in {team}'s match squads. Squad: "
                         + ", ".join(sorted(seen.values())))
    if len(hits) > 1:
        raise SystemExit(f"{args.player!r} matches several {team} players; re-run with --player-id: "
                         + "; ".join(f"{name} (--player-id {pid})" for pid, name in sorted(hits.items(), key=lambda kv: kv[1])))
    return next(iter(hits.items()))


def team_ranks(target: dict, pool: dict[str, dict]) -> dict[str, tuple[int, int]]:
    out = {}
    for k in RANKED:
        col = f"{k}_p90"
        vals = sorted((a[col] for a in pool.values() if a.get(col) is not None), reverse=True)
        if target.get(col) is not None and vals:
            out[k] = (1 + sum(v > target[col] for v in vals), len(vals))
    return out


def observations(tot: dict, ranks: dict, missing_us: int, small: bool) -> list[str]:
    obs = []
    if small:
        obs.append(f"样本小：{tot['apps']} 场 {tot['minutes']:.0f} 分钟。每 90 分钟数据波动很大，只作参考，不要据此下定论。")
    if tot["npxg"] is not None:
        diff = tot["np_goals"] - tot["npxg"]
        obs.append(f"终结：非点球进球 {tot['np_goals']} vs npxG {tot['npxg']:.2f}（差 {diff:+.2f}）。单赛季（尤其赛季初）的"
                   "进球与 xG 之差主要是噪声，只能说“本样本中高于/低于预期”，不能证明终结能力强弱。")
    if tot.get("npxg_per_shot") is not None:
        obs.append(f"射门质量：{tot['np_shots_understat']} 次非点球射门，平均每脚 npxG {tot['npxg_per_shot']:.3f}。")
    if tot.get("xa_p90") is not None:
        r = ranks.get("xa")
        obs.append(f"创造：每 90 分钟 xA {tot['xa_p90']:.2f}、关键传球 {tot['key_passes_p90'] or 0:.2f}"
                   + (f"，xA/90 队内第 {r[0]}/{r[1]}" if r else "") + "。")
    if tot.get("xg_chain_p90") is not None and tot.get("xg_chain"):
        r = ranks.get("xg_chain")
        share = (tot["xg_buildup"] or 0) / tot["xg_chain"]
        role = "更多参与推进和组织（不在最后两脚）" if share >= 0.5 else "主要出现在进攻的最后环节（射门或关键传球）"
        obs.append(f"参与度：xGChain/90 {tot['xg_chain_p90']:.2f}" + (f"（队内第 {r[0]}/{r[1]}）" if r else "")
                   + f"，其中 xGBuildup 占 {share:.0%}：{role}。")
    if missing_us:
        obs.append(f"{missing_us} 场没有 Understat 数据（非五大联赛，或比赛刚结束 24-48 小时内未更新），"
                   "xG 类每 90 分钟只按有数据的场次分钟计算。")
    obs.append("本数据源没有逐事件数据：推进传球、压迫、热区等需要事件数据，历史赛事可用 sb_player.py（StatsBomb 开放数据）。")
    return obs


def report(info: dict, tot: dict, rows: list[dict], pool: dict, ranks: dict, charts: dict, min_minutes: float,
           obs: list[str]) -> str:
    lines = [f"# 球员分析：{info['player']}（{info['team']}）", "",
             f"{info['label']} · {info['scope']} · ESPN 球员 ID `{info['player_id']}`", "",
             f"出场 {tot['apps']} 场（首发 {tot['starts']}），{tot['minutes']:.0f} 分钟。"
             "数据：football-data skill（sports-skills）：ESPN 阵容/时间线/进球助攻 + Understat xG/xA/xGChain/射门位置。"
             "Understat 指标与 StatsBomb 不同模型，不可直接比较。", ""]
    table = [[label, tot.get(k), tot.get(f"{k}_p90")] for k, label in PER90]
    table += [["射正", tot["shots_on_target"], None], ["点球进球", tot["penalty_goals"], None],
              ["每脚非点球射门 npxG", tot.get("npxg_per_shot"), None],
              ["黄牌 / 红牌", f"{tot['yellow_cards']} / {tot['red_cards']}", None]]
    lines += ["## 1. 赛季汇总", "", fc.md_table(["指标", "总计", "每 90 分钟"], table), ""]
    for key, label in (("shot_map", "shot map"), ("match_bars", "xG/xA per match")):
        if key in charts:
            lines += [f"![{label}]({charts[key]})", ""]

    lines += ["## 2. 逐场", "",
              fc.md_table(["日期", "对手", "主客", "比分", "首发", "分钟", "进球", "助攻", "射门", "xG", "npxG", "xA",
                           "xGChain", "xGBuildup", "关键传球"],
                          ([r["date"], r["opponent"], "主" if r["venue"] == "H" else "客", f"{r['score']} {r['result']}",
                            "是" if r["started"] else "替补", f"{r['minutes']:.0f}" + ("*" if r["minutes_guessed"] else ""),
                            r["goals"], r["assists"], r["shots"], r["xg"], r["npxg"], r["xa"], r["xg_chain"],
                            r["xg_buildup"], r["key_passes"]] for r in rows)), ""]
    if any(r["minutes_guessed"] for r in rows):
        lines += ["\\* 替补登场时间缺失，按 15 分钟估算。", ""]

    lines += [f"## 3. 队内对比（每 90 分钟，出场 ≥ {min_minutes:.0f} 分钟，共 {len(pool)} 人）", ""]
    if ranks:
        lines += [fc.md_table(["指标", "每 90 分钟", "队内排名"],
                              ([LABEL.get(k, k), tot.get(f"{k}_p90"), f"{r[0]} / {r[1]}"] for k, r in ranks.items())), "",
                  "排名的分母是该指标有数据的队友人数（Understat 没有匹配到的球员没有 xG 类数据）。", ""]
    else:
        lines += [f"{info['player']} 出场分钟不足门槛，未参与排名。", ""]
    ordered = sorted(pool.values(), key=lambda a: -(a.get("xg_chain_p90") or 0))[:12]
    lines += [fc.md_table(["球员", "出场", "分钟", "进球", "助攻", "npxG/90", "xA/90", "xGChain/90", "xGBuildup/90",
                           "关键传球/90"],
                          ([("**" + a["player"] + "**") if a["player_id"] == info["player_id"] else a["player"],
                            a["apps"], f"{a['minutes']:.0f}", a["goals"], a["assists"], a.get("npxg_p90"),
                            a.get("xa_p90"), a.get("xg_chain_p90"), a.get("xg_buildup_p90"), a.get("key_passes_p90")]
                           for a in ordered)), ""]

    lines += ["## 4. 数据要点（自动生成，需人工复核）", ""] + [f"- {o}" for o in obs] + [""]
    lines += ["## 5. 口径与来源", "",
              "- 分钟：ESPN 首发/替补 + 时间线中的换人与红牌分钟，补时不计（名义 90 分钟）。",
              "- xG / npxG：Understat 模型（`xg.understat` / `npxg.understat`）；npxG 减去 situation=Penalty 射门的 xG。",
              "- xA：Understat 的 xA 实为“被助攻射门的 xG”（`xg_assisted.understat`），不是 Opta 的传球级 xA。",
              "- xGChain / xGBuildup：球员参与的进攻回合的 xG 之和；Buildup 不含最后两脚（射门与关键传球）。",
              "- 进球、助攻、射门、射正、牌：ESPN；点球进球：ESPN 时间线 `penalty_goal`。",
              "- 每 90 分钟 = 总计 x 90 / 分钟；Understat 指标只用有 Understat 数据的场次分钟。", ""]
    return "\n".join(lines)


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player", help="player name fragment (accents and case ignored)")
    ap.add_argument("--player-id", help="ESPN athlete ID (when a name is ambiguous)")
    ap.add_argument("--team", required=True, help="team name, e.g. arsenal")
    ap.add_argument("--competition", help="sports-skills competition slug, e.g. premier-league (default: the team's league)")
    ap.add_argument("--last", type=int, help="only the last N finished matches")
    ap.add_argument("--min-minutes", type=float, help="team-mate comparison threshold (default 30%% of available minutes, at least 180)")
    ap.add_argument("--no-charts", action="store_true")
    ap.add_argument("--out", help="output folder")
    args = ap.parse_args()
    if not args.player and not args.player_id:
        ap.error("give --player NAME or --player-id ID")
    if not fc.ensure_packages(fc.SPORTS_SKILLS_PACKAGES, "football-data (sports-skills)"):
        raise SystemExit("sports-skills is not installed; see the [self-heal] lines above")
    from sports_skills import football as fb

    team, comp = fd.find_team(fb, args.team, args.competition)
    events = fd.finished_events(fb, team["id"], comp)
    if args.last:
        events = events[-args.last:]
    if not events:
        raise SystemExit(f"no finished {comp or ''} match found for {team['name']} this season")
    fc.log(f"[football-data] {team['name']}: {len(events)} finished matches, 3 requests each (cached after a few days)")
    matches = []
    for i, ev in enumerate(events, 1):
        side = next((c.get("qualifier") for c in ev["competitors"] if str(c["team"]["id"]) == str(team["id"])), None)
        stats = event_data(fb, "get_event_players_statistics", ev)
        timeline = event_data(fb, "get_event_timeline", ev).get("timeline") or []
        xg = event_data(fb, "get_event_xg", ev)
        matches.append({
            "event": ev, "timeline": timeline,
            "players": next((t.get("players") or [] for t in stats.get("teams") or [] if t.get("qualifier") == side), []),
            "shots": [s for s in xg.get("shots") or [] if s.get("qualifier") == side],
            "understat": bool(xg.get("shots")),
        })
        if i % 5 == 0:
            fc.log(f"[football-data] {i}/{len(events)} matches read")
    pid, pname = resolve_player(args, matches, team["name"])

    per_player: dict[str, list[dict]] = defaultdict(list)
    for m in matches:
        for p in m["players"]:
            row = match_row(m, p, team["id"])
            if row["minutes"] > 0:
                per_player[row["player_id"]].append(row)
    rows = per_player.get(pid, [])
    if not rows:
        raise SystemExit(f"{pname} did not play in these {len(events)} matches")
    tot = aggregate(rows)
    min_minutes = args.min_minutes or max(180.0, 0.3 * 90 * len(events))
    pool = {}
    for p_id, p_rows in per_player.items():
        agg = aggregate(p_rows)
        if agg["minutes"] >= min_minutes:
            pool[p_id] = {**agg, "player_id": p_id, "player": p_rows[0]["player"]}
    ranks = team_ranks(tot, pool) if pid in pool else {}

    season = (fd.call(fb.get_current_season, required=False, competition_id=comp).get("season") or {}).get("name") \
        if comp else None
    season = season or (events[0].get("season") or {}).get("id") or ""
    competition = (events[0].get("competition") or {}).get("name") or comp or ""
    first, last = rows[0]["date"], rows[-1]["date"]
    info = {"player": pname, "player_id": pid, "team": team["name"], "team_id": team["id"], "competition_slug": comp,
            "competition": competition, "season": season,
            "label": season if competition and fc.norm(competition).replace(" ", "") in fc.norm(season).replace(" ", "")
            else f"{competition} {season}".strip(),
            "scope": f"{len(events)} 场已完赛比赛（{events[0]['start_time'][:10]} 至 {events[-1]['start_time'][:10]}）"
                     + (f"，本人出场 {first} 至 {last}" if first else "")}
    missing_us = sum(1 for m in matches if not m["understat"])
    obs = observations(tot, ranks, missing_us, tot["minutes"] < 450)
    shots = [s for r in rows for s in r["shot_list"]]

    out = fc.make_out_dir("fd-player", f"{pname}-{comp or 'all'}", args.out)
    charts: dict[str, str] = {}
    if fc.charts_enabled(args.no_charts):
        import fa_charts as ch

        credit = "Data: Understat + ESPN via sports-skills"
        jobs = {}
        if shots:
            jobs["shot_map"] = lambda p: ch.player_shot_map(shots, f"{pname} - {info['label']}", p, credit=credit,
                                                            xg_variant="xg.understat")
        if any(r["understat"] for r in rows):
            bars = [{**r, "date": r["short_date"]} for r in rows]
            jobs["match_bars"] = lambda p: ch.player_match_bars(bars, f"{pname}: xG and xA per match", p, credit=credit)
        for key, job in jobs.items():
            try:
                charts[key] = job(out / f"{key}.png")
            except Exception as exc:  # noqa: BLE001 - one broken chart must not lose the report
                fc.log(f"[charts] {key} failed: {type(exc).__name__}: {exc}")

    fc.write_text(out / "report.md", report(info, tot, rows, pool, ranks, charts, min_minutes, obs))
    fc.write_csv(out / "matches.csv", [{k: v for k, v in r.items() if k != "shot_list"} for r in rows])
    fc.write_json(out / "summary.json", {"info": info, "totals": tot, "team_ranks": ranks, "min_minutes": min_minutes,
                                         "teammates": sorted(pool.values(), key=lambda a: -(a.get("xg_chain_p90") or 0)),
                                         "matches": rows, "observations": obs})
    print(f"{pname} ({team['name']}) | {tot['apps']} apps, {tot['minutes']:.0f} min, {tot['goals']} G, {tot['assists']} A"
          + (f", npxG {tot['npxg']:.2f}, xA {tot['xa']:.2f}" if tot["npxg"] is not None and tot["xa"] is not None else ""))
    print(f"report: {out / 'report.md'}")
    return {"out_dir": str(out), "files": ["report.md", "summary.json", "matches.csv"] + sorted(charts.values())}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
