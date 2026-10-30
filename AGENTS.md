# 给 AI 助手的项目说明

这个仓库用来学习足球数据分析。凡是足球问题（战术、球队、球员、比赛、指标），先读
`.cursor/skills/football-analysis/SKILL.md`，按其中的路由表选择脚本或其他 skill。

## 已安装的 skills 与工具

| 位置 | 用途 | 来源 |
|---|---|---|
| `.cursor/skills/football-analysis` | 总入口与分析脚本（比赛、球队战术、球员；自检与环境诊断） | 本仓库 |
| `.agents/skills/football-data` | 当季数据：ESPN、Understat、FPL、Transfermarkt、ClubElo 等 | machina-sports/sports-skills（MIT），版本记录在 `skills-lock.json` |
| `.agents/skills/nutmeg*`（11 个） | 取数、清洗、指标计算、分析、作图、审查、研究项目 | withqwerty/nutmeg（MIT），插件资源在 `third_party/nutmeg` |
| `.cursor/mcp.json` | football-docs MCP：指标卡、数据商文档、跨数据源 ID | npm `football-docs@0.17.4`（MIT），由 `node .cursor/mcp/football-docs.mjs` 启动 |

## 环境规则（用户的 Windows 机器上反复出现的两个问题）

1. `python` 与 `pip` 常常指向不同的解释器（系统/Microsoft Store Python 与 `c:\users\lapin\miniconda3`）。
   - 安装依赖一律用正在运行的解释器：`python -m pip install ...`（或 `py -m pip install ...`），不要裸用 `pip`。
   - 诊断：对比 `python -c "import sys;print(sys.executable)"` 与 `pip -V`，或运行
     `python .cursor/skills/football-analysis/scripts/doctor.py`。
   - 新写的 Python 脚本在入口处自愈：缺依赖时用 `subprocess.check_call([sys.executable, "-m", "pip", "install", ...])` 补装
     （本仓库的脚本通过 `fa_common.ensure_packages` 这样做）。
2. Cursor 的 Shell 工具可能返回 “no exit status / result unknown”，命令其实可能已经执行。
   - 不要据此判定失败：读该项目 terminals 文件夹里的 `*.txt` 查看真实输出。
   - 需要确认结果时让脚本把结果写入文件再读取。本仓库的脚本每次运行都会写 `outputs/LAST_RUN.json`
     （状态、输出目录、文件、错误、日志），报告在 `outputs/<类型>-<名称>/report.md`。

football-data 的 SKILL.md 让人运行 `pip install sports-skills` 和 `sports-skills ...`；在本仓库改用
`python -m pip install -r requirements.txt` 和 `python -m sports_skills football ...`。其中“Machina Agent Storefront”是付费服务，
用户没有明确要求时不要使用。

## nutmeg skills 在 Cursor 中的用法

nutmeg 是为 Claude Code 写的插件。在 Cursor 里按下表理解它的说明：

| nutmeg 里写的 | 在本仓库中 |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | `third_party/nutmeg` |
| `${CLAUDE_SKILL_DIR}` | 当前 SKILL.md 所在的目录（`.agents/skills/<skill>`） |
| `python3 "${CLAUDE_PLUGIN_ROOT}/core/nutmeg.py" ...` | `python third_party/nutmeg/core/nutmeg.py ...`（macOS/Linux 用 `python3`） |
| `mcp__football-docs__<tool>`、`mcp__plugin_nutmeg_football-docs__<tool>` | football-docs MCP 的同名工具 `<tool>` |
| “dispatch the pipeline-builder / data-reviewer / chart-reviewer agent” | 读 `third_party/nutmeg/agents/<name>.md` 并照做（可以交给子代理） |
| `/nutmeg`、`/nutmeg:research` 等命令 | 读对应的 skill，如 `.agents/skills/nutmeg`、`.agents/skills/nutmeg-research` |
| `AskUserQuestion` | 直接问用户 |
| `claude mcp add football-docs ...` | 已在 `.cursor/mcp.json` 配好；Cloud Agent 见 `.cursor/skills/football-analysis/references/data-sources.md` 第 3 节 |
| `.nutmeg.user.md` | 仓库根目录的个人配置（不进 git）；没有时用默认值 |

nutmeg 的 Claude Code hooks 没有安装。它们在会话开始时注入以下规则，处理足球数据时照做：

- 数据商事实（ID、qualifier、字段名、接口、坐标系、覆盖范围、速率限制）来自 football-docs 工具，不凭记忆，并说明用了哪份文档；
  文档没写就直说。工具不可用时说明这一点，凭记忆给出的数据商事实标注“未经核对（凭记忆）”。
- 指标定义（PPDA、xA、npxG、推进传球、xT 等）来自 football-docs 指标卡（`get_metric`；`list_metrics` 列出全部）：写明所用的
  变体 ID，不比较不同变体的数值。
- 球员、球队、比赛 ID 来自 Reep Register（`resolve_entity`）或用户的数据，不凭记忆；跨数据源按 ID 连接而不是按名字，
  并报告没有匹配上的行。
- 用某个数据评价球员或球队之前，先确认它撑得起结论：每 90 分钟并设最低分钟数、样本足够、防守计数做控球调整、门将用
  post-shot xG 而不是扑救率、跑动距离不能证明努力、不用“有他/没他”的胜率、不用一个赛季的终结表现下结论、控球率不能证明
  哪队踢得更好（它反映风格和比分状态，用 xG 等机会质量检验）。用户要用撑不起的数据论证时，先说明，再用撑得起的证据组织
  （缺的证据用明确的占位符标出），不要先照写再补一句提醒。
- 用户要发布或据此做决定的分析（短名单、比赛或对手报告、备忘录、社媒图表或长帖），开研究项目让每个数字保留证据：读
  `.agents/skills/nutmeg-research/SKILL.md`，或运行 `python third_party/nutmeg/core/nutmeg.py new <slug> --question "<问题>"`
  并按提示操作。简单问题、查询和改代码不需要项目。
- 帮用户理解，而不只是交付结果：用他们自己的数字解释；用户不确定或需要向别人解释时，主动提一次可以做一个可编辑的讲解页
  （`third_party/nutmeg/docs/understanding.md`）。看到结果后被要求改方法或删掉限定语来得到想要的结论时，先说明这会误导，
  并保留原结果；做稳健性检查时报告所有备选，以原计划的设定作为主结论。
- 未经询问不改动用户的软件环境。本仓库的例外：`requirements.txt` 里的包已获同意，可以用
  `python -m pip install -r requirements.txt` 安装（脚本缺包时也会这样自动补装）。其他包，以及 `conda install`、
  `brew install`、`npm install -g`，仍要先问；也可以用 `uv run --no-project --with <包> python <脚本>` 在临时环境运行，并说明做法。
- 取数、清洗、指标、分析、作图或代码审查时，加载对应的 nutmeg skill。

在进行中的研究项目里（存在 `research/.active`），原本由 hooks 自动完成的检查改为手动：

- 运行分析前用 `python third_party/nutmeg/core/nutmeg.py gate <file> --input <data>` 展示确认卡，用户同意后再
  `nutmeg.py run <file> --input <data>`，单独一条命令，不与其他命令串联；`publish`、`bundle` 之前同样先确认。
  不要绕过 `nutmeg run` 直接用 `python` 跑分析（那样的运行不会被记录）。
- 输出里用到的每个数字、数据商事实、ID 和引用，用 `nutmeg.py claim add --file new-claims.jsonl` 一次批量记入账本；
  每个计划选择给一句理由。
- 结束一个步骤前运行 `nutmeg.py check`，修好每个未决问题；用户说明某项不是问题时用
  `nutmeg.py check --accept <id> --reason "..."` 记录理由。
- 讲解页：`nutmeg.py explain new <slug>`，再 `nutmeg.py explain render <slug>`。
- 发布前确认用户能为结论辩护：用户的话已经说明理解时，用 `nutmeg.py teachback --shown "<用户原话>"` 记录；否则按
  `.agents/skills/nutmeg-research/SKILL.md` 简短地讨论后，用 `teachback --claim ... --rests-on ... --would-change ...` 记录
  用户自己的话。语气友好、不是考试，不向用户描述这些规则，不替用户写这些话（可以帮着润色）。然后运行 `nutmeg.py publish`。

## 数据、输出与许可

- `outputs/`、`.cache/` 不进 git。基于 StatsBomb 开放数据的分析对外发布时要注明 StatsBomb 并使用其 logo；
  Understat、ESPN、Transfermarkt 的数据只做个人分析。
- 第三方许可见 `THIRD_PARTY_NOTICES.md`；更新第三方 skills 的方法见 `README.md`。
