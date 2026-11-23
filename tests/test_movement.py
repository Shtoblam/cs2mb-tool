"""Tests for the calibrated straight-line movement model."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from movement.source import (  # noqa: E402
    MoveProfile,
    jump_airtime,
    jump_height,
    simulate_straight,
    steady_state_speed,
)


class MovementModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = MoveProfile.from_file()

    def test_measured_steady_state_speeds(self) -> None:
        self.assertAlmostEqual(
            steady_state_speed(215.0, self.profile), 215.0, places=3
        )
        self.assertAlmostEqual(
            steady_state_speed(250.0, self.profile), 250.0, places=3
        )
        self.assertAlmostEqual(
            steady_state_speed(200.0, self.profile), 200.0, places=3
        )
        self.assertAlmostEqual(
            steady_state_speed(
                215.0, self.profile, self.profile.walk_modifier
            ),
            111.8,
            places=3,
        )
        self.assertAlmostEqual(
            steady_state_speed(
                215.0, self.profile, self.profile.crouch_modifier
            ),
            73.1,
            places=3,
        )

    def test_weapon_speed_cap(self) -> None:
        self.assertAlmostEqual(
            steady_state_speed(400.0, self.profile), 320.0, places=3
        )

    def test_straight_line_time_includes_acceleration(self) -> None:
        result = simulate_straight(1000.0, 215.0, self.profile)
        naive = 1000.0 / 215.0
        self.assertGreater(result.time, naive)
        self.assertLess(result.time, naive + 0.5)
        self.assertAlmostEqual(result.average_speed, 207.49, places=1)
        self.assertGreaterEqual(result.distance, 1000.0)
        self.assertLess(result.distance, 1000.0 + result.final_speed / 128.0 + 1.0)

    def test_jump_derived_values(self) -> None:
        self.assertAlmostEqual(jump_airtime(self.profile), 0.7549825, places=6)
        self.assertAlmostEqual(jump_height(self.profile), 56.9999, places=3)

    def test_zero_distance(self) -> None:
        result = simulate_straight(0.0, 215.0, self.profile)
        self.assertEqual(result.time, 0.0)
        self.assertEqual(result.ticks, 0)

    def test_monotonic_distance(self) -> None:
        previous = -1.0
        for distance in (100.0, 500.0, 1000.0, 2000.0):
            result = simulate_straight(distance, 215.0, self.profile)
            self.assertGreater(result.time, previous)
            previous = result.time
            self.assertTrue(math.isfinite(result.time))


if __name__ == "__main__":
    unittest.main()
