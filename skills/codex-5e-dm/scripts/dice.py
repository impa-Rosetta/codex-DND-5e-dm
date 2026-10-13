"""SRD 5.1 dice rolling boundary for the Codex 5e DM project.

This module reports dice facts only. The caller decides whether a result hits,
succeeds, crits, or changes campaign state, then records this exact result in
the committed event. It does not write files or reroll on retry.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from collections.abc import Callable


MAX_DICE = 100
MAX_SIDES = 1000
MAX_ABS_MODIFIER = 10_000
EXPRESSION = re.compile(
    r"(?P<count>[1-9][0-9]*)?d(?P<sides>[1-9][0-9]*)(?P<modifier>[+-](?:0|[1-9][0-9]*))?"
)
MODES = frozenset({"normal", "advantage", "disadvantage"})


def parse_expression(expression: str) -> tuple[int, int, int, str]:
    """Return count, sides, modifier, and normalized source expression."""
    if not isinstance(expression, str):
        raise ValueError("Dice expression must be text")
    normalized = expression.strip()
    match = EXPRESSION.fullmatch(normalized)
    if match is None:
        raise ValueError("Use d20 or NdS with one optional +N/-N modifier")

    count = int(match.group("count") or 1)
    sides = int(match.group("sides"))
    modifier = int(match.group("modifier") or 0)
    if count > MAX_DICE:
        raise ValueError(f"No more than {MAX_DICE} dice may be rolled at once")
    if sides > MAX_SIDES:
        raise ValueError(f"A die may have no more than {MAX_SIDES} sides")
    if abs(modifier) > MAX_ABS_MODIFIER:
        raise ValueError(f"Modifier magnitude may not exceed {MAX_ABS_MODIFIER}")
    return count, sides, modifier, normalized


def roll_dice(
    expression: str,
    *,
    purpose: str,
    mode: str = "normal",
    roller: Callable[[int], int] | None = None,
) -> dict[str, object]:
    """Roll once and return auditable dice facts, without rule adjudication.

    ``roller`` is a deterministic test seam. Production callers omit it and use
    ``secrets.randbelow``. Advantage/disadvantage are valid only for one d20;
    the rules layer resolves simultaneous advantage and disadvantage to normal.
    """
    count, sides, modifier, normalized = parse_expression(expression)
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 120:
        raise ValueError("Purpose must be nonempty text of at most 120 characters")
    if mode not in MODES:
        raise ValueError("Mode must be normal, advantage, or disadvantage")
    if mode != "normal" and (count != 1 or sides != 20):
        raise ValueError("Advantage and disadvantage require exactly one d20")

    draw = roller if roller is not None else lambda die_sides: secrets.randbelow(die_sides) + 1
    draws = 2 if mode != "normal" else count
    raw: list[int] = []
    for _ in range(draws):
        value = draw(sides)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= sides:
            raise ValueError("Roller returned a value outside the die's range")
        raw.append(value)

    if mode == "advantage":
        kept_indices = [0 if raw[0] >= raw[1] else 1]
    elif mode == "disadvantage":
        kept_indices = [0 if raw[0] <= raw[1] else 1]
    else:
        kept_indices = list(range(count))

    kept = [raw[index] for index in kept_indices]
    return {
        "schema_version": 1,
        "purpose": purpose.strip(),
        "expression": normalized,
        "mode": mode,
        "count": count,
        "sides": sides,
        "raw": raw,
        "kept_indices": kept_indices,
        "kept": kept,
        "modifier": modifier,
        "total": sum(kept) + modifier,
        "natural_d20": kept[0] if count == 1 and sides == 20 else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roll auditable SRD 5.1 dice")
    commands = parser.add_subparsers(dest="command", required=True)
    roll_parser = commands.add_parser("roll", help="roll a dice expression once")
    roll_parser.add_argument("expression", help="d20, NdS, or NdS+N / NdS-N")
    roll_parser.add_argument("--purpose", required=True, help="reason for this roll")
    roll_parser.add_argument("--mode", choices=sorted(MODES), default="normal")
    args = parser.parse_args(argv)

    try:
        result = roll_dice(args.expression, purpose=args.purpose, mode=args.mode)
    except ValueError as exc:
        print(
            json.dumps({"error": {"code": "invalid_request", "message": str(exc)}}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
