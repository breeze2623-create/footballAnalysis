# footballAnalysis

足球学习：在 Cursor 里用 Agent Skills 做**战术分析、球员分析、比赛分析**。打开仓库后直接用中文提问，
Cursor 会按 `.cursor/skills/football-analysis/SKILL.md` 选数据源、运行脚本，并给出带图的中文报告。

## 方案

| 层 | 组件 | 作用 |
|---|---|---|
| 数据 | `football-data` skill（sports-skills：ESPN、Understat、FPL、Transfermarkt、ClubElo） | 当季联赛的比赛、球员、积分榜、身价、Elo、赛前预测 |
| 数据 | StatsBomb 开放数据（脚本运行时下载） | 事件级数据：2018/2022 世界杯、2020/2024 欧洲杯、2024 美洲杯、2023 非洲杯、2015/16 英超/西甲/意甲/法甲整季等 |
| 方法 | `nutmeg`（11 个 skills）+ football-docs MCP | 指标口径（变体 ID）、数据商文档、跨数据源 ID、分析与研究流程，防止把数据用错 |
| 执行 | `football-analysis`（本仓库自有 skill） | 路由规则 + 脚本：直接产出中文报告、CSV 和图 |

选型依据见 [docs/football-analysis-skills.md](docs/football-analysis-skills.md)（`football-data` 排第 1，`nutmeg` 排第 2）。
`football-data` 没有逐事件数据，算不了 PPDA、传球网络、压迫位置，所以战术层由自有脚本基于 StatsBomb 开放数据补上。

## 怎么用

打开仓库（或拉取更新）后**新开一个对话**：Cursor 在对话开始时读取技能列表，之前开的对话看不到新装的 skills。
在对话框里直接提问即可；想明确指定时输入 `/football-analysis` 再提问。例如：

| 类型 | 示例提问 | 背后运行 |
|---|---|---|
| 比赛分析 | 复盘 2022 世界杯决赛阿根廷对法国 | `sb_match.py --match 3869685` |
| 比赛分析 | 阿森纳最近一场比赛踢得怎么样？ | `fd_match.py --team arsenal --competition premier-league` |
| 战术分析 | 阿根廷在 2022 世界杯的打法和压迫有什么特点？和其他球队比呢？ | `sb_team.py --team argentina --competition 43 --season 106 --benchmark` |
| 战术分析 | 2015/16 莱斯特城夺冠靠的是什么踢法？ | `sb_team.py --team leicester --competition "Premier League" --season 2015/2016` |
| 球员分析 | 梅西在 2022 世界杯的表现，和同位置球员比怎么样？ | `sb_player.py --player messi --competition 43 --season 106 --benchmark` |
| 球员分析 | 萨卡本赛季的 xG、xA 和射门分布 | `fd_player.py --player saka --team arsenal --competition premier-league` |
| 概念 | PPDA 是什么？StatsBomb 和 Opta 的口径有什么不同？ | football-docs `get_metric` + `nutmeg-learn` |
| 自己的数据 | 帮我清洗这份 FBref 导出的 CSV，并算每 90 分钟数据 | `nutmeg-wrangle`、`nutmeg-compute` |

脚本也可以手动运行（都在 `.cursor/skills/football-analysis/scripts/`，从仓库根目录执行）：

| 脚本 | 作用 |
|---|---|
| `sb_find.py` | 查 StatsBomb 的赛事、比赛、球员 ID |
| `sb_match.py` | 单场比赛与战术报告：射门图、xG 走势、传球网络、压迫热区、xT 势能 |
| `sb_team.py` | 球队整届/整季战术画像：逐场数据、进攻与防守、比分状态拆分、阵型与人员、同赛事排名与风格雷达图 |
| `sb_player.py` | 球员报告：每 90 分钟数据、射门图、热区、推进动作、同位置百分位雷达图 |
| `fd_match.py` | 当季比赛报告（ESPN 统计 + Understat 射门 xG） |
| `fd_player.py` | 当季球员报告（逐场分钟、进球助攻、xG/xA/xGChain、射门图、队内对比） |
| `doctor.py` | 环境诊断：解释器、包、Node.js、football-docs MCP、数据源 |
| `selftest.py` | 用 football-docs 指标卡的测试值校验指标代码 |

报告写在 `outputs/<类型>-<名称>/report.md`，每次运行的状态记在 `outputs/LAST_RUN.json`。

## 安装与首次运行（Windows）

1. Python 3.10 或更新。用**运行脚本的那个解释器**安装依赖，不要裸用 `pip`：

       python -m pip install -r requirements.txt

   不装也可以：脚本发现缺包时会用当前解释器自动补装。
2. Node.js 22.13 或更新（football-docs MCP 需要）。
3. 用 Cursor 打开仓库，在 Customize > MCPs 里打开 `football-docs`（较早的版本在 Settings > MCP），首次连接时批准。
4. 自检：

       python .cursor/skills/football-analysis/scripts/doctor.py
       python .cursor/skills/football-analysis/scripts/selftest.py

   `doctor.py` 会指出 `python`、`pip` 是否属于同一个解释器，并按 `.cursor/mcp.json` 实际启动一次 MCP；结果在 `outputs/doctor.md`。

Customize > Skills 里 `football-data` 可能带警告图标：它上游的 description 有 1395 个字符，超过 Agent Skills 规范的 1024。
这里保留上游原样；总入口按文件路径引用它，不依赖自动匹配。

## 在 Cloud Agent 里运行（GitHub 仓库）

- Cloud Agent 自动加载仓库里的 `.cursor/skills/`、`.agents/skills/` 和 `AGENTS.md`；新提交的 skill 只对之后启动的 agent 生效。
- Python 依赖不用预装：脚本缺包时用当前解释器自动补装。
- football-docs MCP：Cloud Agent 只用在 cursor.com/agents 的 MCP 下拉菜单里配置的服务器。添加 stdio 服务器，命令 `npx`，
  参数 `-y football-docs@0.17.4`。脚本本身不依赖 MCP。

## 目录

```
.cursor/skills/football-analysis/   自有 skill：SKILL.md、scripts/、references/（指标口径、数据来源）
.agents/skills/                     第三方 skills：football-data、nutmeg 等 11 个（版本见 skills-lock.json）
.cursor/mcp.json、.cursor/mcp/      football-docs MCP 配置与跨平台启动脚本
third_party/nutmeg/                 nutmeg 插件资源（文档、研究项目 CLI、agents 说明）
AGENTS.md                           给 AI 助手的规则：环境坑、nutmeg 在 Cursor 中的用法
docs/football-analysis-skills.md    足球分析 skills 调研与排序
outputs/、.cache/                    报告与数据缓存（不进 git）
```

## 更新第三方 skills

    npx -y skills add machina-sports/sports-skills@football-data --agent cursor --copy -y
    npx -y skills add withqwerty/nutmeg --agent cursor --copy -y

更新 nutmeg 后按 `third_party/nutmeg/README.md` 同步插件资源；football-docs 的版本在 `.cursor/mcp/football-docs.mjs` 里。
第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 数据使用

- StatsBomb 开放数据可免费用于研究和个人分析；公开发布基于它的图或分析时，需注明 StatsBomb 并使用其 logo。
- Understat、ESPN、Transfermarkt 等站点的数据只做个人分析，仓库不保存原始数据。
