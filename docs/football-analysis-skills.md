# 足球分析相关 Agent Skills 调研与排序

数据核对时间：2026-10-30 北京时间（已复核一轮）。

核对方法：

- **能否安装**：用 `skills` 命令行实测 `npx skills add <仓库> --list`；判定为「不是技能」的仓库，额外加 `--full-depth` 做全目录扫描。
- **功能与依赖**：逐个通读 SKILL.md 原文，不采信目录站摘要。
- **星标、许可证**：GitHub API。许可证同时检查 LICENSE 文件、README 和清单文件里的声明。
- **最近提交**：默认分支的最近一次提交，换算为北京时间。
- **安装量**：skills.sh 注册表（`npx skills find`）当日数值，比星标更直接地反映技能本身的采用度。

## 排序结论

| 排名 | Skill | 安装量 | 星标 | 许可证 | 最近提交 | 适合谁 |
|---|---|---|---|---|---|---|
| 1 | `machina-sports/sports-skills@football-data` | 2.3K | 261 | MIT | 10-29 | 所有人，默认首装 |
| 2 | `withqwerty/nutmeg`（11 个技能） | 每个 158–185 | 55 | MIT（README 声明） | 10-29 | 想把分析做对、做深的人 |
| 3 | `sugarforever/01coder-agent-skills@fpl-copilot` | 289 | 139 | MIT | 10-20 | 玩英超梦幻足球（FPL）的人 |
| 4 | `Football-Skill/football-match-forecasting` | 3 | 3 | 无 | 06-14 | 想学赛果预测建模的人 |
| 5 | `outsharp/shipp-skills@openfootball` | 131 | 4 | Apache-2.0 | 03-23 | 只要历史赛果、不想装任何包的人 |
| 6 | `Crawlora-org/crawlora-skills` 的 `football-player-comparison` | 19 | 1 | MIT | 10-27 | 只做球员对比、愿意注册 Crawlora 的人 |

日期均为 2026 年、北京时间。

推荐组合：**1 + 2 一起装**。`football-data` 负责「把数拿到」，`nutmeg` 负责「别把数用错」，两者职责不重叠；玩 FPL 再加 3。

安装命令：

```bash
npx skills add machina-sports/sports-skills@football-data
npx skills add withqwerty/nutmeg
npx skills add sugarforever/01coder-agent-skills@fpl-copilot
npx skills add Football-Skill/football-match-forecasting
npx skills add outsharp/shipp-skills@openfootball
npx skills add Crawlora-org/crawlora-skills --skill football-player-comparison
```

## 排序依据

前两条是硬门槛，其余按重要性排列：

1. **真实可安装**：仓库里有合法的 `SKILL.md`（见文末「避坑」，目录站上有不少条目根本装不上）。
2. **不被单一平台或付费服务锁死**：离开某个平台就跑不起来、或核心功能必须付费的，降级处理。
3. **分析深度**：是否处理 xG、PPDA、xT 这类派生指标和口径问题，而不只是报比分。
4. **维护与采用度**：最近提交、贡献者人数、版本发布、skills.sh 安装量。
5. **获取成本**：是否需要 API key、注册或付费。
6. **时效**：世界杯专用技能在 2026-07-19 决赛之后价值大幅下降，单独归类。

## 逐项说明

### 1. `football-data`（machina-sports/sports-skills）

skills.sh 安装量 2.3K，在我搜到的足球类技能里最高（世界杯专用的 Starchild `worldcup` 以 1.4K 排第二），约为非世界杯类足球技能第二名 `fpl-copilot`（289 次）的 8 倍。仓库 261 星、14 位贡献者、MIT；近 30 天里有 14 天有提交（共 62 次），10-24 至 10-29 连发 v0.38–v0.40 三个版本。

目录结构完整：`SKILL.md` + `references/`（`api-reference.md`、`commands.md`、`data-coverage.md`、`schemas.md`）+ `scripts/validate_params.sh`。命令表共 25 条，覆盖积分榜、赛程、阵容、事件时间轴、xG 与射门图、球员资料、转会、伤停、Elo 强度、交锋记录和赛果预测；赛事近 20 个，包括五大联赛、欧冠、世界杯、英冠、荷甲、葡超、巴甲、美职联等，以 `get_competitions` 的实时列表为准。数据来自 ESPN、FPL、Understat、Transfermarkt、football-data.co.uk、ClubElo，**零 API key、零注册**，需要 Python 3.10+（`pip install sports-skills`）。

`SKILL.md` 写得很老实，这比星标更能说明质量：

- 明确标出覆盖边界：`get_event_xg` 只在五大联赛可用，`get_season_leaders` 和 `get_missing_players` 只在英超可用；未覆盖的调用返回带 `message` 的空载荷，而不是假数据。
- 要求 season ID 由 `get_current_season` 推导、team ID 由 `search_team` 解析，避免「两个 Paris」这类重名错配。
- 专门列出 12 个模型常编造的命令名（如 `get_standings`、`get_live_scores`），提醒不要调用。

注意事项：数据抓自第三方公开站点，受各站条款约束；数据为赛后更新，不适合看实时比分；SKILL.md 末尾附有一段可选的付费服务导流（Machina Agent Storefront），不影响免费路径。

### 2. `nutmeg`（withqwerty）

55 星、单一贡献者。许可证方面，README 末尾声明为 MIT，只是仓库里没放 LICENSE 文件，所以 GitHub 页面显示「无许可证」；配套的 `football-docs` npm 包同样是 MIT。

它不是取数工具，而是方法论层：1 个入口技能 `nutmeg` 加 10 个子技能（`nutmeg-acquire`、`-wrangle`、`-compute`、`-analyse`、`-brainstorm`、`-review`、`-heal`、`-store`、`-learn`、`-research`），共 11 个，由入口按意图路由。skills.sh 上各技能安装量在 158–185 次之间，新加的 `nutmeg-research` 只有 6 次。

真正的差异化在配套的 `football-docs` MCP 服务（需 Node 22.13+）。它把 Opta qualifier ID、StatsBomb 坐标系、各家 API 字段这类**模型训练数据里常记错、而且会变**的事实做成可检索索引，让 agent 去查而不是凭记忆编。指标卡区分口径变体（例如 `ppda.statsbomb-hudl`），并禁止跨变体比较数值，这正是业余分析最常犯的错。跨数据源的球员/球队 ID 对齐走 Reep Register（CC0）。

排第二而非第一，原因有三：

- 单人维护。10 月 1–14 日提交密集（81 次），之后到 10-29 只有 1 次。
- 完整体验依赖 MCP 服务。只装 skills 时，它会说明无法核对提供商事实，凭记忆回答的内容标注为 unverified；在 Cursor 里需要手动把 `npx -y football-docs@0.17.4` 配成 MCP 服务。
- 它本身不带开箱即用的数据命令，取数靠它写代码调用 soccerdata 等库，起步比 `football-data` 慢。

### 3. `fpl-copilot`（sugarforever/01coder-agent-skills）

289 次安装、仓库 139 星、MIT，当前版本 v1.3.0，最近一次更新在 10-20。面向 Fantasy Premier League（英超梦幻足球）：球员数据、转会建议、队长选择、赛程难度（FDR）、周赛策略、阵容管理。

工程质量是这批垂直技能里最好的：

- 数据走 FPL 官方公开 API（`fantasy.premierleague.com/api`，无需认证）。
- 用 SQLite 持久化，并有明确的数据新鲜度约定：刷新失败不能当作数据是新的。
- `references/` 里写好了指标公式和决策框架。
- 附 5 个 HTML 报告模板：阵容图、赛程难度矩阵、转会对比、队长排名、周赛报告。

局限：只服务 FPL 这一个场景，不玩 FPL 的话用处不大。

### 4. `football-match-forecasting`（Football-Skill）

3 星、3 次安装、无许可证（LICENSE、README、SKILL.md 均无声明），2026-06-14 当天两次提交后再没动过。能排进前四，靠的是内容质量。

方法是「量化基线 + 受约束的 LLM 调整」：

1. 多源取数，用公开检索补国家队 API 的缺口。
2. 用 Elo 分差映射期望进球，再用 Poisson/Dixon-Coles 生成比分网格，叠加各队攻防强度做集成基线。
3. **只允许 LLM 用具名的具体情报（伤停、阵容、战术）调整基线**。
4. 对真实赛果做验证和自学习。

它给出的一个校准结论很有价值：常用的「每 100 Elo 分差对应 0.32 个进球」会低估强队，用历史结果校准后约为 0.45。模型概率与市场赔率保持独立，市场只用于下注规模和边际判断。

它不只是文档，`scripts/` 里有两个可以直接跑的脚本：`calibrate_backtest.py` 对赛果 CSV 做滚动 Elo 回测，按 log-loss 网格搜索系数，并按 Elo 分差分桶输出校准情况；`build_team_ratings.py` 拟合各队攻防评分。

局限：没有许可证即默认保留所有权利，直接复用脚本存在法律上的不确定性；采用度极低，几乎没有人验证过。

### 5. `openfootball`（outsharp/shipp-skills）

131 次安装、4 星、Apache-2.0，最近提交 03-23。教 agent 直接读取 openfootball 的 `football.json`（公有领域数据，托管在 GitHub raw 和 Pages 上），覆盖五大联赛、欧冠、世界杯、欧洲杯等的赛程和赛果，**零 key、零依赖**，curl 就能用。

局限：只有赛程、比分这类已完赛数据，社区维护，可能滞后数小时到数天；和 `football-data` 有部分重叠（后者也接入了 football-data.co.uk 这个有二十年历史赛果的数据源）。优势是纯静态 JSON，适合不想装 Python 包的场景。

### 6. `football-player-comparison`（Crawlora-org/crawlora-skills）

19 次安装、MIT、近期有更新。提示词写得认真：

- 先确定位置/角色、赛事、时间窗口和最低出场时间，再选对比样本。
- per-90 只对计数型指标、且有同一样本的真实出场分钟时才计算。
- 不把赛季总量和与之重叠的单场数据相加。
- 缺失数据视为「未知」而不是 0；保留指标的原始键名、单位和来源。

局限：数据要经 Crawlora 抓取 FotMob，需要注册拿 `CRAWLORA_API_KEY`（免费档每月 2000 credits，不用绑卡）。它出自一个有 177 个技能的通用爬虫技能仓库，足球只是其中几条（同仓库还有 `football-match-performance-analysis`、`flashscore-match-analysis`、`fotmob-research` 等），仓库仅 1 星。更适合把提示词当模板参考。

## 世界杯类技能：赛事已结束，时效已过

2026 世界杯已于 2026-07-19 结束，决赛西班牙加时 1:0 胜阿根廷。下面这些技能有的安装量很高，但那是赛前和赛中积累的，现在除了做赛后复盘，用处有限：

| Skill | 安装量 | 星标 | 许可证 | 最近提交 | 说明 |
|---|---|---|---|---|---|
| `starchild-ai-agent/official-skills@worldcup` | 1.4K | 29 | 无 | 10-30 | 赛程、比分和积分制竞猜游戏；鉴权写的是「容器 JWT 自动完成」，依赖 Starchild 平台自身的运行环境，不是分析工具 |
| `machina-sports/sports-skills@world-cup` | 674 | 261 | MIT | 10-29 | 纯提示词：免费数据仍走 `football-data`；托管预测、成稿等是按次计费的可选服务，调用前须经用户批准；不需要密钥或额外 MCP |
| `anycap-ai/anycap@anycap-worldcup-predict` | 587 | 48 | MIT | 10-21 | 必须安装并登录 AnyCap CLI，检索按 credit 计费（一次 grounding 检索 5 credits） |
| `qqyule/worldcup-predictor-skill@worldcup-predictor` | 136 | 17 | MIT | 06-18 | 中文世界杯预测，含体彩胜平负（3/1/0）参考 |
| `Wilder1222/WorldCup2026-Skill`（6 个技能） | 未收录 | 0 | MIT（README 声明） | 05-18 | 见下 |

`Wilder1222/WorldCup2026-Skill` 带有一整套 JS 多模型引擎（Elo、贝叶斯、蒙特卡洛、ML 集成）和中文 README，但代码里没有任何联网取数。本地 `data/teams.json` 自己标注为 `SAMPLE_DATA_UNVERIFIED`，只收录了 25 支球队（本届实际为 48 队）；SKILL.md 引用的 `data/historical.json` 在仓库里并不存在。全部 4 次提交在 05-18 当天约 3 小时内完成。可以参考它的输出 schema 设计，不建议实际使用。

## 不推荐

| Skill | 安装量 | 原因 |
|---|---|---|
| `josearroyave/agent-skills@football-betting-analysis` | 268 | 西班牙语、面向博彩，依赖 FlashScore MCP；SKILL.md 长达 1329 行，仓库 0 星，04-17 后未更新 |
| `davila7/claude-code-templates@footballbin-predictions` | 198 | 薄封装：调用第三方接口拿现成的「AI 预测」，主页是 FootballBin 手机 App；所在仓库的 3.3 万星属于整个模板合集，不代表这个技能 |
| `buildkit-ai/soccer-match-tracker` | 184 | 只做比分和积分榜追踪，需要 football-data.org 等两个 API key，02-21 后未更新 |
| `onewave-ai/claude-skills` 的 `scouting-report-builder`、`fantasy-lineup-optimizer` | 316 / 408 | 都是 59 行的通用提示词：前者不针对任何具体运动，后者是覆盖 NFL/NBA/MLB/NHL/足球的梦幻体育排阵 |
| `superluigi0309/soccer-predict`（足球预测） | 71 | 注册表仍可搜到，但 GitHub 上该用户和仓库都已不存在（404） |

## 专业向补充：SkillCorner 数据

`aliamrrr/openbootroom`（MIT，1 星，最近提交 08-24）有 76 个围绕 SkillCorner 追踪数据（Physical、Game Intelligence、Dynamic Events 等）的工作流技能，面向俱乐部数据岗。SkillCorner 是付费商业数据，能搜到的几个技能安装量都只有 3 次，手里真有这类数据时才值得看。

## 避坑：目录站上的「假技能」

OpenAgentSkill 等聚合站把下面这些仓库列成了可以 `npx skills add` 的技能，其中 3 个还给了信任分（roboflow 86、StatsBomb 82、mplsoccer 78），其余标为「index candidate」。我用 `npx skills add <仓库> --list --full-depth` 逐个实测，**全部返回「No valid skills found」**：

| 仓库 | 目录站标注 | 实测 |
|---|---|---|
| `roboflow/sports` | 信任分 86，但注册表自己也标了 `status: unverified` | 无技能 |
| `statsbomb/open-data`（已迁至 `hudl/open-data`） | 信任分 82 | 无技能，纯数据仓库 |
| `andrewRowlinson/mplsoccer` | 信任分 78 | 无技能 |
| `probberechts/soccerdata` | index candidate | 无技能 |
| `ML-KULeuven/socceraction` | index candidate | 无技能 |
| `PySport/kloppy` | index candidate | 无技能 |
| `footballcsv/england` | index candidate | 无技能，纯数据仓库 |

skills.sh 注册表本身也有三类坑，上文已分别点名：源仓库已删除但仍可搜到（`soccer-predict`）、离开特定平台跑不起来（Starchild 的 `worldcup`）、借大仓库星标的薄封装（`footballbin-predictions`）。

上表里的仓库是**优秀的 Python 库和数据集，不是 agent 技能**，正确用法是让 nutmeg 或你自己写的技能去调用它们：

- `probberechts/soccerdata`（2124 星，Apache-2.0）— 从 FBref、Understat、ClubElo、SoFIFA 等抓数，取数首选
- `hudl/open-data`（3753 星）— StatsBomb 公开事件数据，练手和研究的标准数据集；仓库附 `LICENSE.pdf` 使用协议，使用前请阅读
- `ML-KULeuven/socceraction`（823 星，MIT）— SPADL、VAEP、xT 动作价值评估
- `PySport/kloppy`（571 星，BSD-3）— 统一各家事件/追踪数据格式，多源项目的地基
- `andrewRowlinson/mplsoccer`（553 星，MIT）— 球场绘图、射门图、雷达图
- `roboflow/sports`（5455 星，MIT）— 视频侧的球员/球追踪、球衣号识别、相机标定
- `UnravelSports/unravelsports`（250 星，MPL-2.0）— 图神经网络、压迫强度、阵型识别（EFPI）
- `floodlight-sports/floodlight`（134 星，MIT）— 空间控制、代谢功率等追踪数据模型
- `footballcsv/england`（170 星，CC0）— 英格兰历史赛果 CSV

## 给本仓库（足球学习）的建议路径

1. 先装 `football-data`，零配置就能拿到联赛、比赛、球员的真实数据，用来建立手感。
2. 概念层（xG 怎么算、PPDA 有几种口径、坐标系怎么翻转）配 `nutmeg` 的 `nutmeg-learn` 和 `nutmeg-compute`，并把 `football-docs` 配成 MCP 服务。
3. 玩 FPL 的话加装 `fpl-copilot`，它的报告模板本身就是不错的可视化范例。
4. 要做自己的分析管线时，底座用 `soccerdata` + `kloppy` 取数和统一格式，`socceraction` 算动作价值，`mplsoccer` 出图；预测模型参照 `football-match-forecasting` 的 Elo 基线 + 受约束调整思路（它没有许可证，借鉴思路、自己实现）。
