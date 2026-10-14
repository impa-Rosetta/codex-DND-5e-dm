"""Level-one attack and initiative adjudication, with state.py as commit boundary."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dice import roll_dice


class CombatError(ValueError):
    pass


def _actor(combat: dict, actor_id: str) -> dict:
    for combatant in combat["combatants"]:
        if combatant["combatant_id"] == actor_id:
            return combatant
    raise CombatError("Unknown combatant")


def make_initiative(combatants: list[dict], *, roller=None) -> dict:
    if not 2 <= len(combatants) <= 12:
        raise CombatError("Combat requires 2–12 combatants")
    ids = [unit["combatant_id"] for unit in combatants]
    if len(ids) != len(set(ids)):
        raise CombatError("Combatant IDs must be unique")
    units = []
    for unit in combatants:
        if not isinstance(unit.get("initiative_bonus"), int):
            raise CombatError("Each combatant requires initiative_bonus")
        scored = dict(unit)
        scored["initiative_roll"] = roll_dice(
            f"d20{unit['initiative_bonus']:+d}", purpose="initiative", roller=roller)
        scored.setdefault("temp_hp", 0)
        scored.setdefault("reaction_used", False)
        scored.setdefault("dodging", False)
        scored.setdefault("disengaged", False)
        scored.setdefault("dashed", False)
        units.append(scored)
    # The old-mill DM chooses player-first on a PC/monster tie. Preserve the
    # caller's declared order; Dexterity is not an automatic SRD tie-breaker.
    units.sort(key=lambda u: -u["initiative_roll"]["total"])
    return {"round": 1, "turn_index": 0, "combatants": units,
            "action_used": False, "bonus_action_used": False, "reaction_used": False,
            "movement_used": 0}


def resolve_attack(combat: dict, actor_id: str, target_id: str, weapon: dict,
                   *, mode: str = "normal", roller=None, reaction: bool = False,
                   target_unconscious: bool = False,
                   extra_disadvantage: bool = False,
                   damage_resistance: bool = False,
                   sneak_attack_on_advantage: bool = False) -> dict:
    if not combat or not combat.get("combatants"):
        raise CombatError("No active combat")
    current = combat["combatants"][combat["turn_index"]]
    acting = _actor(combat, actor_id) if reaction else current
    if reaction and (current["combatant_id"] == actor_id or acting.get("reaction_used")):
        raise CombatError("Opportunity attack reaction unavailable")
    if not reaction and acting["combatant_id"] != actor_id:
        raise CombatError("It is not this combatant's turn")
    if not reaction and combat["action_used"]:
        raise CombatError("Action already used this turn")
    target = _actor(combat, target_id)
    if (actor_id == target_id or acting["hp"] <= 0 or target["hp"] < 0 or
            (target["hp"] == 0 and not target_unconscious) or
            (target_unconscious and target["hp"] != 0)):
        raise CombatError("Invalid attack target")
    if not all(isinstance(weapon.get(field), int) for field in ("attack_bonus", "damage_bonus", "damage_die")):
        raise CombatError("Weapon requires numeric bonuses and die")
    attack_bonus = weapon["attack_bonus"]
    damage_bonus = weapon["damage_bonus"]
    die = weapon["damage_die"]
    if not 1 <= die <= 100 or not -20 <= attack_bonus <= 50 or not -20 <= damage_bonus <= 50:
        raise CombatError("Weapon values outside supported range")
    if mode not in ("normal", "advantage", "disadvantage"):
        raise CombatError("Invalid attack roll mode")
    has_advantage = mode == "advantage" or target_unconscious
    has_disadvantage = (mode == "disadvantage" or extra_disadvantage or
                        (bool(target.get("dodging")) and not target_unconscious))
    mode = ("normal" if has_advantage == has_disadvantage else
            "advantage" if has_advantage else "disadvantage")
    attack = roll_dice(f"d20{attack_bonus:+d}", purpose="opportunity_attack" if reaction else "attack",
                       mode=mode, roller=roller)
    natural = attack["natural_d20"]
    hit = natural == 20 or (natural != 1 and attack["total"] >= target["ac"])
    critical = hit and (natural == 20 or target_unconscious)
    damage = None
    sneak_damage = None
    amount = 0
    rolled_damage = 0
    if hit:
        damage = roll_dice(f"{2 if critical else 1}d{die}{damage_bonus:+d}",
                           purpose="damage", roller=roller)
        if sneak_attack_on_advantage and mode == "advantage":
            sneak_damage = roll_dice(f"{2 if critical else 1}d6", purpose="sneak_attack", roller=roller)
        rolled_damage = max(0, damage["total"] + (sneak_damage["total"] if sneak_damage else 0))
        amount = rolled_damage // 2 if damage_resistance else rolled_damage
    temp_before = target.get("temp_hp", 0)
    absorbed = min(temp_before, amount)
    hp_before = target["hp"]
    hp_after = max(0, hp_before - (amount - absorbed))
    return {"actor_combatant_id": actor_id, "target_combatant_id": target_id,
            "target_ac": target["ac"], "weapon_name": weapon.get("name", "weapon"),
            "hit": hit, "critical": critical,
            "dice": [attack] + ([damage] if damage else []) + ([sneak_damage] if sneak_damage else []),
            "sneak_attack_used": sneak_damage is not None,
            "damage": amount, "rolled_damage": rolled_damage,
            "hp_before": hp_before, "hp_after": hp_after,
            "temp_hp_before": temp_before, "temp_hp_after": temp_before - absorbed,
            "public_view": {"summary": f"{acting['name']}攻击{target['name']}：{'命中' if hit else '未命中'}，造成{amount}点伤害。",
                            "attack_total": attack["total"], "damage": amount,
                            "target_hp": hp_after}}
