# nutmeg plugin resources (vendored)

The nutmeg skills in `.agents/skills/nutmeg*` were installed with the `skills` CLI, which copies only the
skill folders. They also read files from the nutmeg plugin root (`${CLAUDE_PLUGIN_ROOT}` in Claude Code).
This folder holds those files, unchanged, so the skills work in Cursor. `AGENTS.md` maps
`${CLAUDE_PLUGIN_ROOT}` to this folder.

| | |
|---|---|
| Upstream | https://github.com/withqwerty/nutmeg |
| Commit | `5d6a2d76548bd37cf7bab3ab9c265a284d9b7186` (plugin version 0.5.1) |
| License | MIT, declared in the upstream `README.md` ("## License / MIT"); upstream has no LICENSE file, so `LICENSE` here is the standard MIT text with the author named in `.claude-plugin/plugin.json` |

Included (same paths as upstream):

- `docs/`: accuracy-guardrail, entity-resolution-routing, glossary, metric-misuse, provenance-contract,
  understanding, team-config, publishing-playbook
- `core/`: `nutmeg.py`, `nutmeg_core/` (the research-project CLI, standard library only, Python 3.10+), `pyproject.toml`
- `agents/`: pipeline-builder, data-reviewer, chart-reviewer (read them as instructions; see `AGENTS.md`)
- `skills/_shared/campos-bridge.md`, `skills/brainstorm/references/`

Left out: the Claude Code hooks (`hooks/`; their session rules are restated in `AGENTS.md`), tests, evals,
plans and the skill folders themselves (installed in `.agents/skills`, pinned in `skills-lock.json`).

Run the CLI with the interpreter you use for everything else:

    python third_party/nutmeg/core/nutmeg.py --help

To update: download the new upstream commit, copy the same paths over, update the commit above, and
reinstall the skills with `npx -y skills add withqwerty/nutmeg --agent cursor --copy -y` so both stay in step.
