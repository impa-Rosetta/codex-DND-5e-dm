# SRD 5.1 覆盖矩阵

规则正文唯一来源：[SRD 5.1 CC BY 4.0 原文](https://media.dndbeyond.com/compendium-images/srd/5.1/SRD_CC_v5.1.pdf)。本表按该文件的章节定位，不以 D&D Beyond 的当前 SRD 5.2 页面代替 5.1。稳定 ID 见 [`rules-index.json`](../skills/codex-5e-dm/data/rules-index.json)。

状态词：`已索引`表示只有来源和稳定 ID，**不表示规则已实现**；`未结构化`表示尚无可计算数据；`未测试`表示没有通过机械测试。M2 的“是”只标记纵向样例必需内容，不意味着 M2 已完成。M3/M4 列记录完整成品前尚需的工作。

| 规则 ID / 范围 | SRD 5.1 章节 | M2 必需 | M1 来源 | 结构化/实现 | 测试 | 后续完成目标 |
| --- | --- | --- | --- | --- | --- | --- |
| `race.human` | Races → Human | 是 | 已索引 | 未结构化 | 未测试 | M2 |
| `races.other` | Races | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 种族与亚种 |
| `class.fighter` | Classes → Fighter | 是，仅 1 级 | 已索引 | 未结构化 | 未测试 | M3：扩展 1–20 级与子职业 |
| `classes.other` | Classes | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 职业及等级 |
| `background.acolyte` | Backgrounds → Acolyte | 是 | 已索引 | 未结构化 | 未测试 | M2 |
| `backgrounds.other` | Backgrounds | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 背景 |
| `character.ability_scores` | Using Ability Scores | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `character.proficiency` | Character Advancement / Using Ability Scores | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `character.advancement` | Beyond 1st Level / Classes | 否 | 已索引 | 未结构化 | 未测试 | M3：升级、熟练加值与职业成长 |
| `character.multiclassing` | Multiclassing | 否 | 已索引 | 未结构化 | 未测试 | M3 |
| `check.ability` | Using Ability Scores | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `check.saving_throw` | Using Ability Scores | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `adventuring.exploration` | Adventuring | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `adventuring.rest` | Adventuring → Resting | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `combat.initiative_turn` | Combat → The Order of Combat | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `combat.attack_damage` | Combat → Making an Attack / Damage and Healing | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `combat.movement_position` | Combat → Movement and Position | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `combat.conditions` | Conditions | 是，样例所需状态 | 已索引 | 未结构化 | 未测试 | M3：全部 SRD 状态 |
| `combat.death_saves` | Combat → Dropping to 0 Hit Points | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `equipment.weapons_armor` | Equipment | 是，样例装备 | 已索引 | 未结构化 | 未测试 | M3：全部 SRD 常用装备 |
| `magic.spellcasting` | Spellcasting | 否 | 已索引 | 未结构化 | 未测试 | M3：施法、集中、法术位 |
| `magic.spells` | Spells | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 法术 |
| `monsters.goblin` | Monsters → Goblin | 是 | 已索引 | 未结构化 | 未测试 | M2 |
| `monsters.other` | Monsters | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 怪物 |
| `items.magic` | Magic Items | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 魔法物品 |
| `dm.environment` | Traps / Diseases / Poisons / Objects | 否 | 已索引 | 未结构化 | 未测试 | M3：冒险环境与物件规则 |

## M2 样例边界

完整纵向样例固定为 1 级人类战士、侍僧背景、SRD 基础装备、哥布林及原创开局。M2 必须覆盖建卡、一次探索/社交检定、一次基础战斗、短休或长休、保存与恢复。M2 未涉及的职业、种族、法术和怪物应明确返回“当前规则数据不含此项”，不能临时捏造数值。

## M3/M4 完成方式

M3 需把本表中的聚合项拆为逐条内容索引和测试，尤其是职业 1–20 级、法术与怪物；M4 通过端到端游玩验收后才能宣称成品。每条规则的“结构化/实现”和“测试”必须依据实际代码与测试结果更新，不因写了来源索引而自动改成完成。
