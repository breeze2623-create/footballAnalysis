"""Football metrics on StatsBomb open-data events, in plain Python.

Metrics that have a football-docs metric card carry the variant ID they implement
(``ppda.statsbomb-hudl`` and so on); selftest.py checks them against the cards'
test values on the 2022 World Cup final. Descriptive counts without a card are
defined in references/metrics.md.

StatsBomb coordinates: 120 x 80 pitch, and every event is given in the direction
of the team that made it (that team attacks towards x = 120).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

GOAL_CENTRE = (120.0, 40.0)
PERIOD_START = {1: 0.0, 2: 45.0, 3: 90.0, 4: 105.0}
PERIOD_END = {1: 45.0, 2: 90.0, 3: 105.0, 4: 120.0}
SET_PIECE_PASSES = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
XT_SKIPPED_PASSES = {"Free Kick", "Corner", "Throw-in", "Goal Kick"}
SHOT_ON_TARGET = {"Goal", "Saved", "Saved To Post", "Saved to Post"}
TACKLE_WON = {"Won", "Success In Play", "Success Out"}
SENDING_OFF = {"Red Card", "Second Yellow"}

VARIANTS = {
    "xg": "xg.statsbomb-hudl",
    "npxg": "npxg.statsbomb-hudl",
    "xg_assisted": "xg_assisted.statsbomb-hudl",
    "pass_completion": "pass_completion.statsbomb-hudl",
    "ppda": "ppda.statsbomb-hudl",
    "field_tilt": "field_tilt.stats-perform-2016",
    "progressive_passes": "progressive_passes.statsbomb-blog-2023",
    "progressive_carries": "progressive_carries.statsbomb-blog-2023",
    "xt_added": "xt.singh-open-12x8",
}


# ---------------------------------------------------------------- event helpers


def etype(e: dict) -> str:
    return e["type"]["name"]


def team_name(e: dict) -> str | None:
    return (e.get("team") or {}).get("name")


def player_id(e: dict) -> int | None:
    return (e.get("player") or {}).get("id")


def sub(e: dict, *keys: str) -> Any:
    cur: Any = e
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def in_play(e: dict) -> bool:
    """Everything except the penalty shoot-out (period 5)."""
    return e.get("period") != 5


def clock(e: dict) -> float:
    return e["minute"] + e["second"] / 60.0


def nominal_clock(e: dict) -> float:
    """Match clock with stoppage time folded into the end of its period (45, 90, 105, 120)."""
    return min(clock(e), PERIOD_END.get(e["period"], clock(e)))


def minute_label(e: dict) -> str:
    """Broadcast-style minute: StatsBomb minute 22 (22:xx) is the 23rd minute; stoppage shows as 90+5'."""
    m = e["minute"] + 1
    end = PERIOD_END.get(e["period"])
    if end is not None and m > end:
        return f"{int(end)}+{int(m - end)}'"
    return f"{m}'"


def pass_type(e: dict) -> str | None:
    return sub(e, "pass", "type", "name")


def is_completed_pass(e: dict) -> bool:
    return etype(e) == "Pass" and sub(e, "pass", "outcome") is None


def dist_to_goal(xy: list[float]) -> float:
    return math.hypot(GOAL_CENTRE[0] - xy[0], GOAL_CENTRE[1] - xy[1])


def moves_25pct_closer(start: list[float], end: list[float]) -> bool:
    return dist_to_goal(end) <= 0.75 * dist_to_goal(start)


def is_progressive_pass(e: dict) -> bool:
    """progressive_passes.statsbomb-blog-2023: completed, not a set piece, >= 25% closer to goal centre."""
    return (in_play(e) and is_completed_pass(e) and pass_type(e) not in SET_PIECE_PASSES
            and moves_25pct_closer(e["location"], e["pass"]["end_location"]))


def is_progressive_carry(e: dict) -> bool:
    """progressive_carries.statsbomb-blog-2023: any carry >= 25% closer to goal centre."""
    return (in_play(e) and etype(e) == "Carry"
            and moves_25pct_closer(e["location"], e["carry"]["end_location"]))


def is_ppda_defensive_action(e: dict) -> bool:
    """Defensive actions of ppda.statsbomb-hudl (zone filter applied by the caller)."""
    t = etype(e)
    return ((t == "Duel" and sub(e, "duel", "type", "name") == "Tackle")
            or t in ("Interception", "Dribbled Past", "Foul Committed")
            or (t == "Pass" and pass_type(e) == "Interception"))


def is_field_tilt_pass(e: dict) -> bool:
    """field_tilt.stats-perform-2016 pass set: Opta-like passes started at x >= 80 (completed or not)."""
    return (in_play(e) and etype(e) == "Pass" and e["location"][0] >= 80
            and not sub(e, "pass", "cross") and pass_type(e) != "Throw-in"
            and sub(e, "pass", "body_part", "name") != "Keeper Arm")


def in_box(xy: list[float]) -> bool:
    return xy[0] >= 102 and 18 <= xy[1] <= 62


def xt_zone_value(grid: list[list[float]], xy: list[float]) -> float:
    col = min(max(int(xy[0] / 120 * 12), 0), 11)
    row = min(max(int(xy[1] / 80 * 8), 0), 7)
    return grid[row][col]


def xt_added(e: dict, grid: list[list[float]] | None) -> float | None:
    """xt.singh-open-12x8: end-zone minus start-zone value for completed open passes and all carries."""
    if grid is None or not in_play(e):
        return None
    t = etype(e)
    if t == "Pass" and is_completed_pass(e) and pass_type(e) not in XT_SKIPPED_PASSES:
        end = e["pass"]["end_location"]
    elif t == "Carry":
        end = e["carry"]["end_location"]
    else:
        return None
    return xt_zone_value(grid, end) - xt_zone_value(grid, e["location"])


def formation_label(code: Any) -> str:
    s = str(code or "")
    return "-".join(s) if s.isdigit() else (s or "?")


# ------------------------------------------------------------------- match model


@dataclass
class PlayerInfo:
    player_id: int
    name: str
    nickname: str | None
    team: str
    jersey: int | None
    starter: bool = False
    positions: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        return self.nickname or self.name


@dataclass
class Match:
    match_id: int
    events: list[dict]
    teams: list[str]
    players: dict[int, PlayerInfo]
    meta: dict | None = None

    @classmethod
    def build(cls, match_id: int, events: list[dict], lineups: list[dict], meta: dict | None = None) -> "Match":
        if meta:
            teams = [meta["home_team"]["home_team_name"], meta["away_team"]["away_team_name"]]
        else:
            teams = [team_name(e) for e in events if etype(e) == "Starting XI"][:2]
        players: dict[int, PlayerInfo] = {}
        for t in lineups:
            for p in t["lineup"]:
                if not p.get("positions"):
                    continue
                players[p["player_id"]] = PlayerInfo(
                    player_id=p["player_id"], name=p["player_name"], nickname=p.get("player_nickname"),
                    team=t["team_name"], jersey=p.get("jersey_number"),
                    starter=any(pos.get("start_reason") == "Starting XI" for pos in p["positions"]),
                    positions=[pos["position"] for pos in p["positions"]],
                )
        events = sorted(events, key=lambda e: e["index"])
        return cls(match_id=match_id, events=events, teams=teams, players=players, meta=meta)

    def opponent(self, team: str) -> str:
        return self.teams[1] if team == self.teams[0] else self.teams[0]

    @property
    def extra_time(self) -> bool:
        return any(e["period"] in (3, 4) for e in self.events)

    @property
    def length(self) -> float:
        return 120.0 if self.extra_time else 90.0

    def display_name(self, pid: int | None, fallback: str | None = None) -> str:
        info = self.players.get(pid) if pid is not None else None
        return info.display if info else (fallback or "?")

    # ------------------------------------------------------------ minutes, timing

    def minutes(self) -> dict[int, float]:
        """Minutes on the pitch on the nominal clock (stoppage time not counted, FBref-style)."""
        start: dict[int, float] = {}
        end: dict[int, float] = {}
        for e in self.events:
            t = etype(e)
            if t == "Starting XI":
                for slot in e["tactics"]["lineup"]:
                    start[slot["player"]["id"]] = 0.0
            elif not in_play(e):
                continue
            elif t == "Substitution":
                at = nominal_clock(e)
                end.setdefault(player_id(e), at)
                start.setdefault(e["substitution"]["replacement"]["id"], at)
            elif t in ("Foul Committed", "Bad Behaviour"):
                card = sub(e, "foul_committed", "card", "name") or sub(e, "bad_behaviour", "card", "name")
                if card in SENDING_OFF:
                    end.setdefault(player_id(e), nominal_clock(e))
        out = {}
        for pid, s in start.items():
            m = end.get(pid, self.length) - s
            out[pid] = round(max(m, 1.0 if s > 0 else 0.0), 1)
        return out

    def elapsed_mapper(self):
        """Map an event to minutes elapsed since kick-off (stoppage time kept, no overlap between periods)."""
        last: dict[int, float] = {}
        for e in self.events:
            if e["period"] in PERIOD_START:
                last[e["period"]] = max(last.get(e["period"], 0.0), clock(e))
        offset, acc = {}, 0.0
        for p in sorted(last):
            offset[p] = acc - PERIOD_START[p]
            acc += max(last[p] - PERIOD_START[p], 0.0)
        period_ends = []
        acc = 0.0
        for p in sorted(last):
            acc += max(last[p] - PERIOD_START[p], 0.0)
            period_ends.append((p, acc))

        def to_elapsed(e: dict) -> float:
            return clock(e) + offset.get(e["period"], 0.0)

        return to_elapsed, period_ends

    # ------------------------------------------------------------------ summaries

    def score(self) -> dict[str, int]:
        goals = Counter()
        for e in self.events:
            if not in_play(e):
                continue
            if etype(e) == "Shot" and sub(e, "shot", "outcome", "name") == "Goal":
                goals[team_name(e)] += 1
            elif etype(e) == "Own Goal For":
                goals[team_name(e)] += 1
        return {t: goals.get(t, 0) for t in self.teams}

    def shootout(self) -> dict[str, int] | None:
        kicks = [e for e in self.events if e["period"] == 5 and etype(e) == "Shot"]
        if not kicks:
            return None
        scored = Counter(team_name(e) for e in kicks if sub(e, "shot", "outcome", "name") == "Goal")
        return {t: scored.get(t, 0) for t in self.teams}

    def key_events(self) -> list[dict]:
        out = []
        shape: dict[str, str] = {}
        for e in self.events:
            t = etype(e)
            row = None
            if t == "Starting XI":
                shape[team_name(e)] = formation_label(sub(e, "tactics", "formation"))
            if t == "Shot" and sub(e, "shot", "outcome", "name") == "Goal" and in_play(e):
                kind = "PEN" if sub(e, "shot", "type", "name") == "Penalty" else "GOAL"
                row = (kind, f"{self.display_name(player_id(e))} (xG {e['shot'].get('statsbomb_xg', 0):.2f})")
            elif t == "Own Goal Against":
                row = ("OG", f"own goal by {self.display_name(player_id(e))}")
            elif t == "Substitution" and in_play(e):
                row = ("SUB", f"{self.display_name(e['substitution']['replacement']['id'])} on for "
                              f"{self.display_name(player_id(e))}")
            elif t in ("Foul Committed", "Bad Behaviour"):
                card = sub(e, "foul_committed", "card", "name") or sub(e, "bad_behaviour", "card", "name")
                if card:
                    row = (card.upper().replace(" CARD", ""), self.display_name(player_id(e)))
            elif t == "Tactical Shift":
                new = formation_label(sub(e, "tactics", "formation"))
                if new != shape.get(team_name(e)):
                    row = ("SHAPE", f"formation {shape.get(team_name(e), '?')} -> {new}")
                    shape[team_name(e)] = new
            if row:
                out.append({"minute": minute_label(e), "period": e["period"], "team": team_name(e),
                            "type": row[0], "detail": row[1]})
        return out

    def formations(self) -> dict[str, dict]:
        """Starting formation and lineup per team, plus every change of formation (not mere position swaps)."""
        out: dict[str, dict] = {}
        for e in self.events:
            if etype(e) == "Starting XI":
                out[team_name(e)] = {
                    "starting": formation_label(sub(e, "tactics", "formation")),
                    "lineup": [{"jersey": s.get("jersey_number"), "position": s["position"]["name"],
                                "player": self.display_name(s["player"]["id"], s["player"]["name"])}
                               for s in e["tactics"]["lineup"]],
                    "shifts": [],
                }
            elif etype(e) == "Tactical Shift" and team_name(e) in out:
                f = out[team_name(e)]
                new = formation_label(sub(e, "tactics", "formation"))
                if new != (f["shifts"][-1]["formation"] if f["shifts"] else f["starting"]):
                    f["shifts"].append({"minute": minute_label(e), "formation": new})
        return out


# --------------------------------------------------------------- team metrics


def team_metrics(match: Match, grid: list[list[float]] | None) -> dict[str, dict[str, Any]]:
    """All team-level numbers for one match, keyed by team name."""
    by_id = {e["id"]: e for e in match.events}
    c: dict[str, Counter] = {t: Counter() for t in match.teams}
    xs: dict[str, dict[str, list[float]]] = {t: defaultdict(list) for t in match.teams}
    for e in match.events:
        t = team_name(e)
        if t not in c or not in_play(e):
            continue
        typ = etype(e)
        loc = e.get("location")
        k = c[t]
        if typ == "Shot":
            xg = e["shot"].get("statsbomb_xg", 0.0)
            k["shots"] += 1
            k["xg"] += xg
            if sub(e, "shot", "type", "name") != "Penalty":
                k["np_shots"] += 1
                k["npxg"] += xg
            if sub(e, "shot", "outcome", "name") in SHOT_ON_TARGET:
                k["shots_on_target"] += 1
            kp = e["shot"].get("key_pass_id")
            if kp in by_id and team_name(by_id[kp]) in c:
                c[team_name(by_id[kp])]["xg_assisted"] += xg
                c[team_name(by_id[kp])]["assisted_shots"] += 1
        elif typ == "Pass":
            k["passes"] += 1
            if is_completed_pass(e):
                k["passes_completed"] += 1
                if loc[0] < 72:
                    k["completed_passes_own_60pct"] += 1
                end = e["pass"]["end_location"]
                if loc[0] < 80 <= end[0]:
                    k["deep_progressions"] += 1
                if in_box(end) and not in_box(loc) and pass_type(e) not in SET_PIECE_PASSES:
                    k["box_entries"] += 1
            if is_progressive_pass(e):
                k["progressive_passes"] += 1
            if is_field_tilt_pass(e):
                k["final_third_passes"] += 1
        elif typ == "Carry":
            end = e["carry"]["end_location"]
            if is_progressive_carry(e):
                k["progressive_carries"] += 1
            if loc[0] < 80 <= end[0]:
                k["deep_progressions"] += 1
            if in_box(end) and not in_box(loc):
                k["box_entries"] += 1
        elif typ == "Pressure":
            k["pressures"] += 1
            xs[t]["pressure_x"].append(loc[0])
            if loc[0] >= 80:
                k["pressures_att_third"] += 1
        if is_ppda_defensive_action(e) and loc:
            xs[t]["def_action_x"].append(loc[0])
            if loc[0] >= 48:
                k["ppda_def_actions"] += 1
        v = xt_added(e, grid)
        if v is not None:
            k["xt_added"] += v
    score = match.score()
    all_passes = sum(c[t]["passes"] for t in match.teams) or 1
    out: dict[str, dict[str, Any]] = {}
    for t in match.teams:
        o = match.opponent(t)
        k = c[t]
        ft_total = k["final_third_passes"] + c[o]["final_third_passes"]
        out[t] = {
            "goals": score[t],
            "xg": round(k["xg"], 4),
            "npxg": round(k["npxg"], 4),
            "shots": k["shots"],
            "np_shots": k["np_shots"],
            "shots_on_target": k["shots_on_target"],
            "xg_per_np_shot": round(k["npxg"] / k["np_shots"], 3) if k["np_shots"] else None,
            "xg_assisted": round(k["xg_assisted"], 4),
            "assisted_shots": k["assisted_shots"],
            "passes": k["passes"],
            "passes_completed": k["passes_completed"],
            "pass_completion": round(k["passes_completed"] / k["passes"], 4) if k["passes"] else None,
            "pass_share": round(k["passes"] / all_passes, 4),
            "ppda": round(c[o]["completed_passes_own_60pct"] / k["ppda_def_actions"], 4)
            if k["ppda_def_actions"] else None,
            "ppda_opp_passes": c[o]["completed_passes_own_60pct"],
            "ppda_def_actions": k["ppda_def_actions"],
            "field_tilt": round(k["final_third_passes"] / ft_total, 4) if ft_total else None,
            "final_third_passes": k["final_third_passes"],
            "progressive_passes": k["progressive_passes"],
            "progressive_carries": k["progressive_carries"],
            "deep_progressions": k["deep_progressions"],
            "box_entries": k["box_entries"],
            "xt_added": round(k["xt_added"], 4) if grid is not None else None,
            "pressures": k["pressures"],
            "pressures_att_third": k["pressures_att_third"],
            "pressure_height": round(sum(xs[t]["pressure_x"]) / len(xs[t]["pressure_x"]), 1)
            if xs[t]["pressure_x"] else None,
            "def_action_height": round(sum(xs[t]["def_action_x"]) / len(xs[t]["def_action_x"]), 1)
            if xs[t]["def_action_x"] else None,
        }
    return out


# -------------------------------------------------------------- player metrics

PLAYER_COUNTS = [
    "goals", "np_goals", "penalty_goals", "shots", "np_shots", "shots_on_target", "xg", "npxg",
    "xg_assisted", "key_passes", "assists", "passes", "passes_completed", "progressive_passes",
    "progressive_carries", "deep_progressions", "box_entries", "xt_added", "carries", "dribbles",
    "dribbles_completed", "box_receptions", "pressures", "pressures_att_third", "tackles", "tackles_won",
    "interceptions", "ball_recoveries", "blocks", "clearances", "fouls_committed", "fouls_won",
    "dispossessed", "miscontrols",
]
FLOAT_COUNTS = {"xg", "npxg", "xg_assisted", "xt_added"}


def player_metrics(match: Match, grid: list[list[float]] | None) -> dict[int, dict[str, Any]]:
    """Per-player counts for one match (penalty shoot-out excluded), keyed by StatsBomb player ID."""
    by_id = {e["id"]: e for e in match.events}
    minutes = match.minutes()
    c: dict[int, Counter] = defaultdict(Counter)
    for e in match.events:
        pid = player_id(e)
        if pid is None or not in_play(e):
            continue
        k = c[pid]
        typ = etype(e)
        loc = e.get("location")
        if typ == "Shot":
            xg = e["shot"].get("statsbomb_xg", 0.0)
            pen = sub(e, "shot", "type", "name") == "Penalty"
            goal = sub(e, "shot", "outcome", "name") == "Goal"
            k["shots"] += 1
            k["xg"] += xg
            k["shots_on_target"] += sub(e, "shot", "outcome", "name") in SHOT_ON_TARGET
            if goal:
                k["goals"] += 1
                k["penalty_goals" if pen else "np_goals"] += 1
            if not pen:
                k["np_shots"] += 1
                k["npxg"] += xg
            kp = by_id.get(e["shot"].get("key_pass_id"))
            if kp and player_id(kp) is not None:
                c[player_id(kp)]["xg_assisted"] += xg
        elif typ == "Pass":
            k["passes"] += 1
            if is_completed_pass(e):
                k["passes_completed"] += 1
                end = e["pass"]["end_location"]
                if loc[0] < 80 <= end[0]:
                    k["deep_progressions"] += 1
                if in_box(end) and not in_box(loc) and pass_type(e) not in SET_PIECE_PASSES:
                    k["box_entries"] += 1
            if sub(e, "pass", "shot_assist") or sub(e, "pass", "goal_assist"):
                k["key_passes"] += 1
            if sub(e, "pass", "goal_assist"):
                k["assists"] += 1
            if is_progressive_pass(e):
                k["progressive_passes"] += 1
            if pass_type(e) == "Interception":
                k["interceptions"] += 1
        elif typ == "Carry":
            k["carries"] += 1
            end = e["carry"]["end_location"]
            if is_progressive_carry(e):
                k["progressive_carries"] += 1
            if loc[0] < 80 <= end[0]:
                k["deep_progressions"] += 1
            if in_box(end) and not in_box(loc):
                k["box_entries"] += 1
        elif typ == "Dribble":
            k["dribbles"] += 1
            k["dribbles_completed"] += sub(e, "dribble", "outcome", "name") == "Complete"
        elif typ == "Ball Receipt*":
            if sub(e, "ball_receipt", "outcome") is None and loc and in_box(loc):
                k["box_receptions"] += 1
        elif typ == "Pressure":
            k["pressures"] += 1
            k["pressures_att_third"] += loc[0] >= 80
        elif typ == "Duel" and sub(e, "duel", "type", "name") == "Tackle":
            k["tackles"] += 1
            k["tackles_won"] += sub(e, "duel", "outcome", "name") in TACKLE_WON
        elif typ == "Interception":
            k["interceptions"] += 1
        elif typ == "Ball Recovery":
            k["ball_recoveries"] += not sub(e, "ball_recovery", "recovery_failure")
        elif typ == "Block":
            k["blocks"] += 1
        elif typ == "Clearance":
            k["clearances"] += 1
        elif typ == "Foul Committed":
            k["fouls_committed"] += 1
        elif typ == "Foul Won":
            k["fouls_won"] += 1
        elif typ == "Dispossessed":
            k["dispossessed"] += 1
        elif typ == "Miscontrol":
            k["miscontrols"] += 1
        v = xt_added(e, grid)
        if v is not None:
            k["xt_added"] += v
    out: dict[int, dict[str, Any]] = {}
    for pid in set(minutes) | set(c):
        info = match.players.get(pid)
        row: dict[str, Any] = {
            "player_id": pid,
            "player": match.display_name(pid),
            "full_name": info.name if info else None,
            "team": info.team if info else None,
            "jersey": info.jersey if info else None,
            "position": (info.positions[0] if info and info.positions else None),
            "starter": bool(info and info.starter),
            "minutes": minutes.get(pid, 0.0),
        }
        for name in PLAYER_COUNTS:
            val = c[pid].get(name, 0)
            row[name] = round(float(val), 4) if name in FLOAT_COUNTS else int(val)
        if grid is None:
            row["xt_added"] = None
        out[pid] = row
    return out


# --------------------------------------------------------------- pass networks


def pass_network(match: Match, team: str, min_pair_passes: int = 3) -> dict[str, Any]:
    """Completed passes between team-mates until the team's first substitution (mplsoccer-style network).

    Node position = mean start location of the player's completed passes; node size = passes made;
    edge weight = completed passes between the two players in either direction.
    """
    first_sub = next((e for e in match.events
                      if etype(e) == "Substitution" and team_name(e) == team and in_play(e)), None)
    cutoff = first_sub["index"] if first_sub else float("inf")
    locs: dict[int, list[list[float]]] = defaultdict(list)
    pairs: Counter = Counter()
    for e in match.events:
        if e["index"] >= cutoff:
            break
        if team_name(e) != team or not is_completed_pass(e) or not in_play(e):
            continue
        recipient = sub(e, "pass", "recipient", "id")
        if recipient is None:
            continue
        locs[player_id(e)].append(e["location"])
        pairs[tuple(sorted((player_id(e), recipient)))] += 1
    nodes = []
    for pid, pts in locs.items():
        info = match.players.get(pid)
        nodes.append({
            "player_id": pid, "player": match.display_name(pid), "jersey": info.jersey if info else None,
            "x": sum(p[0] for p in pts) / len(pts), "y": sum(p[1] for p in pts) / len(pts), "passes": len(pts),
        })
    node_ids = {n["player_id"] for n in nodes}
    edges = [{"a": a, "b": b, "passes": n} for (a, b), n in pairs.most_common()
             if n >= min_pair_passes and a in node_ids and b in node_ids]
    window_end = minute_label(first_sub) if first_sub else "full time"
    return {"team": team, "window": f"0' - {window_end}", "nodes": nodes, "edges": edges,
            "top_pairs": [{"pair": f"{match.display_name(a)} <-> {match.display_name(b)}", "passes": n}
                          for (a, b), n in pairs.most_common(5)]}


# ---------------------------------------------------------------- time series


def shot_list(match: Match, player: int | None = None) -> list[dict[str, Any]]:
    """Shots outside the shoot-out, in the shooting team's direction (attacking x = 120)."""
    out = []
    for e in match.events:
        if etype(e) != "Shot" or not in_play(e) or (player is not None and player_id(e) != player):
            continue
        out.append({
            "match_id": match.match_id, "team": team_name(e), "player": match.display_name(player_id(e)),
            "minute": minute_label(e), "x": e["location"][0], "y": e["location"][1],
            "xg": e["shot"].get("statsbomb_xg", 0.0), "outcome": sub(e, "shot", "outcome", "name"),
            "penalty": sub(e, "shot", "type", "name") == "Penalty",
            "body_part": sub(e, "shot", "body_part", "name"),
        })
    return out


def xg_timeline(match: Match) -> dict[str, Any]:
    to_elapsed, period_ends = match.elapsed_mapper()
    shots = []
    for e in match.events:
        if etype(e) == "Shot" and in_play(e):
            shots.append({"team": team_name(e), "t": round(to_elapsed(e), 2), "minute": minute_label(e),
                          "xg": e["shot"].get("statsbomb_xg", 0.0),
                          "goal": sub(e, "shot", "outcome", "name") == "Goal",
                          "player": match.display_name(player_id(e))})
    return {"shots": shots, "period_ends": period_ends}


def xt_by_window(match: Match, grid: list[list[float]] | None, window: int = 5) -> list[dict[str, Any]]:
    """xT added per team in windows of the nominal clock (stoppage folded into each period's last window)."""
    if grid is None:
        return []
    bins: dict[tuple[int, int], Counter] = defaultdict(Counter)
    for e in match.events:
        v = xt_added(e, grid)
        if v is None:
            continue
        start, end = PERIOD_START[e["period"]], PERIOD_END[e["period"]]
        b = min(int((nominal_clock(e) - start) // window), int((end - start) // window) - 1)
        bins[(e["period"], b)][team_name(e)] += v
    rows = []
    for (period, b), cnt in sorted(bins.items()):
        lo = PERIOD_START[period] + b * window
        rows.append({"period": period, "from": lo, "to": lo + window,
                     **{t: round(cnt.get(t, 0.0), 4) for t in match.teams}})
    return rows
