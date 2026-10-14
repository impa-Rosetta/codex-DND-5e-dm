"""Audited commands for the original old-mill level-one encounter.

This is a deliberately finite scenario, not a general 5e rules engine.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from combat import CombatError, make_initiative, resolve_attack
from dice import roll_dice
from state import StateError, transact


GOBLIN = {"name": "哥布林", "ac": 15, "hp": 7, "temp_hp": 0,
          "initiative_bonus": 2, "speed": 30,
          "attack": {"id": "scimitar", "name": "弯刀", "attack_bonus": 4,
                     "damage_die": 6, "damage_bonus": 2, "reach": 5}}
CHALLENGES = {"find_forest_path": {"location_id": "old_mill", "skill": "perception",
                                    "dc": 12, "discovery": "forest_path",
                                    "summary_success": "你发现通往林中岔路的脚印。",
                                    "summary_failure": "你暂时没找到可辨认的踪迹。"}}
LOCATIONS = {"old_mill": "旧磨坊路口", "forest_path": "林中岔路"}


class SessionError(ValueError):
    pass


def _hero(state: dict) -> dict:
    character = state.get("character")
    if character is None:
        raise SessionError("Create a character first")
    return character


def declare(directory, operation_id: str, statement: str):
    if not isinstance(statement, str) or not 1 <= len(statement.strip()) <= 500:
        raise SessionError("Statement must have 1–500 characters")
    return transact(directory, operation_id, "player.declared",
                    lambda state, _events: {"statement": statement.strip(),
                                            "public_view": {"summary": statement.strip()}},
                    rules=[])


def narrate(directory, operation_id: str, observation: str):
    if not isinstance(observation, str) or not 1 <= len(observation.strip()) <= 1000:
        raise SessionError("Observation must have 1–1000 characters")
    return transact(directory, operation_id, "scene.narrated",
                    lambda state, _events: {"observation": observation.strip(),
                                            "public_view": {"summary": observation.strip()}},
                    rules=[])


def check(directory, operation_id: str, challenge_id: str, *, mode="normal", roller=None):
    if challenge_id not in CHALLENGES:
        raise SessionError("Unknown scenario challenge")
    challenge = CHALLENGES[challenge_id]

    def resolve(state, _events):
        hero = _hero(state)
        if state["combat"] is not None or state["scene"]["location_id"] != challenge["location_id"]:
            raise SessionError("Challenge unavailable here")
        if challenge["discovery"] in state["scene"]["discovered_locations"]:
            raise SessionError("Location already discovered")
        bonus = hero["derived"]["skills"][challenge["skill"]]
        result = roll_dice(f"d20{bonus:+d}", purpose=challenge_id, mode=mode, roller=roller)
        success = result["total"] >= challenge["dc"]
        return {"challenge_id": challenge_id, "skill": challenge["skill"],
                "dc": challenge["dc"], "dice": [result], "success": success,
                "discovered_location_id": challenge["discovery"] if success else None,
                "public_view": {"summary": challenge["summary_success"] if success else challenge["summary_failure"],
                                "total": result["total"], "dc": challenge["dc"], "success": success}}

    return transact(directory, operation_id, "check.resolved", resolve,
                    rules=["check.ability", "adventuring.exploration"])


def move_scene(directory, operation_id: str, location_id: str):
    if location_id not in LOCATIONS:
        raise SessionError("Unknown location")

    def resolve(state, _events):
        _hero(state)
        if state["combat"] is not None:
            raise SessionError("Cannot change scenes during combat")
        if location_id not in state["scene"]["discovered_locations"]:
            raise SessionError("Location has not been discovered")
        return {"location_id": location_id, "name": LOCATIONS[location_id],
                "public_view": {"summary": f"你抵达{LOCATIONS[location_id]}。"}}

    return transact(directory, operation_id, "scene.moved", resolve,
                    rules=["adventuring.exploration"])


def start_encounter(directory, operation_id: str, *, roller=None):
    def resolve(state, _events):
        hero = _hero(state)
        if state["combat"] is not None or state["scene"]["location_id"] != "forest_path":
            raise SessionError("Encounter unavailable here")
        if hero["resources"]["hp"]["current"] <= 0 or hero.get("life_state") == "dead":
            raise SessionError("Defeated character cannot start an encounter")
        goblin_id = str(uuid.uuid4())
        fight = make_initiative([
            {"combatant_id": hero["id"], "name": hero["name"],
             "hp": hero["resources"]["hp"]["current"],
             "temp_hp": hero["resources"]["temp_hp"]["current"],
             "ac": hero["derived"]["ac"], "initiative_bonus": hero["derived"]["initiative"],
             "speed": hero["derived"]["speed"], "position": [0, 0]},
            {"combatant_id": goblin_id, "name": GOBLIN["name"],
             "hp": GOBLIN["hp"], "temp_hp": 0, "ac": GOBLIN["ac"],
             "initiative_bonus": GOBLIN["initiative_bonus"],
             "speed": GOBLIN["speed"], "position": [1, 0]}], roller=roller)
        fight["death_saves"] = None
        fight["death_save_made"] = False
        return {"combat": fight,
                "public_view": {"summary": "哥布林从灌木后现身，战斗开始。",
                                "initiative": [{"id": unit["combatant_id"], "dice": unit["initiative_roll"]}
                                               for unit in fight["combatants"]]}}

    return transact(directory, operation_id, "combat.started", resolve,
                    rules=["combat.initiative_turn", "monsters.goblin"])


def advance_turn(directory, operation_id: str):
    def resolve(state, _events):
        combat = state["combat"]
        if combat is None:
            raise SessionError("No active combat")
        current = combat["combatants"][combat["turn_index"]]
        hero = _hero(state)
        if current["combatant_id"] == hero["id"] and current["hp"] == 0:
            death = combat.get("death_saves") or {}
            if not (combat.get("death_save_made") or death.get("stable") or death.get("dead")):
                raise SessionError("Resolve the required death save before ending this turn")
        next_index = (combat["turn_index"] + 1) % len(combat["combatants"])
        round_number = combat["round"] + (1 if next_index == 0 else 0)
        next_actor = combat["combatants"][next_index]
        if next_actor["hp"] <= 0 and next_actor["combatant_id"] != hero["id"]:
            raise SessionError("Defeated combatant cannot take a turn; end encounter")
        if next_actor["combatant_id"] == hero["id"] and (combat.get("death_saves") or {}).get("dead"):
            raise SessionError("Character has died; end encounter")
        return {"turn_index": next_index, "round": round_number,
                "public_view": {"summary": f"第{round_number}轮，轮到{next_actor['name']}。"}}

    return transact(directory, operation_id, "turn.advanced", resolve,
                    rules=["combat.initiative_turn"])


def attack(directory, operation_id: str, target_id: str, *, mode="normal", roller=None):
    def resolve(state, _events):
        hero = _hero(state)
        combat = state["combat"]
        if combat is None:
            raise SessionError("No active combat")
        actor = combat["combatants"][combat["turn_index"]]
        target = next((unit for unit in combat["combatants"] if unit["combatant_id"] == target_id), None)
        if target is None:
            raise SessionError("Unknown target")
        if actor["combatant_id"] == hero["id"]:
            weapon = hero["derived"]["attacks"][0]
        else:
            weapon = GOBLIN["attack"]
        distance = 5 * max(abs(actor["position"][0] - target["position"][0]),
                           abs(actor["position"][1] - target["position"][1]))
        if distance > weapon["reach"]:
            raise SessionError("Target is outside weapon reach")
        outcome = resolve_attack(combat, actor["combatant_id"], target_id, weapon,
                                 mode=mode, roller=roller)
        if target_id == hero["id"] and outcome["hp_after"] == 0 and outcome["hp_before"] > 0:
            effective_damage = outcome["damage"] - (outcome["temp_hp_before"] - outcome["temp_hp_after"])
            remaining = effective_damage - outcome["hp_before"]
            dead = remaining >= hero["resources"]["hp"]["max"]
            outcome["death_saves_after"] = {"successes": 0, "failures": 0,
                                             "stable": False, "dead": dead}
            outcome["public_view"]["summary"] += (" 角色遭受即死伤害。" if dead else " 角色失去意识。")
        return outcome

    return transact(directory, operation_id, "combat.attack_resolved", resolve,
                    rules=["combat.attack_damage"])


def death_save(directory, operation_id: str, *, roller=None):
    def resolve(state, _events):
        hero = _hero(state)
        combat = state["combat"]
        if combat is None or combat["combatants"][combat["turn_index"]]["combatant_id"] != hero["id"]:
            raise SessionError("Death save requires the character's turn")
        death = combat.get("death_saves")
        if (hero["resources"]["hp"]["current"] != 0 or not death or
                death["stable"] or death["dead"] or combat.get("death_save_made")):
            raise SessionError("Death save is not required now")
        dice = roll_dice("d20", purpose="death_save", roller=roller)
        natural = dice["natural_d20"]
        after = dict(death)
        hp_after = 0
        if natural == 20:
            after = None
            hp_after = 1
            summary = f"{hero['name']}掷出自然20，恢复1点生命值。"
        else:
            if natural >= 10:
                after["successes"] += 1
            else:
                after["failures"] += 2 if natural == 1 else 1
            if after["successes"] >= 3:
                after = {"successes": 0, "failures": 0, "stable": True, "dead": False}
                summary = f"{hero['name']}伤势稳定，但仍处于0生命值。"
            elif after["failures"] >= 3:
                after["dead"] = True
                summary = f"{hero['name']}死亡。"
            else:
                summary = f"{hero['name']}进行死亡豁免：成功{after['successes']}次，失败{after['failures']}次。"
        return {"dice": [dice], "death_saves_after": after, "hp_after": hp_after,
                "public_view": {"summary": summary, "natural_d20": natural}}

    return transact(directory, operation_id, "combat.death_save_resolved", resolve,
                    rules=["combat.death_saves"])


def second_wind(directory, operation_id: str, *, roller=None):
    def resolve(state, _events):
        hero = _hero(state)
        combat = state["combat"]
        if combat is None or combat["combatants"][combat["turn_index"]]["combatant_id"] != hero["id"]:
            raise SessionError("Second Wind requires your turn")
        if hero["resources"]["hp"]["current"] <= 0:
            raise SessionError("Unconscious character cannot use Second Wind")
        if combat["bonus_action_used"] or hero["resources"]["second_wind"]["current"] != 1:
            raise SessionError("Second Wind unavailable")
        dice = roll_dice("d10+1", purpose="second_wind", roller=roller)
        before = hero["resources"]["hp"]["current"]
        after = min(hero["resources"]["hp"]["max"], before + dice["total"])
        return {"dice": [dice], "hp_before": before, "hp_after": after,
                "public_view": {"summary": f"{hero['name']}使用第二春，生命值恢复至{after}。",
                                "healed": after - before}}

    return transact(directory, operation_id, "fighter.second_wind_used", resolve,
                    rules=["class.fighter", "adventuring.rest"])


def short_rest(directory, operation_id: str, *, spend_hit_die=False, roller=None):
    def resolve(state, _events):
        hero = _hero(state)
        if state["combat"] is not None or hero["resources"]["hp"]["current"] <= 0:
            raise SessionError("Cannot take a short rest now")
        dice = []
        hit_dice = hero["resources"]["hit_dice_d10"]["current"]
        if spend_hit_die:
            if hit_dice < 1:
                raise SessionError("No hit die remains")
            con = hero["derived"]["modifiers"]["con"]
            expression = f"d10{con:+d}"
            result = roll_dice(expression, purpose="short_rest_hit_die", roller=roller)
            dice.append(result)
            hit_dice -= 1
        before = hero["resources"]["hp"]["current"]
        healed = max(0, dice[0]["total"]) if dice else 0
        after = min(hero["resources"]["hp"]["max"], before + healed)
        return {"dice": dice, "hp_before": before, "hp_after": after,
                "hit_dice_after": hit_dice,
                "public_view": {"summary": f"短休结束，生命值{after}，第二春已恢复。"}}

    return transact(directory, operation_id, "rest.short_completed", resolve,
                    rules=["adventuring.rest", "class.fighter"])


def end_encounter(directory, operation_id: str):
    def resolve(state, _events):
        combat = state["combat"]
        if combat is None:
            raise SessionError("No active combat")
        goblin_defeated = any(unit["name"] == GOBLIN["name"] and unit["hp"] == 0
                              for unit in combat["combatants"])
        death = combat.get("death_saves") or {}
        if goblin_defeated:
            outcome, summary = "victory", "哥布林倒下，遭遇结束。"
        elif death.get("dead"):
            outcome, summary = "defeat_dead", "角色死亡，冒险结束。"
        elif death.get("stable"):
            outcome, summary = "defeat_stable", "角色伤势稳定，但失去行动能力；本次遭遇以战败结束。"
        else:
            raise SessionError("No resolved victory or defeat")
        return {"outcome": outcome, "public_view": {"summary": summary}}

    return transact(directory, operation_id, "combat.ended", resolve,
                    rules=["combat.initiative_turn"])


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Audited old-mill session actions")
    parser.add_argument("directory")
    parser.add_argument("command", choices=("declare", "narrate", "check", "move", "start-combat",
                                            "attack", "advance", "death-save", "second-wind", "short-rest", "end-combat"))
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--text")
    parser.add_argument("--challenge-id")
    parser.add_argument("--location-id")
    parser.add_argument("--target-id")
    parser.add_argument("--mode", choices=("normal", "advantage", "disadvantage"), default="normal")
    parser.add_argument("--spend-hit-die", action="store_true")
    args = parser.parse_args(argv)
    commands = {"declare": lambda: declare(args.directory, args.operation_id, args.text),
                "narrate": lambda: narrate(args.directory, args.operation_id, args.text),
                "check": lambda: check(args.directory, args.operation_id, args.challenge_id, mode=args.mode),
                "move": lambda: move_scene(args.directory, args.operation_id, args.location_id),
                "start-combat": lambda: start_encounter(args.directory, args.operation_id),
                "attack": lambda: attack(args.directory, args.operation_id, args.target_id, mode=args.mode),
                "advance": lambda: advance_turn(args.directory, args.operation_id),
                "death-save": lambda: death_save(args.directory, args.operation_id),
                "second-wind": lambda: second_wind(args.directory, args.operation_id),
                "short-rest": lambda: short_rest(args.directory, args.operation_id,
                                                  spend_hit_die=args.spend_hit_die),
                "end-combat": lambda: end_encounter(args.directory, args.operation_id)}
    try:
        event, state = commands[args.command]()
    except (SessionError, StateError, CombatError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": {"code": "invalid_action", "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"event": event, "state": state}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
