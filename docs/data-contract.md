# 战役数据与事件契约（M1，版本 1）

此文档固定 M2 脚本、Codex 聊天和只读网页面板之间的最小接口；存档服务已有开发版实现，未覆盖本文全部目标。玩家为每个战役指定一个与 Skill 安装目录分离的数据目录。所有 JSON 文件使用 UTF-8，时间使用带 `Z` 的 UTC ISO 8601 字符串，ID 使用 UUID 字符串。

## 文件及权威边界

| 文件 | 作用 | 权威性 |
| --- | --- | --- |
| `manifest.json` | 战役身份、名称、规则版本、创建时间与格式版本 | 身份与规则版本权威来源 |
| `state.json` | 最近一次完整应用事件后的机械状态快照 | 校验并重放日志后才是当前数值权威 |
| `world.md` | 地点、NPC、已确立事实及 DM 私有资料的人类可读视图 | 叙事资料；不得作为 HP、资源或骰值的唯一来源 |
| `events.jsonl` | 按序追加的完整操作事件，一行一个 JSON 对象 | 审计、幂等重试及快照恢复来源 |
| `state.json.bak` | 上一次已校验快照的可恢复副本 | 仅在主快照损坏时供恢复，不自动覆盖原件 |
| `.campaign.lock` | 本机跨进程互斥锁文件 | 不含战役数值；序列化读取恢复与提交 |

### `manifest.json`

必填字段：`schema_version`（整数 `1`）、`campaign_id`、`name`、`ruleset`（固定为 `srd-5.1-2014`）、`created_at`。`campaign_id` 一经创建不得变化。读取时如 `ruleset` 或格式版本不受支持，应停止加载并说明原因，不把 5.2 规则写进旧战役。

### `state.json`

必填字段：`schema_version`、`campaign_id`、`revision`（已应用的最大连续事件序号，初始为 `0`）、`last_applied_event_id`（初始 `null`）、`character`、`scene`、`combat`、`world_time`。新建战役另存 `last_long_rest_start`（上一场长休开始时的战役分钟数，初始 `null`）；旧版同格式存档可能缺少此字段，首次长休按 `null` 处理并写入。`character.id` 是玩家角色稳定 ID；战斗中每个单位有独立 `combatant_id`，即使怪物同名也不共用。`scene` 只含当前地点、已发现地点 ID 和已发现连接；未揭示地图只存在于 DM 私有资料，不进入公开快照。`combat` 在非战斗时为 `null`；战斗时至少保存轮次、当前行动者、各战斗者位置、生命值、状态及已用动作资源。

`state.json` 还应保留角色构建选项、属性、熟练、装备、生命值、临时生命值、职业资源、法术位、经验值及规则版本。M2 可以只填 1 级战士实际具有的资源，但字段语义不得与未来职业冲突：缺少某类资源表示该角色没有该资源，不能解释为“尚未加载”。

### `events.jsonl`

每个事件必填：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 事件格式版本，当前为 `1` |
| `campaign_id` | 必须与 manifest 一致 |
| `seq` | 从 `1` 开始连续递增的整数；比时间戳更权威的顺序 |
| `event_id` | 此次已提交事件的 UUID，永久不变 |
| `operation_id` | 调用方为一次意图提供的 UUID；重试必须复用，重复提交返回原结果 |
| `timestamp` | UTC 时间，供展示和审计；不用于排序 |
| `type` | 事件种类，例如 `combat.attack_resolved` |
| `visibility` | `public` 或 `dm_private` |
| `actor_id` | 操作者 ID；系统事件可为 `null` |
| `causation_event_id` | 引发本事件的上一事件 ID；无则为 `null` |
| `rules` | 本次机械裁定使用的 `rules-index.json` 稳定 ID 数组 |
| `payload` | 类型专属数据；必须足以确定性重放状态变化 |

基础事件类型包含 `character.created`、`character.stable_recovered`、`player.declared`、`scene.narrated`、`check.resolved`、`combat.attack_resolved`、`combat.action_taken`、`combat.move_resolved`、`combat.death_save_resolved`、`equipment.ammunition_recovered`、`resource.changed`、`position.changed`、`location.discovered`、`turn.advanced`。一次攻击的骰值、伤害、箭矢消耗、生命值变更和公开反馈装在**同一个** `combat.attack_resolved` 事件的 `payload` 中，不能分成多个各自生效的事件。固定遭遇的移动事件同时保存逐格路径、最终位置、移动消耗及可能的借机攻击骰值／伤害／反应消耗，不能先写位移再单独补写借机攻击。死亡豁免的骰值与成功／失败／稳定／死亡状态装在同一个 `combat.death_save_resolved` 事件中；稳定后的自发恢复以含原始 `1d4` 骰值与时间推进的单条事件记录。战后搜回箭矢以 `equipment.ammunition_recovered` 记录数量与一分钟时间推进。独立掷骰可使用 `dice.rolled`，但不得把它当作攻击结算的第二次随机数入口。单一操作的 `operation_id` 对应至多一个已提交结算事件；玩家声明可以是另一个事件，并通过 `causation_event_id` 关联。

事件 `payload` 可以含 `dice`（用途、骰式、原始点数、优势/劣势保留项、加值、合计）、`effects`（顺序排列的状态变化）和 `public_view`（给聊天和面板的可见文本及结构化摘要）。`dm_private` 事件不得携带可公开投影；`public` 事件也不得嵌入尚未揭示的地图或 NPC 秘密。网页只接收 `public` 事件和过滤后的公开快照，不直接读取 `world.md`、原始事件日志或内部状态文件。

## 写入、重放与失败处理

1. 先查日志中的 `operation_id`：如已提交，返回原 `event_id` 与结果，不重掷、不再次应用。否则校验请求、规则数据、状态版本及资源是否足够。
2. 生成新的 `event_id` 与下一个 `seq`，一次性构造完整事件；掷骰原始点数和机械变更写在该事件中。事件末尾包含换行符。
3. 将完整事件追加到 `events.jsonl` 并 `flush`、`fsync`。追加失败时不更新状态、不回复成功。
4. 用纯确定性 reducer 将事件应用到内存状态。先把旧的有效快照保存为 `state.json.bak`，再把新状态写到同目录临时文件并 `fsync`，最后用原子替换更新 `state.json`。新快照的 `revision` 和 `last_applied_event_id` 指向刚应用的事件。
5. 状态提交完成后，聊天和面板从同一个事件生成反馈。`world.md` 的更新应可由已提交事件重建；其写入失败不能伪装成数值操作失败后重掷。

加载时核对战役 ID、格式版本、连续 `seq`、唯一 `event_id`/`operation_id` 和快照末尾事件对应关系。若快照 `revision` 落后，只按序重放 `seq > revision` 的完整事件；绝不重放已应用事件。若主快照 JSON 不可读取，只有在备份通过同样的身份／序号／末尾事件校验且日志完整可重放时，才从备份重建主快照；恢复期间不以损坏主快照覆盖备份。若快照领先于日志、日志中间记录损坏、末尾仅有半行、备份无效或文件互相矛盾，应停止自动加载并保留原文件，报告损坏位置供人工恢复；不得静默截断日志。只有明确的迁移程序才能变更格式版本。

## 攻击样例与幂等验收

以下是契约示例，不代表 M1 已实现战斗：1 级战士用长剑攻击 AC 15、剩余 HP 7 的哥布林。d20 原始点数 `14`，攻击加值 `5`，合计 `19`；伤害 d8 原始点数 `6`，加值 `3`，合计 `9`，哥布林 HP 从 `7` 到 `0`。此次结算事件的 `event_id` 在下例中固定为 `11111111-1111-4111-8111-111111111111`，`seq` 为 `42`，`operation_id` 为 `22222222-2222-4222-8222-222222222222`。

```json
{
  "schema_version": 1,
  "campaign_id": "33333333-3333-4333-8333-333333333333",
  "seq": 42,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "operation_id": "22222222-2222-4222-8222-222222222222",
  "timestamp": "2026-10-13T10:00:00Z",
  "type": "combat.attack_resolved",
  "visibility": "public",
  "actor_id": "44444444-4444-4444-8444-444444444444",
  "causation_event_id": null,
  "rules": ["combat.attack_damage", "equipment.weapons_armor"],
  "payload": {
    "target_combatant_id": "55555555-5555-4555-8555-555555555555",
    "target_ac": 15,
    "dice": [
      {"purpose": "attack", "expression": "1d20+5", "raw": [14], "kept": [14], "modifier": 5, "total": 19},
      {"purpose": "damage", "expression": "1d8+3", "raw": [6], "kept": [6], "modifier": 3, "total": 9}
    ],
    "effects": [{"kind": "hp_set", "combatant_id": "55555555-5555-4555-8555-555555555555", "before": 7, "after": 0}],
    "public_view": {"summary": "长剑命中哥布林，造成 9 点伤害。", "event_id": "11111111-1111-4111-8111-111111111111"}
  }
}
```

若日志已包含 `seq=42`，但快照仍为 `revision=41`，加载后仅应用该事件一次并保存 `revision=42`。若客户端因超时重试同一 `operation_id`，直接返回 `event_id=1111…` 的已提交结果；HP 仍为 `0`，不会再减 `9`。聊天反馈、面板骰子记录和 HP 更新必须显示同一个 `event_id`，且面板断线后从公开快照恢复一致数值。
