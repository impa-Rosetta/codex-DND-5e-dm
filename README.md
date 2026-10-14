# Codex 5e DM

一款面向 Codex 的中文单人 D&D 第五版冒险 Skill。玩家在 Codex 聊天中声明行动，由 Codex 担任地下城主；本地脚本处理掷骰、数值与存档，侧边栏网页只读展示角色、探索地图和冒险记录。

项目目前处于**M2 开发中，尚未达到完整可玩验收**。首版以 2014 年版 SRD 5.1 为规则基础，先完成单人游玩，再考虑由玩家创作、AI 审核的可选扩展包。项目不会复制参考项目的代码或界面。

M1 已建立规则来源与覆盖范围、事件/存档契约。M2 当前已有独立掷骰器、有限建卡计算器、并发安全的事件存档与恢复、原创旧磨坊固定场景（检定、地图揭示、哥布林遭遇、双方移动与借机攻击、弓箭射击、第二春、野蛮人狂暴、游荡者优势偷袭、休息与部分死亡规则），以及只读本地面板。**完整 SRD 5.1 一级建卡和所有可建角色的一级游玩能力尚未实现**：目前仅有普通人类战士／野蛮人／游荡者＋侍僧的固定起始装备路径可构建；其他种族／职业仅在目录中标为 `indexed_only`。施法、完整装备选择、其余动作／反应、急救／治疗和端到端新会话验收仍待完成。项目的完整边界见 [M2 实际覆盖](docs/m2-status.md)。

## 试用掷骰器

需要 Python 3.10 或更新版本。在项目根目录运行：

```powershell
python skills/codex-5e-dm/scripts/dice.py roll d20+5 --purpose attack
python skills/codex-5e-dm/scripts/dice.py roll 1d20 --purpose check --mode advantage
python -m unittest discover -s tests -v
```

命令输出一行 JSON，包含原始点数、优势/劣势保留项、修正值与合计。掷骰器**不判定命中、成功或重击，也不写入战役存档**；这些需要后续规则与事件服务处理。掷骰式目前支持 `d20`、`NdS`，以及一个 `+N` 或 `-N` 修正项；优势/劣势仅用于单颗 d20。测试可注入固定骰值，正式运行使用系统随机源。

## 当前可运行的开发版接口

```powershell
python skills/codex-5e-dm/scripts/character.py options
python skills/codex-5e-dm/scripts/state.py create <独立战役目录> --name "旧磨坊的回声"
python skills/codex-5e-dm/scripts/state.py load <独立战役目录>
python skills/codex-5e-dm/scripts/session.py <独立战役目录> --help
python skills/codex-5e-dm/display/server.py <独立战役目录> --port 8765
```

最后一条命令输出本地面板地址 `http://127.0.0.1:8765/`，仅监听本机。正式建卡需要按 [建卡工作流](skills/codex-5e-dm/references/create-character.md) 提交 JSON；预览不会写入角色，确认后使用固定操作 ID 提交。当前仓库内的 `skills/codex-5e-dm/SKILL.md` 是 Codex Skill 源文件；仅克隆仓库并不会自动安装到用户的 Skill 发现目录。

## 文档

- [设计规格](docs/design.md)
- [M1–M2 实施计划](docs/m1-m2-plan.md)
- [SRD 5.1 覆盖矩阵](docs/srd-coverage.md)
- [一级选项对账清单（部分冻结）](docs/level1-options-inventory.md)
- [战役数据与事件契约](docs/data-contract.md)
- [规则与架构决定](docs/decisions.md)
- [M2 实际覆盖与缺口](docs/m2-status.md)
- [SRD 5.1 来源与署名](LICENSES/SRD-5.1-CC-BY-4.0.md)

## 路线图

1. M1：SRD 5.1 规则来源、覆盖矩阵与事件/存档契约。
2. M2：掷骰、角色与存档脚本；可玩的单人冒险纵向版本及 Codex 侧边栏面板。
3. M3：补齐 SRD 5.1 的 1–20 级核心覆盖。
4. M4：测试、打磨与正式发布。
5. 后续：可选的玩家自定义扩展包。

## 规则与版权

本项目是非官方作品。使用 SRD 5.1 内容时将遵守其 [CC BY 4.0 许可与署名要求](https://media.dndbeyond.com/compendium-images/srd/5.1/SRD_CC_v5.1.pdf)。非 SRD 的官方书籍、设定及模组不随项目分发。源码许可会在正式编码前确定。
