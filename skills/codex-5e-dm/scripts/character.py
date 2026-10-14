"""Deterministic, deliberately bounded SRD 5.1 level-one character builder.

Only verified human/fighter-or-barbarian/acolyte starting routes are buildable in this
release. Listing an option never implies complete mechanical implementation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RULESET = "srd-5.1-2014"
ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)
POINT_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
SKILL_ABILITY = {"acrobatics": "dex", "animal_handling": "wis", "arcana": "int",
                 "athletics": "str", "deception": "cha", "history": "int", "insight": "wis",
                 "intimidation": "cha", "investigation": "int", "medicine": "wis", "nature": "int",
                 "perception": "wis", "performance": "cha", "persuasion": "cha",
                 "religion": "int", "sleight_of_hand": "dex", "stealth": "dex", "survival": "wis"}
FIGHTER_SKILLS = frozenset(("acrobatics", "animal_handling", "athletics", "history",
                            "insight", "intimidation", "perception", "survival"))
BARBARIAN_SKILLS = frozenset(("animal_handling", "athletics", "intimidation",
                              "nature", "perception", "survival"))
ROGUE_SKILLS = frozenset(("acrobatics", "athletics", "deception", "insight",
                          "intimidation", "investigation", "perception", "performance",
                          "persuasion", "sleight_of_hand", "stealth"))
MONK_SKILLS = frozenset(("acrobatics", "athletics", "history", "insight", "religion", "stealth"))
PALADIN_SKILLS = frozenset(("athletics", "insight", "intimidation", "medicine",
                            "persuasion", "religion"))
MONK_TOOLS = frozenset(("calligraphers_supplies", "carpenters_tools", "cobblers_tools",
                        "cooks_utensils", "flute", "lute", "painters_supplies", "potters_tools"))
LANGUAGES = frozenset(("dwarvish", "elvish", "giant", "gnomish", "goblin", "halfling",
                       "orc", "abyssal", "celestial", "draconic", "deep_speech", "infernal",
                       "primordial", "sylvan", "undercommon"))
STYLES = frozenset(("archery", "defense", "dueling", "great_weapon_fighting",
                    "protection", "two_weapon_fighting"))
MAX_INPUT = 32_768
CATALOG = Path(__file__).resolve().parents[1] / "data" / "character-options.json"


class CharacterError(ValueError):
    def __init__(self, code: str, field: str, message: str):
        self.code, self.field, self.message = code, field, message
        super().__init__(message)


def _err(code: str, field: str, message: str):
    raise CharacterError(code, field, message)


def _unique(values, field, count):
    if not isinstance(values, list) or len(values) != count or any(not isinstance(v, str) for v in values) or len(set(values)) != count:
        _err("invalid_choice", field, f"Choose {count} distinct entries")


def ability_scores(data: dict, verified_roll: list[int] | None = None) -> dict[str, int]:
    method = data.get("ability_method")
    if method == "rolled":
        if verified_roll is None or len(verified_roll) != 6:
            _err("unverified_roll", "roll_event_id", "A campaign roll event is required")
        assignment = data.get("rolled_assignment")
        if (not isinstance(assignment, dict) or set(assignment) != set(ABILITIES)
                or any(type(index) is not int for index in assignment.values())
                or sorted(assignment.values()) != list(range(6))):
            _err("invalid_choice", "rolled_assignment", "Assign each of six roll indices once")
        if "base_abilities" in data:
            _err("unverified_roll", "base_abilities", "Rolled scores come only from event")
        return {ability: verified_roll[index] for ability, index in assignment.items()}
    values = data.get("base_abilities")
    if method not in ("standard_array", "point_buy"):
        _err("invalid_ability_method", "ability_method", "Supported: standard_array, point_buy, verified rolled")
    if not isinstance(values, dict) or set(values) != set(ABILITIES) or any(type(v) is not int for v in values.values()):
        _err("invalid_choice", "base_abilities", "Supply six integer ability scores")
    if method == "standard_array" and sorted(values.values()) != sorted(STANDARD_ARRAY):
        _err("invalid_choice", "base_abilities", "Use each standard array score once")
    if method == "point_buy":
        if any(v not in POINT_COST for v in values.values()) or sum(POINT_COST[v] for v in values.values()) > 27:
            _err("invalid_choice", "base_abilities", "Point buy: 8–15, total cost at most 27")
    return dict(values)


def catalog() -> dict:
    value = json.loads(CATALOG.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or value.get("ruleset") != RULESET:
        _err("ruleset_mismatch", "catalog", "Character catalog version mismatch")
    for group in ("races", "classes", "backgrounds"):
        entries = value[group]
        ids = [entry["id"] for entry in entries]
        if len(ids) != len(set(ids)) or any(not entry.get("section") for entry in entries):
            _err("invalid_choice", "catalog", f"Invalid {group} catalog")
    return value


def options(context: dict | None = None) -> dict:
    context = context or {}
    data = catalog()
    return {"schema_version": 1, "ruleset": RULESET,
            "catalog_version": data["catalog_version"],
            "races": data["races"], "classes": data["classes"], "backgrounds": data["backgrounds"],
            "ability_methods": ["standard_array", "point_buy", "rolled"],
            "fighter_skills": sorted(FIGHTER_SKILLS),
            "barbarian_skills": sorted(BARBARIAN_SKILLS),
            "rogue_skills": sorted(ROGUE_SKILLS),
            "monk_skills": sorted(MONK_SKILLS), "monk_tools": sorted(MONK_TOOLS),
            "paladin_skills": sorted(PALADIN_SKILLS),
            "fighting_styles": [{"id": style, "status": "buildable" if style in ("archery", "defense", "dueling") else "indexed_only"}
                                for style in sorted(STYLES)],
            "languages": sorted(LANGUAGES),
            "notice": "Verified fixed routes: human fighter, barbarian, rogue, monk, or paladin with acolyte."}


def build(data: dict, *, verified_roll: list[int] | None = None) -> dict:
    catalog()
    if not isinstance(data, dict):
        _err("invalid_choice", "$", "Input must be an object")
    allowed = {"schema_version", "ruleset", "name", "backstory", "race", "class", "background",
               "ability_method", "base_abilities", "class_skills", "background_languages",
               "fighting_style", "expertise", "monk_tool", "armor", "shield", "weapon", "roll_event_id", "rolled_assignment"}
    extra = set(data) - allowed
    if extra:
        _err("invalid_choice", sorted(extra)[0], "Unknown mechanical field")
    if data.get("ruleset") != RULESET:
        _err("ruleset_mismatch", "ruleset", f"Expected {RULESET}")
    if data.get("schema_version") != 1:
        _err("ruleset_mismatch", "schema_version", "Expected schema version 1")
    for field in ("race", "class", "background"):
        if field not in data:
            _err("missing_choice", field, f"Choose {field}")
    if data["race"] != "human":
        _err("unsupported_option", "race", f"{data['race']} is not mechanically verified yet")
    if data["class"] not in ("fighter", "barbarian", "rogue", "monk", "paladin"):
        _err("unsupported_option", "class", f"{data['class']} is not mechanically verified yet")
    if data["background"] != "acolyte":
        _err("unsupported_option", "background", f"{data['background']} is not mechanically verified yet")
    barbarian = data["class"] == "barbarian"
    rogue = data["class"] == "rogue"
    monk = data["class"] == "monk"
    paladin = data["class"] == "paladin"
    name = data.get("name", "")
    backstory = data.get("backstory", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or not isinstance(backstory, str) or len(backstory) > 2000:
        _err("invalid_choice", "name/backstory", "Name 1–80, backstory at most 2000 characters")
    base = ability_scores(data, verified_roll)
    scores = {ability: score + 1 for ability, score in base.items()}
    modifiers = {ability: (score - 10) // 2 for ability, score in scores.items()}
    class_skills = data.get("class_skills")
    _unique(class_skills, "class_skills", 4 if rogue else 2)
    allowed_skills = (PALADIN_SKILLS if paladin else ROGUE_SKILLS if rogue else MONK_SKILLS if monk else
                      BARBARIAN_SKILLS if barbarian else FIGHTER_SKILLS)
    if not set(class_skills) <= allowed_skills or set(class_skills) & {"insight", "religion"}:
        _err("invalid_choice", "class_skills", "Choose two class skills not granted by acolyte")
    background_languages = data.get("background_languages")
    _unique(background_languages, "background_languages", 2)
    if not set(background_languages) <= LANGUAGES:
        _err("invalid_choice", "background_languages", "Choose two non-Common standard languages")
    expertise = data.get("expertise")
    if rogue:
        _unique(expertise, "expertise", 2)
        if not set(expertise) <= (set(class_skills) | {"insight", "religion"}):
            _err("invalid_choice", "expertise", "Choose two proficient skills")
    elif "expertise" in data:
        _err("invalid_choice", "expertise", "Expertise is a rogue feature")
    if monk:
        if data.get("monk_tool") not in MONK_TOOLS:
            _err("invalid_choice", "monk_tool", "Choose one supported monk artisan tool or instrument")
    elif "monk_tool" in data:
        _err("invalid_choice", "monk_tool", "Only monks choose a monk tool")
    style = data.get("fighting_style")
    if barbarian or rogue or monk or paladin:
        if "fighting_style" in data:
            _err("invalid_choice", "fighting_style", "This class does not choose a fighting style at level one")
    else:
        if style not in STYLES:
            _err("missing_choice", "fighting_style", "Choose one fighter fighting style")
        if style not in ("archery", "defense", "dueling"):
            _err("unsupported_option", "fighting_style", "This style's action rules are not implemented")
    armor = data.get("armor")
    shield = data.get("shield")
    if type(shield) is not bool:
        _err("missing_choice", "shield", "Specify whether shield is equipped")
    weapon = data.get("weapon")
    archer = not barbarian and style == "archery"
    if paladin:
        if armor != "chain_mail" or not shield or weapon != "longsword":
            _err("unsupported_option", "armor/shield/weapon",
                 "Verified paladin route requires chain mail, donned shield, and longsword")
        ac = 18
    elif monk:
        if armor != "none" or shield or weapon != "shortsword":
            _err("unsupported_option", "armor/shield/weapon",
                 "Verified monk route requires no armor, no shield, and shortsword")
        ac = 10 + modifiers["dex"] + modifiers["wis"]
    elif rogue:
        if armor != "leather_armor" or shield or weapon != "rapier":
            _err("unsupported_option", "armor/shield/weapon",
                 "Verified rogue route requires leather armor, no shield, and rapier")
        ac = 11 + modifiers["dex"]
    elif barbarian:
        if armor != "none" or shield or weapon != "greataxe":
            _err("unsupported_option", "armor/shield/weapon",
                 "Verified barbarian route requires no armor, no shield, and greataxe")
        ac = 10 + modifiers["dex"] + modifiers["con"]
    elif archer:
        if armor != "leather_armor" or shield or weapon != "longbow":
            _err("unsupported_option", "armor/shield/weapon",
                 "Verified archery route requires leather armor, no donned shield, and longbow")
        ac = 11 + modifiers["dex"]
    else:
        if armor != "chain_mail":
            _err("unsupported_option", "armor", "Only the chain-mail melee starter package is verified")
        if weapon != "longsword":
            _err("unsupported_option", "weapon", "Only longsword melee package is verified")
        ac = 16 + (2 if shield else 0) + (1 if style == "defense" else 0)
    skill_set = set(class_skills) | {"insight", "religion"}
    skills = {skill: modifiers[ability] + (4 if rogue and skill in expertise else 2 if skill in skill_set else 0)
              for skill, ability in SKILL_ABILITY.items()}
    save_proficiencies = (("wis", "cha") if paladin else ("dex", "int") if rogue else
                          ("str", "dex") if monk else ("str", "con"))
    saving_throws = {ability: modifiers[ability] + (2 if ability in save_proficiencies else 0)
                     for ability in ABILITIES}
    hit_die = "d8" if rogue or monk else "d12" if barbarian else "d10"
    hp = max(1, (8 if rogue or monk else 12 if barbarian else 10) + modifiers["con"])
    if armor == "chain_mail" and scores["str"] < 13:
        speed = 20
    else:
        speed = 30
    if paladin:
        equipment = [{"id": "longsword", "quantity": 1}, {"id": "shield", "quantity": 1},
                     {"id": "javelin", "quantity": 5}, {"id": "explorers_pack", "quantity": 1},
                     {"id": "chain_mail", "quantity": 1}, {"id": "holy_symbol", "quantity": 1}]
    elif monk:
        equipment = [{"id": "shortsword", "quantity": 1},
                     {"id": "explorers_pack", "quantity": 1},
                     {"id": "dart", "quantity": 10}]
    elif rogue:
        equipment = [{"id": "rapier", "quantity": 1}, {"id": "shortsword", "quantity": 1},
                     {"id": "explorers_pack", "quantity": 1},
                     {"id": "leather_armor", "quantity": 1}, {"id": "dagger", "quantity": 2},
                     {"id": "thieves_tools", "quantity": 1}]
    elif barbarian:
        equipment = [{"id": "greataxe", "quantity": 1},
                     {"id": "handaxe", "quantity": 2},
                     {"id": "explorers_pack", "quantity": 1},
                     {"id": "javelin", "quantity": 4}]
    else:
        equipment = ([{"id": "leather_armor", "quantity": 1},
                      {"id": "longbow", "quantity": 1}, {"id": "arrow", "quantity": 20}]
                     if archer else [{"id": "chain_mail", "quantity": 1}])
        equipment += [{"id": "shield", "quantity": 1},
                      {"id": "longsword", "quantity": 1},
                      {"id": "handaxe", "quantity": 2},
                      {"id": "explorers_pack", "quantity": 1}]
    equipment += [{"id": "holy_symbol", "quantity": 1},
                  {"id": "prayer_book", "quantity": 1},
                  {"id": "incense", "quantity": 5},
                  {"id": "vestments", "quantity": 1},
                  {"id": "common_clothes", "quantity": 1},
                  {"id": "gp", "quantity": 15}]
    if paladin:
        attacks = [{"id": "longsword", "name": "长剑", "attack_bonus": modifiers["str"] + 2,
                    "damage_die": 8, "damage_bonus": modifiers["str"], "reach": 5,
                    "damage_type": "slashing"}]
    elif monk:
        attacks = [{"id": "shortsword", "name": "短剑", "attack_bonus": modifiers["dex"] + 2,
                    "damage_die": 6, "damage_bonus": modifiers["dex"], "reach": 5,
                    "damage_type": "piercing", "monk_weapon": True},
                   {"id": "unarmed_strike", "name": "徒手打击", "attack_bonus": modifiers["dex"] + 2,
                    "damage_die": 4, "damage_bonus": modifiers["dex"], "reach": 5,
                    "damage_type": "bludgeoning", "monk_weapon": True}]
    elif rogue:
        attacks = [{"id": "rapier", "name": "刺剑", "attack_bonus": modifiers["dex"] + 2,
                    "damage_die": 8, "damage_bonus": modifiers["dex"], "reach": 5,
                    "damage_type": "piercing", "finesse": True}]
    elif barbarian:
        attacks = [{"id": "greataxe", "name": "巨斧", "attack_bonus": modifiers["str"] + 2,
                    "damage_die": 12, "damage_bonus": modifiers["str"], "reach": 5,
                    "damage_type": "slashing"}]
    else:
        attacks = ([{"id": "longbow", "name": "长弓", "attack_bonus": modifiers["dex"] + 4,
                     "damage_die": 8, "damage_bonus": modifiers["dex"],
                     "range_normal": 150, "range_long": 600, "damage_type": "piercing"}]
                   if archer else [])
        attacks += [{"id": "longsword", "name": "长剑", "attack_bonus": modifiers["str"] + 2,
                     "damage_die": 8, "damage_bonus": modifiers["str"] + (2 if style == "dueling" else 0),
                     "reach": 5, "damage_type": "slashing"},
                    {"id": "handaxe", "name": "手斧", "attack_bonus": modifiers["str"] + 2,
                     "damage_die": 6, "damage_bonus": modifiers["str"],
                     "range_normal": 20, "range_long": 60, "damage_type": "slashing"}]
    resources = {"hp": {"current": hp, "max": hp},
                 "temp_hp": {"current": 0, "max": None},
                 f"hit_dice_{hit_die}": {"current": 1, "max": 1, "recovery": "long_rest"}}
    if barbarian:
        resources["rage"] = {"current": 2, "max": 2, "recovery": "long_rest"}
    elif paladin:
        senses = max(0, 1 + modifiers["cha"])
        resources["divine_sense"] = {"current": senses, "max": senses, "recovery": "long_rest"}
        resources["lay_on_hands"] = {"current": 5, "max": 5, "recovery": "long_rest"}
    elif not rogue and not monk and not paladin:
        resources["second_wind"] = {"current": 1, "max": 1, "recovery": "short_or_long_rest"}
    if archer:
        resources["ammunition_arrow"] = {"current": 20, "max": 20,
                                          "recovery": "recover_half_after_battle"}
        resources["recoverable_arrow"] = {"current": 0, "max": 20,
                                           "recovery": "battlefield_search"}
    source_choices = {"race": "human", "class": data["class"], "background": "acolyte",
                      "ability_method": data["ability_method"], "base_abilities": base,
                      "roll_event_id": data.get("roll_event_id"),
                      "rolled_assignment": data.get("rolled_assignment"),
                      "class_skills": class_skills, "background_languages": background_languages,
                      "armor": armor, "shield": shield, "weapon": weapon}
    if monk:
        source_choices["monk_tool"] = data["monk_tool"]
    elif rogue:
        source_choices["expertise"] = expertise
    elif not barbarian and not paladin:
        source_choices["fighting_style"] = style
    rule_ids = ["race.human", f"class.{data['class']}", "background.acolyte",
                "character.ability_scores", "character.proficiency", "equipment.weapons_armor"]
    rule_ids += (["class.paladin.divine_sense", "class.paladin.lay_on_hands"]
                 if paladin else ["class.monk.unarmored_defense", "class.monk.martial_arts"]
                 if monk else ["class.rogue.expertise", "class.rogue.sneak_attack", "class.rogue.thieves_cant"]
                 if rogue else ["class.barbarian.rage", "class.barbarian.unarmored_defense"]
                 if barbarian else [f"class.fighter.style.{style}"])
    return {"schema_version": 1, "ruleset": RULESET, "catalog_version": "0.1.0-partial",
            "name": name.strip(), "backstory": backstory,
            "source_choices": source_choices,
            "equipment": equipment,
            "rule_ids": rule_ids,
            "derived": {"level": 1, "abilities": scores, "modifiers": modifiers,
                        "proficiency_bonus": 2, "saving_throws": saving_throws, "skills": skills,
                        "passive_perception": 10 + skills["perception"], "initiative": modifiers["dex"],
                        "ac": ac, "speed": speed, "max_hp": hp, "hit_die": hit_die,
                        "attacks": attacks,
                        "languages": ["common", *background_languages, *(["thieves_cant"] if rogue else [])],
                        "tool_proficiencies": ([data["monk_tool"]] if monk else
                                               ["thieves_tools"] if rogue else [])},
            "resources": resources}


def _read_input(path: str) -> dict:
    source = Path(path)
    if source.stat().st_size > MAX_INPUT:
        _err("invalid_choice", "$", "Input JSON too large")
    return json.loads(source.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    command = parser.add_subparsers(dest="command", required=True)
    for name in ("options", "build"):
        p = command.add_parser(name)
        p.add_argument("--input" if name == "build" else "--context")
    args = parser.parse_args(argv)
    try:
        path = args.input if args.command == "build" else args.context
        data = _read_input(path) if path else {}
        value = build(data) if args.command == "build" else options(data)
    except CharacterError as exc:
        print(json.dumps({"error": {"code": exc.code, "field": exc.field, "message": exc.message}}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": {"code": "invalid_choice", "field": "$", "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
