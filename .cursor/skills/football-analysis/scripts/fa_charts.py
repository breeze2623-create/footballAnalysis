"""Charts for the football-analysis reports (matplotlib + mplsoccer, Agg backend).

Import this module only after fa_common.charts_enabled() returned True. Labels are
English on purpose: default matplotlib fonts have no CJK glyphs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mplsoccer import Pitch, PyPizza, VerticalPitch  # noqa: E402

TEAM_COLOURS = ("#1f6fb4", "#d1495b")
PITCH_KW = dict(pitch_type="statsbomb", pitch_color="#fbfbf8", line_color="#a9b4bb", line_zorder=1)
CREDIT = "Data: StatsBomb open data (Hudl)"


def _save(fig, path: Path, note: str | None = None, credit: str = CREDIT) -> str:
    fig.text(0.99, 0.0, credit + (f" | {note}" if note else ""), ha="right", va="top", fontsize=8, color="#666")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path.name


def match_shot_map(shots: list[dict], teams: list[str], totals: dict[str, dict], path: Path,
                   credit: str = CREDIT, xg_variant: str = "xg.statsbomb-hudl") -> str:
    pitch = Pitch(**PITCH_KW)
    fig, ax = pitch.draw(figsize=(12, 8))
    for i, team in enumerate(teams):
        for s in (s for s in shots if s["team"] == team):
            x, y = (s["x"], s["y"]) if i == 0 else (120 - s["x"], 80 - s["y"])
            goal = s["outcome"] == "Goal"
            pitch.scatter(x, y, s=80 + 1400 * s["xg"], ax=ax, zorder=3 if goal else 2,
                          marker="football" if goal else "o",
                          c="white" if goal else TEAM_COLOURS[i], alpha=1 if goal else 0.55,
                          edgecolors=TEAM_COLOURS[i], linewidths=1.2)
    home, away = teams
    ax.set_title(f"{home} {totals[home]['goals']} ({totals[home]['xg']:.2f} xG)  vs  "
                 f"{totals[away]['goals']} ({totals[away]['xg']:.2f} xG) {away}", fontsize=15)
    ax.text(2, -3, f"<- {away} attack", color=TEAM_COLOURS[1], fontsize=11)
    ax.text(118, -3, f"{home} attack ->", color=TEAM_COLOURS[0], fontsize=11, ha="right")
    return _save(fig, path, f"marker size = xG ({xg_variant}), ball = goal, shoot-out excluded", credit)


def xg_race(timeline: dict[str, Any], teams: list[str], path: Path,
            credit: str = CREDIT, xg_variant: str = "xg.statsbomb-hudl") -> str:
    fig, ax = plt.subplots(figsize=(12, 5.5))
    end = max([pe for _, pe in timeline["period_ends"]] or [90])
    for i, team in enumerate(teams):
        shots = sorted((s for s in timeline["shots"] if s["team"] == team), key=lambda s: s["t"])
        xs, ys, total, last_label = [0.0], [0.0], 0.0, -99.0
        for s in shots:
            xs += [s["t"], s["t"]]
            ys += [total, total + s["xg"]]
            total += s["xg"]
            if s["goal"]:
                crowded = s["t"] - last_label < 6
                last_label = s["t"]
                ax.scatter([s["t"]], [total], s=70, color=TEAM_COLOURS[i], zorder=3, edgecolors="black")
                ax.annotate(f"{s['player']} {s['minute']}", (s["t"], total), xytext=(6, -14 if crowded else 6),
                            textcoords="offset points", fontsize=8, color=TEAM_COLOURS[i])
        xs.append(end)
        ys.append(total)
        ax.plot(xs, ys, color=TEAM_COLOURS[i], lw=2.2, label=f"{team} {total:.2f} xG")
    labels = {1: "HT", 2: "FT", 3: "ET HT", 4: "AET"}
    for period, t in timeline["period_ends"]:
        ax.axvline(t, color="#bbb", ls="--", lw=1)
        ax.text(t, ax.get_ylim()[1] * 0.98, labels.get(period, ""), ha="right", va="top", fontsize=8, color="#777")
    ax.set_xlabel("minutes elapsed (stoppage time included)")
    ax.set_ylabel("cumulative xG")
    ax.set_xlim(0, end)
    ax.legend(loc="upper left")
    ax.grid(alpha=0.25)
    ax.set_title("xG race")
    return _save(fig, path, f"{xg_variant}, shoot-out excluded", credit)


def pass_networks(networks: list[dict], path: Path) -> str:
    pitch = Pitch(**PITCH_KW)
    fig, axs = pitch.draw(nrows=1, ncols=len(networks), figsize=(16, 6.5))
    axs = list(axs) if hasattr(axs, "__iter__") else [axs]
    for i, (net, ax) in enumerate(zip(networks, axs)):
        pos = {n["player_id"]: n for n in net["nodes"]}
        top = max((e["passes"] for e in net["edges"]), default=1)
        for e in net["edges"]:
            a, b = pos[e["a"]], pos[e["b"]]
            pitch.lines(a["x"], a["y"], b["x"], b["y"], lw=1 + 9 * e["passes"] / top, color=TEAM_COLOURS[i],
                        alpha=0.25 + 0.6 * e["passes"] / top, zorder=2, ax=ax)
        most = max((n["passes"] for n in net["nodes"]), default=1)
        for n in net["nodes"]:
            pitch.scatter(n["x"], n["y"], s=250 + 1100 * n["passes"] / most, color=TEAM_COLOURS[i],
                          edgecolors="black", linewidths=1, zorder=3, ax=ax)
            pitch.annotate(str(n["jersey"] or ""), xy=(n["x"], n["y"]), c="white", va="center", ha="center",
                           fontsize=10, weight="bold", zorder=4, ax=ax)
        ax.set_title(f"{net['team']} passing network ({net['window']})", fontsize=13)
    return _save(fig, path, "node = mean pass origin, size = completed passes; lines = pairs with >= min passes")


def pressure_maps(points: dict[str, list[tuple[float, float]]], teams: list[str], path: Path) -> str:
    pitch = Pitch(**PITCH_KW)
    fig, axs = pitch.draw(nrows=1, ncols=2, figsize=(16, 6.5))
    for i, (team, ax) in enumerate(zip(teams, axs)):
        pts = points.get(team) or []
        if pts:
            bs = pitch.bin_statistic([p[0] for p in pts], [p[1] for p in pts], statistic="count",
                                     bins=(6, 5), normalize=True)
            pitch.heatmap(bs, ax=ax, cmap="Blues" if i == 0 else "Reds", edgecolors="#fbfbf8", alpha=0.85)
            pitch.label_heatmap(bs, ax=ax, str_format="{:.0%}", fontsize=10, ha="center", va="center",
                                color="#222", exclude_zeros=True)
        ax.set_title(f"{team} pressures (n={len(pts)}), attacking ->", fontsize=13)
    return _save(fig, path, "StatsBomb Pressure events, share per zone")


def xt_momentum(windows: list[dict], teams: list[str], path: Path) -> str:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    labels, values = [], []
    for w in windows:
        labels.append(f"{int(w['from'])}-{int(w['to'])}")
        values.append(w.get(teams[0], 0.0) - w.get(teams[1], 0.0))
    colours = [TEAM_COLOURS[0] if v >= 0 else TEAM_COLOURS[1] for v in values]
    ax.bar(range(len(values)), values, color=colours, width=0.85)
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=60, fontsize=8)
    ax.set_ylabel(f"xT added: {teams[0]} minus {teams[1]}")
    ax.set_title(f"Threat momentum per 5 minutes (up = {teams[0]}, down = {teams[1]})")
    ax.grid(axis="y", alpha=0.25)
    return _save(fig, path, "xt.singh-open-12x8; stoppage time folded into each period's last window")


def player_shot_map(shots: list[dict], title: str, path: Path,
                    credit: str = CREDIT, xg_variant: str = "xg.statsbomb-hudl") -> str:
    pitch = VerticalPitch(half=True, **PITCH_KW)
    fig, ax = pitch.draw(figsize=(8, 7))
    for s in shots:
        goal = s["outcome"] == "Goal"
        pitch.scatter(s["x"], s["y"], s=80 + 1400 * s["xg"], ax=ax, marker="football" if goal else "o",
                      c="white" if goal else TEAM_COLOURS[0], alpha=1 if goal else 0.55,
                      edgecolors=TEAM_COLOURS[0], linewidths=1.2, zorder=3 if goal else 2)
    goals = sum(s["outcome"] == "Goal" for s in shots)
    xg = sum(s["xg"] for s in shots)
    ax.set_title(f"{title}\n{len(shots)} shot{'s' * (len(shots) != 1)}, {goals} goal{'s' * (goals != 1)}, {xg:.2f} xG",
                 fontsize=13)
    return _save(fig, path, f"size = xG ({xg_variant}), ball = goal", credit)


def player_match_bars(rows: list[dict], title: str, path: Path, credit: str = CREDIT) -> str:
    """Per-match xG and xA bars; goals and assists printed above each pair."""
    fig, ax = plt.subplots(figsize=(max(8, 0.9 * len(rows) + 3), 5))
    idx = range(len(rows))
    xg = [r.get("xg") or 0 for r in rows]
    xa = [r.get("xa") or 0 for r in rows]
    ax.bar([i - 0.2 for i in idx], xg, width=0.4, color=TEAM_COLOURS[0], label="xG")
    ax.bar([i + 0.2 for i in idx], xa, width=0.4, color=TEAM_COLOURS[1], label="xA")
    top = max(xg + xa + [0.5])
    for i, r in zip(idx, rows):
        tag = " ".join(t for t in (f"{r['goals']}G" if r.get("goals") else "", f"{r['assists']}A" if r.get("assists")
                                   else "") if t)
        if tag:
            ax.text(i, max(xg[i], xa[i]) + top * 0.03, tag, ha="center", fontsize=9, weight="bold")
    ax.set_xticks(list(idx))
    ax.set_xticklabels([f"{r['date']}\n{r['venue']} {r['opponent']}\n{r['minutes']:.0f}'" for r in rows], fontsize=8)
    ax.set_ylim(0, top * 1.2)
    ax.set_ylabel("per match")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    ax.set_title(title)
    return _save(fig, path, "xG = xg.understat, xA = xg_assisted.understat; G/A = goals/assists", credit)


def team_match_xg(rows: list[dict], team: str, title: str, path: Path, window: int = 5) -> str:
    """xG for and against per match: bars with the score for up to 12 matches, rolling means beyond that."""
    n = len(rows)
    xg_for = [r["xg"] for r in rows]
    xg_against = [r["xg_against"] for r in rows]
    if n > 12:
        fig, ax = plt.subplots(figsize=(12, 5.5))
        x = list(range(1, n + 1))

        def rolling(v: list[float]) -> list[float]:
            return [sum(v[max(0, i - window + 1):i + 1]) / len(v[max(0, i - window + 1):i + 1]) for i in range(n)]

        for vals, colour, label in ((xg_for, TEAM_COLOURS[0], f"{team} xG"),
                                    (xg_against, TEAM_COLOURS[1], "opponent xG")):
            ax.scatter(x, vals, color=colour, alpha=0.3, s=18)
            ax.plot(x, rolling(vals), color=colour, lw=2.2, label=f"{label}, {window}-match rolling mean")
        ax.set_xlim(0.5, n + 0.5)
        ax.set_xlabel(f"match number ({rows[0]['date']} to {rows[-1]['date']}); dots = single matches")
        note = (f"xg.statsbomb-hudl incl. penalties, shoot-out excluded; "
                f"the first {window - 1} points average fewer matches")
    else:
        fig, ax = plt.subplots(figsize=(max(8, 0.9 * n + 3), 5.5))
        idx = range(n)
        ax.bar([i - 0.2 for i in idx], xg_for, width=0.4, color=TEAM_COLOURS[0], label=f"{team} xG")
        ax.bar([i + 0.2 for i in idx], xg_against, width=0.4, color=TEAM_COLOURS[1], label="opponent xG")
        top = max(xg_for + xg_against + [0.5])
        for i, r in zip(idx, rows):
            ax.text(i, max(xg_for[i], xg_against[i]) + top * 0.03, r["score"], ha="center", fontsize=9,
                    weight="bold")
        ax.set_xticks(list(idx))
        ax.set_xticklabels([f"{r['date']}\n{r['venue']} {r['opponent']}".replace("\n ", "\n") for r in rows],
                           fontsize=8)
        ax.set_ylim(0, top * 1.2)
        note = "xg.statsbomb-hudl incl. penalties, shoot-out excluded; label = score (team first)"
    ax.set_ylabel("xG per match")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    ax.set_title(title)
    return _save(fig, path, note)


def player_heatmap(points: list[list[float]], title: str, path: Path) -> str:
    from scipy.ndimage import gaussian_filter

    pitch = Pitch(**PITCH_KW)
    fig, ax = pitch.draw(figsize=(12, 8))
    if points:
        bs = pitch.bin_statistic([p[0] for p in points], [p[1] for p in points], statistic="count", bins=(30, 20))
        bs["statistic"] = gaussian_filter(bs["statistic"], 1.2)
        pitch.heatmap(bs, ax=ax, cmap="YlOrRd", edgecolors="none", alpha=0.9)
    ax.set_title(f"{title}: on-ball and defensive actions (n={len(points)}), attacking ->", fontsize=13)
    return _save(fig, path)


def player_progression_map(passes: list[dict], carries: list[dict], title: str, path: Path) -> str:
    pitch = Pitch(**PITCH_KW)
    fig, ax = pitch.draw(figsize=(12, 8))
    if passes:
        pitch.arrows([p["x"] for p in passes], [p["y"] for p in passes], [p["end_x"] for p in passes],
                     [p["end_y"] for p in passes], width=2, headwidth=5, headlength=5, color=TEAM_COLOURS[0],
                     alpha=0.8, ax=ax, label=f"progressive passes ({len(passes)})")
    if carries:
        pitch.arrows([c["x"] for c in carries], [c["y"] for c in carries], [c["end_x"] for c in carries],
                     [c["end_y"] for c in carries], width=1.5, headwidth=4, headlength=4, color=TEAM_COLOURS[1],
                     alpha=0.7, ax=ax, label=f"progressive carries ({len(carries)})")
    if passes or carries:
        ax.legend(loc="upper left", fontsize=10)
    ax.set_title(f"{title}: progressive actions, attacking ->", fontsize=13)
    return _save(fig, path, "progressive_*.statsbomb-blog-2023 (>= 25% closer to goal centre)")


def player_pizza(params: list[str], percentiles: list[float], title: str, subtitle: str, path: Path,
                 note: str = "percentile rank vs. the comparison group, per 90") -> str:
    baker = PyPizza(params=params, background_color="#fbfbf8", straight_line_color="#d0d0d0",
                    straight_line_lw=1, last_circle_lw=1, other_circle_lw=0, inner_circle_size=18)
    fig, ax = baker.make_pizza(
        [round(p) for p in percentiles], figsize=(9, 9.5), param_location=110,
        kwargs_slices=dict(facecolor=TEAM_COLOURS[0], edgecolor="#fbfbf8", zorder=2, linewidth=1),
        kwargs_params=dict(color="#222", fontsize=10, va="center"),
        kwargs_values=dict(color="#222", fontsize=10, zorder=3,
                           bbox=dict(edgecolor="#222", facecolor="white", boxstyle="round,pad=0.2", lw=1)),
    )
    fig.text(0.5, 0.985, title, ha="center", va="top", fontsize=15, weight="bold")
    fig.text(0.5, 0.955, subtitle, ha="center", va="top", fontsize=10, color="#555")
    return _save(fig, path, note)
