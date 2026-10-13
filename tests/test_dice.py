"""Tests for the M2 dice boundary; no campaign state is written here."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "codex-5e-dm" / "scripts" / "dice.py"
sys.path.insert(0, str(SCRIPT.parent))

import dice  # noqa: E402


def fixed_rolls(*values: int):
    rolls = iter(values)

    def roll_one(sides: int) -> int:
        return next(rolls)

    return roll_one


class DiceTests(unittest.TestCase):
    def test_plain_d20_with_modifier(self):
        result = dice.roll_dice("d20+5", purpose="attack", roller=fixed_rolls(14))
        self.assertEqual(result["raw"], [14])
        self.assertEqual(result["kept"], [14])
        self.assertEqual(result["modifier"], 5)
        self.assertEqual(result["total"], 19)
        self.assertEqual(result["natural_d20"], 14)
        self.assertNotIn("success", result)
        self.assertNotIn("critical", result)

    def test_multiple_dice_and_negative_modifier(self):
        result = dice.roll_dice("2d6-1", purpose="damage", roller=fixed_rolls(2, 6))
        self.assertEqual(result["raw"], [2, 6])
        self.assertEqual(result["kept"], [2, 6])
        self.assertEqual(result["total"], 7)
        self.assertIsNone(result["natural_d20"])

    def test_advantage_keeps_higher_natural_die(self):
        result = dice.roll_dice(
            "1d20+3", purpose="check", mode="advantage", roller=fixed_rolls(4, 17)
        )
        self.assertEqual(result["raw"], [4, 17])
        self.assertEqual(result["kept"], [17])
        self.assertEqual(result["kept_indices"], [1])
        self.assertEqual(result["total"], 20)
        self.assertEqual(result["natural_d20"], 17)

    def test_disadvantage_keeps_lower_natural_die(self):
        result = dice.roll_dice(
            "d20-2", purpose="save", mode="disadvantage", roller=fixed_rolls(17, 5)
        )
        self.assertEqual(result["raw"], [17, 5])
        self.assertEqual(result["kept"], [5])
        self.assertEqual(result["kept_indices"], [1])
        self.assertEqual(result["total"], 3)

    def test_equal_advantage_rolls_keep_first_for_provenance(self):
        result = dice.roll_dice(
            "d20", purpose="check", mode="advantage", roller=fixed_rolls(9, 9)
        )
        self.assertEqual(result["kept_indices"], [0])

    def test_natural_twenty_and_one_are_not_adjudicated(self):
        twenty = dice.roll_dice("d20-10", purpose="check", roller=fixed_rolls(20))
        one = dice.roll_dice("d20+10", purpose="check", roller=fixed_rolls(1))
        self.assertEqual(twenty["natural_d20"], 20)
        self.assertEqual(one["natural_d20"], 1)
        self.assertNotIn("critical", twenty)
        self.assertNotIn("automatic_failure", one)

    def test_bad_expressions_are_rejected(self):
        for expression in ("", "0d6", "1d0", "2d6+", "2d6+1d4", "d20/2", "101d6", "d1001"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                dice.roll_dice(expression, purpose="test", roller=fixed_rolls(1))

    def test_advantage_only_applies_to_one_d20(self):
        for expression in ("2d20", "1d8"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                dice.roll_dice(expression, purpose="test", mode="advantage")

    def test_invalid_purpose_mode_and_roller_value_are_rejected(self):
        with self.assertRaises(ValueError):
            dice.roll_dice("d20", purpose=" ")
        with self.assertRaises(ValueError):
            dice.roll_dice("d20", purpose="test", mode="both")
        with self.assertRaises(ValueError):
            dice.roll_dice("d20", purpose="test", roller=fixed_rolls(21))

    def test_cli_emits_one_json_result(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "roll", "d20+5", "--purpose", "attack"],
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["purpose"], "attack")
        self.assertEqual(result["expression"], "d20+5")
        self.assertEqual(result["total"], result["natural_d20"] + 5)
        self.assertEqual(completed.stderr, "")

    def test_cli_invalid_expression_is_nonzero_json_error(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "roll", "d0", "--purpose", "attack"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stderr)["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
