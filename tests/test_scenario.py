"""Tests for the time-only 5-player rush envelope."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simulation.scenario import rush_envelope, split_envelope  # noqa: E402


class RushEnvelopeTests(unittest.TestCase):
    def test_all_subsets_are_enumerated(self) -> None:
        envelope = rush_envelope(
            [float(i) for i in range(1, 16)],
            [float(i + 1) for i in range(1, 16)],
            team_size=5,
        )
        self.assertEqual(envelope.n_teams, math.comb(15, 5))
        self.assertEqual(envelope.team_size, 5)
        self.assertLessEqual(envelope.low_p10, envelope.low_median)
        self.assertLessEqual(envelope.low_median, envelope.low_p90)
        self.assertLessEqual(envelope.low_median, envelope.high_median)
        self.assertLessEqual(envelope.high_median, envelope.high_p90)

    def test_equal_times_have_zero_spread(self) -> None:
        envelope = rush_envelope([5.0] * 15, [7.0] * 15)
        self.assertEqual(envelope.n_teams, 3003)
        self.assertAlmostEqual(envelope.low_p10, 5.0)
        self.assertAlmostEqual(envelope.low_median, 5.0)
        self.assertAlmostEqual(envelope.low_p90, 5.0)
        self.assertAlmostEqual(envelope.high_median, 7.0)
        self.assertAlmostEqual(envelope.high_p90, 7.0)

    def test_single_player_uses_spawn_distribution(self) -> None:
        envelope = rush_envelope(
            [float(i) for i in range(1, 16)],
            [float(i + 1) for i in range(1, 16)],
            team_size=1,
        )
        self.assertEqual(envelope.n_teams, 15)
        self.assertAlmostEqual(envelope.low_median, 8.0)
        self.assertAlmostEqual(envelope.low_p10, 2.4)
        self.assertAlmostEqual(envelope.low_p90, 13.6)

    def test_invalid_inputs_raise(self) -> None:
        with self.assertRaises(ValueError):
            rush_envelope([1.0], [1.0, 2.0])
        with self.assertRaises(ValueError):
            rush_envelope([1.0, 2.0], [1.0, 2.0], team_size=3)

    def test_split_envelope_uses_quotas_and_assignments(self) -> None:
        spawn_times = [
            {
                "A": (10.0, 20.0),
                "B": (20.0, 30.0),
                "Mid": (30.0, 40.0),
            }
            for _ in range(15)
        ]
        envelope = split_envelope(
            spawn_times,
            {"A": 2, "B": 2, "Mid": 1},
        )
        self.assertEqual(envelope.n_teams, 3003)
        self.assertEqual(envelope.n_samples, 3003)
        self.assertEqual(envelope.n_assignments, 30)
        self.assertEqual(envelope.policy, "optimal")
        self.assertAlmostEqual(envelope.targets["A"].low_median, 10.0)
        self.assertAlmostEqual(envelope.targets["B"].low_median, 20.0)
        self.assertAlmostEqual(envelope.targets["Mid"].low_median, 30.0)

    def test_split_optimal_assignment(self) -> None:
        spawn_times = [
            {"A": (1.0, 2.0), "B": (100.0, 101.0), "Mid": (100.0, 101.0)},
            {"A": (100.0, 101.0), "B": (1.0, 2.0), "Mid": (100.0, 101.0)},
            {"A": (100.0, 101.0), "B": (100.0, 101.0), "Mid": (1.0, 2.0)},
        ]
        envelope = split_envelope(
            spawn_times,
            {"A": 1, "B": 1, "Mid": 1},
        )
        self.assertEqual(envelope.n_teams, 1)
        self.assertEqual(envelope.n_assignments, 6)
        for target in ("A", "B", "Mid"):
            self.assertAlmostEqual(envelope.targets[target].low_median, 1.0)

    def test_random_policy_is_seeded_and_reproducible(self) -> None:
        spawn_times = [
            {
                "A": (float(i % 5), float(i % 5) + 10.0),
                "B": (float((i * 3) % 7), float((i * 3) % 7) + 10.0),
                "Mid": (float((i * 5) % 9), float((i * 5) % 9) + 10.0),
            }
            for i in range(15)
        ]
        first = split_envelope(
            spawn_times,
            {"A": 2, "B": 2, "Mid": 1},
            policy="random",
            seed=7,
            samples_per_team=4,
        )
        second = split_envelope(
            spawn_times,
            {"A": 2, "B": 2, "Mid": 1},
            policy="random",
            seed=7,
            samples_per_team=4,
        )
        self.assertEqual(first.n_samples, 3003 * 4)
        self.assertEqual(first.targets, second.targets)
        self.assertEqual(first.policy, "random")

    def test_softmax_policy_and_validation(self) -> None:
        spawn_times = [
            {
                "A": (10.0, 20.0),
                "B": (20.0, 30.0),
                "Mid": (30.0, 40.0),
            }
            for _ in range(15)
        ]
        envelope = split_envelope(
            spawn_times,
            {"A": 2, "B": 2, "Mid": 1},
            policy="softmax",
            seed=3,
            samples_per_team=2,
            temperature=5.0,
        )
        self.assertEqual(envelope.n_samples, 3003 * 2)
        self.assertEqual(envelope.policy, "softmax")
        with self.assertRaises(ValueError):
            split_envelope(
                spawn_times,
                {"A": 2, "B": 2, "Mid": 1},
                policy="softmax",
                temperature=0.0,
            )
        with self.assertRaises(ValueError):
            split_envelope(
                spawn_times,
                {"A": 2, "B": 2, "Mid": 1},
                policy="unknown",
            )

    def test_split_two_player_group_median(self) -> None:
        spawn_times = [
            {"A": (1.0, 2.0)},
            {"A": (3.0, 4.0)},
        ]
        envelope = split_envelope(spawn_times, {"A": 2})
        self.assertAlmostEqual(envelope.targets["A"].low_median, 2.0)
        self.assertAlmostEqual(envelope.targets["A"].high_median, 3.0)


if __name__ == "__main__":
    unittest.main()
