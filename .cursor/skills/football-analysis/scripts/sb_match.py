"""Match and tactics report from StatsBomb open data (event level).

    python sb_match.py --match 3869685
    python sb_match.py --match 3869685 --competition 43 --season 106 --min-pair-passes 4
    python sb_match.py --match 3869685 --no-charts

Writes outputs/match-<home>-vs-<away>-<id>/ with report.md (Chinese), summary.json,
players.csv and charts (shot map, xG race, passing networks, pressure maps, xT momentum).
Find match IDs with sb_find.py.
"""
from __future__ import annotations

import argparse

import fa_common as fc
import fa_metrics as fm

ROW_LABELS = [
    ("goals", "进球 Goals", 0),
    ("xg", "xG（含点球）", 2),
    ("npxg", "npxG（不含点球）", 2),
    ("shots", "射门 Shots", 0),
    ("shots_on_target", "射正 On target", 0),
    ("xg_per_np_shot", "每脚非点球射门 xG", 3),
    ("xg_assisted", "xG assisted（助攻机会质量）", 2),
    ("passes", "传球 Passes", 0),
    ("pass_completion", "传球成功率", 3),
    ("pass_share", "传球占比（控球代理）", 3),
    ("field_tilt", "Field tilt（前场三区传球占比）", 3),
    ("progressive_passes", "推进传球", 0),
    ("progressive_carries", "推进带球", 0),
    ("deep_progressions", "进入前场三区（传+带）", 0),
    ("box_entries", "进入禁区（传+带）", 0),
    ("xt_added", "xT added（威胁增量）", 2),
    ("ppda", "PPDA（越低压迫越强）", 2),
    ("pressures", "压迫次数 Pressures", 0),
    ("pressures_att_third", "前场三区压迫", 0),
    ("pressure_height", "压迫平均高度 x（0–120）", 1),
    ("def_action_height", "防守动作平均高度 x", 1),
]

DEFINITIONS = [
    ("xG / npxG", "xg.statsbomb-hudl / npxg.statsbomb-hudl", "StatsBomb 每脚射门 xG 求和；npxG 去掉点球；点球大战不计"),
    ("xG assisted", "xg_assisted.statsbomb-hudl", "关键传球所导致射门的 xG，记在传球方"),
    ("传球成功率", "pass_completion.statsbomb-hudl", "无 pass.outcome 的传球 / 全部传球（含定位球）"),
    ("PPDA", "ppda.statsbomb-hudl", "对手在其本方 60% 区域(x<72)的成功传球 / 本队在 x>=48 的抢断+拦截(含传球拦截)+被过+犯规"),
    ("Field tilt", "field_tilt.stats-perform-2016", "本队 x>=80 起脚的传球(不含传中/界外球/门将手抛) / 双方之和"),
    ("推进传球", "progressive_passes.statsbomb-blog-2023", "成功的非定位球传球，使球到球门中心距离缩短 >=25%"),
    ("推进带球", "progressive_carries.statsbomb-blog-2023", "带球使球到球门中心距离缩短 >=25%"),
    ("xT added", "xt.singh-open-12x8", "Karun Singh 12x8 xT 表：成功的运动战传球与带球，终点区值-起点区值"),
    ("其余计数", "无 football-docs 卡片（描述性）", "定义见 references/metrics.md，不与其他来源的同名数字比较"),
]


def build(args) -> dict:
    meta = fc.find_match_meta(args.match, args.competition, args.season)
    match = fm.Match.build(args.match, fc.sb_events(args.match), fc.sb_lineups(args.match), meta)
    grid = fc.xt_grid()
    home, away = match.teams
    team = fm.team_metrics(match, grid)
    players = sorted(fm.player_metrics(match, grid).values(),
                     key=lambda r: (match.teams.index(r["team"]) if r["team"] in match.teams else 9, -r["minutes"]))
    networks = [fm.pass_network(match, t, args.min_pair_passes) for t in match.teams]
    return {
        "match": match, "meta": meta, "grid": grid, "home": home, "away": away, "team": team,
        "players": players, "networks": networks, "formations": match.formations(),
        "events": match.key_events(), "shots": fm.shot_list(match), "timeline": fm.xg_timeline(match),
        "xt_windows": fm.xt_by_window(match, grid), "shootout": match.shootout(),
    }


def observations(d: dict) -> list[str]:
    t, home, away = d["team"], d["home"], d["away"]
    h, a = t[home], t[away]
    obs = []
    better = home if h["npxg"] >= a["npxg"] else away
    worse = away if better == home else home
    so = d["shootout"]
    score = f"{h['goals']}–{a['goals']}" + (f"（点球大战 {so[home]}–{so[away]}）" if so else "")
    obs.append(f"机会质量：{better} 的非点球机会更好（npxG {t[better]['npxg']:.2f} vs {t[worse]['npxg']:.2f}，"
               f"非点球射门 {t[better]['np_shots']} vs {t[worse]['np_shots']}）；含点球的 xG 为 {home} {h['xg']:.2f}、"
               f"{away} {a['xg']:.2f}；实际比分 {home} {score} {away}。")
    if h["xg_per_np_shot"] and a["xg_per_np_shot"]:
        obs.append(f"射门选择：每脚非点球射门 xG {home} {h['xg_per_np_shot']:.3f}，{away} {a['xg_per_np_shot']:.3f}"
                   "（越高说明在更好的位置起脚）。")
    if h["field_tilt"] is not None:
        dom = home if h["field_tilt"] >= 0.5 else away
        obs.append(f"领地：{dom} 掌握前场（field tilt {t[dom]['field_tilt']:.0%}，传球占比 {t[dom]['pass_share']:.0%}）。"
                   "领先方常主动回收，控球与领地需结合比分状态解读，不能单独证明谁踢得更好。")
    if h["ppda"] and a["ppda"]:
        hi = home if h["ppda"] <= a["ppda"] else away
        lo = away if hi == home else home
        text = (f"压迫：{hi} 的 PPDA 更低（{t[hi]['ppda']:.2f} vs {t[lo]['ppda']:.2f}），即对手在其后场 60% 区域"
                f"每完成 {t[hi]['ppda']:.1f} 次传球，{hi} 就做出一次抢断/拦截/犯规")
        higher = lo if (t[lo]["pressures_att_third"] > t[hi]["pressures_att_third"]
                        and (t[lo]["pressure_height"] or 0) > (t[hi]["pressure_height"] or 0)) else None
        if higher:
            text += (f"；但 {higher} 的 Pressure 事件更靠前（前场三区压迫 {t[higher]['pressures_att_third']} vs "
                     f"{t[hi]['pressures_att_third']}，平均高度 x={t[higher]['pressure_height']} vs "
                     f"{t[hi]['pressure_height']}），两类指标结论不同，需要结合比分状态看")
        obs.append(text + "。PPDA 只与同口径（ppda.statsbomb-hudl）的数字比较。")
    for side in (home, away):
        s = t[side]
        style = "更依赖带球推进" if s["progressive_carries"] > s["progressive_passes"] else "更依赖传球推进"
        obs.append(f"推进方式：{side} 推进传球 {s['progressive_passes']}、推进带球 {s['progressive_carries']}，{style}；"
                   f"进入前场三区 {s['deep_progressions']} 次，进入禁区 {s['box_entries']} 次。")
    if d["grid"] is not None:
        top = sorted(d["players"], key=lambda r: -(r["xt_added"] or 0))[:3]
        obs.append("威胁创造（xT added）前三：" + "；".join(f"{r['player']}（{r['team']}，{r['xt_added']:.2f}）" for r in top) + "。")
    for side in (home, away):
        f = d["formations"].get(side)
        if f and f["shifts"]:
            shifts = "，".join(f"{s['minute']} 改为 {s['formation']}" for s in f["shifts"])
            obs.append(f"阵型变化：{side} 首发 {f['starting']}，之后 {shifts}。")
    obs.append("样本提醒：以上均为单场数据，受比分状态、红牌、加时影响较大；做结论前请用多场或赛季数据复核。")
    return obs


def leaders(players: list[dict], grid_ok: bool) -> list[list[str]]:
    cats = [("xT added", lambda r: r["xt_added"] or 0, 2)] if grid_ok else []
    cats += [
        ("npxG", lambda r: r["npxg"], 2),
        ("xG assisted", lambda r: r["xg_assisted"], 2),
        ("推进传球+带球", lambda r: r["progressive_passes"] + r["progressive_carries"], 0),
        ("压迫 Pressures", lambda r: r["pressures"], 0),
        ("抢断+拦截", lambda r: r["tackles"] + r["interceptions"], 0),
    ]
    rows = []
    for label, key, digits in cats:
        top = [r for r in sorted(players, key=key, reverse=True)[:3] if key(r)]
        rows.append([label] + [f"{r['player']} ({fc.fmt(float(key(r)), digits) if digits else int(key(r))})" for r in top]
                    + [""] * (3 - len(top)))
    return rows


def report(d: dict, charts: dict[str, str]) -> str:
    m, meta, t, home, away = d["match"], d["meta"], d["team"], d["home"], d["away"]
    score = f"{t[home]['goals']}–{t[away]['goals']}"
    so = d["shootout"]
    title = f"# 比赛分析：{home} {score} {away}" + (f"（点球大战 {so[home]}–{so[away]}）" if so else "")
    if meta:
        ctx = (f"{meta['competition']['competition_name']} {meta['season']['season_name']} · "
               f"{meta.get('competition_stage', {}).get('name', '')} · {meta['match_date']}"
               f"{' · ' + meta['stadium']['name'] if meta.get('stadium') else ''}")
    else:
        ctx = "（未找到比赛元数据，比分由事件数据计算）"
    lines = [title, "", f"{ctx} · StatsBomb match `{m.match_id}`" + (" · 含加时" if m.extra_time else ""), "",
             "数据：StatsBomb 开放数据（Hudl StatsBomb）。每个指标的口径（football-docs 变体 ID）见文末；"
             "不同口径的数字不可直接比较。", ""]
    lines += ["## 1. 比赛概览", "",
              fc.md_table(["指标", home, away],
                          ([label, t[home][k], t[away][k]] for k, label, dg in ROW_LABELS[:7]), digits=2), ""]
    lines += ["### 关键事件", "", fc.md_table(["时间", "球队", "类型", "说明"],
                                          ([e["minute"], e["team"], e["type"], e["detail"]] for e in d["events"])), ""]
    if "shot_map" in charts:
        lines += [f"![shot map]({charts['shot_map']})", ""]
    if "xg_race" in charts:
        lines += [f"![xG race]({charts['xg_race']})", ""]

    lines += ["## 2. 战术分析", "", "### 2.1 阵型与首发", ""]
    for side in (home, away):
        f = d["formations"].get(side)
        if not f:
            continue
        shifts = "；".join(f"{s['minute']} → {s['formation']}" for s in f["shifts"]) or "无"
        lines += [f"**{side}** 首发 {f['starting']}（阵型变化：{shifts}）", "",
                  fc.md_table(["号码", "位置", "球员"], ([p["jersey"], p["position"], p["player"]] for p in f["lineup"])),
                  ""]
    lines += ["### 2.2 控球、领地与推进", "",
              fc.md_table(["指标", home, away], ([label, t[home][k], t[away][k]] for k, label, dg in ROW_LABELS[7:16]),
                          digits=3), ""]
    lines += ["### 2.3 压迫与防守", "",
              fc.md_table(["指标", home, away], ([label, t[home][k], t[away][k]] for k, label, dg in ROW_LABELS[16:]),
                          digits=2), "",
              f"PPDA 分子/分母：{home} = {t[home]['ppda_opp_passes']}/{t[home]['ppda_def_actions']}，"
              f"{away} = {t[away]['ppda_opp_passes']}/{t[away]['ppda_def_actions']}。", ""]
    if "pressures" in charts:
        lines += [f"![pressure maps]({charts['pressures']})", ""]
    lines += ["### 2.4 传球网络", ""]
    for net in d["networks"]:
        pairs = "；".join(f"{p['pair']}（{p['passes']}）" for p in net["top_pairs"]) or "无"
        lines += [f"- **{net['team']}**（时间窗 {net['window']}，至首次换人）最常见传球组合：{pairs}"]
    lines.append("")
    if "pass_network" in charts:
        lines += [f"![passing networks]({charts['pass_network']})", ""]
    if "xt_momentum" in charts:
        lines += ["### 2.5 威胁势能（xT momentum）", "", f"![xT momentum]({charts['xt_momentum']})", ""]

    lines += ["## 3. 球员表现", "", "### 各项前三", "",
              fc.md_table(["类别", "#1", "#2", "#3"], leaders(d["players"], d["grid"] is not None)), "",
              "### 全部出场球员", "",
              fc.md_table(["球员", "球队", "位置", "分钟", "进球", "npxG", "xGA", "关键传球", "推进传球", "推进带球",
                           "xT", "压迫", "抢断+拦截"],
                          ([r["player"], r["team"], r["position"], round(r["minutes"]), r["goals"], r["npxg"],
                            r["xg_assisted"],
                            r["key_passes"], r["progressive_passes"], r["progressive_carries"], r["xt_added"],
                            r["pressures"], r["tackles"] + r["interceptions"]] for r in d["players"]), digits=2), "",
              "完整字段见 `players.csv`（分钟为名义比赛时间，补时不计）。", ""]
    lines += ["## 4. 数据要点（自动生成，需人工复核）", ""] + [f"- {o}" for o in observations(d)] + [""]
    lines += ["## 5. 指标口径", "", fc.md_table(["指标", "变体 ID", "定义"], DEFINITIONS), "",
              "测试：`selftest.py` 用 football-docs 指标卡的测试值（2022 世界杯决赛）校验上述带变体 ID 的指标。", ""]
    return "\n".join(lines)


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--match", type=int, required=True, help="StatsBomb match_id (see sb_find.py matches)")
    ap.add_argument("--competition", type=int, help="competition_id (speeds up the metadata lookup)")
    ap.add_argument("--season", type=int, help="season_id")
    ap.add_argument("--min-pair-passes", type=int, default=3, help="passing-network edge threshold (default 3)")
    ap.add_argument("--no-charts", action="store_true", help="skip charts (no matplotlib/mplsoccer needed)")
    ap.add_argument("--out", help="output folder (default outputs/match-<home>-vs-<away>-<id>)")
    args = ap.parse_args()

    d = build(args)
    out = fc.make_out_dir("match", f"{d['home']}-vs-{d['away']}-{args.match}", args.out)
    charts: dict[str, str] = {}
    if fc.charts_enabled(args.no_charts):
        import fa_charts as ch

        jobs = {
            "shot_map": lambda p: ch.match_shot_map(d["shots"], d["match"].teams, d["team"], p),
            "xg_race": lambda p: ch.xg_race(d["timeline"], d["match"].teams, p),
            "pass_network": lambda p: ch.pass_networks(d["networks"], p),
            "pressures": lambda p: ch.pressure_maps(
                {t: [tuple(e["location"]) for e in d["match"].events
                     if fm.etype(e) == "Pressure" and fm.team_name(e) == t and fm.in_play(e)] for t in d["match"].teams},
                d["match"].teams, p),
            "xt_momentum": lambda p: ch.xt_momentum(d["xt_windows"], d["match"].teams, p) if d["xt_windows"] else None,
        }
        for name, job in jobs.items():
            try:
                saved = job(out / f"{name}.png")
                if saved:
                    charts[name] = saved
            except Exception as exc:  # noqa: BLE001 - one broken chart must not lose the report
                fc.log(f"[charts] {name} failed: {type(exc).__name__}: {exc}")
    fc.write_text(out / "report.md", report(d, charts))
    fc.write_csv(out / "players.csv", d["players"])
    fc.write_json(out / "summary.json", {
        "match_id": args.match, "teams": d["match"].teams, "meta": d["meta"], "variants": fm.VARIANTS,
        "team_metrics": d["team"], "formations": d["formations"], "key_events": d["events"],
        "shootout": d["shootout"], "pass_networks": d["networks"], "xt_by_5min": d["xt_windows"],
        "players": d["players"],
    })
    t = d["team"]
    print(f"{d['home']} {t[d['home']]['goals']}-{t[d['away']]['goals']} {d['away']} | "
          f"xG {t[d['home']]['xg']:.2f}-{t[d['away']]['xg']:.2f} | PPDA {t[d['home']]['ppda']}-{t[d['away']]['ppda']}"
          f" | field tilt {t[d['home']]['field_tilt']}-{t[d['away']]['field_tilt']}")
    print(f"report: {out / 'report.md'}")
    return {"out_dir": str(out), "files": ["report.md", "summary.json", "players.csv"] + sorted(charts.values())}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
