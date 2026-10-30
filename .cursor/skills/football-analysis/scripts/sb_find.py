"""Find StatsBomb open-data competitions, matches and players (IDs for the other scripts).

    python sb_find.py competitions --q "world cup"
    python sb_find.py matches --competition "FIFA World Cup" --season 2022 --team Argentina
    python sb_find.py matches --competition 43 --season 106
    python sb_find.py players --match 3869685 --q messi
    python sb_find.py players --competition 43 --season 106 --q "mac allister"

Names match without accents or case ("mbappe" finds "Kylian Mbappé Lottin").
Results are printed and saved to outputs/find-latest.md.
"""
from __future__ import annotations

import argparse

import fa_common as fc


def competitions(args) -> tuple[list[str], list[list]]:
    rows = fc.resolve_competition(args.q or args.competition, args.season)
    rows.sort(key=lambda r: (r["competition_name"], r["season_name"]))
    return (["competition_id", "season_id", "competition", "season", "country", "gender"],
            [[r["competition_id"], r["season_id"], r["competition_name"], r["season_name"], r["country_name"],
              r.get("competition_gender")] for r in rows])


def _seasons(args) -> list[dict]:
    if not args.competition:
        raise SystemExit("--competition is required (ID or name), with --season (ID or year)")
    rows = fc.resolve_competition(args.competition, args.season)
    if not rows:
        raise SystemExit(f"no competition/season matches {args.competition!r} / {args.season!r}; "
                         "list them with: sb_find.py competitions")
    if len(rows) > 12 and not args.season:
        raise SystemExit(f"{len(rows)} seasons match; add --season to narrow it down")
    return rows


def matches(args) -> tuple[list[str], list[list]]:
    out = []
    for r in _seasons(args):
        for m in fc.sb_matches(r["competition_id"], r["season_id"]):
            home, away = m["home_team"]["home_team_name"], m["away_team"]["away_team_name"]
            if args.team and not fc.name_matches(args.team, home, away):
                continue
            out.append([m["match_id"], m["match_date"], (m.get("competition_stage") or {}).get("name"),
                        home, f"{m['home_score']}-{m['away_score']}", away,
                        r["competition_id"], r["season_id"], r["competition_name"], r["season_name"]])
    out.sort(key=lambda row: (row[1], row[0]))
    return (["match_id", "date", "stage", "home", "score", "away", "competition_id", "season_id",
             "competition", "season"], out)


def players(args) -> tuple[list[str], list[list]]:
    if args.match:
        match_rows = [(args.match, None)]
    else:
        match_rows = [(m["match_id"], r) for r in _seasons(args)
                      for m in fc.sb_matches(r["competition_id"], r["season_id"])]
        if len(match_rows) > 80 and not args.q:
            raise SystemExit(f"{len(match_rows)} matches to scan; add --q <name> to search for a player")
    seen: dict[int, list] = {}
    for mid, _ in match_rows:
        for team in fc.sb_lineups(mid):
            for p in team["lineup"]:
                if args.q and not fc.name_matches(args.q, p["player_name"], p.get("player_nickname")):
                    continue
                played = bool(p.get("positions"))
                row = seen.setdefault(p["player_id"], [p["player_id"], p.get("player_nickname") or p["player_name"],
                                                       p["player_name"], team["team_name"], p.get("jersey_number"),
                                                       (p["positions"][0]["position"] if played else "-"), 0])
                row[6] += played
    rows = sorted(seen.values(), key=lambda r: (r[3], -r[6], r[1]))
    return (["player_id", "name", "full_name", "team", "jersey", "first_position", "matches_played"], rows)


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["competitions", "matches", "players"])
    ap.add_argument("--q", help="name filter (competition name for 'competitions', player name for 'players')")
    ap.add_argument("--competition", help="competition ID or name fragment")
    ap.add_argument("--season", help="season ID or name fragment such as 2022 or 2015/2016")
    ap.add_argument("--team", help="team name filter for 'matches'")
    ap.add_argument("--match", type=int, help="match ID for 'players'")
    args = ap.parse_args()

    headers, rows = {"competitions": competitions, "matches": matches, "players": players}[args.what](args)
    table = fc.md_table(headers, rows)
    print(table)
    print(f"\n{len(rows)} rows")
    out = fc.outputs_dir()
    fc.write_text(out / "find-latest.md", f"# sb_find {args.what}\n\nargs: {vars(args)}\n\n{table}\n")
    fc.write_json(out / "find-latest.json", [dict(zip(headers, r)) for r in rows])
    return {"out_dir": str(out), "files": ["find-latest.md", "find-latest.json"], "rows": len(rows)}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
