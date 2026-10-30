"""Team tactical profile over one competition-season from StatsBomb open data (event level).

    python sb_team.py --team argentina --competition 43 --season 106
    python sb_team.py --team spain --competition "UEFA Euro" --season 2024 --benchmark
    python sb_team.py --team "bayer leverkusen" --competition "1. Bundesliga" --season 2023/2024

Combines every match of the team in the competition-season: chance creation and concession,
possession and territory, progression, pressing, how these change with the score (level,
leading, trailing), formations and the most used players. --benchmark ranks the team against
every team with at least 3 matches in the same competition-season (downloads the events of all
its matches; World Cup 2022: 64 files, ~230 MB). Writes outputs/team-<team>-<competition>-<season>/
with report.md (Chinese), summary.json, matches.csv and charts.
"""
from __future__ import annotations

import argparse
import statistics
from collections import Counter, defaultdict

import fa_common as fc
import fa_metrics as fm

FOR_KEYS = ["goals", "xg", "npxg", "shots", "np_shots", "shots_on_target", "passes", "passes_completed",
            "final_third_passes", "progressive_passes", "progressive_carries", "deep_progressions", "box_entries",
            "xt_added", "pressures", "pressures_att_third", "ppda_opp_passes", "ppda_def_actions"]
AGAINST_KEYS = ["goals", "xg", "npxg", "np_shots", "shots_on_target", "passes", "final_third_passes",
                "deep_progressions", "box_entries", "ppda_opp_passes", "ppda_def_actions"]
PER90_FOR = ["goals", "xg", "npxg", "np_shots", "shots_on_target", "passes", "progressive_passes",
             "progressive_carries", "deep_progressions", "box_entries", "xt_added", "pressures", "pressures_att_third"]
PER90_AGAINST = ["goals", "xg", "npxg", "np_shots", "shots_on_target", "deep_progressions", "box_entries"]
STATES = ("level", "leading", "trailing")
STATE_CN = {"level": "平局时", "leading": "领先时", "trailing": "落后时"}
MIN_BENCH_MATCHES = 3
SMALL_STATE_MINUTES = 45

# key -> (Chinese label, chart label, True if a higher value means more of what the label names)
PROFILE = {
    "npxg_p90": ("npxG / 90", "npxG", True),
    "np_shots_p90": ("非点球射门 / 90", "NP shots", True),
    "xg_per_np_shot": ("每脚非点球射门 xG", "xG per shot", True),
    "box_entries_p90": ("进入禁区 / 90", "Box entries", True),
    "xt_added_p90": ("xT added / 90", "xT added", True),
    "opp_npxg_p90": ("对手 npxG / 90（越低越好）", "Low npxG against", False),
    "opp_box_entries_p90": ("对手进入禁区 / 90（越低越好）", "Few opp. box entries", False),
    "pass_share": ("传球占比（控球代理）", "Pass share", True),
    "field_tilt": ("Field tilt（领地）", "Field tilt", True),
    "progressive_passes_p90": ("推进传球 / 90", "Prog. passes", True),
    "progressive_carries_p90": ("推进带球 / 90", "Prog. carries", True),
    "ppda": ("PPDA（越低压迫越强）", "Pressing (low PPDA)", False),
    "pressures_att_third_p90": ("前场三区压迫 / 90", "Att. third pressures", True),
    "pressure_height": ("压迫平均高度 x", "Pressure height", True),
    "def_action_height": ("防守动作平均高度 x", "Def. action height", True),
}


def ratio(num: float, den: float, digits: int = 4) -> float | None:
    return round(num / den, digits) if den else None


def resolve_scope(competition: str, season: str) -> tuple[dict, list[dict]]:
    seasons = fc.resolve_competition(competition, season)
    if not seasons:
        raise SystemExit(f"no competition/season matches {competition!r} / {season!r}; list them with "
                         "sb_find.py competitions")
    if len(seasons) > 1:
        listing = "; ".join(f"{r['competition_name']} {r['season_name']} ({r['competition_id']}/{r['season_id']})"
                            for r in seasons[:10])
        raise SystemExit(f"{len(seasons)} seasons match: {listing}. Pass the IDs, e.g. --competition 43 --season 106")
    row = seasons[0]
    matches = sorted(fc.sb_matches(row["competition_id"], row["season_id"]),
                     key=lambda m: (m["match_date"], m.get("kick_off") or "", m["match_id"]))
    return row, matches


def teams_of(m: dict) -> tuple[str, str]:
    return m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]


def resolve_team(matches: list[dict], query: str) -> str:
    names = sorted({n for m in matches for n in teams_of(m) if fc.name_matches(query, n)})
    if not names:
        raise SystemExit(f"no team matching {query!r} in this competition-season; list the matches with "
                         "sb_find.py matches --competition ... --season ...")
    exact = [n for n in names if fc.norm(n) == fc.norm(query)]
    if len(names) > 1 and not exact:
        raise SystemExit(f"{len(names)} teams match {query!r}: {', '.join(names)}. Use the full name.")
    return exact[0] if exact else names[0]


def match_detail(match: fm.Match, team: str) -> dict:
    """What team_metrics does not give: game-state splits, action heights and pressure locations."""
    opp = match.opponent(team)
    to_elapsed, period_ends = match.elapsed_mapper()
    end = period_ends[-1][1] if period_ends else match.length
    goals = {team: 0, opp: 0}
    states = {s: Counter() for s in STATES}
    state_minutes: Counter = Counter()
    sums: Counter = Counter()
    pressures: dict[str, list] = {"team": [], "opp": []}
    last = 0.0

    def state() -> str:
        diff = goals[team] - goals[opp]
        return "level" if diff == 0 else "leading" if diff > 0 else "trailing"

    for e in match.events:
        side = fm.team_name(e)
        if side not in goals or not fm.in_play(e):
            continue
        mine = side == team
        typ = fm.etype(e)
        loc = e.get("location")
        c = states[state()]
        if typ == "Pass":
            c["passes" if mine else "opp_passes"] += 1
            if fm.is_field_tilt_pass(e):
                c["final_third_passes" if mine else "opp_final_third_passes"] += 1
            if not mine and fm.is_completed_pass(e) and loc[0] < 72:
                c["ppda_opp_passes"] += 1
        elif typ == "Shot" and fm.sub(e, "shot", "type", "name") != "Penalty":
            c["npxg" if mine else "opp_npxg"] += e["shot"].get("statsbomb_xg", 0.0)
        elif typ == "Pressure" and loc:
            pressures["team" if mine else "opp"].append(loc[:2])
            if mine:
                sums["pressure_x"] += loc[0]
                sums["pressure_n"] += 1
        if mine and loc and fm.is_ppda_defensive_action(e):
            sums["def_action_x"] += loc[0]
            sums["def_action_n"] += 1
            if loc[0] >= 48:
                c["ppda_def_actions"] += 1
        if (typ == "Shot" and fm.sub(e, "shot", "outcome", "name") == "Goal") or typ == "Own Goal For":
            t = to_elapsed(e)
            state_minutes[state()] += max(t - last, 0.0)
            last = t
            goals[side] += 1
    state_minutes[state()] += max(end - last, 0.0)
    return {"states": states, "state_minutes": state_minutes, "sums": sums, "pressures": pressures}


def new_total() -> dict:
    return {"matches": 0, "minutes": 0.0, "for": Counter(), "against": Counter(), "xt_missing": False,
            "states": {s: Counter() for s in STATES}, "state_minutes": Counter(), "sums": Counter(),
            "results": Counter()}


def add_match(total: dict, match: fm.Match, team: str, tm: dict, detail: dict) -> None:
    opp = match.opponent(team)
    total["matches"] += 1
    total["minutes"] += match.length
    for k in FOR_KEYS:
        if tm[team].get(k) is None:
            total["xt_missing"] = True
            continue
        total["for"][k] += tm[team][k]
    for k in AGAINST_KEYS:
        total["against"][k] += tm[opp].get(k) or 0
    for s in STATES:
        total["states"][s].update(detail["states"][s])
        total["state_minutes"][s] += detail["state_minutes"][s]
    total["sums"].update(detail["sums"])
    gf, ga = tm[team]["goals"], tm[opp]["goals"]
    total["results"]["W" if gf > ga else "D" if gf == ga else "L"] += 1


def profile(total: dict) -> dict:
    f, a, s = total["for"], total["against"], total["sums"]
    mins = total["minutes"] or 1.0
    out: dict = {"matches": total["matches"], "minutes": total["minutes"], "results": dict(total["results"])}
    for k in FOR_KEYS:
        out[k] = None if (k == "xt_added" and total["xt_missing"]) else round(f[k], 4)
    for k in AGAINST_KEYS:
        out[f"opp_{k}"] = round(a[k], 4)
    for k in PER90_FOR:
        out[f"{k}_p90"] = None if out[k] is None else round(f[k] * 90 / mins, 3)
    for k in PER90_AGAINST:
        out[f"opp_{k}_p90"] = round(a[k] * 90 / mins, 3)
    out.update({
        "xg_per_np_shot": ratio(f["npxg"], f["np_shots"], 3),
        "opp_xg_per_np_shot": ratio(a["npxg"], a["np_shots"], 3),
        "pass_completion": ratio(f["passes_completed"], f["passes"]),
        "pass_share": ratio(f["passes"], f["passes"] + a["passes"]),
        "field_tilt": ratio(f["final_third_passes"], f["final_third_passes"] + a["final_third_passes"]),
        "ppda": ratio(f["ppda_opp_passes"], f["ppda_def_actions"]),
        "ppda_faced": ratio(a["ppda_opp_passes"], a["ppda_def_actions"]),
        "pressure_height": ratio(s["pressure_x"], s["pressure_n"], 1),
        "def_action_height": ratio(s["def_action_x"], s["def_action_n"], 1),
    })
    rows = []
    for st in STATES:
        c, m = total["states"][st], total["state_minutes"][st]
        rows.append({
            "state": st, "minutes": round(m, 1),
            "pass_share": ratio(c["passes"], c["passes"] + c["opp_passes"]),
            "field_tilt": ratio(c["final_third_passes"], c["final_third_passes"] + c["opp_final_third_passes"]),
            "ppda": ratio(c["ppda_opp_passes"], c["ppda_def_actions"]),
            "ppda_opp_passes": c["ppda_opp_passes"], "ppda_def_actions": c["ppda_def_actions"],
            "npxg_p90": ratio(c["npxg"] * 90, m, 3), "opp_npxg_p90": ratio(c["opp_npxg"] * 90, m, 3),
        })
    out["game_states"] = rows
    return out


def percentile(values: list[float], v: float) -> float:
    below = sum(x < v for x in values)
    equal = sum(x == v for x in values)
    return 100.0 * (below + 0.5 * equal) / len(values)


def rank_team(team: str, profiles: dict[str, dict]) -> dict:
    pool = {t: p for t, p in profiles.items() if p["matches"] >= MIN_BENCH_MATCHES}
    result = {"n": len(pool), "min_matches": MIN_BENCH_MATCHES, "rows": [],
              "pool": {t: {k: p.get(k) for k in ["matches", *PROFILE]} for t, p in sorted(pool.items())}}
    if team not in pool or len(pool) < 6:
        result["reason"] = (f"对比组只有 {len(pool)} 支球队（至少 {MIN_BENCH_MATCHES} 场）" if team in pool
                            else f"{team} 不足 {MIN_BENCH_MATCHES} 场")
        return result
    for key, (label, label_en, higher) in PROFILE.items():
        vals = [p[key] for p in pool.values() if p.get(key) is not None]
        v = pool[team].get(key)
        if v is None or not vals:
            continue
        pct = percentile(vals, v)
        result["rows"].append({
            "metric": key, "label": label, "label_en": label_en, "value": v,
            "median": round(statistics.median(vals), 4),
            "rank": 1 + sum((x > v) if higher else (x < v) for x in vals),
            "percentile": round(pct if higher else 100 - pct, 1),
        })
    return result


def single_team_dataset(matches: list[dict], team: str) -> bool:
    """True when the season only holds this team's matches (e.g. Barcelona-only La Liga seasons)."""
    counts = Counter(t for m in matches for t in teams_of(m))
    others = [c for t, c in counts.items() if t != team]
    return len(matches) > 3 and counts[team] == len(matches) and max(others, default=0) <= 2


def observations(team: str, p: dict, formations: Counter, bench: dict | None, small: bool) -> list[str]:
    r = p["results"]
    obs = [f"结果与机会：{p['matches']} 场 {r.get('W', 0)} 胜 {r.get('D', 0)} 平 {r.get('L', 0)} 负（常规时间+加时，点球大战计平），"
           f"进 {p['goals']} 失 {p['opp_goals']}；npxG {p['npxg']:.2f} vs 对手 {p['opp_npxg']:.2f}"
           f"（每 90 分钟 {p['npxg_p90']:.2f} vs {p['opp_npxg_p90']:.2f}）。进失球与 xG 的差距在这样的样本里多为波动。"]
    if p["pass_share"] is not None and p["field_tilt"] is not None:
        obs.append(f"控球与领地：传球占比 {p['pass_share']:.0%}，field tilt {p['field_tilt']:.0%}，传球成功率 "
                   f"{p['pass_completion']:.0%}。控球多少反映风格与比分状态，不能单独证明踢得更好，要和机会质量一起看。")
    if p["ppda"] is not None:
        obs.append(f"压迫：PPDA {p['ppda']:.2f}（{p['ppda_opp_passes']:.0f}/{p['ppda_def_actions']:.0f}），压迫平均高度 "
                   f"x={fc.fmt(p['pressure_height'], 1)}，前场三区压迫每 90 分钟 {p['pressures_att_third_p90']:.1f} 次；"
                   f"对手对 {team} 的 PPDA 为 {fc.fmt(p['ppda_faced'])}（越低说明 {team} 被压得越狠）。")
    style = "更依赖带球推进" if p["progressive_carries"] > p["progressive_passes"] else "更依赖传球推进"
    obs.append(f"推进：每 90 分钟推进传球 {p['progressive_passes_p90']:.1f}、推进带球 {p['progressive_carries_p90']:.1f}，"
               f"{style}；进入禁区 {p['box_entries_p90']:.1f} 次/90，对手 {p['opp_box_entries_p90']:.1f} 次/90。")
    gs = {g["state"]: g for g in p["game_states"]}
    lead, trail = gs["leading"], gs["trailing"]
    level = gs["level"]
    if lead["minutes"] >= SMALL_STATE_MINUTES and trail["minutes"] >= SMALL_STATE_MINUTES \
            and lead["pass_share"] is not None and trail["pass_share"] is not None:
        level_share = f"{level['pass_share']:.0%}" if level["pass_share"] is not None else "–"
        obs.append(f"比分状态：领先时传球占比 {lead['pass_share']:.0%}（{lead['minutes']:.0f} 分钟），落后时 "
                   f"{trail['pass_share']:.0%}（{trail['minutes']:.0f} 分钟），平局时 {level_share}"
                   f"（{level['minutes']:.0f} 分钟）。领先方通常回收、落后方通常压上，评价风格时以平局时的数据为主。")
    else:
        short = [STATE_CN[g["state"]] for g in p["game_states"] if g["minutes"] < SMALL_STATE_MINUTES]
        if short:
            obs.append(f"比分状态：{'、'.join(short)}不足 {SMALL_STATE_MINUTES} 分钟，分状态的数字只作参考；"
                       f"平局时的数据（{level['minutes']:.0f} 分钟）最能代表默认打法。")
    if formations:
        top = "、".join(f"{f}（{n} 场）" for f, n in formations.most_common(3))
        obs.append(f"阵型：首发阵型 {top}。阵型是 StatsBomb 记录的首发站位，比赛中的实际站位可能不同。")
    if bench and bench.get("rows"):
        strong = [b for b in bench["rows"] if b["percentile"] >= 80]
        weak = [b for b in bench["rows"] if b["percentile"] <= 20]
        if strong:
            obs.append(f"与同赛事 {bench['n']} 支球队相比突出：" + "、".join(
                f"{b['label']}（第 {b['rank']}/{bench['n']}）" for b in strong) + "。")
        if weak:
            obs.append(f"与同赛事 {bench['n']} 支球队相比偏低：" + "、".join(
                f"{b['label']}（第 {b['rank']}/{bench['n']}）" for b in weak) + "。偏低不一定是缺点，可能是打法选择。")
    if small:
        obs.append(f"样本提醒：只有 {p['matches']} 场，对手强弱与赛程阶段影响很大，结论只描述这几场比赛。")
    return obs


def report(team: str, scope: str, p: dict, rows: list[dict], formations: Counter, players: list[dict],
           bench: dict | None, charts: dict, single_team: bool, international: bool) -> str:
    r = p["results"]
    lines = [f"# 球队战术画像：{team}", "",
             f"{scope} · {p['matches']} 场（{r.get('W', 0)} 胜 {r.get('D', 0)} 平 {r.get('L', 0)} 负）· "
             f"进 {p['goals']} 失 {p['opp_goals']}", "",
             "数据：StatsBomb 开放数据（Hudl StatsBomb）。每 90 分钟按名义比赛时长（90 或含加时的 120 分钟）折算；"
             "点球大战不计；比率类指标（PPDA、field tilt、传球占比等）用全部场次的分子分母合计计算。", ""]
    if single_team:
        lines += [f"> 这个赛季的开放数据只有 {team} 的比赛（对手各 1-2 场），只能描述 {team} 本身，无法与其他球队排名。", ""]
    venue_col = [] if international else ["主客"]
    lines += ["## 1. 逐场", "",
              fc.md_table(["日期", "阶段", "对手", *venue_col, "比分", "首发阵型", "xG", "对手 xG", "传球占比",
                           "Field tilt", "PPDA", "压迫高度"],
                          ([m["date"], m["stage"], m["opponent"], *([m["venue"]] if not international else []),
                            m["score"], m["formation"], m["xg"], m["xg_against"], m["pass_share"], m["field_tilt"],
                            m["ppda"], m["pressure_height"]] for m in rows)), ""]
    if "xg_by_match" in charts:
        lines += [f"![xG by match]({charts['xg_by_match']})", ""]

    def per90_table(items: list[tuple[str, str, str | None]]) -> str:
        return fc.md_table(["指标", "总计", "每 90 分钟"], ([label, p[k], p[k90] if k90 else None]
                                                       for label, k, k90 in items))

    lines += ["## 2. 进攻：创造与推进", "", per90_table([
        ("进球", "goals", "goals_p90"), ("xG（含点球）", "xg", "xg_p90"), ("npxG", "npxg", "npxg_p90"),
        ("非点球射门", "np_shots", "np_shots_p90"), ("射正", "shots_on_target", "shots_on_target_p90"),
        ("每脚非点球射门 xG", "xg_per_np_shot", None), ("进入前场三区（传+带）", "deep_progressions", "deep_progressions_p90"),
        ("进入禁区（传+带）", "box_entries", "box_entries_p90"), ("推进传球", "progressive_passes", "progressive_passes_p90"),
        ("推进带球", "progressive_carries", "progressive_carries_p90"), ("xT added", "xt_added", "xt_added_p90"),
    ]), ""]
    if "shots_for" in charts:
        lines += [f"![shots]({charts['shots_for']})", ""]
    lines += ["## 3. 防守：限制对手与压迫", "", per90_table([
        ("失球", "opp_goals", "opp_goals_p90"), ("对手 xG（含点球）", "opp_xg", "opp_xg_p90"),
        ("对手 npxG", "opp_npxg", "opp_npxg_p90"), ("对手非点球射门", "opp_np_shots", "opp_np_shots_p90"),
        ("对手射正", "opp_shots_on_target", "opp_shots_on_target_p90"),
        ("对手每脚非点球射门 xG", "opp_xg_per_np_shot", None),
        ("对手进入前场三区", "opp_deep_progressions", "opp_deep_progressions_p90"),
        ("对手进入禁区", "opp_box_entries", "opp_box_entries_p90"),
        ("压迫次数", "pressures", "pressures_p90"), ("前场三区压迫", "pressures_att_third", "pressures_att_third_p90"),
    ]), "",
        f"PPDA {fc.fmt(p['ppda'])}（对手后场 60% 成功传球 {p['ppda_opp_passes']:.0f} / 本队 x≥48 防守动作 "
        f"{p['ppda_def_actions']:.0f}）；压迫平均高度 x={fc.fmt(p['pressure_height'], 1)}；防守动作平均高度 "
        f"x={fc.fmt(p['def_action_height'], 1)}（0 = 本方球门线，120 = 对方球门线）。", ""]
    for key in ("shots_against", "pressures"):
        if key in charts:
            lines += [f"![{key}]({charts[key]})", ""]
    lines += ["## 4. 控球与领地", "", fc.md_table(["指标", "数值"], [
        ["传球", p["passes"]], ["传球成功率", p["pass_completion"]], ["传球占比（控球代理）", p["pass_share"]],
        ["Field tilt（前场三区传球占比）", p["field_tilt"]], [f"对手对 {team} 的 PPDA（越低被压得越狠）", p["ppda_faced"]],
    ], digits=3), ""]
    lines += ["## 5. 比分状态", "",
              fc.md_table(["状态", "分钟", "传球占比", "Field tilt", "PPDA", "npxG / 90", "对手 npxG / 90"],
                          ([STATE_CN[g["state"]], g["minutes"], g["pass_share"], g["field_tilt"], g["ppda"],
                            g["npxg_p90"], g["opp_npxg_p90"]] for g in p["game_states"]), digits=2), "",
              f"分钟为实际经过时间（含补时，不含点球大战）。少于 {SMALL_STATE_MINUTES} 分钟的状态只作参考。"
              "进球那一刻的射门计入进球前的状态。", ""]
    lines += ["## 6. 阵型与人员", "",
              "首发阵型：" + ("、".join(f"{f}（{n} 场）" for f, n in formations.most_common()) or "无"), "",
              fc.md_table(["球员", "主要位置", "出场", "首发", "分钟"],
                          ([pl["player"], pl["position"], pl["apps"], pl["starts"], round(pl["minutes"])]
                           for pl in players[:18])), ""]
    if bench is not None:
        lines += ["## 7. 同赛事排名", ""]
        if bench.get("rows"):
            lines += [f"对比组：本赛事赛季出场至少 {bench['min_matches']} 场的 {bench['n']} 支球队。排名 1 = 该项最高"
                      "（标注“越低越好”的指标，1 = 数值最低）；百分位已按同一方向换算，越高越“多/强”。", "",
                      fc.md_table(["指标", team, "中位数", "排名", "百分位"],
                                  ([b["label"], b["value"], b["median"], f"{b['rank']}/{bench['n']}", round(b["percentile"])]
                                   for b in bench["rows"]), digits=3), ""]
            if "style" in charts:
                lines += [f"![style profile]({charts['style']})", ""]
        else:
            lines += [f"未生成：{bench.get('reason', '对比组不足')}。", ""]
    lines += ["## 8. 数据要点（自动生成，需人工复核）", ""]
    lines += [f"- {o}" for o in observations(team, p, formations, bench, p["matches"] < 10)] + [""]
    lines += ["## 9. 指标口径", "",
              "- xG / npxG：xg.statsbomb-hudl / npxg.statsbomb-hudl；PPDA：ppda.statsbomb-hudl；"
              "Field tilt：field_tilt.stats-perform-2016",
              "- 推进传球/带球：progressive_passes / progressive_carries.statsbomb-blog-2023；xT added：xt.singh-open-12x8；"
              "传球成功率：pass_completion.statsbomb-hudl",
              "- 传球占比、进入前场三区/禁区、压迫高度、防守动作高度为描述性指标，定义见 references/metrics.md；"
              "不同口径的数字不能直接比较。", ""]
    return "\n".join(lines)


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", required=True, help="team name, e.g. argentina (accents and case ignored)")
    ap.add_argument("--competition", required=True, help="competition ID or name (see sb_find.py competitions)")
    ap.add_argument("--season", required=True, help="season ID or name, e.g. 106 or 2022 or 2015/2016")
    ap.add_argument("--benchmark", action="store_true",
                    help="rank against every team of the competition-season (reads all its matches)")
    ap.add_argument("--no-charts", action="store_true")
    ap.add_argument("--out", help="output folder")
    args = ap.parse_args()

    season_row, matches = resolve_scope(args.competition, args.season)
    team = resolve_team(matches, args.team)
    scope = f"{season_row['competition_name']} {season_row['season_name']}"
    international = bool(season_row.get("competition_international"))
    single_team = single_team_dataset(matches, team)
    own = [m for m in matches if team in teams_of(m)]
    bench_wanted = args.benchmark and not single_team
    to_read = matches if bench_wanted else own
    if bench_wanted:
        fc.log(f"[benchmark] reading events of {len(to_read)} matches (cached after the first run)")
    grid = fc.xt_grid()

    totals: dict[str, dict] = defaultdict(new_total)
    rows, shots_for, shots_against = [], [], []
    pressure_pts: dict[str, list] = {"team": [], "opp": []}
    formations: Counter = Counter()
    people: dict[int, dict] = {}
    for i, m in enumerate(to_read, 1):
        try:
            match = fm.Match.build(m["match_id"], fc.sb_events(m["match_id"]), fc.sb_lineups(m["match_id"]), m)
        except fc.DataNotFound as exc:
            fc.log(f"[skip] match {m['match_id']}: {exc}")
            continue
        tm = fm.team_metrics(match, grid)
        for t in (match.teams if bench_wanted else [team]):
            detail = match_detail(match, t)
            add_match(totals[t], match, t, tm, detail)
            if t != team:
                continue
            opp = match.opponent(t)
            home = t == match.teams[0]
            so = match.shootout()
            score = f"{tm[t]['goals']}-{tm[opp]['goals']}"
            formation = match.formations().get(t, {}).get("starting", "?")
            formations[formation] += 1
            rows.append({
                "match_id": m["match_id"], "date": m["match_date"],
                "stage": (m.get("competition_stage") or {}).get("name", ""), "opponent": opp,
                "venue": "H" if home else "A", "score": score + (f"（点球 {so[t]}-{so[opp]}）" if so else ""),
                "score_en": score + (f" ({so[t]}-{so[opp]} pens)" if so else ""), "formation": formation,
                "extra_time": match.extra_time, "xg": tm[t]["xg"], "xg_against": tm[opp]["xg"],
                "npxg": tm[t]["npxg"], "npxg_against": tm[opp]["npxg"], "pass_share": tm[t]["pass_share"],
                "field_tilt": tm[t]["field_tilt"], "ppda": tm[t]["ppda"], "pressure_height": tm[t]["pressure_height"],
                "def_action_height": tm[t]["def_action_height"], "box_entries": tm[t]["box_entries"],
                "box_entries_against": tm[opp]["box_entries"], "xt_added": tm[t]["xt_added"],
            })
            for s in fm.shot_list(match):
                (shots_for if s["team"] == t else shots_against).append(s)
            for k in pressure_pts:
                pressure_pts[k].extend(detail["pressures"][k])
            for pid, mins in match.minutes().items():
                info = match.players.get(pid)
                if not info or info.team != t:
                    continue
                pl = people.setdefault(pid, {"player_id": pid, "player": info.display, "apps": 0, "starts": 0,
                                             "minutes": 0.0, "positions": Counter()})
                pl["apps"] += 1
                pl["starts"] += info.starter
                pl["minutes"] += mins
                pl["positions"][info.positions[0] if info.positions else "?"] += mins
        if bench_wanted and i % 10 == 0:
            fc.log(f"[benchmark] {i}/{len(to_read)} matches")
    if not rows:
        raise SystemExit(f"no event data for {team} in {scope}")

    p = profile(totals[team])
    bench = None
    if args.benchmark:
        if single_team:
            bench = {"n": 0, "rows": [], "reason": f"该赛季开放数据只有 {team} 的比赛"}
        else:
            bench = rank_team(team, {t: profile(tot) for t, tot in totals.items()})
    players = sorted(({**pl, "position": pl["positions"].most_common(1)[0][0]} for pl in people.values()),
                     key=lambda pl: -pl["minutes"])
    for pl in players:
        del pl["positions"]

    out = fc.make_out_dir("team", f"{team}-{season_row['competition_name']}-{season_row['season_name']}", args.out)
    charts: dict[str, str] = {}
    if fc.charts_enabled(args.no_charts):
        import fa_charts as ch

        chart_rows = [{**r, "score": r["score_en"], "venue": "" if international else r["venue"]} for r in rows]
        jobs = {
            "xg_by_match": lambda path: ch.team_match_xg(chart_rows, team, f"{team} - {scope}: xG for and against",
                                                         path),
            "shots_for": lambda path: ch.player_shot_map(shots_for, f"{team} shots - {scope}", path),
            "shots_against": lambda path: ch.player_shot_map(shots_against, f"Shots conceded by {team} - {scope}",
                                                             path),
            "pressures": lambda path: ch.pressure_maps({team: pressure_pts["team"], "Opponents": pressure_pts["opp"]},
                                                       [team, "Opponents"], path),
            "style": lambda path: ch.player_pizza(
                [b["label_en"] for b in bench["rows"]], [b["percentile"] for b in bench["rows"]],
                f"{team} - team style", f"{scope} | percentile vs {bench['n']} teams with >= "
                                        f"{bench['min_matches']} matches", path,
                note="percentile rank among the teams; counts per 90, ratios pooled over matches")
            if bench and bench.get("rows") else None,
        }
        for key, job in jobs.items():
            try:
                saved = job(out / f"{key}.png")
                if saved:
                    charts[key] = saved
            except Exception as exc:  # noqa: BLE001 - one broken chart must not lose the report
                fc.log(f"[charts] {key} failed: {type(exc).__name__}: {exc}")

    fc.write_text(out / "report.md", report(team, scope, p, rows, formations, players, bench, charts, single_team,
                                            international))
    fc.write_csv(out / "matches.csv", rows)
    fc.write_json(out / "summary.json", {
        "team": team, "scope": scope, "competition_id": season_row["competition_id"],
        "season_id": season_row["season_id"], "single_team_dataset": single_team, "variants": fm.VARIANTS,
        "profile": p, "matches": rows, "formations": dict(formations), "players": players, "benchmark": bench,
    })
    res = p["results"]
    print(f"{team} ({scope}): {p['matches']} matches {res.get('W', 0)}-{res.get('D', 0)}-{res.get('L', 0)}, "
          f"npxG {p['npxg']:.2f} vs {p['opp_npxg']:.2f}, PPDA {p['ppda']}, field tilt {p['field_tilt']}"
          + (f", benchmark n={bench['n']}" if bench else ""))
    print(f"report: {out / 'report.md'}")
    return {"out_dir": str(out), "files": ["report.md", "summary.json", "matches.csv"] + sorted(charts.values())}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
