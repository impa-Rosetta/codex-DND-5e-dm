"""Level-one attack and initiative adjudication, with state.py as commit boundary."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dice import roll_dice
from state import StateError, commit, load


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
        units.append(scored)
    units.sort(key=lambda u: (-u["initiative_roll"]["total"], -u["initiative_bonus"], u["combatant_id"]))
    return {"round": 1, "turn_index": 0, "combatants": units,
            "action_used": False, "bonus_action_used": False, "reaction_used": False,
            "movement_used": 0}


def resolve_attack(combat: dict, actor_id: str, target_id: str, weapon: dict,
                   *, mode: str = "normal", roller=None) -> dict:
    if not combat or not combat.get("combatants"):
        raise CombatError("No active combat")
    acting = combat["combatants"][combat["turn_index"]]
    if acting["combatant_id"] != actor_id:
        raise CombatError("It is not this combatant's turn")
    if combat["action_used"]:
        raise CombatError("Action already used this turn")
    target = _actor(combat, target_id)
    if actor_id == target_id or acting["hp"] <= 0 or target["hp"] <= 0:
        raise CombatError("Invalid attack target")
    if not all(isinstance(weapon.get(field), int) for field in ("attack_bonus", "damage_bonus", "damage_die")):
        raise CombatError("Weapon requires numeric bonuses and die")
    attack_bonus = weapon["attack_bonus"]
    damage_bonus = weapon["damage_bonus"]
    die = weapon["damage_die"]
    if not 1 <= die <= 100 or not -20 <= attack_bonus <= 50 or not -20 <= damage_bonus <= 50:
        raise CombatError("Weapon values outside supported range")
    attack = roll_dice(f"d20{attack_bonus:+d}", purpose="attack", mode=mode, roller=roller)
    natural = attack["natural_d20"]
    hit = natural == 20 or (natural != 1 and attack["total"] >= target["ac"])
    critical = natural == 20
    damage = None
    amount = 0
    if hit:
        damage = roll_dice(f"{2 if critical else 1}d{die}{damage_bonus:+d}",
                           purpose="damage", roller=roller)
        amount = max(0, damage["total"])
    temp_before = target.get("temp_hp", 0)
    absorbed = min(temp_before, amount)
    hp_before = target["hp"]
    hp_after = max(0, hp_before - (amount - absorbed))
    return {"actor_combatant_id": actor_id, "target_combatant_id": target_id,
            "target_ac": target["ac"], "weapon_name": weapon.get("name", "weapon"),
            "hit": hit, "critical": critical, "dice": [attack] + ([damage] if damage else []),
            "damage": amount, "hp_before": hp_before, "hp_after": hp_after,
            "temp_hp_before": temp_before, "temp_hp_after": temp_before - absorbed,
            "public_view": {"summary": f"{acting['name']}攻击{target['name']}：{'命中' if hit else '未命中'}，造成{amount}点伤害。",
                            "attack_total": attack["total"], "damage": amount,
                            "target_hp": hp_after}}


def attack_and_commit(directory: str | Path, operation_id: str, actor_id: str,
                      target_id: str, weapon: dict, *, mode: str = "normal") -> dict:
    _, state, events = load(directory)
    for event in events:
        if event["operation_id"] == operation_id:
            return {"event": event, "state": state}
    payload = resolve_attack(state["combat"], actor_id, target_id, weapon, mode=mode)
    event, snapshot = commit(directory, operation_id, "combat.attack_resolved", payload,
                             actor_id=actor_id, rules=["combat.attack_damage"])
    return {"event": event, "state": snapshot}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--weapon", required=True, help="JSON file with attack_bonus, damage_bonus, damage_die")
    parser.add_argument("--mode", choices=("normal", "advantage", "disadvantage"), default="normal")
    args = parser.parse_args(argv)
    try:
        uuid.UUID(args.operation_id)
        weapon = json.loads(Path(args.weapon).read_text(encoding="utf-8"))
        result = attack_and_commit(args.directory, args.operation_id, args.actor_id,
                                   args.target_id, weapon, mode=args.mode)
    except (CombatError, StateError, ValueError, KeyError, OSError) as exc:
        print(json.dumps({"error": {"code": "invalid_attack", "message": str(exc)}}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
