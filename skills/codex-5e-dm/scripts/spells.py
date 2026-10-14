"""Small audited spell-effect resolvers for the supported level-one routes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dice import roll_dice


class SpellError(ValueError):
    pass


SAVE_SPELLS = {
    "poison_spray": {"save": "con", "damage": "d12", "damage_type": "poison", "half_on_save": False},
    "burning_hands": {"save": "dex", "damage": "3d6", "damage_type": "fire", "half_on_save": True},
}


def resolve_save_spell(spell_id: str, caster: dict, target: dict, save_bonus: int,
                       *, roller=None) -> dict:
    if spell_id not in SAVE_SPELLS:
        raise SpellError("Unsupported saving-throw spell")
    if not isinstance(save_bonus, int):
        raise SpellError("Saving throw bonus must be numeric")
    spell = SAVE_SPELLS[spell_id]
    dc = caster["derived"]["spellcasting"]["save_dc"]
    save = roll_dice(f"d20{save_bonus:+d}", purpose=f"{spell_id}_save", roller=roller)
    saved = save["total"] >= dc
    damage_roll = roll_dice(spell["damage"], purpose=f"{spell_id}_damage", roller=roller)
    rolled_damage = damage_roll["total"]
    amount = (rolled_damage // 2 if spell["half_on_save"] else 0) if saved else rolled_damage
    temp_before = target.get("temp_hp", 0)
    absorbed = min(temp_before, amount)
    hp_before = target["hp"]
    hp_after = max(0, hp_before - (amount - absorbed))
    return {"actor_combatant_id": caster["id"], "target_combatant_id": target["combatant_id"],
            "target_ac": target["ac"], "weapon_name": spell_id, "spell_id": spell_id,
            "save_ability": spell["save"], "save_dc": dc, "saved": saved,
            "hit": amount > 0, "critical": False, "dice": [save, damage_roll],
            "damage_type": spell["damage_type"], "rolled_damage": rolled_damage,
            "damage": amount, "hp_before": hp_before, "hp_after": hp_after,
            "temp_hp_before": temp_before, "temp_hp_after": temp_before - absorbed,
            "public_view": {"summary": f"{spell_id}：{target['name']}豁免{'成功' if saved else '失败'}，受到{amount}点伤害。",
                            "save_total": save["total"], "save_dc": dc,
                            "damage": amount, "target_hp": hp_after}}
