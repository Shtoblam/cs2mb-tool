"""Tests for the time-only balance verdict."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simulation.balance import time_only_balance  # noqa: E402


class BalanceVerdictTests(unittest.TestCase):
    def test_ct_faster_is_ct_advantage(self) -> None:
        verdict = time_only_balance(
            {
                "T": {"A": {"time_low": 20.0}, "B": {"time_low": 18.0}},
                "CT": {"A": {"time_low": 16.0}, "B": {"time_low": 17.0}},
            }
        )
        self.assertIsNotNone(verdict)
        assert verdict is not None
        self.assertEqual(verdict.side, "CT")
        self.assertEqual(verdict.verdict, "ct_slight")
        self.assertAlmostEqual(verdict.ct_advantage_s, 2.5)

    def test_t_faster_is_t_advantage(self) -> None:
        verdict = time_only_balance(
            {
                "T": {"A": {"time_low": 15.0}, "B": {"time_low": 18.0}},
                "CT": {"A": {"time_low": 19.0}, "B": {"time_low": 22.0}},
            }
        )
        self.assertIsNotNone(verdict)
        assert verdict is not None
        self.assertEqual(verdict.side, "T")
        self.assertEqual(verdict.verdict, "t_clear")

    def test_close_times_are_balanced(self) -> None:
        verdict = time_only_balance(
            {
                "T": {"A": {"time_low": 20.0}},
                "CT": {"A": {"time_low": 20.7}},
            }
        )
        self.assertIsNotNone(verdict)
        assert verdict is not None
        self.assertEqual(verdict.side, "balanced")
        self.assertEqual(verdict.verdict, "balanced")
        self.assertEqual(verdict.targets, ("A",))

    def test_missing_common_targets_returns_none(self) -> None:
        self.assertIsNone(time_only_balance({"T": {"Mid": {"time_low": 10.0}}}))
        self.assertIsNone(time_only_balance({}))


if __name__ == "__main__":
    unittest.main()
