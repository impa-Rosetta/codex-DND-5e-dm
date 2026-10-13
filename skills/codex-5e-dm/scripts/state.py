"""Append-only campaign events and recoverable snapshots (schema version 1)."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


RULESET = "srd-5.1-2014"
FILES = ("manifest.json", "state.json", "events.jsonl", "world.md")


class StateError(ValueError):
    pass


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise StateError(f"{path.name} must contain an object")
    return value


def _atomic(path: Path, value: dict) -> None:
    data = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def create(directory: str | Path, name: str) -> dict:
    path = Path(directory).resolve()
    if not name.strip() or len(name) > 120:
        raise StateError("Campaign name must have 1–120 characters")
    if path.exists() and any(path.iterdir()):
        raise StateError("Campaign directory must be empty")
    path.mkdir(parents=True, exist_ok=True)
    campaign_id = str(uuid.uuid4())
    manifest = {"schema_version": 1, "campaign_id": campaign_id, "name": name.strip(),
                "ruleset": RULESET, "created_at": _utc()}
    state = {"schema_version": 1, "campaign_id": campaign_id, "revision": 0,
             "last_applied_event_id": None, "character": None,
             "scene": {"location_id": "old_mill", "name": "旧磨坊路口",
                       "discovered_locations": ["old_mill"], "discovered_connections": []},
             "combat": None, "world_time": None, "recent_public_events": []}
    _atomic(path / "manifest.json", manifest)
    _atomic(path / "state.json", state)
    (path / "events.jsonl").touch(exist_ok=False)
    (path / "world.md").write_text("# 旧磨坊路口\n\n旅人失踪，磨坊主的女儿请求帮忙。林中岔路尚未发现。\n", encoding="utf-8")
    return {"manifest": manifest, "state": state}


def _events(path: Path, campaign_id: str) -> list[dict]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise StateError(f"Cannot read events.jsonl: {exc}") from exc
    if raw and not raw.endswith(b"\n"):
        raise StateError("events.jsonl has an incomplete final line")
    result, event_ids, operation_ids = [], set(), set()
    for line_no, line in enumerate(raw.splitlines(), 1):
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateError(f"Invalid event at line {line_no}: {exc}") from exc
        if not isinstance(event, dict) or event.get("schema_version") != 1 or event.get("campaign_id") != campaign_id or event.get("seq") != line_no:
            raise StateError(f"Invalid event identity or sequence at line {line_no}")
        try:
            uuid.UUID(event["event_id"])
            uuid.UUID(event["operation_id"])
        except (KeyError, ValueError, TypeError) as exc:
            raise StateError(f"Invalid event UUID at line {line_no}") from exc
        if event["event_id"] in event_ids or event["operation_id"] in operation_ids:
            raise StateError(f"Duplicate event or operation at line {line_no}")
        if not isinstance(event.get("payload"), dict) or event.get("visibility") not in ("public", "dm_private"):
            raise StateError(f"Invalid payload or visibility at line {line_no}")
        event_ids.add(event["event_id"])
        operation_ids.add(event["operation_id"])
        result.append(event)
    return result


def apply_event(state: dict, event: dict) -> dict:
    if event["seq"] != state["revision"] + 1:
        raise StateError("Non-contiguous event replay")
    result = copy.deepcopy(state)
    payload = event["payload"]
    kind = event["type"]
    if kind == "character.created":
        if result["character"] is not None:
            raise StateError("Character already exists")
        result["character"] = copy.deepcopy(payload["character"])
    elif kind == "location.discovered":
        location_id = payload["location_id"]
        if location_id not in result["scene"]["discovered_locations"]:
            result["scene"]["discovered_locations"].append(location_id)
    elif kind == "scene.moved":
        if payload["location_id"] not in result["scene"]["discovered_locations"]:
            raise StateError("Cannot move to undiscovered location")
        result["scene"].update(location_id=payload["location_id"], name=payload["name"])
    elif kind == "combat.started":
        if result["combat"] is not None:
            raise StateError("Combat already active")
        result["combat"] = copy.deepcopy(payload["combat"])
    elif kind == "combat.ended":
        result["combat"] = None
    elif kind == "combat.attack_resolved":
        target = payload["target_combatant_id"]
        for combatant in result["combat"]["combatants"]:
            if combatant["combatant_id"] == target:
                combatant["hp"] = payload["hp_after"]
                combatant["temp_hp"] = payload["temp_hp_after"]
                if result["character"] and combatant["combatant_id"] == result["character"]["id"]:
                    result["character"]["resources"]["hp"]["current"] = payload["hp_after"]
                    result["character"]["resources"]["temp_hp"]["current"] = payload["temp_hp_after"]
                break
        else:
            raise StateError("Unknown target combatant")
        result["combat"]["action_used"] = True
    elif kind == "turn.advanced":
        result["combat"]["turn_index"] = payload["turn_index"]
        result["combat"]["round"] = payload["round"]
        result["combat"]["action_used"] = False
        result["combat"]["bonus_action_used"] = False
        result["combat"]["movement_used"] = 0
    elif kind == "position.changed":
        for combatant in result["combat"]["combatants"]:
            if combatant["combatant_id"] == payload["combatant_id"]:
                combatant["position"] = payload["to"]
                break
        else:
            raise StateError("Unknown moving combatant")
        result["combat"]["movement_used"] += payload["feet"]
    elif kind == "resource.changed":
        resource = result["character"]["resources"][payload["resource_id"]]
        resource["current"] = payload["after"]
    elif kind in ("character.ability_scores_rolled", "dice.rolled", "check.resolved", "player.declared", "scene.narrated"):
        pass
    else:
        raise StateError(f"Unsupported event type: {kind}")
    if event["visibility"] == "public":
        result["recent_public_events"] = (result["recent_public_events"] + [{
            "event_id": event["event_id"], "seq": event["seq"], "type": kind,
            "timestamp": event["timestamp"], "view": payload.get("public_view", {})
        }])[-30:]
    result["revision"] = event["seq"]
    result["last_applied_event_id"] = event["event_id"]
    return result


def load(directory: str | Path) -> tuple[dict, dict, list[dict]]:
    path = Path(directory).resolve()
    manifest = _json(path / "manifest.json")
    if manifest.get("schema_version") != 1 or manifest.get("ruleset") != RULESET:
        raise StateError("Unsupported campaign schema or ruleset")
    state = _json(path / "state.json")
    if state.get("schema_version") != 1 or state.get("campaign_id") != manifest["campaign_id"]:
        raise StateError("Snapshot identity mismatch")
    events = _events(path / "events.jsonl", manifest["campaign_id"])
    revision = state.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0 or revision > len(events):
        raise StateError("Snapshot revision is invalid or ahead of log")
    if revision and state.get("last_applied_event_id") != events[revision - 1]["event_id"]:
        raise StateError("Snapshot event ID mismatch")
    if not revision and state.get("last_applied_event_id") is not None:
        raise StateError("Initial snapshot has an event ID")
    if revision < len(events):
        for event in events[revision:]:
            state = apply_event(state, event)
        _atomic(path / "state.json", state)
    return manifest, state, events


def commit(directory: str | Path, operation_id: str, kind: str, payload: dict, *,
           rules: list[str] | None = None, actor_id: str | None = None,
           visibility: str = "public", causation_event_id: str | None = None) -> tuple[dict, dict]:
    uuid.UUID(operation_id)
    path = Path(directory).resolve()
    manifest, state, events = load(path)
    for existing in events:
        if existing["operation_id"] == operation_id:
            if existing["type"] != kind:
                raise StateError("Operation ID belongs to a different event type")
            return existing, state
    event = {"schema_version": 1, "campaign_id": manifest["campaign_id"],
             "seq": len(events) + 1, "event_id": str(uuid.uuid4()),
             "operation_id": operation_id, "timestamp": _utc(), "type": kind,
             "visibility": visibility, "actor_id": actor_id,
             "causation_event_id": causation_event_id, "rules": rules or [], "payload": payload}
    next_state = apply_event(state, event)
    encoded = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    with (path / "events.jsonl").open("ab") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    _atomic(path / "state.json.bak", state)
    _atomic(path / "state.json", next_state)
    return event, next_state


def public_snapshot(state: dict, manifest: dict) -> dict:
    source_scene = state["scene"]
    scene = {key: source_scene[key] for key in
             ("location_id", "name", "discovered_locations", "discovered_connections")
             if key in source_scene}
    combat = state["combat"]
    if combat is not None:
        combat = {"round": combat["round"], "turn_index": combat["turn_index"],
                  "combatants": [{key: unit.get(key) for key in
                                   ("combatant_id", "name", "hp", "temp_hp", "ac", "position")}
                                  for unit in combat["combatants"]]}
    return {"schema_version": 1, "campaign_id": manifest["campaign_id"],
            "name": manifest["name"], "revision": state["revision"],
            "last_applied_event_id": state["last_applied_event_id"],
            "character": state["character"], "scene": scene,
            "combat": combat, "events": state["recent_public_events"]}


def confirm_character(directory: str | Path, operation_id: str, choices: dict) -> tuple[dict, dict]:
    """Validate a candidate and commit it once; never trust a caller-computed card."""
    _, snapshot, events = load(directory)
    for event in events:
        if event["operation_id"] == operation_id:
            if event["type"] != "character.created":
                raise StateError("Operation ID belongs to a different event type")
            return event, snapshot
    if snapshot["character"] is not None:
        raise StateError("Campaign already has a character")
    card = preview_character(directory, choices, loaded_events=events)
    card["id"] = str(uuid.uuid4())
    payload = {"character": card, "catalog_version": card["catalog_version"],
               "source_choices": card["source_choices"],
               "public_view": {"summary": f"{card['name']}加入冒险。"}}
    return commit(directory, operation_id, "character.created", payload,
                  rules=card["rule_ids"], actor_id=card["id"])


def _sibling_module(name: str):
    spec = importlib.util.spec_from_file_location(f"campaign_{name}", Path(__file__).resolve().with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def roll_ability_scores(directory: str | Path, operation_id: str, *, roller=None) -> tuple[dict, dict]:
    _, snapshot, events = load(directory)
    for event in events:
        if event["operation_id"] == operation_id:
            if event["type"] != "character.ability_scores_rolled":
                raise StateError("Operation ID belongs to a different event type")
            return event, snapshot
    if snapshot["character"] is not None:
        raise StateError("Character already created")
    dice = _sibling_module("dice")
    groups = []
    for index in range(6):
        result = dice.roll_dice("4d6", purpose=f"ability_score_{index + 1}", roller=roller)
        raw = result["raw"]
        dropped_index = raw.index(min(raw))
        kept = [value for i, value in enumerate(raw) if i != dropped_index]
        groups.append({"raw": raw, "dropped_index": dropped_index,
                       "kept": kept, "total": sum(kept)})
    return commit(directory, operation_id, "character.ability_scores_rolled",
                  {"groups": groups, "public_view": {"summary": "完成六组属性掷骰。",
                                                     "totals": [g["total"] for g in groups]}},
                  rules=["character.ability_scores"])


def preview_character(directory: str | Path, choices: dict, *, loaded_events: list[dict] | None = None) -> dict:
    if loaded_events is None:
        _, _, loaded_events = load(directory)
    verified = None
    if choices.get("ability_method") == "rolled":
        event_id = choices.get("roll_event_id")
        event = next((item for item in loaded_events if item["event_id"] == event_id), None)
        if event is None or event["type"] != "character.ability_scores_rolled":
            raise StateError("unverified_roll: no matching campaign roll event")
        verified = [group["total"] for group in event["payload"]["groups"]]
    return _sibling_module("character").build(choices, verified_roll=verified)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create"); p.add_argument("directory"); p.add_argument("--name", required=True)
    p = sub.add_parser("load"); p.add_argument("directory")
    p = sub.add_parser("commit"); p.add_argument("directory"); p.add_argument("--operation-id", required=True)
    p.add_argument("--type", required=True); p.add_argument("--payload", required=True)
    p = sub.add_parser("confirm-character"); p.add_argument("directory")
    p.add_argument("--operation-id", required=True); p.add_argument("--input", required=True)
    p = sub.add_parser("preview-character"); p.add_argument("directory"); p.add_argument("--input", required=True)
    p = sub.add_parser("roll-abilities"); p.add_argument("directory"); p.add_argument("--operation-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            value = create(args.directory, args.name)
        elif args.command == "load":
            manifest, state, _ = load(args.directory)
            value = public_snapshot(state, manifest)
        elif args.command == "confirm-character":
            event, state = confirm_character(args.directory, args.operation_id, _json(Path(args.input)))
            value = {"event": event, "state": state}
        elif args.command == "preview-character":
            value = preview_character(args.directory, _json(Path(args.input)))
        elif args.command == "roll-abilities":
            event, state = roll_ability_scores(args.directory, args.operation_id)
            value = {"event": event, "state": state}
        else:
            event, state = commit(args.directory, args.operation_id, args.type,
                                  _json(Path(args.payload)))
            value = {"event": event, "state": state}
    except (StateError, ValueError, KeyError, OSError) as exc:
        print(json.dumps({"error": {"code": "invalid_state", "message": str(exc)}}), file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
