# 指标口径（football-analysis 脚本）

所有 StatsBomb 指标都在 `scripts/fa_metrics.py` 里用纯 Python 计算。坐标为 StatsBomb 120 x 80，且每个事件都按
**做出该动作的球队的进攻方向**给出（该队进攻 x = 120）。点球大战（period 5）不计入任何指标。

## 1. 有 football-docs 指标卡的指标（带变体 ID）

这些指标与 football-docs MCP 的指标卡一致（`get_metric` 可查原卡）。`selftest.py` 用卡片给出的测试值
（2022 世界杯决赛阿根廷 vs 法国，match 3869685）逐项校验，误差 0.0001，当前 23/23 通过。
比较数字时只在同一变体内比较；不同变体（例如 `xg.statsbomb-hudl` 与 `xg.understat`）不能直接对比。

| 指标 | 变体 ID | 定义 | 测试值 ARG / FRA |
|---|---|---|---|
| xG | `xg.statsbomb-hudl` | 每脚射门 `shot.statsbomb_xg` 求和 | 2.7583 / 2.2726 |
| npxG | `npxg.statsbomb-hudl` | 同上，去掉点球 | 1.9748 / 0.7056 |
| xG assisted | `xg_assisted.statsbomb-hudl` | 射门的 `key_pass_id` 指向的传球者获得该射门的 xG | 1.3397 / 0.5687 |
| 传球成功率 | `pass_completion.statsbomb-hudl` | 无 `pass.outcome` 的传球 / 全部传球（含定位球） | 0.8081 / 0.7614 |
| PPDA | `ppda.statsbomb-hudl` | 对手在其本方 60% 区域（x < 72）的成功传球 / 本队在 x >= 48 的防守动作（抢断类 Duel、Interception、传球类型 Interception、Dribbled Past、Foul Committed）。越低 = 压迫越积极 | 7.4222 / 9.0909 |
| Field tilt | `field_tilt.stats-perform-2016` | 本队在 x >= 80 起脚的传球（成功与否都算；不含传中、界外球、门将手抛）/ 双方之和 | 0.6186 / 0.3814 |
| 推进传球 | `progressive_passes.statsbomb-blog-2023` | 成功的非定位球传球，使球到球门中心 (120, 40) 的距离缩短至少 25% | 46 / 23 |
| 推进带球 | `progressive_carries.statsbomb-blog-2023` | 带球使球到球门中心的距离缩短至少 25% | 25 / 26 |
| xT added | `xt.singh-open-12x8` | Karun Singh 公开的 12 x 8 xT 表：成功的运动战传球（不含任意球、角球、界外球、球门球）与所有带球，终点格值 - 起点格值 | 1.8631 / 1.1759 |

球员级测试值（xG assisted）：Mac Allister 0.3034、Di María 0.2781、Messi 0.2742、Konaté 0.2775、Thuram 0.1017。

xT 表在运行时从 `https://karun.in/blog/data/open_xt_12x8_v1.json` 下载并缓存（不随仓库分发，原作者未声明许可）；
下载失败时 xT 列留空，其余指标照常。

## 2. 描述性指标（没有指标卡，只在本工具内部比较）

球队（`sb_match.py` 的 summary.json `team_metrics` 与报告第 1、2 节；`sb_team.py` 把这些字段按场次合计）：

| 字段 | 定义 |
|---|---|
| `goals` | 比赛中（含加时、含点球）的进球 + 对方乌龙；不含点球大战 |
| `shots` / `np_shots` / `shots_on_target` | 射门 / 非点球射门 / 射正（Goal、Saved、Saved To Post） |
| `xg_per_np_shot` | npxG / 非点球射门数，衡量机会质量 |
| `assisted_shots` | 由关键传球直接导致的射门数 |
| `pass_share` | 本队传球数 / 双方传球数（控球率的近似；不是按时间算的控球率） |
| `ppda_opp_passes` / `ppda_def_actions` | PPDA 的分子与分母，样本小时一起报告 |
| `final_third_passes` | field tilt 的分子 |
| `deep_progressions` | 从 x < 80 出发、终点 x >= 80 的成功传球与带球（进入前场三区） |
| `box_entries` | 从禁区外进入禁区（x >= 102 且 18 <= y <= 62）的成功非定位球传球与带球 |
| `pressures` / `pressures_att_third` | Pressure 事件总数 / 其中 x >= 80 的部分 |
| `pressure_height` | 压迫事件的平均 x（0 = 本方球门线，120 = 对方球门线），越大 = 压得越高 |
| `def_action_height` | PPDA 类防守动作（全场）的平均 x，防线/拦截高度的近似 |

球员（`players.csv`、`sb_player.py`）：

| 字段 | 定义 |
|---|---|
| `minutes` | 名义时钟上的出场分钟（补时折算进 45/90/105/120，FBref 口径）；替补至少记 1 分钟；红牌即止 |
| `goals` / `np_goals` / `penalty_goals` | 进球 / 非点球进球 / 点球进球 |
| `key_passes` / `assists` | 带 `shot_assist` 或 `goal_assist` 的传球 / 带 `goal_assist` 的传球 |
| `box_receptions` | 在禁区内成功接球（Ball Receipt 无 outcome） |
| `dribbles` / `dribbles_completed` | 过人尝试 / 成功（Complete） |
| `tackles` / `tackles_won` | 抢断类 Duel / 结果为 Won、Success In Play、Success Out |
| `interceptions` | Interception 事件 + 类型为 Interception 的传球 |
| `ball_recoveries` | 非失败的 Ball Recovery |
| `blocks` / `clearances` / `fouls_committed` / `fouls_won` / `dispossessed` / `miscontrols` | 对应事件计数 |
| `*_p90` | 计数 x 90 / 出场分钟 |

## 3. 方法细节

- **传球网络**：每队从开场到本队第一次换人为止的成功传球；节点位置 = 该球员成功传球起点的平均位置，节点大小 = 传球数，
  连线 = 两人之间双向成功传球数，低于 `--min-pair-passes`（默认 3）的不画。报告列出传球最多的 5 对组合。
- **xT 走势**：每 5 分钟（名义时钟，补时并入该半场最后一个窗口）各队 xT added 之和。
- **xG 走势**：按实际经过时间（保留补时）累计 xG，进球处标注。
- **时间标注**：StatsBomb 的 minute 22（22:xx）显示为 23'，补时显示为 90+5'（转播口径）。
- **球队多场汇总**（`sb_team.py`）：计数类按场次求和，每 90 分钟 = 总数 x 90 / 名义比赛时长之和（常规 90、含加时 120）；
  比率类（PPDA、field tilt、传球占比、传球成功率、每脚射门 xG）用各场分子、分母分别求和后再相除，不是逐场比率的平均；
  压迫高度、防守动作高度按事件数加权。“对手对本队的 PPDA”= 对手的 PPDA，反映本队出球时受压程度。
- **比分状态**（`sb_team.py` 第 5 节）：按事件发生前的比分把事件分到平局、领先、落后三种状态（进球那脚射门算进球前的状态；
  乌龙球按 `Own Goal For` 计给得分方）；各状态的分钟为实际经过时间（含补时），npxG/90 按该状态的分钟折算。
  三种状态的传球、PPDA 分子分母、npxG 相加等于全场数值。
- **球队排名**（`sb_team.py --benchmark`）：同一赛事赛季、至少 3 场的球队；排名 1 = 该项最高，PPDA、对手 npxG、对手进入禁区
  这类越低越好的指标排名 1 = 最低；百分位按同样方向换算（越高越“多/强”），用中位秩公式。只有单队数据的赛季
  （例如只有巴萨或迈阿密国际的比赛）不做排名。
- **球员百分位**（`sb_player.py --benchmark`）：同一赛事赛季、同一位置组（GK、CB、FB、MF、AM/W、FW，按出场分钟最多的
  位置归组）、出场分钟 >= 门槛（默认：所选范围的比赛数 <= 80 时 270 分钟，否则 900 分钟）的球员池里，用中位秩百分位
  （低于的个数 + 一半相等的个数）/ 总数。门将不做雷达图。

## 4. Understat / ESPN（`fd_match.py`，当季五大联赛）

| 指标 | 变体 / 来源 | 说明 |
|---|---|---|
| xG / npxG | `xg.understat` / `npxg.understat` | Understat 模型；npxG 去掉 situation = Penalty 的射门。与 StatsBomb xG 模型不同，不可混比 |
| xA | `xg_assisted.understat` | Understat 的 xA 实为“被助攻射门的 xG”，不是 Opta 的传球级 xA |
| xGChain / xGBuildup | Understat | 球员参与的进攻回合的 xG 之和；Buildup 不含最后两脚（射门与关键传球） |
| 其余统计 | ESPN | 控球率、射门、传球等由 ESPN 定义，与 StatsBomb 事件计数口径不同；传球成功率按 accurate / total 自算 |

Understat 坐标：X 从 0（本方球门线）到 1（对方球门线）；Y 与 Opta 同向，0 = 进攻方的**右**侧边线，1 = 左侧边线。
StatsBomb 的 y = 0 是进攻方左侧，所以换算为 x = X * 120、y = (1 - Y) * 80（`fd_match.understat_xy`）。
方向是实测确定的（2026/27 赛季前 6 轮的非点球射门：右边锋 Saka、Yamal 的平均 Y 约 0.42-0.44，左边锋 Vinícius、
Doku 约 0.62-0.67，主客场一致）；football-docs 的 Understat 文档写作“0 = 电视画面上方边线”，与实测相反，以实测为准。

## 5. 解读规则（下结论前逐条检查）

1. **单场 = 小样本**：一场比赛的 PPDA、field tilt、xG 差只描述这场比赛，不能推出“这支球队的风格”；要谈风格用多场。
2. **比分状态**：领先方常主动退守，落后方传球与控球会被动升高。解读控球、PPDA、field tilt 时先看比分变化与红牌。
3. **控球 ≠ 更好**：控球/传球占比反映风格和比分状态；“谁踢得更好”用机会质量（npxG、xG/射门、禁区进入）检验。
4. **PPDA 有两面**：PPDA 低说明对方在本方 60% 区域传球少、我方前场防守动作多，但也要看 `pressure_height`、
   `pressures_att_third`；两类指标结论不同时如实写出分歧。
5. **球员比较用每 90 分钟 + 分钟门槛**，并报告样本量（场次、分钟）；百分位只在同位置组、同赛事赛季内有意义。
6. **终结能力不看一季**：进球 - npxG 的差值在一个赛季（更别说一届杯赛）里噪声很大，只能说“本样本中高于/低于预期”。
7. **防守计数要看对手控球**：抢断、拦截多可能只是对手控球多；没有控球调整时不要据此评价防守好坏。
8. **跨来源不混比**：StatsBomb、Understat、Opta、FBref 的 xG 与计数口径不同；跨来源对比前用 football-docs
   的 `get_metric` / `list_metrics` 确认变体。

更多误用模式见 `third_party/nutmeg/docs/metric-misuse.md`。
