# SRD 5.1 一级选项对账清单（部分冻结）

版本：2026-10-14。来源是 [2014 SRD 5.1 原文](https://media.dndbeyond.com/compendium-images/srd/5.1/SRD_CC_v5.1.pdf)。本页是计划任务 0 的进度，不代表一级建卡完成。机器清单见 [`level1-inventory.json`](../skills/codex-5e-dm/data/level1-inventory.json)，逐项规则来源见 [`rules-index.json`](../skills/codex-5e-dm/data/rules-index.json)，测试见 `tests/test_level1_inventory.py`。

| 范围 | 已逐项冻结的 ID | 当前机械实现 |
| --- | --- | --- |
| 种族／亚种（14） | `dwarf_hill`, `dwarf_mountain`, `elf_high`, `elf_wood`, `elf_drow`, `halfling_lightfoot`, `halfling_stout`, `human`, `dragonborn`, `gnome_forest`, `gnome_rock`, `half_elf`, `half_orc`, `tiefling` | 仅普通人类的窄样例可建 |
  | 职业（12） | `barbarian`, `bard`, `cleric`, `druid`, `fighter`, `monk`, `paladin`, `ranger`, `rogue`, `sorcerer`, `warlock`, `wizard` | 战士、野蛮人、游荡者、武僧、圣武士、游侠、魔契师、术士的窄样例可建 |
| 一级即需选择的 SRD 子职业（3） | `class.cleric.life_domain`, `class.sorcerer.draconic_bloodline`, `class.warlock.fiend` | 尚不可建；这不是非 SRD 官方子职业的许可 |
| 背景（2 个入口） | `acolyte`, `custom_background` | 仅固定侍僧路径；自定义背景待实现 |
| 属性方式 | `standard_array`, `point_buy`, `rolled_4d6_drop_lowest` | 三种方式已有窄样例计算及审计 |
| 龙裔祖先（10） | `black`, `blue`, `brass`, `bronze`, `copper`, `gold`, `green`, `red`, `silver`, `white` | 尚不可建；这里只冻结龙种选择，不代表吐息和抗性已实现 |
| 战士战斗风格（6） | `archery`, `defense`, `dueling`, `great_weapon_fighting`, `protection`, `two_weapon_fighting` | 固定装备样例支持防御的 AC +1、决斗的单手长剑伤害 +2、箭术的长弓命中 +2；余下三种仅索引 |
| 四个非施法职业的起始装备与技能／工具选择 | 野蛮人、战士、武僧、游荡者：见 [`level1-martial-creation-choices.json`](../skills/codex-5e-dm/data/level1-martial-creation-choices.json) | 仅机器清单；合法替代项、数量及通用武器类别已有独立 ID，尚不能据此建卡 |
| 六种一级施法职业的戏法／一级法术列表 | 见 [`level1-spell-lists.json`](../skills/codex-5e-dm/data/level1-spell-lists.json) | 只建立了 SRD 名称与职业归属；法术效果、选择数量、法术位尚未实现 |

尚未冻结为逐项清单：余下八职业的一级技能／工具及起始装备分支、各职业一级特性选择（包括游荡者专精）、游侠宿敌／地形、术士龙脉祖先、种族给予的法术选择及逐个法术的机械效果。六个职业的法术列表虽已转录，尚未按法术项建立效果或允许建卡。这些都属于 M2 验收，不得用 `races.other`、`classes.other`、`magic.spells` 等聚合 ID 代替，也不得因为本页出现了名称便标记为 `buildable`。

下一批对账按官方章节逐项列出以上分支，给每个合法选项稳定 ID、来源、数据项和针对性测试；缺少的 SRD 内容保持 `indexed_only` 或 `not_frozen`。非 SRD 官方书籍、种族、职业和背景不是内置选项。
