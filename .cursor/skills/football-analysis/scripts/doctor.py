"""Environment check for the football skills (run it first on a new machine).

    python doctor.py              # check and install missing Python packages into THIS interpreter
    python doctor.py --check-only # report only
    python doctor.py --offline    # skip the MCP server start and the data-source checks

Checks: which interpreter runs (and whether `pip`/`python` on PATH point to the same one),
Python packages, Node.js, installed skills, the football-docs MCP server started exactly as
.cursor/mcp.json says, and the data sources. The full result is written to outputs/doctor.md
and outputs/doctor.json.
"""
from __future__ import annotations

import argparse
import collections
import importlib.metadata as md
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import fa_common as fc

PACKAGES = {**fc.CHART_PACKAGES, **fc.SPORTS_SKILLS_PACKAGES}
DIST_NAMES = {"matplotlib": "matplotlib", "mplsoccer": "mplsoccer", "sports_skills": "sports-skills",
              "numpy": "numpy", "pandas": "pandas", "scipy": "scipy"}
URLS = {
    "StatsBomb open data (GitHub raw)": "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json",
    "StatsBomb open data (jsDelivr mirror)": "https://cdn.jsdelivr.net/gh/statsbomb/open-data@master/data/competitions.json",
    "xT surface (karun.in)": fc.XT_GRID_URLS[0],
    "ESPN API (football-data skill)": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
    "npm registry (football-docs MCP)": "https://registry.npmjs.org/football-docs/latest",
}
NODE_MIN = (22, 13)


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           shell=False, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)


def check_interpreters() -> list[tuple[str, str, str]]:
    rows = [("OK" if sys.version_info >= fc.MIN_PYTHON else "FAIL", "running interpreter",
             f"{sys.executable} (Python {platform.python_version()}, {platform.system()} {platform.machine()})")]
    code, out = run([sys.executable, "-m", "pip", "--version"])
    rows.append(("OK" if code == 0 else "FAIL", f"{os.path.basename(sys.executable)} -m pip", out.splitlines()[0] if out else "pip missing: run `python -m ensurepip --upgrade`"))
    mine = os.path.normcase(os.path.realpath(sys.executable))
    for exe in ("python", "python3", "py"):
        path = shutil.which(exe)
        if not path:
            continue
        code, out = run([path, "-c", "import sys; print(sys.executable)"])
        target = os.path.normcase(os.path.realpath(out.splitlines()[-1])) if code == 0 and out else "?"
        if target == mine:
            rows.append(("OK", f"`{exe}` on PATH", f"{path} -> {target}"))
        else:
            rows.append(("WARN", f"`{exe}` on PATH",
                         f"{path} -> {target}  (NOT the interpreter running doctor.py)"))
    pip = shutil.which("pip")
    if pip:
        code, out = run([pip, "-V"])
        detail = out.splitlines()[0] if out else "?"
        m = re.search(r"from (.+?) \(python ([0-9.]+)\)", out)
        same = False
        if m:
            site_dir = os.path.normcase(os.path.realpath(m.group(1)))
            same_version = m.group(2) == f"{sys.version_info[0]}.{sys.version_info[1]}"
            same = site_dir.startswith(os.path.normcase(os.path.realpath(sys.prefix))) or (
                same_version and site_dir.startswith(os.path.normcase(os.path.realpath(os.path.expanduser("~")))))
        if same:
            rows.append(("OK", "bare `pip` on PATH", detail))
        else:
            rows.append(("WARN", "bare `pip` on PATH",
                         f"{detail}  -> NOT this interpreter; always use \"{sys.executable}\" -m pip install ..."))
    return rows


def check_packages(fix: bool) -> list[tuple[str, str, str]]:
    if fix:
        fc.ensure_packages(PACKAGES, "doctor --fix")
    rows = []
    for mod, dist in DIST_NAMES.items():
        try:
            rows.append(("OK", f"package {dist}", md.version(dist)))
        except md.PackageNotFoundError:
            needed = mod in PACKAGES
            rows.append(("FAIL" if needed else "WARN", f"package {dist}",
                         f"missing; install with \"{sys.executable}\" -m pip install -r "
                         f"\"{fc.repo_root() / 'requirements.txt'}\""))
    return rows


def check_node() -> list[tuple[str, str, str]]:
    node = shutil.which("node")
    if not node:
        return [("WARN", "Node.js", f"not found; the football-docs MCP server needs Node >= {NODE_MIN[0]}.{NODE_MIN[1]}")]
    code, out = run([node, "--version"])
    m = re.match(r"v(\d+)\.(\d+)", out or "")
    ok = bool(m) and (int(m.group(1)), int(m.group(2))) >= NODE_MIN
    rows = [("OK" if ok else "WARN", "Node.js", f"{out} at {node}" + ("" if ok else f" (need >= {NODE_MIN[0]}.{NODE_MIN[1]})"))]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    rows.append(("OK" if npx else "WARN", "npx", npx or "not found"))
    return rows


def _mcp_resolve(value: str, root: Path) -> str:
    fixed = {"workspaceFolder": str(root), "workspaceFolderBasename": root.name, "userHome": str(Path.home()),
             "pathSeparator": os.sep, "/": os.sep}

    def sub(m: re.Match) -> str:
        key = m.group(1)
        return os.environ.get(key[4:], "") if key.startswith("env:") else fixed.get(key, m.group(0))

    return re.sub(r"\$\{([^}]+)\}", sub, value)


def check_mcp(timeout: float) -> list[tuple[str, str, str]]:
    """Start football-docs the way Cursor does (command and args from .cursor/mcp.json) and call one tool."""
    root = fc.repo_root()
    label = "football-docs server"
    try:
        server = json.loads((root / ".cursor" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["football-docs"]
    except (OSError, ValueError, KeyError) as exc:
        return [("WARN", label, f"cannot read the football-docs entry in .cursor/mcp.json: {exc!r}")]
    cmd = [_mcp_resolve(server["command"], root)] + [_mcp_resolve(a, root) for a in server.get("args", [])]
    exe = shutil.which(cmd[0])
    if not exe:
        return [("FAIL", label, f"`{cmd[0]}` (the command in .cursor/mcp.json) is not on PATH")]
    proc = subprocess.Popen([exe, *cmd[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", cwd=root)
    lines: queue.Queue = queue.Queue()
    stderr_tail: collections.deque = collections.deque(maxlen=20)
    threading.Thread(target=lambda: [lines.put(line) for line in proc.stdout], daemon=True).start()
    threading.Thread(target=lambda: [stderr_tail.append(line.rstrip()) for line in proc.stderr], daemon=True).start()
    deadline = time.monotonic() + timeout

    def send(msg: dict) -> None:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", **msg}) + "\n")
        proc.stdin.flush()

    def rpc(msg_id: int, method: str, params: dict) -> dict:
        send({"id": msg_id, "method": method, "params": params})
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"no answer to {method} within {timeout:.0f}s")
            try:
                line = lines.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                if proc.poll() is not None:
                    raise RuntimeError(f"the server exited with code {proc.returncode}") from None
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise RuntimeError(f"{method} failed: {msg['error']}")
                return msg["result"]

    rows = []
    try:
        info = rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "football-doctor", "version": "1"}})
        send({"method": "notifications/initialized"})
        tools = [t["name"] for t in rpc(2, "tools/list", {})["tools"]]
        server_info = info.get("serverInfo", {})
        rows.append(("OK", label, f"{server_info.get('name', '?')} {server_info.get('version', '')}: "
                                  f"{len(tools)} tools ({', '.join(tools)})"))
        card = rpc(3, "tools/call", {"name": "get_metric", "arguments": {"id": "ppda.statsbomb-hudl"}})
        text = "".join(c.get("text", "") for c in card.get("content", []))
        ok = not card.get("isError") and "ppda" in text.lower()
        rows.append(("OK" if ok else "WARN", "get_metric ppda.statsbomb-hudl",
                     f"metric card returned ({len(text)} characters)" if ok else text[:300]))
    except (TimeoutError, RuntimeError, OSError, KeyError, ValueError) as exc:
        tail = " | ".join(stderr_tail)[-600:]
        rows.append(("FAIL", label, f"{exc}" + (f"; server stderr: {tail}" if tail else "")))
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return rows


def check_files() -> list[tuple[str, str, str]]:
    root = fc.repo_root()
    rows = []
    for label, rel in (("project skills (.agents/skills)", ".agents/skills"),
                       ("project skills (.cursor/skills)", ".cursor/skills")):
        d = root / rel
        names = sorted(p.parent.name for p in d.glob("*/SKILL.md")) if d.exists() else []
        rows.append(("OK" if names else "WARN", label, ", ".join(names) or "none"))
    for label, rel in (("MCP config", ".cursor/mcp.json"), ("nutmeg core", "third_party/nutmeg/core/nutmeg.py"),
                       ("agent rules", "AGENTS.md")):
        exists = (root / rel).exists()
        rows.append(("OK" if exists else "WARN", label, rel if exists else f"missing: {rel}"))
    return rows


def check_network() -> list[tuple[str, str, str]]:
    rows = []
    proxy = {k: v for k, v in os.environ.items() if k.lower() in ("https_proxy", "http_proxy", "all_proxy")}
    if proxy:
        rows.append(("INFO", "proxy env", ", ".join(sorted(proxy))))
    for label, url in URLS.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": fc.USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                rows.append(("OK", label, f"HTTP {r.status}"))
        except Exception as exc:  # noqa: BLE001 - any failure is a finding
            rows.append(("WARN", label, f"{type(exc).__name__}: {exc}"))
    return rows


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-only", action="store_true", help="do not install missing packages")
    ap.add_argument("--offline", action="store_true", help="skip the MCP server start and the network checks")
    ap.add_argument("--mcp-timeout", type=float, default=240,
                    help="seconds to wait for the MCP server (the first start downloads it with npx)")
    args = ap.parse_args()

    sections = {
        "Python interpreters": check_interpreters(),
        "Python packages": check_packages(fix=not args.check_only),
        "Node.js": check_node(),
        "Skills and config": check_files(),
    }
    if not args.offline:
        sections["football-docs MCP (started as .cursor/mcp.json says)"] = check_mcp(args.mcp_timeout)
        sections["Data sources"] = check_network()
    lines = ["# football skills doctor", "", f"interpreter: `{sys.executable}`", ""]
    worst = "OK"
    for title, rows in sections.items():
        lines += [f"## {title}", "", fc.md_table(["status", "check", "detail"], rows), ""]
        for status, _, _ in rows:
            if status == "FAIL" or (status == "WARN" and worst == "OK"):
                worst = status
    out = fc.outputs_dir()
    fc.write_text(out / "doctor.md", "\n".join(lines))
    fc.write_json(out / "doctor.json", {k: [dict(zip(["status", "check", "detail"], r)) for r in v]
                                        for k, v in sections.items()})
    print("\n".join(lines))
    print(f"overall: {worst}")
    return {"out_dir": str(out), "files": ["doctor.md", "doctor.json"], "overall": worst,
            "exit_code": 1 if worst == "FAIL" else 0}


if __name__ == "__main__":
    raise SystemExit(fc.run_main(main))
