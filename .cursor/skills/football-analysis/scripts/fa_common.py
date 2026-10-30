"""Shared plumbing for the football-analysis skill scripts.

Every script imports this module first. It keeps the scripts runnable on a fresh
machine (including Windows with several Python installs):

* console output is forced to UTF-8 so player names never crash a GBK console;
* missing packages are installed with the interpreter that is actually running
  (``sys.executable -m pip install``), never with a bare ``pip``;
* downloads are cached under ``<repo>/.cache/football-analysis`` and fall back to
  the jsDelivr CDN when raw.githubusercontent.com is unreachable;
* every run records its status, output folder and errors in
  ``<repo>/outputs/LAST_RUN.json`` so the result can be checked by reading a file
  even when the terminal output is lost.
"""
from __future__ import annotations

import csv
import importlib
import importlib.util
import io
import json
import os
import re
import site
import subprocess
import sys
import time
import traceback
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

MIN_PYTHON = (3, 10)

if sys.version_info < MIN_PYTHON:
    sys.exit(
        "football-analysis needs Python %d.%d+, but this is %s at %s. "
        "Run the script with a newer interpreter (for example `py -3.12`)."
        % (MIN_PYTHON[0], MIN_PYTHON[1], sys.version.split()[0], sys.executable)
    )

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, io.UnsupportedOperation):
        pass

SKILL_DIR = Path(__file__).resolve().parent.parent

CHART_PACKAGES = {"matplotlib": "matplotlib>=3.7", "mplsoccer": "mplsoccer>=1.4"}
SPORTS_SKILLS_PACKAGES = {"sports_skills": "sports-skills>=0.40"}

STATSBOMB_BASES = (
    "https://raw.githubusercontent.com/statsbomb/open-data/master/data",
    "https://cdn.jsdelivr.net/gh/statsbomb/open-data@master/data",
)
XT_GRID_URLS = ("https://karun.in/blog/data/open_xt_12x8_v1.json",)
USER_AGENT = "football-analysis-skill/1.0 (+https://github.com/statsbomb/open-data)"

RUN_LOG: list[str] = []


class DataUnavailable(RuntimeError):
    """A data file could not be downloaded from any source."""


class DataNotFound(RuntimeError):
    """The data source answered, but the requested file does not exist."""


def log(msg: str) -> None:
    RUN_LOG.append(msg)
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- paths


def repo_root() -> Path:
    env = os.environ.get("FOOTBALL_ANALYSIS_HOME")
    if env:
        return Path(env).expanduser().resolve()
    for start in (Path.cwd().resolve(), SKILL_DIR):
        for p in (start, *start.parents):
            if (p / ".git").exists():
                return p
    return Path.cwd().resolve()


def cache_dir() -> Path:
    env = os.environ.get("FOOTBALL_ANALYSIS_CACHE")
    return Path(env).expanduser().resolve() if env else repo_root() / ".cache" / "football-analysis"


def outputs_dir() -> Path:
    return repo_root() / "outputs"


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")
    return (s[:max_len].rstrip("-")) or "x"


def make_out_dir(kind: str, slug: str, override: str | None = None) -> Path:
    path = Path(override).expanduser() if override else outputs_dir() / f"{kind}-{slugify(slug)}"
    if not path.is_absolute():
        path = repo_root() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


# --------------------------------------------------------------------- self-heal


def _in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix) or bool(os.environ.get("CONDA_PREFIX"))


def _pip_install(args: list[str]) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *args]
    log("[self-heal] " + " ".join(cmd))
    try:
        subprocess.check_call(cmd)
        return True
    except (subprocess.CalledProcessError, OSError) as exc:
        log(f"[self-heal] attempt failed: {exc}")
        return False


def ensure_packages(packages: dict[str, str], purpose: str) -> bool:
    """Import-check ``packages`` ({module: pip spec}) and install the missing ones.

    Installs go through ``sys.executable -m pip`` so they land in the interpreter
    running this script. Set FOOTBALL_ANALYSIS_NO_INSTALL=1 to only report.
    """
    missing = {m: spec for m, spec in packages.items() if importlib.util.find_spec(m) is None}
    if not missing:
        return True
    specs = list(missing.values())
    manual = f'"{sys.executable}" -m pip install ' + " ".join(f'"{s}"' for s in specs)
    if os.environ.get("FOOTBALL_ANALYSIS_NO_INSTALL") == "1":
        log(f"[self-heal] missing {specs} for {purpose}; auto-install is off. Install with: {manual}")
        return False
    log(f"[self-heal] {purpose} needs {specs}; installing into {sys.executable}")
    attempts = [specs]
    if not _in_virtualenv():
        attempts += [["--user", *specs], ["--user", "--break-system-packages", *specs]]
    if not any(_pip_install(a) for a in attempts):
        log(f"[self-heal] could not install {specs}. Try by hand: {manual}"
            f" (if pip itself is missing: \"{sys.executable}\" -m ensurepip --upgrade)")
        return False
    importlib.invalidate_caches()
    user_site = site.getusersitepackages()
    if os.path.isdir(user_site) and user_site not in sys.path:
        site.addsitedir(user_site)
    still = [m for m in missing if importlib.util.find_spec(m) is None]
    if still:
        log(f"[self-heal] installed but still not importable: {still}. Re-run the script once.")
        return False
    return True


def charts_enabled(disabled: bool = False) -> bool:
    if disabled:
        return False
    if not ensure_packages(CHART_PACKAGES, "charts"):
        log("[charts] skipped: matplotlib/mplsoccer unavailable; the report and metrics are still written.")
        return False
    import matplotlib

    matplotlib.use("Agg")
    return True


# ------------------------------------------------------------------------- data


def _http_get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def cached_json(rel_path: str, urls: Iterable[str], timeout: float = 90) -> Any:
    path = cache_dir() / rel_path
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            path.unlink(missing_ok=True)
    errors = []
    for url in urls:
        for attempt in range(2):
            try:
                raw = _http_get(url, timeout)
                obj = json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise DataNotFound(f"{url} does not exist (HTTP 404)") from exc
                errors.append(f"{url}: HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                errors.append(f"{url}: {exc}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + ".part")
                tmp.write_bytes(raw)
                os.replace(tmp, path)
                return obj
            time.sleep(1 + attempt)
    raise DataUnavailable(
        "Could not download " + rel_path + ". Tried:\n  " + "\n  ".join(errors)
        + "\nCheck the network or proxy (HTTPS_PROXY), set STATSBOMB_OPEN_DATA_BASE to a mirror,"
        " or point STATSBOMB_OPEN_DATA_DIR at a local copy of statsbomb/open-data/data."
    )


def statsbomb(rel_path: str) -> Any:
    local = os.environ.get("STATSBOMB_OPEN_DATA_DIR")
    if local:
        p = Path(local).expanduser() / rel_path
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    bases = [b for b in (os.environ.get("STATSBOMB_OPEN_DATA_BASE"),) if b] + list(STATSBOMB_BASES)
    return cached_json(f"statsbomb/{rel_path}", [f"{b.rstrip('/')}/{rel_path}" for b in bases])


def sb_competitions() -> list[dict]:
    return statsbomb("competitions.json")


def sb_matches(competition_id: int, season_id: int) -> list[dict]:
    return statsbomb(f"matches/{competition_id}/{season_id}.json")


def sb_events(match_id: int) -> list[dict]:
    return statsbomb(f"events/{match_id}.json")


def sb_lineups(match_id: int) -> list[dict]:
    return statsbomb(f"lineups/{match_id}.json")


def xt_grid() -> list[list[float]] | None:
    """Karun Singh's published 12 x 8 xT surface (8 rows x 12 columns), or None if unreachable."""
    try:
        grid = cached_json("xt/open_xt_12x8_v1.json", XT_GRID_URLS, timeout=30)
    except (DataUnavailable, DataNotFound) as exc:
        log(f"[xT] surface unavailable, xT columns are left empty: {exc}")
        return None
    if len(grid) != 8 or any(len(row) != 12 for row in grid):
        log("[xT] unexpected surface shape, xT disabled")
        return None
    return grid


# ----------------------------------------------------------------- name matching

_EXTRA_FOLD = str.maketrans({"ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "ß": "ss", "ł": "l", "Ł": "l",
                             "đ": "d", "Đ": "d", "ı": "i", "œ": "oe", "Œ": "oe", "þ": "th"})


def norm(text: str | None) -> str:
    s = unicodedata.normalize("NFKD", (text or "").translate(_EXTRA_FOLD))
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).casefold().split())


def name_matches(query: str, *candidates: str | None) -> bool:
    q = norm(query).split()
    for cand in candidates:
        c = norm(cand)
        if c and all(tok in c for tok in q):
            return True
    return False


def resolve_competition(competition: str | None, season: str | None) -> list[dict]:
    """Competition-season rows matching an ID or a name fragment for each part."""
    rows = sb_competitions()
    out = []
    for r in rows:
        if competition:
            if competition.isdigit():
                if int(competition) != r["competition_id"]:
                    continue
            elif not name_matches(competition, r["competition_name"], r.get("country_name")):
                continue
        if season:
            if season.isdigit() and int(season) == r["season_id"]:
                pass
            elif not name_matches(season, r["season_name"]):
                continue
        out.append(r)
    return out


def find_match_meta(match_id: int, competition_id: int | None = None, season_id: int | None = None) -> dict | None:
    """Match row from matches/{cid}/{sid}.json; scans every season (cached) when the IDs are not given."""
    index_path = cache_dir() / "statsbomb" / "match_index.json"
    index: dict[str, list[int]] = {}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {}
    pairs: list[tuple[int, int]] = []
    if competition_id and season_id:
        pairs.append((competition_id, season_id))
    if str(match_id) in index:
        pairs.append(tuple(index[str(match_id)]))
    newest_first = sorted(sb_competitions(), key=lambda r: re.sub(r"\D", "", r["season_name"])[:4], reverse=True)
    pairs += [(r["competition_id"], r["season_id"]) for r in newest_first]
    seen = set()
    for cid, sid in pairs:
        if (cid, sid) in seen:
            continue
        seen.add((cid, sid))
        try:
            matches = sb_matches(cid, sid)
        except DataNotFound:
            continue
        for m in matches:
            index.setdefault(str(m["match_id"]), [cid, sid])
        hit = next((m for m in matches if m["match_id"] == match_id), None)
        if hit:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(json.dumps(index), encoding="utf-8")
            return hit
    return None


# ----------------------------------------------------------------------- output


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path: Path, obj: Any) -> Path:
    return write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def fmt(v: Any, digits: int = 2) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def md_table(headers: list[str], rows: Iterable[Iterable[Any]], digits: int = 2) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(fmt(c, digits).replace("|", "/") for c in row) + " |")
    return "\n".join(lines)


def run_main(main: Callable[[], dict | None]) -> int:
    """Run ``main`` and record the outcome in outputs/LAST_RUN.json.

    ``main`` returns a dict (at least ``out_dir`` and ``files``); an ``exit_code`` key, when
    non-zero, marks the run as failed while keeping the rest of the record.
    """
    started = datetime.now(timezone.utc)
    record: dict[str, Any] = {
        "script": Path(sys.argv[0]).name,
        "argv": sys.argv[1:],
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "started_utc": started.isoformat(timespec="seconds"),
    }
    code = 0
    try:
        result = dict(main() or {})
        code = int(result.pop("exit_code", 0) or 0)
        record.update(status="ok" if code == 0 else "failed", **result)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        record.update(status="ok" if code == 0 else "error", error=None if code == 0 else str(exc.code))
        if code:
            log(f"[error] {exc.code}")
    except (DataUnavailable, DataNotFound) as exc:
        code = 2
        record.update(status="error", error=str(exc))
        log(f"[error] {exc}")
    except Exception as exc:  # noqa: BLE001 - the record must capture any failure
        code = 1
        record.update(status="error", error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
        log(traceback.format_exc())
    record["log"] = RUN_LOG
    record["seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    try:
        write_json(outputs_dir() / "LAST_RUN.json", record)
        if record.get("out_dir") and Path(record["out_dir"]).resolve() != outputs_dir().resolve():
            write_json(Path(record["out_dir"]) / "run.json", record)
    except OSError as exc:
        print(f"[warn] could not write LAST_RUN.json: {exc}", file=sys.stderr)
    status = record.get("status")
    print(f"[{status}] details: {outputs_dir() / 'LAST_RUN.json'}"
          + (f" | report folder: {record['out_dir']}" if record.get("out_dir") else ""))
    return code
