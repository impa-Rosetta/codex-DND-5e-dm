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
                     "damage_die": 6, "damage_bonus": 2, "reach": 5,
                     "damage_type": "slashing"}}
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
        if hero["source_choices"]["class"] == "barbarian":
            fight.update(rage_active=False, rage_sustained=False, rage_rounds_remaining=0)
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
            weapon = dict(hero["derived"]["attacks"][0])
            if combat.get("rage_active") and "reach" in weapon:
                weapon["damage_bonus"] += 2
        else:
            weapon = GOBLIN["attack"]
        distance = 5 * max(abs(actor["position"][0] - target["position"][0]),
                           abs(actor["position"][1] - target["position"][1]))
        ranged_disadvantage = False
        ammunition_after = None
        if "reach" in weapon:
            if distance > weapon["reach"]:
                raise SessionError("Target is outside weapon reach")
        elif weapon["id"] == "longbow" and actor["combatant_id"] == hero["id"]:
            if distance > weapon["range_long"]:
                raise SessionError("Target is outside longbow range")
            arrows = hero["resources"]["ammunition_arrow"]["current"]
            if arrows < 1:
                raise SessionError("No arrows remain")
            ammunition_after = arrows - 1
            if distance > weapon["range_normal"] or (distance <= 5 and target["hp"] > 0):
                ranged_disadvantage = True
        else:
            raise SessionError("Selected weapon attack mode is not implemented")
        unconscious_target = target_id == hero["id"] and target["hp"] == 0
        if unconscious_target and (combat.get("death_saves") or {}).get("dead"):
            raise SessionError("Character is already dead")
        outcome = resolve_attack(combat, actor["combatant_id"], target_id, weapon,
                                 mode=mode, roller=roller,
                                 target_unconscious=unconscious_target,
                                 extra_disadvantage=ranged_disadvantage,
                                 damage_resistance=(combat.get("rage_active", False) and
                                                    target_id == hero["id"] and
                                                    weapon.get("damage_type") in
                                                    ("bludgeoning", "piercing", "slashing")),
                                 sneak_attack_on_advantage=(actor["combatant_id"] == hero["id"] and
                                                            hero["source_choices"]["class"] == "rogue" and
                                                            weapon.get("finesse", False) and
                                                            not combat.get("sneak_attack_used", False)))
        if ammunition_after is not None:
            outcome["ammunition_arrow_after"] = ammunition_after
        if target_id == hero["id"] and outcome["hp_after"] == 0 and outcome["hp_before"] > 0:
            effective_damage = outcome["damage"] - (outcome["temp_hp_before"] - outcome["temp_hp_after"])
            remaining = effective_damage - outcome["hp_before"]
            dead = remaining >= hero["resources"]["hp"]["max"]
            outcome["death_saves_after"] = {"successes": 0, "failures": 0,
                                             "stable": False, "dead": dead}
            outcome["public_view"]["summary"] += (" 角色遭受即死伤害。" if dead else " 角色失去意识。")
        elif unconscious_target and outcome["hit"]:
            effective_damage = outcome["damage"] - (outcome["temp_hp_before"] - outcome["temp_hp_after"])
            if effective_damage > 0:
                before = combat.get("death_saves") or {"successes": 0, "failures": 0,
                                                        "stable": False, "dead": False}
                after = dict(before)
                after["stable"] = False
                after["failures"] += 2 if outcome["critical"] else 1
                after["dead"] = after["failures"] >= 3 or effective_damage >= hero["resources"]["hp"]["max"]
                outcome["death_saves_after"] = after
                outcome["public_view"]["summary"] += (" 角色死亡。" if after["dead"] else
                                                       f" 死亡豁免失败累计{after['failures']}次。")
        if actor["combatant_id"] == hero["id"] and hero["source_choices"]["class"] == "monk":
            outcome["monk_attack_ready"] = True
        return outcome

    return transact(directory, operation_id, "combat.attack_resolved", resolve,
                    rules=["combat.attack_damage"])


def martial_arts(directory, operation_id: str, target_id: str, *, mode="normal", roller=None):
    def resolve(state, _events):
        hero = _hero(state)
        combat = state["combat"]
        if hero["source_choices"]["class"] != "monk":
            raise SessionError("Martial Arts is a monk feature")
        if combat is None or combat["combatants"][combat["turn_index"]]["combatant_id"] != hero["id"]:
            raise SessionError("Martial Arts requires your turn")
        if not combat.get("monk_attack_ready") or combat["bonus_action_used"]:
            raise SessionError("First take the Attack action with a monk weapon")
        actor = combat["combatants"][combat["turn_index"]]
        target = next((unit for unit in combat["combatants"] if unit["combatant_id"] == target_id), None)
        if target is None or max(abs(actor["position"][0] - target["position"][0]),
                                 abs(actor["position"][1] - target["position"][1])) > 1:
            raise SessionError("Target is outside unarmed reach")
        outcome = resolve_attack(combat, hero["id"], target_id, hero["derived"]["attacks"][1],
                                 mode=mode, roller=roller, bonus_action_attack=True)
        outcome["bonus_action_attack"] = True
        return outcome

    return transact(directory, operation_id, "combat.attack_resolved", resolve,
                    rules=["combat.attack_damage", "class.monk.martial_arts"])


def combat_action(directory, operation_id: str, action: str):
    if action not in ("dash", "disengage", "dodge"):
        raise SessionError("Unsupported combat action")
    labels = {"dash": "疾走", "disengage": "撤离", "dodge": "闪避"}

    def resolve(state, _events):
        _hero(state)
        combat = state["combat"]
        if combat is None:
            raise SessionError("No active combat")
        actor = combat["combatants"][combat["turn_index"]]
        if actor["hp"] <= 0:
            raise SessionError("Combat action requires a conscious actor's turn")
        if combat["action_used"]:
            raise SessionError("Action already used this turn")
        return {"actor_combatant_id": actor["combatant_id"], "action": action,
                "public_view": {"summary": f"{actor['name']}采取{labels[action]}动作。"}}

    return transact(directory, operation_id, "combat.action_taken", resolve,
                    rules=["combat.initiative_turn", "combat.movement_position"])


def move_combat(directory, operation_id: str, path: list, *, use_reaction: bool | None = None,
                roller=None):
    """Walk a 5-foot square path in the old-mill open encounter grid."""
    def resolve(state, _events):
        hero = _hero(state)
        combat = state["combat"]
        if combat is None:
            raise SessionError("No active combat")
        actor = combat["combatants"][combat["turn_index"]]
        if actor["hp"] <= 0:
            raise SessionError("Movement requires a conscious actor's turn")
        if use_reaction is not None and type(use_reaction) is not bool:
            raise SessionError("Reaction choice must be true or false")
        if not isinstance(path, list) or not 1 <= len(path) <= 100:
            raise SessionError("Path requires one or more grid squares")
        origin = list(actor["position"])
        previous = origin
        for square in path:
            if (not isinstance(square, list) or len(square) != 2 or
                    any(type(n) is not int or abs(n) > 100 for n in square) or
                    max(abs(square[0] - previous[0]), abs(square[1] - previous[1])) != 1):
                raise SessionError("Path must use adjacent 5-foot grid squares")
            if any(unit["combatant_id"] != actor["combatant_id"] and unit["hp"] > 0 and
                   unit["position"] == square for unit in combat["combatants"]):
                raise SessionError("Cannot enter a hostile occupied square")
            previous = square
        feet = 5 * len(path)
        allowed = actor["speed"] * (2 if actor.get("dashed") else 1)
        if combat["movement_used"] + feet > allowed:
            raise SessionError("Movement exceeds this turn's speed")
        enemy = next((unit for unit in combat["combatants"]
                      if unit["combatant_id"] != actor["combatant_id"] and unit["hp"] > 0), None)
        opportunity = None
        traveled = []
        previous = origin
        for square in path:
            leaving_reach = (enemy is not None and opportunity is None and
                             not actor.get("disengaged") and
                             not enemy.get("reaction_used") and
                             max(abs(previous[0] - enemy["position"][0]),
                                 abs(previous[1] - enemy["position"][1])) == 1 and
                             max(abs(square[0] - enemy["position"][0]),
                                 abs(square[1] - enemy["position"][1])) > 1)
            if leaving_reach:
                if enemy["combatant_id"] == hero["id"] and use_reaction is None:
                    raise SessionError("Ask the player whether to use their opportunity attack")
                if enemy["combatant_id"] != hero["id"] or use_reaction:
                    if enemy["combatant_id"] == hero["id"] and hero["source_choices"]["weapon"] == "longbow":
                        raise SessionError("A held longbow cannot make the verified melee opportunity attack")
                    weapon = (dict(hero["derived"]["attacks"][0]) if enemy["combatant_id"] == hero["id"]
                              else GOBLIN["attack"])
                    if enemy["combatant_id"] == hero["id"] and combat.get("rage_active"):
                        weapon["damage_bonus"] += 2
                    opportunity = resolve_attack(combat, enemy["combatant_id"],
                                                 actor["combatant_id"], weapon,
                                                 roller=roller, reaction=True,
                                                 damage_resistance=(actor["combatant_id"] == hero["id"] and
                                                                    combat.get("rage_active", False) and
                                                                    weapon.get("damage_type") in
                                                                    ("bludgeoning", "piercing", "slashing")),
                                                 sneak_attack_on_advantage=(enemy["combatant_id"] == hero["id"] and
                                                                            hero["source_choices"]["class"] == "rogue" and
                                                                            weapon.get("finesse", False) and
                                                                            not combat.get("sneak_attack_used", False)))
                if opportunity is not None and opportunity["hp_after"] == 0:
                    remaining = (opportunity["damage"] -
                                 (opportunity["temp_hp_before"] - opportunity["temp_hp_after"]) -
                                 opportunity["hp_before"])
                    if actor["combatant_id"] == hero["id"]:
                        opportunity["death_saves_after"] = {
                            "successes": 0, "failures": 0, "stable": False,
                            "dead": remaining >= hero["resources"]["hp"]["max"]}
                    break
            traveled.append(square)
            previous = square
        return {"actor_combatant_id": actor["combatant_id"], "from": origin,
                "to": traveled[-1] if traveled else origin,
                "path": traveled, "feet": 5 * len(traveled),
                "opportunity_attack": opportunity,
                "public_view": {"summary": f"{actor['name']}移动了{5 * len(traveled)}英尺。" +
                                (" 触发借机攻击。" if opportunity else ""),
                                "position": traveled[-1] if traveled else origin,
                                "opportunity_attack": opportunity["public_view"] if opportunity else None}}

    return transact(directory, operation_id, "combat.move_resolved", resolve,
                    rules=["combat.movement_position", "combat.opportunity_attack"])


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
        if hero["source_choices"]["class"] != "fighter":
            raise SessionError("Second Wind is a fighter feature")
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


def rage(directory, operation_id: str):
    def resolve(state, _events):
        hero = _hero(state)
        combat = state["combat"]
        if hero["source_choices"]["class"] != "barbarian":
            raise SessionError("Rage is a barbarian feature")
        if (combat is None or
                combat["combatants"][combat["turn_index"]]["combatant_id"] != hero["id"] or
                hero["resources"]["hp"]["current"] <= 0):
            raise SessionError("Rage requires your conscious combat turn")
        if (combat["bonus_action_used"] or combat.get("rage_active") or
                hero["resources"]["rage"]["current"] <= 0):
            raise SessionError("Rage unavailable")
        return {"public_view": {"summary": f"{hero['name']}进入狂暴。"}}

    return transact(directory, operation_id, "barbarian.rage_started", resolve,
                    rules=["class.barbarian.rage"])


def short_rest(directory, operation_id: str, *, spend_hit_die=False, roller=None):
    def resolve(state, _events):
        hero = _hero(state)
        if state["combat"] is not None or hero["resources"]["hp"]["current"] <= 0:
            raise SessionError("Cannot take a short rest now")
        dice = []
        hit_die = hero["derived"]["hit_die"]
        hit_die_key = f"hit_dice_{hit_die}"
        hit_dice = hero["resources"][hit_die_key]["current"]
        if spend_hit_die:
            if hit_dice < 1:
                raise SessionError("No hit die remains")
            con = hero["derived"]["modifiers"]["con"]
            expression = f"{hit_die}{con:+d}"
            result = roll_dice(expression, purpose="short_rest_hit_die", roller=roller)
            dice.append(result)
            hit_dice -= 1
        before = hero["resources"]["hp"]["current"]
        healed = max(0, dice[0]["total"]) if dice else 0
        after = min(hero["resources"]["hp"]["max"], before + healed)
        return {"dice": dice, "hp_before": before, "hp_after": after,
                "hit_dice_after": hit_dice, "hit_die_key": hit_die_key,
                "public_view": {"summary": f"短休结束，生命值{after}。"}}

    return transact(directory, operation_id, "rest.short_completed", resolve,
                    rules=["adventuring.rest"])


def long_rest(directory, operation_id: str):
    def resolve(state, _events):
        hero = _hero(state)
        if state["combat"] is not None or hero["resources"]["hp"]["current"] < 1:
            raise SessionError("Long rest requires a conscious character outside combat")
        if hero.get("life_state") in ("dead", "stable"):
            raise SessionError("Defeated character cannot take a long rest")
        started_at = state["world_time"] or 0
        last_start = state.get("last_long_rest_start")
        if last_start is not None and started_at - last_start < 24 * 60:
            raise SessionError("A character cannot benefit from another long rest within 24 hours")
        resources = hero["resources"]
        hit_die_key = f"hit_dice_{hero['derived']['hit_die']}"
        hit_dice = resources[hit_die_key]
        restored_dice = max(1, hit_dice["max"] // 2)
        hit_dice_after = min(hit_dice["max"], hit_dice["current"] + restored_dice)
        hp_after = resources["hp"]["max"]
        return {"started_at": started_at, "completed_at": started_at + 8 * 60,
                "hp_after": hp_after, "hit_dice_after": hit_dice_after,
                "hit_die_key": hit_die_key,
                "temp_hp_after": 0,
                "public_view": {"summary": f"{hero['name']}完成长休，生命值恢复至{hp_after}，生命骰恢复至{hit_dice_after}颗。"}}

    return transact(directory, operation_id, "rest.long_completed", resolve,
                    rules=["adventuring.rest"])


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


def recover_stable(directory, operation_id: str, *, roller=None):
    """Resolve the SRD's 1d4-hour spontaneous recovery after a stable defeat."""
    def resolve(state, _events):
        hero = _hero(state)
        if (state["combat"] is not None or hero.get("life_state") != "stable" or
                hero["resources"]["hp"]["current"] != 0):
            raise SessionError("Stable recovery requires a stable hero outside combat")
        dice = roll_dice("d4", purpose="stable_recovery_hours", roller=roller)
        before = state["world_time"] or 0
        after = before + dice["total"] * 60
        return {"dice": [dice], "hours": dice["total"], "started_at": before,
                "completed_at": after, "hp_after": 1,
                "public_view": {"summary": f"{hero['name']}在{dice['total']}小时后恢复意识，生命值为1。"}}

    return transact(directory, operation_id, "character.stable_recovered", resolve,
                    rules=["combat.death_saves", "adventuring.rest"])


def search_battlefield(directory, operation_id: str):
    """Spend one minute recovering half the arrows expended in the last victory."""
    def resolve(state, _events):
        hero = _hero(state)
        resources = hero["resources"]
        if (state["combat"] is not None or hero.get("life_state") in ("dead", "stable") or
                state["scene"]["location_id"] != "forest_path" or
                "recoverable_arrow" not in resources or
                resources["recoverable_arrow"]["current"] <= 0):
            raise SessionError("No recoverable arrows here")
        recovered = resources["recoverable_arrow"]["current"]
        if resources["ammunition_arrow"]["current"] + recovered > resources["ammunition_arrow"]["max"]:
            raise SessionError("Arrow capacity would be exceeded")
        started = state["world_time"] or 0
        return {"recovered": recovered, "started_at": started, "completed_at": started + 1,
                "public_view": {"summary": f"{hero['name']}搜索战场一分钟，找回{recovered}支箭。"}}

    return transact(directory, operation_id, "equipment.ammunition_recovered", resolve,
                    rules=["equipment.weapons_armor", "adventuring.exploration"])


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Audited old-mill session actions")
    parser.add_argument("directory")
    parser.add_argument("command", choices=("declare", "narrate", "check", "move", "start-combat",
                                            "attack", "combat-action", "combat-move", "advance", "death-save",
                                            "second-wind", "rage", "martial-arts", "short-rest", "long-rest", "end-combat", "recover-stable",
                                            "search-battlefield"))
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--text")
    parser.add_argument("--challenge-id")
    parser.add_argument("--location-id")
    parser.add_argument("--target-id")
    parser.add_argument("--action", choices=("dash", "disengage", "dodge"))
    parser.add_argument("--path", help="JSON array of adjacent [x,y] grid squares")
    parser.add_argument("--reaction", choices=("accept", "decline"),
                        help="Player's decision when a goblin leaves the hero's reach")
    parser.add_argument("--mode", choices=("normal", "advantage", "disadvantage"), default="normal")
    parser.add_argument("--spend-hit-die", action="store_true")
    args = parser.parse_args(argv)
    commands = {"declare": lambda: declare(args.directory, args.operation_id, args.text),
                "narrate": lambda: narrate(args.directory, args.operation_id, args.text),
                "check": lambda: check(args.directory, args.operation_id, args.challenge_id, mode=args.mode),
                "move": lambda: move_scene(args.directory, args.operation_id, args.location_id),
                "start-combat": lambda: start_encounter(args.directory, args.operation_id),
                "attack": lambda: attack(args.directory, args.operation_id, args.target_id, mode=args.mode),
                "combat-action": lambda: combat_action(args.directory, args.operation_id, args.action),
                "combat-move": lambda: move_combat(args.directory, args.operation_id,
                                                     json.loads(args.path) if args.path else None,
                                                     use_reaction={"accept": True, "decline": False}.get(args.reaction)),
                "advance": lambda: advance_turn(args.directory, args.operation_id),
                "death-save": lambda: death_save(args.directory, args.operation_id),
                "second-wind": lambda: second_wind(args.directory, args.operation_id),
                "rage": lambda: rage(args.directory, args.operation_id),
                "martial-arts": lambda: martial_arts(args.directory, args.operation_id,
                                                     args.target_id, mode=args.mode),
                "short-rest": lambda: short_rest(args.directory, args.operation_id,
                                                  spend_hit_die=args.spend_hit_die),
                "long-rest": lambda: long_rest(args.directory, args.operation_id),
                "end-combat": lambda: end_encounter(args.directory, args.operation_id)}
    commands["recover-stable"] = lambda: recover_stable(args.directory, args.operation_id)
    commands["search-battlefield"] = lambda: search_battlefield(args.directory, args.operation_id)
    try:
        event, state = commands[args.command]()
    except (SessionError, StateError, CombatError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": {"code": "invalid_action", "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"event": event, "state": state}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
