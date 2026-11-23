"""Tests for route-level vertical and turn profiling."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from movement.route import route_profile  # noqa: E402
from movement.source import MoveProfile, simulate_straight  # noqa: E402


class RouteProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.move = MoveProfile.from_file()

    def test_flat_route_matches_straight_model(self) -> None:
        profile = route_profile(
            [(0.0, 0.0, 0.0), (300.0, 0.0, 0.0), (1000.0, 0.0, 0.0)],
            215.0,
            self.move,
        )
        expected = simulate_straight(1000.0, 215.0, self.move).time
        self.assertAlmostEqual(profile.xy_distance, 1000.0, places=6)
        self.assertAlmostEqual(profile.distance_3d, 1000.0, places=6)
        self.assertAlmostEqual(profile.ideal_time, expected, places=9)
        expected_stop_go = (
            simulate_straight(300.0, 215.0, self.move).time
            + simulate_straight(700.0, 215.0, self.move).time
        )
        self.assertAlmostEqual(profile.stop_go_time, expected_stop_go, places=9)
        self.assertGreater(profile.time_high, profile.time_low)
        self.assertEqual(profile.vertical_transitions, 0)
        self.assertFalse(profile.has_vertical)
        self.assertEqual(profile.turn_count, 0)
        self.assertEqual(profile.jump_up_candidates, 0)
        self.assertEqual(profile.jump_budget, 0.0)
        self.assertEqual(profile.time_high_with_jumps, profile.time_high)

    def test_rise_and_right_turn_are_reported(self) -> None:
        profile = route_profile(
            [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 50.0, 40.0)],
            215.0,
            self.move,
        )
        self.assertAlmostEqual(profile.xy_distance, 150.0, places=6)
        self.assertAlmostEqual(
            profile.distance_3d,
            100.0 + (50.0**2 + 40.0**2) ** 0.5,
            places=6,
        )
        self.assertAlmostEqual(profile.vertical_up, 40.0, places=6)
        self.assertAlmostEqual(profile.max_rise, 40.0, places=6)
        self.assertEqual(profile.vertical_transitions, 1)
        self.assertEqual(profile.rise_segments, 1)
        self.assertEqual(profile.jump_up_candidates, 1)
        self.assertEqual(profile.ramp_rises, 0)
        self.assertGreater(profile.jump_budget, 0.0)
        self.assertGreater(profile.time_high_with_jumps, profile.time_high)
        self.assertTrue(profile.has_vertical)
        self.assertGreater(profile.stop_go_time, profile.ideal_time)
        self.assertEqual(profile.turn_count, 1)
        self.assertAlmostEqual(profile.max_turn_deg, 90.0, places=6)

    def test_drop_is_reported_separately(self) -> None:
        profile = route_profile(
            [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (200.0, 0.0, -50.0)],
            215.0,
            self.move,
        )
        self.assertAlmostEqual(profile.vertical_down, 50.0, places=6)
        self.assertAlmostEqual(profile.max_drop, 50.0, places=6)
        self.assertEqual(profile.vertical_transitions, 1)
        self.assertEqual(profile.drop_segments, 1)
        self.assertEqual(profile.rise_segments, 0)
        self.assertEqual(profile.jump_up_candidates, 0)
        self.assertGreater(profile.stop_go_time, profile.ideal_time)

    def test_long_rise_is_ramp_not_jump_candidate(self) -> None:
        profile = route_profile(
            [(0.0, 0.0, 0.0), (180.0, 0.0, 93.0)],
            215.0,
            self.move,
        )
        self.assertEqual(profile.rise_segments, 1)
        self.assertEqual(profile.jump_up_candidates, 0)
        self.assertEqual(profile.ramp_rises, 1)
        self.assertEqual(profile.jump_budget, 0.0)


if __name__ == "__main__":
    unittest.main()
