# Codex 5e DM

一款面向 Codex 的中文单人 D&D 第五版冒险 Skill。玩家在 Codex 聊天中声明行动，由 Codex 担任地下城主；本地脚本处理掷骰、数值与存档，侧边栏网页只读展示角色、探索地图和冒险记录。

项目目前处于**M2 开发初期，尚不可游玩**。首版以 2014 年版 SRD 5.1 为规则基础，先完成单人游玩，再考虑由玩家创作、AI 审核的可选扩展包。项目不会复制参考项目的代码或界面。

M1 已建立规则来源与覆盖范围、事件/存档契约。M2 已实现独立掷骰器；`rules-index.json` 目前仍只有来源索引，角色、战斗、存档和 Skill 游玩流程尚未实现。

## 试用掷骰器

需要 Python 3.10 或更新版本。在项目根目录运行：

```powershell
python skills/codex-5e-dm/scripts/dice.py roll d20+5 --purpose attack
python skills/codex-5e-dm/scripts/dice.py roll 1d20 --purpose check --mode advantage
python -m unittest discover -s tests -v
```

命令输出一行 JSON，包含原始点数、优势/劣势保留项、修正值与合计。掷骰器**不判定命中、成功或重击，也不写入战役存档**；这些需要后续规则与事件服务处理。掷骰式目前支持 `d20`、`NdS`，以及一个 `+N` 或 `-N` 修正项；优势/劣势仅用于单颗 d20。测试可注入固定骰值，正式运行使用系统随机源。

## 文档

- [设计规格](docs/design.md)
- [M1–M2 实施计划](docs/m1-m2-plan.md)
- [SRD 5.1 覆盖矩阵](docs/srd-coverage.md)
- [战役数据与事件契约](docs/data-contract.md)
- [规则与架构决定](docs/decisions.md)
- [SRD 5.1 来源与署名](LICENSES/SRD-5.1-CC-BY-4.0.md)

## 路线图

1. M1：SRD 5.1 规则来源、覆盖矩阵与事件/存档契约。
2. M2：掷骰、角色与存档脚本；可玩的单人冒险纵向版本及 Codex 侧边栏面板。
3. M3：补齐 SRD 5.1 的 1–20 级核心覆盖。
4. M4：测试、打磨与正式发布。
5. 后续：可选的玩家自定义扩展包。

## 规则与版权

本项目是非官方作品。使用 SRD 5.1 内容时将遵守其 [CC BY 4.0 许可与署名要求](https://media.dndbeyond.com/compendium-images/srd/5.1/SRD_CC_v5.1.pdf)。非 SRD 的官方书籍、设定及模组不随项目分发。源码许可会在正式编码前确定。
