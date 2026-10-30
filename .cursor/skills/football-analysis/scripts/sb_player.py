"""Player report from StatsBomb open data (event level).

    python sb_player.py --player messi --competition 43 --season 106
    python sb_player.py --player messi --competition 43 --season 106 --benchmark
    python sb_player.py --player "mac allister" --match 3869685
    python sb_player.py --player-id 5503 --competition 43 --season 106 --team argentina

Writes outputs/player-<name>-<competition>-<season>/ with report.md (Chinese), summary.json,
matches.csv and charts (shot map, action heatmap, progressive actions, and with --benchmark a
percentile pizza against players of the same position group with enough minutes).
--benchmark downloads the events of every match in the season (World Cup 2022: 64 files, ~230 MB).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

import fa_common as fc
import fa_metrics as fm

PER90 = {
    "npxg": ("npxG", "npxG"),
    "np_goals": ("非点球进球", "NP goals"),
    "shots": ("射门", "Shots"),
    "xg_assisted": ("xG assisted", "xG assisted"),
    "key_passes": ("关键传球", "Key passes"),
    "box_receptions": ("禁区内接球", "Box receptions"),
    "dribbles_completed": ("成功过人", "Dribbles won"),
    "progressive_passes": ("推进传球", "Prog. passes"),
    "progressive_carries": ("推进带球", "Prog. carries"),
    "deep_progressions": ("进入前场三区（传+带）", "Final-third entries"),
    "box_entries": ("进入禁区（传+带）", "Box entries"),
    "xt_added": ("xT added", "xT added"),
    "passes_completed": ("成功传球", "Passes completed"),
    "pressures": ("压迫", "Pressures"),
    "pressures_att_third": ("前场三区压迫", "Att. third pressures"),
    "tackles_won": ("抢断成功", "Tackles won"),
    "interceptions": ("拦截", "Interceptions"),
    "ball_recoveries": ("夺回球权", "Recoveries"),
    "blocks": ("封堵", "Blocks"),
    "clearances": ("解围", "Clearances"),
}
RATIOS = {
    "pass_completion": ("传球成功率", "Pass completion", "passes_completed", "passes"),
    "dribble_success": ("过人成功率", "Dribble success", "dribbles_completed", "dribbles"),
}
POSITION_GROUPS = {
    "GK": ["Goalkeeper"],
    "CB": ["Center Back", "Left Center Back", "Right Center Back"],
    "FB": ["Left Back", "Right Back", "Left Wing Back", "Right Wing Back"],
    "MF": ["Center Defensive Midfield", "Left Defensive Midfield", "Right Defensive Midfield",
           "Center Midfield", "Left Center Midfield", "Right Center Midfield"],
    "AM/W": ["Center Attacking Midfield", "Left Attacking Midfield", "Right Attacking Midfield",
             "Left Wing", "Right Wing", "Left Midfield", "Right Midfield"],
    "FW": ["Center Forward", "Left Center Forward", "Right Center Forward", "Secondary Striker"],
}
GROUP_LABEL = {"GK": "门将", "CB": "中后卫", "FB": "边后卫/翼卫", "MF": "中场/后腰", "AM/W": "前腰/边锋", "FW": "前锋"}
PIZZA = {
    "FW": ["npxg", "np_goals", "shots", "box_receptions", "xg_assisted", "key_passes", "dribbles_completed",
           "progressive_carries", "xt_added", "pressures", "pressures_att_third"],
    "AM/W": ["npxg", "shots", "xg_assisted", "key_passes", "dribbles_completed", "progressive_carries",
             "progressive_passes", "box_entries", "xt_added", "pressures_att_third", "ball_recoveries"],
    "MF": ["passes_completed", "pass_completion", "progressive_passes", "deep_progressions", "xt_added",
           "xg_assisted", "progressive_carries", "pressures", "tackles_won", "interceptions", "ball_recoveries"],
    "FB": ["progressive_passes", "progressive_carries", "deep_progressions", "box_entries", "xg_assisted",
           "xt_added", "pass_completion", "pressures", "tackles_won", "interceptions", "ball_recoveries"],
    "CB": ["passes_completed", "pass_completion", "progressive_passes", "progressive_carries", "xt_added",
           "tackles_won", "interceptions", "blocks", "clearances", "ball_recoveries", "pressures"],
}
SUM_FIELDS = ["minutes"] + fm.PLAYER_COUNTS


def position_group(position: str | None) -> str | None:
    return next((g for g, names in POSITION_GROUPS.items() if position in names), None)


def season_scope(args) -> tuple[list[dict], list[dict]]:
    """(season rows, match rows) for the requested competition/season or single match."""
    if args.match:
        meta = fc.find_match_meta(args.match)
        if not meta:
            raise SystemExit(f"match {args.match} not found in StatsBomb open data")
        return [], [meta]
    if not args.competition or not args.season:
        raise SystemExit("give --match, or --competition and --season (IDs or names; see sb_find.py)")
    seasons = fc.resolve_competition(args.competition, args.season)
    if not seasons:
        raise SystemExit(f"no competition/season matches {args.competition!r} / {args.season!r}")
    if len(seasons) > 1 and not args.all_seasons:
        listing = "; ".join(f"{r['competition_name']} {r['season_name']} ({r['competition_id']}/{r['season_id']})"
                            for r in seasons[:10])
        raise SystemExit(f"{len(seasons)} seasons match: {listing}. Narrow --season or add --all-seasons")
    matches = [m for r in seasons for m in fc.sb_matches(r["competition_id"], r["season_id"])]
    return seasons, matches


def find_player(matches: list[dict], args) -> tuple[int, dict, list[dict]]:
    pool = [m for m in matches if not args.team or fc.name_matches(
        args.team, m["home_team"]["home_team_name"], m["away_team"]["away_team_name"])]
    candidates: dict[int, dict] = {}
    played: dict[int, list[dict]] = defaultdict(list)
    for m in pool:
        for team in fc.sb_lineups(m["match_id"]):
            if args.team and not fc.name_matches(args.team, team["team_name"]):
                continue
            for p in team["lineup"]:
                if args.player_id and p["player_id"] != args.player_id:
                    continue
                if not args.player_id and not fc.name_matches(args.player, p["player_name"], p.get("player_nickname")):
                    continue
                candidates.setdefault(p["player_id"], {"player_id": p["player_id"], "name": p["player_name"],
                                                       "nickname": p.get("player_nickname"), "team": team["team_name"]})
                if p.get("positions"):
                    played[p["player_id"]].append(m)
    if not candidates:
        raise SystemExit(f"no player matching {args.player or args.player_id!r} in these matches; "
                         "search with: sb_find.py players --competition ... --season ... --q <name>")
    if len(candidates) > 1 and args.player:
        exact = {pid: c for pid, c in candidates.items()
                 if fc.norm(args.player) in (fc.norm(c["nickname"]), fc.norm(c["name"]))}
        if len(exact) == 1:
            candidates = exact
    if len(candidates) > 1:
        listing = "; ".join(f"{c['nickname'] or c['name']} ({c['team']}, --player-id {pid})"
                            for pid, c in candidates.items())
        raise SystemExit(f"{len(candidates)} players match {args.player!r}: {listing}")
    pid, info = next(iter(candidates.items()))
    if not played[pid]:
        raise SystemExit(f"{info['nickname'] or info['name']} is in the squad lists but did not play in these matches")
    return pid, info, sorted(played[pid], key=lambda m: (m["match_date"], m["match_id"]))


def add_rates(row: dict) -> dict:
    mins = row.get("minutes") or 0
    for key in PER90:
        row[f"{key}_p90"] = round(row[key] * 90 / mins, 3) if mins and row.get(key) is not None else None
    for key, (_, _, num, den) in RATIOS.items():
        row[key] = round(row[num] / row[den], 3) if row.get(den) else None
    return row


def aggregate(rows: list[dict]) -> dict:
    total: dict = {k: 0 for k in SUM_FIELDS}
    positions: Counter = Counter()
    for r in rows:
        for k in SUM_FIELDS:
            if r.get(k) is not None:
                total[k] += r[k]
        positions[r.get("position")] += r.get("minutes") or 0
    if rows and all(r.get("xt_added") is None for r in rows):
        total["xt_added"] = None
    total["matches"] = len(rows)
    total["main_position"] = positions.most_common(1)[0][0] if positions else None
    return add_rates(total)


def percentile(values: list[float], v: float) -> float:
    below = sum(x < v for x in values)
    equal = sum(x == v for x in values)
    return 100.0 * (below + 0.5 * equal) / len(values)


def benchmark(matches: list[dict], grid, pid: int, group: str, min_minutes: float) -> dict:
    per_player: dict[int, list[dict]] = defaultdict(list)
    fc.log(f"[benchmark] reading events of {len(matches)} matches (cached after the first run)")
    for i, m in enumerate(matches, 1):
        match = fm.Match.build(m["match_id"], fc.sb_events(m["match_id"]), fc.sb_lineups(m["match_id"]), m)
        for p, row in fm.player_metrics(match, grid).items():
            per_player[p].append(row)
        if i % 10 == 0:
            fc.log(f"[benchmark] {i}/{len(matches)} matches")
    pool = {}
    for p, rows in per_player.items():
        agg = aggregate(rows)
        agg.update(player=rows[0]["player"], team=rows[0]["team"])
        if agg["minutes"] >= min_minutes and position_group(agg["main_position"]) == group:
            pool[p] = agg
    target = pool.get(pid)
    keys = PIZZA.get(group, [])
    result = {"group": group, "min_minutes": min_minutes, "n": len(pool), "included": target is not None, "rows": []}
    if not target:
        return result
    for key in keys:
        col = key if key in RATIOS else f"{key}_p90"
        vals = [a[col] for a in pool.values() if a.get(col) is not None]
        if target.get(col) is None or not vals:
            continue
        label_cn, label_en = (RATIOS[key][:2] if key in RATIOS else PER90[key])
        result["rows"].append({"metric": key, "label": label_cn, "label_en": label_en, "value": target[col],
                               "percentile": round(percentile(vals, target[col]), 1),
                               "group_median": sorted(vals)[len(vals) // 2]})
    return result


def collect_maps(match: fm.Match, pid: int) -> dict[str, list]:
    passes, carries, points = [], [], []
    for e in match.events:
        if fm.player_id(e) != pid or not fm.in_play(e):
            continue
        if e.get("location"):
            points.append(e["location"])
        if fm.is_progressive_pass(e):
            passes.append({"x": e["location"][0], "y": e["location"][1],
                           "end_x": e["pass"]["end_location"][0], "end_y": e["pass"]["end_location"][1]})
        elif fm.is_progressive_carry(e):
            carries.append({"x": e["location"][0], "y": e["location"][1],
                            "end_x": e["carry"]["end_location"][0], "end_y": e["carry"]["end_location"][1]})
    return {"passes": passes, "carries": carries, "points": points, "shots": fm.shot_list(match, pid)}


def observations(name: str, total: dict, bench: dict | None, small_sample: bool) -> list[str]:
    obs = []
    if total["xt_added"] is not None:
        obs.append(f"{name} 每 90 分钟 xT added {total['xt_added_p90']:.2f}、推进传球 {total['progressive_passes_p90']:.1f}、"
                   f"推进带球 {total['progressive_carries_p90']:.1f}：反映把球带/传到更危险区域的能力。")
    if total["shots"]:
        diff = total["np_goals"] - total["npxg"]
        obs.append(f"终结：非点球进球 {total['np_goals']} vs npxG {total['npxg']:.2f}（差值 {diff:+.2f}）。"
                   "单届赛事的进球-xG 差值多为噪声，不足以判断“终结能力”。")
    if total["xg_assisted"]:
        obs.append(f"创造：xG assisted {total['xg_assisted']:.2f}（关键传球 {total['key_passes']}，助攻 {total['assists']}）。")
    if bench and bench.get("rows"):
        strong = [r for r in bench["rows"] if r["percentile"] >= 80]
        weak = [r for r in bench["rows"] if r["percentile"] <= 20]
        grp = f"{GROUP_LABEL.get(bench['group'], bench['group'])}（出场≥{bench['min_minutes']:.0f} 分钟，共 {bench['n']} 人）"
        if strong:
            obs.append(f"相对同位置{grp}的突出项：" + "、".join(f"{r['label']}（第 {r['percentile']:.0f} 百分位）" for r in strong) + "。")
        if weak:
            obs.append(f"相对同位置{grp}的偏弱项：" + "、".join(f"{r['label']}（第 {r['percentile']:.0f} 百分位）" for r in weak)
                       + "。偏弱项可能来自角色分工，而非能力不足。")
    if small_sample:
        obs.append("样本提醒：出场时间较少，每 90 分钟数据波动大，只宜作参考。")
    obs.append("球队风格和对手强度会影响个人数据（例如控球多的球队，球员传球数自然更高）；比较时尽量在同队或同风格球队内比较。")
    return obs


def report(info: dict, scope: str, total: dict, per_match: list[dict], bench: dict | None, charts: dict,
           min_minutes: float) -> str:
    name = info["nickname"] or info["name"]
    group = position_group(total["main_position"])
    small = total["minutes"] < min_minutes
    lines = [f"# 球员分析：{name}", "",
             f"{scope} · {info['team']} · 主要位置 {total['main_position']}（{GROUP_LABEL.get(group, '?')}）· "
             f"{total['matches']} 场 · {total['minutes']:.0f} 分钟 · StatsBomb player `{info['player_id']}`", "",
             "数据：StatsBomb 开放数据（Hudl StatsBomb）；分钟为名义比赛时间（补时不计）；点球大战不计。", ""]
    if small:
        lines += [f"> 出场 {total['minutes']:.0f} 分钟，少于 {min_minutes:.0f} 分钟门槛：每 90 分钟数据仅供参考。", ""]
    lines += ["## 1. 汇总与每 90 分钟", "",
              fc.md_table(["指标", "总计", "每 90 分钟"],
                          [["进球（其中点球）", f"{total['goals']}（{total['penalty_goals']}）", None],
                           ["助攻", total["assists"], None]]
                          + [[label, total[k], total[f"{k}_p90"]] for k, (label, _) in PER90.items()]
                          + [[RATIOS[k][0], total[k], None] for k in RATIOS], digits=2), ""]
    lines += ["## 2. 逐场", "",
              fc.md_table(["日期", "对手", "比分", "分钟", "进球", "npxG", "xGA", "关键传球", "推进传球", "推进带球",
                           "xT", "压迫"],
                          ([m["date"], m["opponent"], m["score"], round(m["minutes"]), m["goals"], m["npxg"],
                            m["xg_assisted"], m["key_passes"], m["progressive_passes"], m["progressive_carries"],
                            m["xt_added"], m["pressures"]] for m in per_match)), ""]
    if bench is not None:
        lines += ["## 3. 同位置对比（百分位）", ""]
        if bench.get("rows"):
            lines += [f"对比组：{GROUP_LABEL.get(bench['group'], bench['group'])}，出场 ≥ {bench['min_minutes']:.0f} 分钟，"
                      f"共 {bench['n']} 人（含本人）。百分位越高越好；比率类为整体比率。", "",
                      fc.md_table(["指标", "本人（每90/比率）", "组中位数", "百分位"],
                                  ([r["label"], r["value"], r["group_median"], round(r["percentile"])]
                                   for r in bench["rows"]),
                                  digits=2), ""]
        else:
            lines += [f"未生成：本人不在对比组内（位置组 {bench['group']}，门槛 {bench['min_minutes']:.0f} 分钟）"
                      "或该位置组没有对比参数（门将）。", ""]
    lines += ["## 4. 图表", ""] + [f"![{k}]({v})" for k, v in charts.items()] + [""]
    lines += ["## 5. 数据要点（自动生成，需人工复核）", ""] + [f"- {o}" for o in observations(name, total, bench, small)]
    lines += ["", "## 6. 指标口径", "",
              "- npxG：npxg.statsbomb-hudl；xG assisted：xg_assisted.statsbomb-hudl（记在关键传球者名下）",
              "- 推进传球/带球：progressive_passes / progressive_carries.statsbomb-blog-2023",
              "- xT added：xt.singh-open-12x8；传球成功率：pass_completion.statsbomb-hudl",
              "- 其余计数为 StatsBomb 事件计数（定义见 references/metrics.md），每 90 分钟 = 总数 × 90 / 出场分钟。", ""]
    return "\n".join(lines)


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player", help="player name fragment (accents and case ignored)")
    ap.add_argument("--player-id", type=int, help="StatsBomb player_id (when a name is ambiguous)")
    ap.add_argument("--competition", help="competition ID or name")
    ap.add_argument("--season", help="season ID or name (e.g. 2022, 2015/2016)")
    ap.add_argument("--all-seasons", action="store_true", help="allow several seasons (large downloads)")
    ap.add_argument("--match", type=int, help="single match instead of a season")
    ap.add_argument("--team", help="restrict to one team (faster lookup)")
    ap.add_argument("--benchmark", action="store_true", help="percentiles vs. same-position players (all season events)")
    ap.add_argument("--min-minutes", type=float, help="minutes threshold (default 270 for tournaments, 900 for leagues)")
    ap.add_argument("--no-charts", action="store_true")
    ap.add_argument("--out", help="output folder")
    args = ap.parse_args()
    if not args.player and not args.player_id:
        ap.error("give --player or --player-id")

    seasons, matches = season_scope(args)
    pid, info, played = find_player(matches, args)
    name = info["nickname"] or info["name"]
    min_minutes = args.min_minutes or (270.0 if len(matches) <= 80 else 900.0)
    grid = fc.xt_grid()

    rows, per_match, maps = [], [], defaultdict(list)
    for m in played:
        match = fm.Match.build(m["match_id"], fc.sb_events(m["match_id"]), fc.sb_lineups(m["match_id"]), m)
        row = fm.player_metrics(match, grid).get(pid)
        if not row:
            continue
        rows.append(row)
        home, away = match.teams
        opp = away if row["team"] == home else home
        per_match.append({**row, "match_id": m["match_id"], "date": m["match_date"], "opponent": opp,
                          "score": f"{m['home_score']}-{m['away_score']}" if row["team"] == home
                          else f"{m['away_score']}-{m['home_score']}"})
        for k, v in collect_maps(match, pid).items():
            maps[k].extend(v)
    total = aggregate(rows)
    group = position_group(total["main_position"])

    bench = None
    if args.benchmark:
        if group in PIZZA:
            bench = benchmark(matches, grid, pid, group, min_minutes)
        else:
            bench = {"group": group, "min_minutes": min_minutes, "n": 0, "rows": []}

    if args.match:
        scope = f"单场 {played[0]['home_team']['home_team_name']} vs {played[0]['away_team']['away_team_name']}" \
                f"（{played[0]['match_date']}）"
        slug = f"{name}-{args.match}"
    else:
        scope = " + ".join(f"{r['competition_name']} {r['season_name']}" for r in seasons)
        slug = f"{name}-{seasons[0]['competition_name']}-{seasons[0]['season_name']}"
    out = fc.make_out_dir("player", slug, args.out)

    charts: dict[str, str] = {}
    if fc.charts_enabled(args.no_charts):
        import fa_charts as ch

        jobs = {
            "shot_map": lambda p: ch.player_shot_map(maps["shots"], f"{name} - {scope}", p) if maps["shots"] else None,
            "heatmap": lambda p: ch.player_heatmap(maps["points"], name, p),
            "progression": lambda p: ch.player_progression_map(maps["passes"], maps["carries"], name, p),
            "pizza": lambda p: ch.player_pizza(
                [r["label_en"] for r in bench["rows"]], [r["percentile"] for r in bench["rows"]],
                f"{name} ({info['team']})",
                f"{scope} | vs {bench['n']} {bench['group']} players with >= {bench['min_minutes']:.0f} min | per 90",
                p) if bench and bench.get("rows") else None,
        }
        for key, job in jobs.items():
            try:
                saved = job(out / f"{key}.png")
                if saved:
                    charts[key] = saved
            except Exception as exc:  # noqa: BLE001 - one broken chart must not lose the report
                fc.log(f"[charts] {key} failed: {type(exc).__name__}: {exc}")

    fc.write_text(out / "report.md", report(info, scope, total, per_match, bench, charts, min_minutes))
    fc.write_csv(out / "matches.csv", per_match)
    fc.write_json(out / "summary.json", {"player": info, "scope": scope, "variants": fm.VARIANTS, "total": total,
                                         "per_match": per_match, "benchmark": bench, "shots": maps["shots"]})
    print(f"{name} ({info['team']}): {total['matches']} matches, {total['minutes']:.0f} min, "
          f"{total['goals']} goals, npxG {total['npxg']:.2f}, xGA {total['xg_assisted']:.2f}"
          + (f", benchmark n={bench['n']}" if bench else ""))
    print(f"report: {out / 'report.md'}")
    return {"out_dir": str(out), "files": ["report.md", "summary.json", "matches.csv"] + sorted(charts.values())}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
