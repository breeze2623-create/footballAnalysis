# Third-party notices

This repository includes or uses the following third-party material.

## Included in this repository

### football-data skill (sports-skills)

- Files: `.agents/skills/football-data/`
- Source: https://github.com/machina-sports/sports-skills (`skills/football-data`), installed with
  `npx -y skills add machina-sports/sports-skills@football-data --agent cursor --copy -y`; hash in `skills-lock.json`
- License: MIT

```
MIT License

Copyright (c) 2026 Machina Sports

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### nutmeg skills and plugin resources

- Files: `.agents/skills/nutmeg*/` (11 skills) and `third_party/nutmeg/`
- Source: https://github.com/withqwerty/nutmeg, commit `5d6a2d76548bd37cf7bab3ab9c265a284d9b7186` (plugin 0.5.1);
  skills installed with `npx -y skills add withqwerty/nutmeg --agent cursor --copy -y`; hashes in `skills-lock.json`
- License: MIT, as declared in the upstream README. The full text is in `third_party/nutmeg/LICENSE`
  ("Copyright (c) withqwerty"); provenance in `third_party/nutmeg/README.md`.

## Used at run time, not included

| What | How it is used | License / terms |
|---|---|---|
| football-docs (npm `football-docs@0.17.4`, https://github.com/withqwerty/football-docs) | MCP server started with `npx` by `.cursor/mcp/football-docs.mjs` | MIT |
| sports-skills (PyPI) | Python package behind the football-data skill and the `fd_*.py` scripts | MIT |
| StatsBomb open data (https://github.com/statsbomb/open-data) | Downloaded to `.cache/` by the `sb_*.py` scripts | StatsBomb terms in the repository's `LICENSE.pdf`: credit StatsBomb as the source and use their logo when publishing work based on the data (https://statsbomb.com/media-pack/) |
| ESPN, Understat, FPL, Transfermarkt, ClubElo, football-data.co.uk | Fetched through sports-skills | Each site's own terms; this repository uses them for personal analysis only and stores no copies |
| Expected threat grid by Karun Singh (https://karun.in/blog/data/open_xt_12x8_v1.json) | Downloaded to `.cache/` for the xT metric | No license stated; not redistributed |
| matplotlib, mplsoccer, scipy | Installed from PyPI (`requirements.txt`) for the charts | matplotlib license (PSF-based), MIT, BSD-3-Clause |
