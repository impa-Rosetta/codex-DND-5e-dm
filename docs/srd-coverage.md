# SRD 5.1 覆盖矩阵

规则正文唯一来源：[SRD 5.1 CC BY 4.0 原文](https://media.dndbeyond.com/compendium-images/srd/5.1/SRD_CC_v5.1.pdf)。本表按该文件的章节定位，不以 D&D Beyond 的当前 SRD 5.2 页面代替 5.1。稳定 ID 见 [`rules-index.json`](../skills/codex-5e-dm/data/rules-index.json)。

状态词：`已索引`表示只有来源和稳定 ID，**不表示规则已实现**；`部分实现`仅代表表中明确说明的路径经过计算和测试，不代表整项 SRD 已覆盖；`未结构化`表示尚无可计算数据。M2 的“是”包括全部 SRD 一级建卡选项和纵向游玩必需规则，不意味着 M2 已完成。当前实况另见 [`m2-status.md`](m2-status.md)。

| 规则 ID / 范围 | SRD 5.1 章节 | M2 必需 | M1 来源 | 结构化/实现 | 测试 | 后续完成目标 |
| --- | --- | --- | --- | --- | --- | --- |
| `race.human` | Races → Human | 是 | 已索引 | 普通人类属性加值、速度；部分实现 | 建卡测试通过 | M2：其余特性与组合验证 |
| `races.other` | Races | 是，全部一级选项 | 已索引 | 未结构化 | 未测试 | M2：逐项覆盖 SRD 种族与亚种 |
| `class.fighter` | Classes → Fighter | 是，仅 1 级 | 已索引 | HP、熟练、第二春、选风格；部分实现 | 建卡测试通过 | M2：全部风格的运行时；M3：2–20 级 |
| `classes.other` | Classes | 是，全部一级选项 | 已索引 | 未结构化 | 未测试 | M2：一级职业；M3：更高等级 |
| `background.acolyte` | Backgrounds → Acolyte | 是 | 已索引 | 洞悉、宗教、语言；部分实现 | 建卡测试通过 | M2：装备与背景特性 |
| `background.customization` | Backgrounds → Customizing a Background | 是，SRD 允许的自定义 | 已索引 | 未结构化 | 未测试 | SRD 仅收录侍僧；不把未收录背景当作内置选项 |
| `character.ability_scores` | Using Ability Scores | 是 | 已索引 | 标准数组、购点、可审计 4d6；部分实现 | 属性／事件测试通过 | M2：其余组合验证 |
| `character.proficiency` | Character Advancement / Using Ability Scores | 是 | 已索引 | 一级 +2 与样例技能／豁免；部分实现 | 建卡测试通过 | M2：全部职业 |
| `character.advancement` | Beyond 1st Level / Classes | 否 | 已索引 | 未结构化 | 未测试 | M3：升级、熟练加值与职业成长 |
| `character.multiclassing` | Multiclassing | 否 | 已索引 | 未结构化 | 未测试 | M3 |
| `check.ability` | Using Ability Scores | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `check.saving_throw` | Using Ability Scores | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `adventuring.exploration` | Adventuring | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `adventuring.rest` | Adventuring → Resting | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `combat.initiative_turn` | Combat → The Order of Combat | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `combat.attack_damage` | Combat → Making an Attack / Damage and Healing | 是 | 已索引 | 单次攻击、自然 1／20、临时 HP；部分实现 | 战斗测试通过 | M2：攻击距离、状态、完整行动经济 |
| `combat.movement_position` | Combat → Movement and Position | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `combat.conditions` | Conditions | 是，样例所需状态 | 已索引 | 未结构化 | 未测试 | M3：全部 SRD 状态 |
| `combat.death_saves` | Combat → Dropping to 0 Hit Points | 是 | 已索引 | 未结构化 | 未测试 | M2 基础，M3 完整 |
| `equipment.weapons_armor` | Equipment | 是，全部一级起始选项 | 已索引 | 未结构化 | 未测试 | M3：其余 SRD 常用装备 |
| `magic.spellcasting` | Spellcasting | 是，一级施法 | 已索引 | 未结构化 | 未测试 | M2：一级施法；M3：更高等级与完整规则 |
| `magic.spells` | Spells | 是，一级可选法术 | 已索引 | 未结构化 | 未测试 | M2：一级合法选项；M3：其余法术 |
| `monsters.goblin` | Monsters → Goblin | 是 | 已索引 | 未结构化 | 未测试 | M2 |
| `monsters.other` | Monsters | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 怪物 |
| `items.magic` | Magic Items | 否 | 已索引 | 未结构化 | 未测试 | M3：逐项覆盖 SRD 魔法物品 |
| `dm.environment` | Traps / Diseases / Poisons / Objects | 否 | 已索引 | 未结构化 | 未测试 | M3：冒险环境与物件规则 |

## M2 样例边界

完整纵向回归样例固定为 1 级人类战士、侍僧背景、SRD 基础装备、哥布林及原创开局；玩家建卡不限于该样例。M2 必须覆盖 SRD 全部一级建卡选项，以及所有可建角色的一级核心规则、探索/社交检定、战斗、休息、保存与恢复。SRD 未收录的官方内容和 M2 未完成的内容要分别说明，不临时捏造数值；在可建角色无法实际游玩前，不宣称 M2 可玩。

## M3/M4 完成方式

M2 建卡前须把种族、职业、一级装备与法术的聚合项拆为逐条内容索引和测试；M3 再完成职业 2–20 级、其余法术与怪物。M4 通过端到端游玩验收后才能宣称成品。每条规则的“结构化/实现”和“测试”必须依据实际代码与测试结果更新，不因写了来源索引而自动改成完成。
