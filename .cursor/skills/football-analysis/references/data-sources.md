# 数据来源、覆盖范围与使用条件

## 1. StatsBomb 开放数据（事件级，`sb_find.py` / `sb_match.py` / `sb_team.py` / `sb_player.py`）

每次传球、射门、压迫、抢断都有坐标，因此能算 PPDA、传球网络、推进、xT、热区。免费用于研究与兴趣分析。
脚本运行时从 GitHub 下载（失败时自动改用 jsDelivr 镜像），缓存在 `.cache/football-analysis/statsbomb/`；
仓库不分发原始数据。下表按 2026-10-30 的 `competitions.json` 逐季统计（共 80 个赛事赛季）。

**整届/整季（适合做球员百分位对比）**

| 赛事 | competition_id | 赛季（season_id）：场次 |
|---|---|---|
| FIFA World Cup | 43 | 2018 (3): 64；2022 (106): 64 |
| UEFA Euro | 55 | 2020 (43): 51；2024 (282): 51 |
| Copa America | 223 | 2024 (282): 32 |
| African Cup of Nations | 1267 | 2023 (107): 52 |
| Premier League | 2 | 2015/2016 (27): 380 |
| La Liga | 11 | 2015/2016 (27): 380 |
| Serie A | 12 | 2015/2016 (27): 380 |
| Ligue 1 | 7 | 2015/2016 (27): 377 |
| Women's World Cup | 72 | 2019 (30): 52；2023 (107): 64 |
| UEFA Women's Euro | 53 | 2022 (106): 31；2025 (315): 31 |
| FA Women's Super League | 37 | 2018/2019 (4): 107；2019/2020 (42): 87；2020/2021 (90): 131；2023/2024 (281): 132 |
| Frauen Bundesliga / Liga F / Serie A Women | 135 / 182 / 131 | 2023/2024 (281): 132 / 240 / 130 |
| NWSL | 49 | 2018 (3): 36；2023 (107): 137 |
| Indian Super League | 1238 | 2021/2022 (108): 115 |

**只有一支球队的比赛**（球员百分位只能和这支队的队友比，样本有偏；`sb_team.py` 不做球队排名）

| 赛事 | 内容 |
|---|---|
| La Liga 2004/05-2020/21（除 2015/16） | 只有巴萨的比赛（每季 7-38 场，梅西时期） |
| Premier League 2003/04 (44) | 只有阿森纳（38 场） |
| 1. Bundesliga 2015/16 (27)、2023/24 (281) | 只有勒沃库森（各 34 场） |
| Ligue 1 2021/22 (108)、2022/23 (235) | 只有巴黎圣日耳曼（26、32 场） |
| Major League Soccer 2023 (107) | 只有迈阿密国际（6 场） |
| FIFA World Cup 1958 (269) / 1970 (272) / 1986 (54) | 分别只有巴西 2 场 / 巴西 6 场 / 阿根廷 3 场 |
| UEFA Europa League 1988/89 (35/75) | 只有那不勒斯（3 场） |

**零散比赛**：Champions League 1970/71-2018/19 每季 1 场（多为决赛）；World Cup 1962（1 场）、1974（6 场）、
1990（1 场）；Copa del Rey、Liga Profesional、La Liga 1973/74、Serie A 1986/87、FIFA U20 World Cup 1979、
North American League 1977 各 1 场。

先用 `python sb_find.py competitions` / `matches` 确认有哪些比赛，不要凭印象给 ID。

常用 ID：2022 世界杯 43/106（决赛 3869685，阿根廷 3-3 法国，点球 4-2）；2024 欧洲杯 55/282（决赛 3943043，
西班牙 2-1 英格兰）；2024 美洲杯 223/282；2023 非洲杯 1267/107。

**使用条件**：发布、分享任何基于该数据的分析时，需注明数据来源 StatsBomb 并使用其 logo
（见 https://github.com/statsbomb/open-data 的 Terms & Conditions 与 LICENSE.pdf、https://statsbomb.com/media-pack/）。
脚本生成的图已带 “Data: StatsBomb open data (Hudl)”；对外发布时再按要求加 logo。

## 2. football-data skill（sports-skills：ESPN + Understat + FPL + Transfermarkt + ClubElo；`fd_match.py` / `fd_player.py`）

当季数据，没有逐事件数据（没有传球网络、PPDA、推进传球）。命令行一律用模块方式调用，避免 Windows 上找不到
`sports-skills` 命令或装到另一个解释器：

    python -m sports_skills football <command> --参数=值

| 需求 | 命令 | 覆盖 |
|---|---|---|
| 当前赛季 ID | `get_current_season --competition_id=premier-league` | 所有联赛 |
| 积分榜 | `get_season_standings --season_id=premier-league-2026` | 所有联赛 |
| 球队 ID | `search_team --query=arsenal` | 所有联赛 |
| 球队赛程/赛果 | `get_team_schedule --team_id=359 --competition_id=premier-league` | 所有联赛 |
| 单场摘要/统计/阵容/时间线 | `get_event_summary` / `get_event_statistics` / `get_event_lineups` / `get_event_timeline --event_id=...` | ESPN，所有联赛 |
| 射门级 xG | `get_event_xg --event_id=...` | Understat，仅五大联赛，赛后 24-48 小时更新 |
| 球员单场 xG/xA/xGChain | `get_event_players_statistics --event_id=...` | xG 类仅五大联赛 |
| 球员搜索 | `search_player --query=saka` | 返回 ESPN 与 Transfermarkt ID |
| 球员近况 | `get_player_season_stats --player_id=<ESPN ID> --league_slug=premier-league` | 只含最近约 5 场 |
| 身价/转会 | `get_player_profile --tm_player_id=...`，`get_season_transfers` | Transfermarkt |
| 伤停、射手榜 | `get_missing_players` / `get_season_leaders --season_id=premier-league-...` | 仅英超（FPL） |
| 交锋、Elo、赛前预测 | `get_head_to_head` / `get_team_strength` / `get_match_forecast` | 欧洲联赛；预测只看约一周内 |

完整参数见 `.agents/skills/football-data/SKILL.md` 与其 `references/`。赛季 ID 必须先用 `get_current_season` 取，
球队/球员 ID 先搜索，不要猜。`fd_player.py` 会把已结束 3 天以上的比赛数据缓存到
`.cache/football-analysis/football-data/`。

Understat、ESPN、Transfermarkt 的数据只用于个人分析；仓库不保存它们的原始数据。

## 3. football-docs MCP（方法与口径，不是比赛数据）

`.cursor/mcp.json` 通过 `node .cursor/mcp/football-docs.mjs` 启动 `football-docs@0.17.4`（需 Node.js >= 22.13）。
常用工具：`get_metric`（指标卡：定义、变体、测试值）、`list_metrics`、`search_docs`（各数据商的 ID、坐标、字段）、
`compare_providers`、`resolve_entity`（跨数据源的球员/球队 ID）、`search_papers` 等，共 17 个。
本地 Cursor 读取 `.cursor/mcp.json`，改动后需在 Settings > MCP 里启用或重启 Cursor。Cloud Agent 使用在
cursor.com/agents 的 MCP 下拉菜单里为团队配置的服务器（Cursor 文档 Cloud Agents 一节）；要在云端使用，在那里添加
stdio 服务器：命令 `npx`，参数 `-y football-docs@0.17.4`。MCP 不可用时脚本照常运行，口径以本目录的 `metrics.md` 为准。

## 4. 环境变量

| 变量 | 作用 |
|---|---|
| `STATSBOMB_OPEN_DATA_DIR` | 指向本地 `statsbomb/open-data/data` 目录（离线或网络慢时） |
| `STATSBOMB_OPEN_DATA_BASE` | 自定义镜像地址（优先于 GitHub 与 jsDelivr） |
| `HTTPS_PROXY` / `HTTP_PROXY` | 代理；Python 的 urllib 与 npx 都会读取 |
| `FOOTBALL_ANALYSIS_HOME` | 输出与缓存的根目录（默认：当前 git 仓库根目录） |
| `FOOTBALL_ANALYSIS_CACHE` | 缓存目录（默认 `<根目录>/.cache/football-analysis`） |
| `FOOTBALL_ANALYSIS_NO_INSTALL=1` | 只报告缺少的包，不自动安装 |

缓存体积：一届世界杯全部事件约 230 MB（`sb_player.py --benchmark`、`sb_team.py --benchmark` 会全部下载），单场约 3-4 MB；
一个 380 场的联赛赛季全部下载超过 1 GB，联赛做 `--benchmark` 前先确认磁盘与网络。
