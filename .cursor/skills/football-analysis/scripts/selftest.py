"""Check the metric code against the football-docs metric-card test values.

All test values are for the 2022 World Cup final, Argentina v France (StatsBomb match 3869685),
as published in the football-docs MCP metric cards (football-docs@0.17.4).

    python selftest.py            # writes outputs/selftest/selftest.md and summary.json
"""
from __future__ import annotations

import argparse

import fa_common as fc
import fa_metrics as fm

MATCH_ID = 3869685
TEAM_EXPECTED = {
    "xg": {"Argentina": 2.7583, "France": 2.2726},
    "npxg": {"Argentina": 1.9748, "France": 0.7056},
    "xg_assisted": {"Argentina": 1.3397, "France": 0.5687},
    "pass_completion": {"Argentina": 0.8081, "France": 0.7614},
    "ppda": {"Argentina": 7.4222, "France": 9.0909},
    "field_tilt": {"Argentina": 0.6186, "France": 0.3814},
    "progressive_passes": {"Argentina": 46, "France": 23},
    "progressive_carries": {"Argentina": 25, "France": 26},
    "xt_added": {"Argentina": 1.8631, "France": 1.1759},
}
PLAYER_XG_ASSISTED = {
    "Alexis Mac Allister": 0.3034,
    "Ángel Di María": 0.2781,
    "Lionel Messi": 0.2742,
    "Ibrahima Konaté": 0.2775,
    "Marcus Thuram": 0.1017,
}
TOLERANCE = 0.0001


def close(actual, expected) -> bool:
    if actual is None:
        return False
    if isinstance(expected, int):
        return actual == expected
    return abs(round(actual, 4) - expected) <= TOLERANCE


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="output folder (default outputs/selftest)")
    args = ap.parse_args()

    match = fm.Match.build(MATCH_ID, fc.sb_events(MATCH_ID), fc.sb_lineups(MATCH_ID))
    grid = fc.xt_grid()
    teams = fm.team_metrics(match, grid)
    players = fm.player_metrics(match, grid)

    rows, failures = [], 0
    for metric, exp in TEAM_EXPECTED.items():
        for team, expected in exp.items():
            actual = teams[team][metric]
            ok = close(actual, expected)
            failures += not ok
            rows.append([fm.VARIANTS[metric], team, expected, actual, "PASS" if ok else "FAIL"])
    for name, expected in PLAYER_XG_ASSISTED.items():
        actual = next((p["xg_assisted"] for p in players.values()
                       if fc.norm(name) in (fc.norm(p["player"]), fc.norm(p["full_name"]))), None)
        ok = close(actual, expected)
        failures += not ok
        rows.append([fm.VARIANTS["xg_assisted"] + " (player)", name, expected, actual, "PASS" if ok else "FAIL"])

    out = fc.make_out_dir("selftest", "", args.out) if args.out else fc.outputs_dir() / "selftest"
    out.mkdir(parents=True, exist_ok=True)
    table = fc.md_table(["variant", "team / player", "card test value", "this code", "result"], rows, digits=4)
    verdict = "ALL PASS" if failures == 0 else f"{failures} FAILED"
    fc.write_text(out / "selftest.md",
                  f"# football-analysis self-test: {verdict}\n\n"
                  f"Match {MATCH_ID} (2022 World Cup final), StatsBomb open data. Expected values are the test values"
                  f" of the football-docs metric cards. Tolerance {TOLERANCE}.\n\n{table}\n")
    fc.write_json(out / "summary.json", {"verdict": verdict, "failures": failures, "checks": [
        dict(zip(["variant", "subject", "expected", "actual", "result"], r)) for r in rows]})
    print(table)
    print(f"\n{verdict} ({len(rows)} checks)")
    return {"out_dir": str(out), "files": ["selftest.md", "summary.json"], "verdict": verdict,
            "exit_code": 1 if failures else 0}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
