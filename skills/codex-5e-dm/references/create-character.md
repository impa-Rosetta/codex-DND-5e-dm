# 一级建卡（当前验证范围）

先运行 `python scripts/character.py options`。当前只有普通人类战士或野蛮人＋侍僧的固定起始装备路径可提交；其他 ID 是待实现索引，不能建卡。玩家自由填写姓名和个人往事；故事文本不产生额外奖励。

野蛮人从职业技能中选择两项；固定起始包为巨斧、两把手斧、探索者套组和四支标枪，提交 `class: barbarian`、`armor: none`、`shield: false`、`weapon: greataxe`，不要提交 `fighting_style`。一级野蛮人拥有无甲防御和两次狂暴；其他装备分支暂不支持。

向玩家询问六项基础属性的分配方式：标准数组 `15,14,13,12,10,8`，玩家主动选择 27 点购点，或六组 `4d6` 取最高三颗。掷骰方式先执行 `python scripts/state.py roll-abilities <战役目录> --operation-id <UUID>`；事件内有六组原始点数、舍弃索引、保留点数和总数。同一次掷骰重试必须复用操作 ID，不重掷。玩家按 0–5 索引把六组合计一一分配给属性，输入 `ability_method: rolled`、`roll_event_id` 和 `rolled_assignment`，不可自报 `base_abilities`。询问两个战士技能（不可与侍僧的洞悉重复）、侍僧的两门语言。当前支持以下固定合法起始包，必须由玩家选择，不得擅自替换：①“防御”或“决斗”风格、链甲、长剑（`weapon: longsword`）、可选择是否装备盾牌、两把手斧、探索者套组；②“箭术”风格、皮甲（`armor: leather_armor`）、长弓（`weapon: longbow`）、20 支箭、盾牌放在行囊中（`shield: false`）、长剑、两把手斧、探索者套组。“决斗”的 +2 只计入单手长剑伤害；“箭术”的 +2 只计入长弓命中。若玩家要其他合法选项，说明尚未支持，不要代选。

把选择写成 JSON 文件。标准数组或购点可执行 `python scripts/character.py build --input <文件>` 预览；掷骰方式须执行 `python scripts/state.py preview-character <战役目录> --input <文件>`，以战役事件核验骰值。预览不写正式角色。展示生命值、护甲等级、属性、熟练和资源，询问玩家是否确认。得到明确确认后生成一次 UUID 操作 ID，执行 `python scripts/state.py confirm-character <战役目录> --operation-id <UUID> --input <同一文件>`。网络或进程重试复用原操作 ID，不重新建卡。已确认角色更改机械项须走未来重建流程，禁止手改 `state.json`。

脚本错误会输出稳定代码：`missing_choice`、`invalid_choice`、`unsupported_option`、`invalid_ability_method`、`ruleset_mismatch`。把错误字段反馈给玩家并继续询问；不要自行修正玩家的选择。
