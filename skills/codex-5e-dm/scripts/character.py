"""Deterministic, deliberately bounded SRD 5.1 level-one character builder.

Only verified human/fighter/acolyte is buildable in this release. Listing an
option never implies it has a complete mechanical implementation.
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
            "fighting_styles": [{"id": style, "status": "buildable" if style == "defense" else "indexed_only"}
                                for style in sorted(STYLES)],
            "languages": sorted(LANGUAGES),
            "notice": "Only human fighter with acolyte background is currently mechanically verified."}


def build(data: dict, *, verified_roll: list[int] | None = None) -> dict:
    catalog()
    if not isinstance(data, dict):
        _err("invalid_choice", "$", "Input must be an object")
    allowed = {"schema_version", "ruleset", "name", "backstory", "race", "class", "background",
               "ability_method", "base_abilities", "class_skills", "background_languages",
               "fighting_style", "armor", "shield", "roll_event_id", "rolled_assignment"}
    extra = set(data) - allowed
    if extra:
        _err("invalid_choice", sorted(extra)[0], "Unknown mechanical field")
    if data.get("ruleset") != RULESET:
        _err("ruleset_mismatch", "ruleset", f"Expected {RULESET}")
    if data.get("schema_version") != 1:
        _err("ruleset_mismatch", "schema_version", "Expected schema version 1")
    for field, supported in (("race", "human"), ("class", "fighter"), ("background", "acolyte")):
        if field not in data:
            _err("missing_choice", field, f"Choose {field}")
        if data[field] != supported:
            _err("unsupported_option", field, f"{data[field]} is not mechanically verified yet")
    name = data.get("name", "")
    backstory = data.get("backstory", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or not isinstance(backstory, str) or len(backstory) > 2000:
        _err("invalid_choice", "name/backstory", "Name 1–80, backstory at most 2000 characters")
    base = ability_scores(data, verified_roll)
    scores = {ability: score + 1 for ability, score in base.items()}
    modifiers = {ability: (score - 10) // 2 for ability, score in scores.items()}
    class_skills = data.get("class_skills")
    _unique(class_skills, "class_skills", 2)
    if not set(class_skills) <= FIGHTER_SKILLS or set(class_skills) & {"insight", "religion"}:
        _err("invalid_choice", "class_skills", "Choose two fighter skills not granted by acolyte")
    background_languages = data.get("background_languages")
    _unique(background_languages, "background_languages", 2)
    if not set(background_languages) <= LANGUAGES:
        _err("invalid_choice", "background_languages", "Choose two non-Common standard languages")
    style = data.get("fighting_style")
    if style not in STYLES:
        _err("missing_choice", "fighting_style", "Choose one fighter fighting style")
    if style != "defense":
        _err("unsupported_option", "fighting_style", "This style's action rules are not implemented")
    armor = data.get("armor")
    if armor not in ("chain_mail", "leather", "none"):
        _err("invalid_choice", "armor", "Choose chain_mail, leather, or none")
    shield = data.get("shield")
    if type(shield) is not bool:
        _err("missing_choice", "shield", "Specify whether shield is equipped")
    if armor == "chain_mail":
        ac = 16
    elif armor == "leather":
        ac = 11 + modifiers["dex"]
    else:
        ac = 10 + modifiers["dex"]
    if shield:
        ac += 2
    if style == "defense" and armor != "none":
        ac += 1
    skill_set = set(class_skills) | {"insight", "religion"}
    skills = {skill: modifiers[ability] + (2 if skill in skill_set else 0)
              for skill, ability in SKILL_ABILITY.items()}
    saving_throws = {ability: modifiers[ability] + (2 if ability in ("str", "con") else 0)
                     for ability in ABILITIES}
    hp = max(1, 10 + modifiers["con"])
    if armor == "chain_mail" and scores["str"] < 13:
        speed = 20
    else:
        speed = 30
    return {"schema_version": 1, "ruleset": RULESET, "catalog_version": "0.1.0-partial",
            "name": name.strip(), "backstory": backstory,
            "source_choices": {"race": "human", "class": "fighter", "background": "acolyte",
                               "ability_method": data["ability_method"], "base_abilities": base,
                               "roll_event_id": data.get("roll_event_id"),
                               "rolled_assignment": data.get("rolled_assignment"),
                               "class_skills": class_skills, "background_languages": background_languages,
                               "fighting_style": style, "armor": armor, "shield": shield},
            "rule_ids": ["race.human", "class.fighter", "background.acolyte",
                         "character.ability_scores", "character.proficiency", "equipment.weapons_armor"],
            "derived": {"level": 1, "abilities": scores, "modifiers": modifiers,
                        "proficiency_bonus": 2, "saving_throws": saving_throws, "skills": skills,
                        "passive_perception": 10 + skills["perception"], "initiative": modifiers["dex"],
                        "ac": ac, "speed": speed, "max_hp": hp, "hit_die": "d10",
                        "languages": ["common", *background_languages]},
            "resources": {"hp": {"current": hp, "max": hp},
                          "temp_hp": {"current": 0, "max": None},
                          "second_wind": {"current": 1, "max": 1, "recovery": "short_or_long_rest"},
                          "hit_dice_d10": {"current": 1, "max": 1, "recovery": "long_rest"}}}


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
