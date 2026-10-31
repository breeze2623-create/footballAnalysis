---
name: football-analysis
description: >-
  足球数据分析总入口：战术分析（阵型、压迫/PPDA、传球网络、field tilt、推进、xT、比分状态）、球员分析（每 90 分钟数据、
  xG/xA、射门图、同位置百分位雷达图）、比赛分析（赛后复盘、xG 走势、关键事件）。Football/soccer analysis hub for
  tactics, teams, players and matches. Runs the bundled scripts on StatsBomb open event data (World Cup, Euro,
  Copa America, AFCON, 2015/16 top leagues, Messi-era Barcelona, women's tournaments) and on current-season leagues
  through the football-data skill (ESPN + Understat), and routes metric definitions to the football-docs MCP and
  work on the user's own data to the nutmeg skills. Use for any question about how a team or player played, a match
  report, team style, pressing, xG, shot maps, passing networks, player comparison or scouting numbers.
---

# 足球分析（战术 / 球员 / 比赛）

总入口：先按第 1 节选工具，再按对应流程做。脚本在 `.cursor/skills/football-analysis/scripts/`，从仓库根目录运行；
每次运行在 `outputs/<类型>-<名称>/`（如 `match-spain-vs-england-3943043`、`team-argentina-fifa-world-cup-2022`）写出
`report.md`（中文报告）、`summary.json`、CSV 和 PNG 图；准确路径见命令最后一行的 `report folder`，或 `outputs/LAST_RUN.json` 的 `out_dir`。

## 0. 运行规则（每次都适用）

- **解释器**：Windows 用 `python`（找不到时用 `py -3`），macOS/Linux 用 `python3`；下文统一写作 `python`。同一任务的所有命令用同一个解释器。
- **安装依赖只用** `python -m pip install -r requirements.txt`（仓库根目录），不要裸用 `pip`：`pip` 与 `python` 可能属于不同的解释器。
  脚本缺包时会用正在运行的解释器自动补装（`sys.executable -m pip install`）；设 `FOOTBALL_ANALYSIS_NO_INSTALL=1` 可关闭。
- **新机器或出错时先跑** `python .cursor/skills/football-analysis/scripts/doctor.py`：检查解释器、Python 包、Node.js、
  football-docs MCP 与数据源，结果写到 `outputs/doctor.md`。
- **终端输出丢失**（Shell 返回 no exit status / result unknown）时不要判定失败：读 `outputs/LAST_RUN.json`
  （`status`、`out_dir`、`files`、`error`、`log`），再读 `<out_dir>/report.md`；也可以读 Cursor 的 terminals 文件夹里的 `*.txt`。
- **football-data 命令**一律写成 `python -m sports_skills football <command> --参数=值`；不要用 `sports-skills` 可执行文件，
  也不要照 football-data 的 SKILL.md 运行裸 `pip install`。不要使用其中提到的付费 Machina 服务，除非用户明确要求。
- **名称与 ID**：球队、球员、赛事名称忽略大小写和重音，可以只写一部分；有歧义时脚本列出候选，球队改写全名，球员改用 `--player-id`。
  `sb_find`、`sb_team`、`sb_player` 的 `--competition`/`--season` 写 ID（`43`/`106`）或名称（`"FIFA World Cup"`/`2022`、`2015/2016`）都可以，
  `sb_match` 只收数字 ID（也可省略）。常用：2022 世界杯 43/106，2018 世界杯 43/3，2024 欧洲杯 55/282，2020 欧洲杯 55/43，
  2024 美洲杯 223/282，2023 非洲杯 1267/107，2015/16 英超 2/27；其他用 `sb_find.py competitions --q <名称>` 查，不凭记忆写 ID。
- StatsBomb 数据首次下载后缓存在 `.cache/football-analysis/`；网络、代理、离线用法见 `references/data-sources.md` 第 4 节。

## 1. 选工具

| 用户想要 | 用什么 |
|---|---|
| 某场比赛的复盘与战术细节（StatsBomb 有数据的比赛） | `sb_find.py matches` 找 ID，再 `sb_match.py` |
| 一支球队整届/整季的打法、压迫、比分状态下的变化 | `sb_team.py`；加 `--benchmark` 与同赛事所有球队排名 |
| 球员在一届赛事/一个赛季的表现、同位置对比 | `sb_player.py`；加 `--benchmark` 出百分位与雷达图 |
| 本赛季某场比赛（最近一场、指定对手） | `fd_match.py`（五大联赛有 Understat xG，其余联赛只有 ESPN 统计） |
| 本赛季球员表现（逐场、xG/xA、射门图、队内对比） | `fd_player.py` |
| 积分榜、赛程、交锋、Elo、赛前预测、身价、转会、伤停 | football-data skill（`.agents/skills/football-data/SKILL.md`），命令表见 `references/data-sources.md` 第 2 节 |
| 指标含义、算法、各数据商口径、跨数据源 ID | football-docs MCP：`get_metric`、`list_metrics`、`search_docs`、`resolve_entity`；配合 `references/metrics.md`，讲解用 nutmeg-learn |
| 用户自己的数据（CSV、FBref 表、Wyscout/Opta 导出） | nutmeg-acquire、nutmeg-wrangle、nutmeg-compute、nutmeg-analyse |
| 设计或审查图表、可视化代码 | nutmeg-brainstorm、nutmeg-review |
| 要发布或据此做决定的分析（球探短名单、对手报告、社媒长图） | nutmeg-research（研究项目，每个数字都记录证据） |

football-data 与 nutmeg 系列在 `.agents/skills/<名称>/SKILL.md`；技能列表里没有它们时（例如安装前就开始的对话）直接读这些文件。
nutmeg 是为 Claude Code 写的，其中 `${CLAUDE_PLUGIN_ROOT}`、`mcp__football-docs__*`、hooks 等在 Cursor 里的对应做法见仓库根目录 `AGENTS.md`。

StatsBomb 开放数据覆盖：2018/2022 世界杯、2020/2024 欧洲杯、2024 美洲杯、2023 非洲杯、2015/16 英超/西甲/意甲/法甲整季、
女足世界杯与欧洲杯、WSL 等；梅西时期巴萨、2023/24 勒沃库森等只有单队比赛。详见 `references/data-sources.md` 第 1 节。
用户问的比赛不在其中且是当季比赛时用 `fd_*`；都没有时直说没有事件级数据，不要编。

## 2. 比赛分析（赛后复盘）

1. 找比赛。大赛/历史比赛：

       python .cursor/skills/football-analysis/scripts/sb_find.py matches --competition "FIFA World Cup" --season 2022 --team Argentina

   当季比赛直接运行 `fd_match.py`（默认最近一场已结束的比赛；`--vs everton` 指定对手，`--nth 2` 倒数第二场，`--event-id` 指定 ESPN 比赛 ID）：

       python .cursor/skills/football-analysis/scripts/fd_match.py --team arsenal --competition premier-league

   欧冠、欧联等杯赛同样可用（`--competition champions-league`），但只有 ESPN 统计，没有 Understat xG。
   `--vs` 找不到时，先用 football-data 的 `get_season_schedule` 确认两队本季在该赛事是否交手，不要换个赛事当作同一场。

2. 生成报告（StatsBomb）：

       python .cursor/skills/football-analysis/scripts/sb_match.py --match 3869685 --competition 43 --season 106

3. 读 `report.md` 和 `summary.json`，按这个顺序组织回答：比分与机会质量（xG、npxG、每脚射门 xG）；比赛走势（xG 走势、
   进球/红牌/换人/阵型变化）；谁控制了比赛（field tilt、传球占比，结合比分状态）；关键球员（xT、npxG、xG assisted 前三）。
4. 图：`sb_match` 有 `shot_map.png`、`xg_race.png`、`pass_network.png`、`pressures.png`、`xt_momentum.png`；`fd_match` 有射门图与 xG 走势。

## 3. 战术分析

单场战术看 `sb_match` 报告第 2 节。球队打法用多场数据：

    python .cursor/skills/football-analysis/scripts/sb_team.py --team argentina --competition 43 --season 106 --benchmark

按这个顺序分析：

- **阵型与人员**：首发阵型及场上变化、主力与轮换（`sb_team` 第 6 节，单场看 `summary.json` 的 `formations`）。
- **控球与推进**：传球占比、field tilt、推进传球与推进带球的比例、进入前场三区和禁区、传球网络里的核心连线。
- **压迫与防守**：PPDA（同时给出分子/分母）、压迫平均高度、前场三区压迫、防守动作高度、压迫热区图；
  “对手对本队的 PPDA”反映本队出球时受压程度。
- **比分状态**：平局时的数据最能代表默认打法，领先/落后时的变化体现调整（`sb_team` 第 5 节）；少于 45 分钟的状态只作参考。
- **同赛事排名**（`--benchmark`）：哪些方面靠前、靠后；偏低可能是打法选择，不一定是缺点。

当季联赛没有逐事件数据（没有 PPDA、传球网络、压迫位置）。这类问题用 `fd_match.py` 的 ESPN 统计与 Understat 射门，
多场就逐场运行或用 football-data 的 `get_team_schedule` 加 `get_event_xg`，并告诉用户这个限制。

## 4. 球员分析

- 大赛/历史：

      python .cursor/skills/football-analysis/scripts/sb_player.py --player messi --competition 43 --season 106 --benchmark

  名字有歧义时脚本列出候选，改用 `--player-id <ID>`（代替 `--player`）重跑；拼写不确定先 `sb_find.py players --competition 43 --season 106 --q messi`。
- 当季（`--last 5` 只看最近 5 场）：

      python .cursor/skills/football-analysis/scripts/fd_player.py --player saka --team arsenal --competition premier-league

- 读法：每 90 分钟数据加出场分钟（样本量）；终结看进球与 npxG（只说“本样本中高于/低于预期”）；创造看 xG assisted/xA、关键传球；
  推进看推进传球/带球、xT；防守看压迫、抢断、拦截并考虑球队控球。百分位只与同位置组、同赛事赛季、过分钟门槛的球员比较。
- 两名球员对比：分别运行，再用两份 `summary.json` 对比同口径的每 90 分钟数据；不同来源（StatsBomb 与 Understat）不能混比。
- 身价、转会、伤停：football-data 的 `search_player`，再 `get_player_profile --tm_player_id=...`；`get_missing_players` 只覆盖英超。

## 5. 解读规则（下结论前逐条检查）

1. 单场是小样本；谈风格用多场（`sb_team`）。
2. 先看比分状态和红牌，再解读控球、PPDA、field tilt。
3. 控球、领地不等于踢得更好；用 npxG、每脚射门 xG、禁区进入检验。
4. 球员比较用每 90 分钟加分钟门槛，并报告场次和分钟。
5. 一个赛季（更别说一届杯赛）的“进球减 xG”不能证明终结能力强弱。
6. 抢断、拦截等防守计数受对手控球多少影响。
7. 不同口径不混比：`xg.statsbomb-hudl` 与 `xg.understat` 是不同模型；比较前用 `get_metric` / `list_metrics` 确认变体。
8. 数据商事实（ID、坐标系、字段含义、覆盖范围）查 football-docs，不凭记忆；查不到就说明“未经核对”。

细节见 `references/metrics.md` 第 5 节与 `third_party/nutmeg/docs/metric-misuse.md`。

## 6. 回答格式

- 默认用中文（用户用其他语言提问时用该语言，脚本报告是中文，转述时翻译）；先给 2-4 句结论，再分点列证据。
  数字带口径和样本，例如“PPDA 7.42（ppda.statsbomb-hudl，1 场）”。
- 引用图时给出 `outputs/.../*.png` 路径（可用 Markdown 图片语法嵌入）。
- 注明数据来源：StatsBomb 开放数据，或 ESPN + Understat（经 sports-skills）。用户要公开发布基于 StatsBomb 数据的图或分析时，
  提醒注明 StatsBomb 并使用其 logo（见 `references/data-sources.md` 第 1 节）。
- 报告里的“数据要点”是自动生成的，转述前先核对表格；有缺失（Understat 未更新、xT 表下载失败、单队数据集）要说出来。
- 比分、进球者等事实以数据为准，不凭记忆补充。

## 7. 故障排除

| 现象 | 处理 |
|---|---|
| `ModuleNotFoundError`，或“已安装”却找不到 | 用运行脚本的同一个解释器：`python -m pip install -r requirements.txt`；对比 `python -c "import sys;print(sys.executable)"` 与 `pip -V`；或运行 `doctor.py` |
| 下载失败或超时 | 脚本会自动改用 jsDelivr 镜像；仍失败时设 `HTTPS_PROXY`，或让 `STATSBOMB_OPEN_DATA_DIR` 指向本地 `statsbomb/open-data/data` |
| `get_event_xg` 为空 | Understat 赛后 24-48 小时才更新，或不是五大联赛 |
| football-docs MCP 不可用 | 运行 `doctor.py` 看启动结果（需要 Node.js >= 22.13）；本地在 Customize > MCPs 打开它，Cloud Agent 要在 cursor.com/agents 添加（`references/data-sources.md` 第 3 节）；仍不可用时按 `references/metrics.md` 的口径回答，并说明未经 football-docs 核对 |
| 图没有生成 | 看 `outputs/LAST_RUN.json` 的 `log`；报告与数字不受影响 |
| 命令输出丢失 | 读 `outputs/LAST_RUN.json` 与 `<out_dir>/report.md` |

## 参考

- `references/metrics.md`：指标定义、变体 ID 与测试值、坐标方向、解读规则
- `references/data-sources.md`：数据覆盖、football-data 命令表、使用条件、MCP、环境变量
- `python .cursor/skills/football-analysis/scripts/selftest.py`：用 football-docs 指标卡的测试值校验指标代码
