"""Current-season match report from the football-data skill (sports-skills: ESPN + Understat).

    python fd_match.py --team arsenal --competition premier-league            # latest finished match
    python fd_match.py --team arsenal --competition premier-league --vs everton
    python fd_match.py --team "real madrid" --competition la-liga --nth 2      # second most recent
    python fd_match.py --event-id 401878768

Writes outputs/fd-match-<home>-vs-<away>-<id>/ with report.md (Chinese), summary.json, players.csv
and charts (Understat shot map and xG race; top-5 European leagues only).
ESPN gives team/player box scores and lineups; Understat gives shot-level xG. There is no
event-level data here, so passing networks / PPDA need sb_match.py (StatsBomb open data).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import fa_common as fc

BEIJING = timezone(timedelta(hours=8))
TEAM_STATS = [
    ("ball_possession", "控球率 %"), ("shots_total", "射门"), ("shots_on_target", "射正"),
    ("shots_blocked", "被封堵"), ("passes_accurate", "成功传球"), ("passes_total", "传球"), ("pass_pct", "传球成功率"),
    ("long_balls_accurate", "成功长传"), ("long_balls_total", "长传"), ("crosses_accurate", "成功传中"),
    ("crosses", "传中"), ("corner_kicks", "角球"), ("fouls", "犯规"), ("offsides", "越位"),
    ("yellow_cards", "黄牌"), ("red_cards", "红牌"), ("tackles_effective", "成功抢断"), ("tackles", "抢断"),
    ("interceptions", "拦截"), ("clearances", "解围"), ("goalkeeper_saves", "扑救"),
]
SITUATIONS = {"OpenPlay": "运动战", "FromCorner": "角球", "SetPiece": "定位球", "DirectFreekick": "直接任意球",
              "Penalty": "点球"}
TIMELINE_TYPES = {"goal": "GOAL", "penalty_goal": "PEN", "penalty": "PEN", "penalty_missed": "PEN MISSED",
                  "own_goal": "OG", "own goal": "OG", "yellow_card": "YELLOW", "red_card": "RED",
                  "yellow_red_card": "2nd YELLOW", "substitution": "SUB"}


def understat_xy(coords: dict) -> tuple[float, float]:
    """Understat X/Y (0-1) on the StatsBomb 120 x 80 pitch.

    Understat's Y runs from the attacking team's right touchline (0) to its left (1), like Opta;
    StatsBomb's y = 0 is the attacking team's left, so Y is flipped.
    """
    return float(coords["x"]) * 120, (1 - float(coords["y"])) * 80


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def count(v):
    f = num(v)
    return int(f) if f is not None else None


def call(fn, required: bool = True, **kwargs) -> dict:
    res = fn(**kwargs)
    if isinstance(res, dict) and res.get("status"):
        return res.get("data") or {}
    msg = res.get("message") if isinstance(res, dict) else res
    if required:
        raise fc.DataUnavailable(f"sports-skills {fn.__name__}({kwargs}) failed: {msg}")
    fc.log(f"[football-data] {fn.__name__} unavailable: {msg}")
    return {}


def find_team(fb, query: str, competition: str | None) -> tuple[dict, str | None]:
    """ESPN team for a name (an exact name match wins) and the competition slug to use with it."""
    res = call(fb.search_team, query=query, **({"competition_id": competition} if competition else {}))
    results = res.get("results") or []
    if not results:
        raise SystemExit(f"no team found for {query!r}; check the name or pass --competition (e.g. premier-league)")
    exact = [r for r in results if fc.norm(r["team"]["name"]) == fc.norm(query)]
    chosen = (exact or results)[0]
    return chosen["team"], competition or (chosen.get("competition") or {}).get("id")


def finished_events(fb, team_id: str, competition: str | None) -> list[dict]:
    """The team's finished matches in the current season of ``competition``, oldest first."""
    sched = call(fb.get_team_schedule, team_id=team_id, **({"competition_id": competition} if competition else {}))
    events = [e for e in sched.get("events") or [] if e.get("status") == "closed"]
    return sorted(events, key=lambda e: e.get("start_time") or "")


def pick_event(fb, args) -> str:
    if args.event_id:
        return str(args.event_id)
    team, comp = find_team(fb, args.team, args.competition)
    events = finished_events(fb, team["id"], comp)
    if args.vs:
        events = [e for e in events if any(fc.name_matches(args.vs, c["team"]["name"]) for c in e["competitors"])]
    if not events:
        raise SystemExit(f"no finished match found for {team['name']}"
                         + (f" vs {args.vs}" if args.vs else "") + (f" in {comp}" if comp else ""))
    if args.nth > len(events):
        raise SystemExit(f"only {len(events)} finished matches available")
    return str(events[-args.nth]["id"])


def kickoff_text(start: str | None) -> str:
    if not start:
        return "时间未知"
    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    return f"{dt.astimezone(BEIJING):%Y-%m-%d %H:%M} 北京时间（{dt.astimezone(timezone.utc):%H:%M} UTC）"


def build(fb, eid: str) -> dict:
    summary = call(fb.get_event_summary, event_id=eid)
    event = summary.get("event") or {}
    comps = sorted(event.get("competitors") or [], key=lambda c: c.get("qualifier") != "home")
    teams = [c["team"]["name"] for c in comps]
    if len(teams) != 2:
        raise fc.DataUnavailable(f"event {eid}: expected two competitors, got {teams}")
    side = {c.get("qualifier"): c["team"]["name"] for c in comps}
    stats = {side.get(t.get("qualifier"), t["team"]["name"]): t.get("statistics") or {}
             for t in call(fb.get_event_statistics, required=False, event_id=eid).get("teams") or []}
    lineups = {side.get(t.get("qualifier"), t["team"]["name"]): t
               for t in call(fb.get_event_lineups, required=False, event_id=eid).get("lineups") or []}
    xg = call(fb.get_event_xg, required=False, event_id=eid)
    players = call(fb.get_event_players_statistics, required=False, event_id=eid)
    timeline = call(fb.get_event_timeline, required=False, event_id=eid).get("timeline") or []

    shots = []
    for s in xg.get("shots") or []:
        team = side.get(s.get("qualifier"))
        coords = s.get("coordinates") or {}
        if team is None or coords.get("x") is None or coords.get("y") is None:
            continue
        x, y = understat_xy(coords)
        shots.append({"team": team, "player": (s.get("player") or {}).get("name"), "minute": f"{s.get('minute')}'",
                      "t": float(s.get("minute") or 0), "x": x, "y": y,
                      "xg": float(s.get("xg") or 0), "outcome": "Goal" if s.get("result") == "Goal" else s.get("result"),
                      "goal": s.get("result") == "Goal", "situation": s.get("situation"),
                      "shot_type": s.get("shot_type"), "assist": s.get("assist"), "last_action": s.get("last_action")})
    player_rows = []
    for t in players.get("teams") or []:
        team = side.get(t.get("qualifier"), t["team"]["name"])
        for p in t.get("players") or []:
            st = p.get("statistics") or {}
            player_rows.append({
                "player": p.get("name"), "team": team, "position": p.get("position"), "shirt": p.get("shirt_number"),
                "starter": p.get("starter"), "sub_minute": p.get("sub_minute"),
                "goals": count(st.get("totalGoals")), "assists": count(st.get("goalAssists")),
                "shots": count(st.get("totalShots")), "shots_on_target": count(st.get("shotsOnTarget")),
                "xg": num(st.get("xg")), "xa": num(st.get("xa")), "xg_chain": num(st.get("xg_chain")),
                "xg_buildup": num(st.get("xg_buildup")), "key_passes": count(st.get("key_passes")),
                "fouls_committed": count(st.get("foulsCommitted")), "fouls_suffered": count(st.get("foulsSuffered")),
                "yellow_cards": count(st.get("yellowCards")), "red_cards": count(st.get("redCards")),
                "saves": count(st.get("saves")),
            })
    return {"event_id": eid, "event": event, "teams": teams, "scores": {c["team"]["name"]: c.get("score") for c in comps},
            "stats": stats, "lineups": lineups, "xg_teams": {side.get(t.get("qualifier")): t.get("xg")
                                                             for t in xg.get("teams") or []},
            "xg_source": xg.get("source"), "shots": shots, "players": player_rows, "timeline": timeline}


def xg_split(d: dict) -> dict[str, dict]:
    out = {t: defaultdict(float) for t in d["teams"]}
    for s in d["shots"]:
        out[s["team"]][s["situation"] or "Unknown"] += s["xg"]
        out[s["team"]]["_total"] += s["xg"]
        out[s["team"]]["_shots"] += 1
        if s["situation"] != "Penalty":
            out[s["team"]]["_npxg"] += s["xg"]
            out[s["team"]]["_np_shots"] += 1
    return out


def observations(d: dict, split: dict) -> list[str]:
    home, away = d["teams"]
    sc = d["scores"]
    obs = []
    if d["shots"]:
        h, a = split[home], split[away]
        better = home if h["_npxg"] >= a["_npxg"] else away
        worse = away if better == home else home
        obs.append(f"机会质量（Understat）：{better} 的 npxG 更高（{split[better]['_npxg']:.2f} vs {split[worse]['_npxg']:.2f}，"
                   f"非点球射门 {int(split[better]['_np_shots'])} vs {int(split[worse]['_np_shots'])}）；"
                   f"实际比分 {home} {sc[home]}–{sc[away]} {away}。")
        for t in (home, away):
            s = split[t]
            if s["_total"] > 0:
                sp = s["FromCorner"] + s["SetPiece"] + s["DirectFreekick"]
                obs.append(f"{t}：每脚射门 xG {s['_total'] / max(s['_shots'], 1):.3f}；定位球（角球/任意球）xG 占比 "
                           f"{sp / s['_total']:.0%}，点球 xG {s['Penalty']:.2f}。")
    else:
        obs.append("本场没有 Understat 射门数据（只覆盖英超、西甲、德甲、意甲、法甲），以下仅基于 ESPN 统计。")
    st = d["stats"]
    if st.get(home) and st.get(away):
        poss_h, poss_a = num(st[home].get("ball_possession")), num(st[away].get("ball_possession"))
        if poss_h is not None and poss_a is not None:
            more = home if poss_h >= poss_a else away
            obs.append(f"控球：{more} 控球更多（{max(poss_h, poss_a):.0f}%）。控球率反映风格和比分状态，不能单独证明谁踢得更好，"
                       "要和机会质量（xG）一起看。")
    chain = sorted((p for p in d["players"] if p["xg_chain"]), key=lambda p: -p["xg_chain"])[:3]
    if chain:
        obs.append("参与制造机会最多（xGChain）：" + "；".join(f"{p['player']}（{p['team']}，{p['xg_chain']:.2f}）"
                                                    for p in chain) + "。")
    obs.append("本数据源没有逐事件数据：传球网络、PPDA、推进传球等战术指标请用 sb_match.py（StatsBomb 开放数据）"
               "或授权的事件数据。")
    return obs


def report(d: dict, split: dict, charts: dict) -> str:
    home, away = d["teams"]
    ev, sc = d["event"], d["scores"]
    comp = (ev.get("competition") or {}).get("name") or ""
    season = (ev.get("season") or {}).get("name") or ""
    lines = [f"# 比赛分析：{home} {sc[home]}–{sc[away]} {away}", "",
             f"{comp} {season} · {kickoff_text(ev.get('start_time'))}"
             + (f" · {ev['venue']['name']}" if (ev.get("venue") or {}).get("name") else "")
             + f" · ESPN event `{d['event_id']}`", "",
             "数据：football-data skill（sports-skills）：ESPN 比赛统计/阵容/时间线 + Understat 射门 xG。"
             "Understat xG（xg.understat）与 StatsBomb xG 模型不同，不可直接比较。", ""]
    rows = [["进球", sc[home], sc[away]]]
    if d["shots"]:
        rows += [["xG（Understat，含点球）", split[home]["_total"], split[away]["_total"]],
                 ["npxG（去掉点球）", split[home]["_npxg"], split[away]["_npxg"]],
                 ["Understat 射门数", int(split[home]["_shots"]), int(split[away]["_shots"])]]
    for key, label in TEAM_STATS:
        if key in d["stats"].get(home, {}) or key in d["stats"].get(away, {}):
            vals = [d["stats"].get(t, {}).get(key) for t in (home, away)]
            if key == "pass_pct":
                label = "传球成功率（成功/总数）"
                vals = [round(num(st.get("passes_accurate")) / num(st.get("passes_total")), 3)
                        if num(st.get("passes_accurate")) is not None and num(st.get("passes_total")) else v
                        for st, v in ((d["stats"].get(t, {}), v) for t, v in zip((home, away), vals))]
            rows.append([label, *vals])
    lines += ["## 1. 比赛概览", "", fc.md_table(["指标", home, away], rows), ""]

    events = []
    for t in d["timeline"]:
        kind = TIMELINE_TYPES.get(str(t.get("type")).lower())
        if not kind:
            continue
        minute = f"{t.get('minute')}'" + (f"+{t['added_time']}" if t.get("added_time") else "")
        who = (t.get("player") or {}).get("name") or ""
        if kind == "SUB":
            who = f"{(t.get('player_in') or {}).get('name')} on for {(t.get('player_out') or {}).get('name')}"
        events.append([minute, (t.get("team") or {}).get("name"), kind, who])
    if events:
        lines += ["### 关键事件（ESPN）", "", fc.md_table(["时间", "球队", "类型", "球员"], events), ""]

    if d["shots"]:
        lines += ["## 2. 机会分布（Understat）", "",
                  fc.md_table(["来源", home, away],
                              [[SITUATIONS.get(k, k), split[home].get(k, 0.0), split[away].get(k, 0.0)]
                               for k in SITUATIONS if split[home].get(k) or split[away].get(k)]), "",
                  "### 最佳机会（xG 前 6）", "",
                  fc.md_table(["时间", "球队", "球员", "xG", "结果", "来源", "部位", "助攻"],
                              ([s["minute"], s["team"], s["player"], s["xg"], s["outcome"],
                                SITUATIONS.get(s["situation"], s["situation"]), s["shot_type"], s["assist"] or ""]
                               for s in sorted(d["shots"], key=lambda s: -s["xg"])[:6]), digits=3), ""]
    for key, label in (("shot_map", "shot map"), ("xg_race", "xG race")):
        if key in charts:
            lines += [f"![{label}]({charts[key]})", ""]

    lines += ["## 3. 阵容（ESPN）", ""]
    for team in d["teams"]:
        lu = d["lineups"].get(team) or {}
        start = lu.get("starting") or []
        if not start:
            continue
        lines += [f"**{team}**（阵型：{lu.get('formation') or 'ESPN 未提供'}）", "",
                  fc.md_table(["号码", "位置", "球员"], ([p.get("shirt_number"), p.get("position"), p.get("name")]
                                                     for p in start)), ""]
    if d["players"]:
        ranked = sorted(d["players"], key=lambda p: (-(p["xg_chain"] or 0), -(p["xg"] or 0)))
        lines += ["## 4. 球员（按 xGChain 排序，前 16）", "",
                  fc.md_table(["球员", "球队", "位置", "首发", "进球", "助攻", "射门", "射正", "xG", "xA", "xGChain",
                               "xGBuildup", "关键传球"],
                              ([p["player"], p["team"], p["position"], "是" if p["starter"] else f"替补 {p['sub_minute'] or ''}",
                                p["goals"], p["assists"], p["shots"], p["shots_on_target"], p["xg"], p["xa"],
                                p["xg_chain"], p["xg_buildup"], p["key_passes"]] for p in ranked[:16])), "",
                  "完整字段见 `players.csv`。", ""]
    lines += ["## 5. 数据要点（自动生成，需人工复核）", ""] + [f"- {o}" for o in observations(d, split)] + [""]
    lines += ["## 6. 口径与来源", "",
              "- xG / npxG：Understat 模型（football-docs 变体 `xg.understat` / `npxg.understat`）；npxG 去掉 situation=Penalty 的射门。",
              "- xA：Understat 的 xA 实为“被助攻射门的 xG”（`xg_assisted.understat`），不是 Opta 的传球级 xA。",
              "- xGChain / xGBuildup：Understat 定义，球员参与的进攻回合的 xG（Buildup 不含最后两脚：射门和关键传球）。",
              "- 其余统计来自 ESPN，口径由 ESPN 定义，与 StatsBomb 事件计数不同。", ""]
    return "\n".join(lines)


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", help="team name, e.g. arsenal")
    ap.add_argument("--competition", help="sports-skills competition slug, e.g. premier-league, la-liga, serie-a")
    ap.add_argument("--vs", help="only matches against this opponent")
    ap.add_argument("--nth", type=int, default=1, help="1 = most recent finished match, 2 = the one before, ...")
    ap.add_argument("--event-id", help="ESPN event ID (skips the team lookup)")
    ap.add_argument("--no-charts", action="store_true")
    ap.add_argument("--out", help="output folder")
    args = ap.parse_args()
    if not args.event_id and not args.team:
        ap.error("give --team (and ideally --competition) or --event-id")
    if not fc.ensure_packages(fc.SPORTS_SKILLS_PACKAGES, "football-data (sports-skills)"):
        raise SystemExit("sports-skills is not installed; see the [self-heal] lines above")
    from sports_skills import football as fb

    eid = pick_event(fb, args)
    d = build(fb, eid)
    split = xg_split(d)
    home, away = d["teams"]
    out = fc.make_out_dir("fd-match", f"{home}-vs-{away}-{eid}", args.out)
    charts: dict[str, str] = {}
    if d["shots"] and fc.charts_enabled(args.no_charts):
        import fa_charts as ch

        totals = {t: {"goals": d["scores"][t], "xg": split[t]["_total"]} for t in d["teams"]}
        src = dict(credit="Data: Understat via sports-skills", xg_variant="xg.understat")
        jobs = {
            "shot_map": lambda p: ch.match_shot_map(d["shots"], d["teams"], totals, p, **src),
            "xg_race": lambda p: ch.xg_race({"shots": d["shots"], "period_ends": [(1, 45.0), (2, 90.0)]},
                                            d["teams"], p, **src),
        }
        for key, job in jobs.items():
            try:
                charts[key] = job(out / f"{key}.png")
            except Exception as exc:  # noqa: BLE001 - one broken chart must not lose the report
                fc.log(f"[charts] {key} failed: {type(exc).__name__}: {exc}")
    fc.write_text(out / "report.md", report(d, split, charts))
    fc.write_csv(out / "players.csv", d["players"])
    fc.write_json(out / "summary.json", {**{k: v for k, v in d.items() if k != "event"}, "event": d["event"],
                                         "xg_by_situation": {t: dict(v) for t, v in split.items()}})
    print(f"{home} {d['scores'][home]}-{d['scores'][away]} {away} | Understat xG "
          + (f"{split[home]['_total']:.2f}-{split[away]['_total']:.2f}" if d["shots"] else "n/a"))
    print(f"report: {out / 'report.md'}")
    return {"out_dir": str(out), "files": ["report.md", "summary.json", "players.csv"] + sorted(charts.values())}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
