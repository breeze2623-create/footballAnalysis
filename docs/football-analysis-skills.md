# 足球分析相关 Agent Skills 调研与排序

数据核对时间：2026-10-30（星期五，北京时间）。星标数、最近提交时间均通过 GitHub API 实测，不取自目录站的宣传页。

## 排序结论

| 排名 | Skill | 安装 | 星标 | 许可证 | 最近提交 | 一句话定位 |
|---|---|---|---|---|---|---|
| 1 | `machina-sports/sports-skills` 的 `football-data` | `npx skills add machina-sports/sports-skills@football-data` | 261 | MIT | 2026-10-30 | 免 API key 的数据取数层，首选默认装 |
| 2 | `withqwerty/nutmeg` | `npx skills add withqwerty/nutmeg` | 55 | 无（⚠️） | 2026-10-28 | 足球数据方法论层，懂 Opta/StatsBomb 口径与指标变体 |
| 3 | `Football-Skill/football-match-forecasting` | `npx skills add Football-Skill/football-match-forecasting` | 3 | 无（⚠️） | 2026-06-14 | 赛果预测方法论（Elo + Poisson/Dixon-Coles），当参考文档读 |
| 4 | `machina-sports/sports-skills` 的 `world-cup` | 同 1 的仓库 | — | MIT（壳） | 2026-10-30 | 2026 世界杯专用，但数据面要 `machina-cli` / MCP 凭证 |
| 5 | `Crawlora-org/crawlora-skills` 的 `football-player-comparison` | `npx skills add Crawlora-org/crawlora-skills --skill football-player-comparison` | 1 | MIT | 2026-10-27 | 球员对比提示词，但出自批量生产的爬虫技能农场 |
| 6 | `Wilder1222/WorldCup2026-Skill` 的 `team-analysis` | `npx skills add https://github.com/Wilder1222/WorldCup2026-Skill --skill team-analysis` | 0 | 无（⚠️） | 2026-05-18 | 演示级，数据写死在本地 JSON，已半年未更新 |

推荐组合：**1 + 2 一起装**。`football-data` 负责「把数拿到」，`nutmeg` 负责「别把数用错」，两者职责不重叠。

## 排序依据

按以下五个维度加权，前两维是硬门槛：

1. **真实可安装**：仓库里是否真有 `SKILL.md`（见下方「避坑」一节，很多目录站的条目是假的）。
2. **维护活跃度**：最近提交时间、贡献者人数、是否有版本发布。
3. **覆盖深度**：联赛/数据源覆盖面，以及是否处理 xG、PPDA、xT 这类派生指标。
4. **获取成本**：是否需要 API key、付费订阅或额外 MCP 服务。
5. **许可与风险**：有无开源许可证，数据源的使用条款。

## 逐项说明

### 1. `football-data`（machina-sports/sports-skills）

261 星、38 fork、14 位贡献者、MIT，2026-10-29 刚发 v0.40.0，提交几乎每天都有——是这批里工程化程度最高、维护最稳的一个。

技能目录结构完整：`SKILL.md` + `references/`（`api-reference.md`、`commands.md`、`data-coverage.md`、`schemas.md`）+ `scripts/validate_params.sh`。25 条命令覆盖积分榜、赛程、阵容、事件时间轴、xG 与射门图、球员资料、转会、伤停、Elo 强度、赛果预测。数据来自 ESPN、FPL、Understat、Transfermarkt、football-data.co.uk、ClubElo，**零 API key、零注册**。

`SKILL.md` 里把覆盖边界写得很老实，这点比星标更能说明质量：`get_event_xg` 只在五大联赛可用，`get_season_leaders` 和 `get_missing_players` 只在英超可用，未覆盖的调用返回空载荷而不是数据。它还强制要求 season ID 必须由 `get_current_season` 推导、team ID 必须由 `search_team` 解析，避免「两个 Paris」这类重名错配。

注意：数据是抓第三方公开站点，受各站点条款约束；且明确说明不适合实时比分，数据为赛后更新。

### 2. `nutmeg`（withqwerty）

55 星、单一贡献者、**无 LICENSE 文件**（默认即保留所有权利，公司内部使用前需要先确认授权）。但内容深度在这批里是断崖式领先的。

它不是取数工具，而是方法论层：11 个子技能按意图路由——`acquire`（抓取与密钥管理）、`wrangle`（坐标系转换、事件流重塑）、`compute`（xG、PPDA、传球网络、xT）、`analyse`、`brainstorm`（可视化设计）、`review`（发布前查代码和图表）、`heal`（修挂掉的爬虫）、`store`、`learn`、`research`。

真正的差异化在配套的 `football-docs` MCP 服务（npm 包，需 Node 22.13+）：它把 Opta qualifier ID、StatsBomb 坐标系、各家 API 字段这类**模型训练数据里经常记错、且会变动**的事实做成可检索索引，让 agent 去查而不是凭记忆编。指标卡会区分变体（例如 `ppda.statsbomb-hudl`），并禁止跨变体比较数值——这正是业余足球分析最常犯的错。跨源球员/球队 ID 对齐走 Reep Register（CC0）。

代价：想要完整体验得装 MCP 服务，只装 skills 的话它会把答不了的问题标记为 unverified。单人维护 + 无许可证是主要风险。

### 3. `football-match-forecasting`（Football-Skill）

3 星、2026-06 创建后没再动过、无许可证，仓库只有 `README.md`、`SKILL.md`、`references/`、`scripts/`。

价值在方法论本身而非代码：先多源取数、用公开检索补国家队 API 的缺口，建标定过的 Elo + 各队攻防强度集成基线，**只允许 LLM 用具名的具体情报（伤停、阵容、战术）去调整基线**，最后对真实赛果做验证和自学习。这套「量化基线 + 受约束的 LLM 调整」的分工，比大多数让模型直接张口预测的做法靠谱。当成一份设计文档读，自己实现，比直接依赖它更合适。

### 4. `world-cup`（machina-sports/sports-skills）

和第 1 名同仓库，所以维护质量有保障，但它是 premium 通道：官方赛事事实 + Kalshi/Polymarket 实时盘口 + AI 简报，要通过 `machina-cli` 和 MCP 接 Machina Intelligence Layer。只在明确做 2026 世界杯且愿意接商业数据源时考虑。

### 5. `football-player-comparison`（Crawlora-org）

MIT、近期有更新，提示词本身写得不差：强调按位置/角色、赛季窗口、最低出场时间来筛选对比样本，禁止混用赛季总量和近期状态，保留指标出处。

但 `crawlora-skills` 是一个几百个技能的通用爬虫技能农场（从亚马逊招聘到动漫研究全都有），足球只是其中一条流水线产物，仓库仅 1 星，数据依赖 Crawlora 抓 FotMob。可以把它的提示词当模板抄走，不建议作为依赖。

### 6. `team-analysis`（Wilder1222/WorldCup2026-Skill）

0 星、无许可证、自 2026-05-18 起未更新。从本地 `data/teams.json` 读数，输出 Elo、阵型、压迫/反击/转换速度、动量指数的结构化 team_profile。它自己的规则里就写明「球员年龄、俱乐部、评分、近期状态须为 2026-05-18 当日有效，否则标注为历史数据——需更新」，也就是说现在读出来的全是过期数据。参考其输出 schema 设计即可。

## 避坑：目录站上的「假技能」

OpenAgentSkill 等聚合站把下面这些仓库列成了可以 `npx skills add` 的技能，并给出了信任分。我逐个查过它们的仓库根目录和 `.claude/skills/`，**都不存在 `SKILL.md`**：

| 仓库 | 目录站宣称 | 实测 |
|---|---|---|
| `PySport/kloppy` | `npx skills add PySport/kloppy` | 无 SKILL.md |
| `ML-KULeuven/socceraction` | `npx skills add ML-KULeuven/socceraction` | 无 SKILL.md |
| `probberechts/soccerdata` | `npx skills add probberechts/soccerdata` | 无 SKILL.md |
| `andrewRowlinson/mplsoccer` | `npx skills add andrewRowlinson/mplsoccer` | 无 SKILL.md |
| `statsbomb/open-data`（已迁至 `hudl/open-data`） | `npx skills add statsbomb/open-data` | 纯数据仓库，无 SKILL.md |
| `roboflow/sports` | 注册表条目 `roboflow-sports`，信任分 86 | 无 SKILL.md，注册表自己也标了 `status: unverified` |

这些是**优秀的 Python 库，不是 agent 技能**。正确用法是让 nutmeg 或你自己写的技能去调用它们：

- `probberechts/soccerdata`（2124 星）— 从 FBref、Understat、ClubElo、SoFIFA 等抓数，取数首选
- `hudl/open-data`（3753 星）— StatsBomb 公开事件数据，练手和研究的标准数据集
- `ML-KULeuven/socceraction`（823 星，MIT）— SPADL、VAEP、xT 动作价值评估
- `PySport/kloppy`（571 星，BSD-3）— 统一各家事件/追踪数据格式，多源项目的地基
- `andrewRowlinson/mplsoccer`（553 星，MIT）— 球场绘图、射门图、雷达图
- `roboflow/sports`（5455 星，MIT）— 视频侧的球员/球追踪、球衣号识别、相机标定
- `UnravelSports/unravelsports`（250 星）— 图神经网络、压迫强度、阵型识别（EFPI）
- `floodlight-sports/floodlight`（134 星，MIT）— 空间控制、代谢功率等追踪数据模型

## 给本仓库（足球学习）的建议路径

1. 先装 `football-data`，零配置就能拿到联赛、比赛、球员的真实数据，适合建立手感。
2. 概念层（xG 到底怎么算、PPDA 有几种口径、坐标系怎么翻转）配 `nutmeg` 的 `learn` 和 `compute`，但要先接受它无许可证这个前提。
3. 真要做自己的分析管线时，底座用 `soccerdata` + `kloppy` 取数和统一格式，`socceraction` 算动作价值，`mplsoccer` 出图；预测模型参照 `football-match-forecasting` 的 Elo 基线 + 受约束调整思路。
