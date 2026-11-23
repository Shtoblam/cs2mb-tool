"""Route-level vertical/turn profile and no-jump time estimate.

The movement model in :mod:`movement.source` is straight-line ground movement.
A nav route can contain ramps, drops, box jump-ups and turns.  This module
exposes vertical transitions and adds a separate one-airtime jump budget for
short upward steps; it is not a measured route-time model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from movement.source import MoveProfile, jump_airtime, simulate_straight


@dataclass(frozen=True)
class RouteProfile:
    xy_distance: float
    distance_3d: float
    ideal_time: float
    stop_go_time: float
    vertical_up: float
    vertical_down: float
    max_rise: float
    max_drop: float
    vertical_transitions: int
    rise_segments: int
    drop_segments: int
    jump_up_candidates: int
    ramp_rises: int
    jump_budget: float
    turn_count: int
    max_turn_deg: float

    @property
    def has_vertical(self) -> bool:
        return self.vertical_transitions > 0

    @property
    def time_low(self) -> float:
        return self.ideal_time

    @property
    def time_high(self) -> float:
        return max(self.ideal_time, self.stop_go_time)

    @property
    def time_high_with_jumps(self) -> float:
        """Stop-go high plus one full airtime per jump-up candidate."""
        return self.time_high + self.jump_budget


def route_profile(
    points: list[tuple[float, float, float]] | tuple[tuple[float, float, float], ...],
    weapon_speed: float = 215.0,
    profile: MoveProfile | None = None,
    max_climb: float = 16.0,
    max_jump_up: float = 68.0,
    max_jump_horizontal: float = 64.0,
    turn_threshold_deg: float = 20.0,
) -> RouteProfile:
    """Summarize a 3D polyline and expose a conservative jump budget.

    ``ideal_time`` is the measured straight-line ground model over the full 3D
    distance.  ``jump_budget`` adds one full measured airtime for each short
    upward step (``max_climb < dz <= max_jump_up`` and horizontal distance
    <= ``max_jump_horizontal``).  It is a budget, not an observed jump time.
    """
    if len(points) < 2:
        return RouteProfile(
            xy_distance=0.0,
            distance_3d=0.0,
            ideal_time=0.0,
            stop_go_time=0.0,
            vertical_up=0.0,
            vertical_down=0.0,
            max_rise=0.0,
            max_drop=0.0,
            vertical_transitions=0,
            rise_segments=0,
            drop_segments=0,
            jump_up_candidates=0,
            ramp_rises=0,
            jump_budget=0.0,
            turn_count=0,
            max_turn_deg=0.0,
        )

    move_profile = profile or MoveProfile.from_file()
    xy_distance = 0.0
    distance_3d = 0.0
    stop_go_time = 0.0
    vertical_up = 0.0
    vertical_down = 0.0
    max_rise = 0.0
    max_drop = 0.0
    vertical_transitions = 0
    rise_segments = 0
    drop_segments = 0
    jump_up_candidates = 0
    ramp_rises = 0
    headings: list[float] = []

    for p, q in zip(points, points[1:]):
        dx, dy, dz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        horizontal = math.hypot(dx, dy)
        xy_distance += horizontal
        segment_3d = math.dist(p, q)
        distance_3d += segment_3d
        stop_go_time += simulate_straight(
            segment_3d, weapon_speed, move_profile
        ).time
        if dz > 0:
            vertical_up += dz
            max_rise = max(max_rise, dz)
        elif dz < 0:
            vertical_down += -dz
            max_drop = max(max_drop, -dz)
        if abs(dz) > max_climb:
            vertical_transitions += 1
            if dz > 0:
                rise_segments += 1
                if dz <= max_jump_up and horizontal <= max_jump_horizontal:
                    jump_up_candidates += 1
                else:
                    ramp_rises += 1
            else:
                drop_segments += 1
        if horizontal > 1e-9:
            headings.append(math.atan2(dy, dx))

    turn_count = 0
    max_turn_deg = 0.0
    for previous, current in zip(headings, headings[1:]):
        delta = abs(math.degrees(current - previous)) % 360.0
        if delta > 180.0:
            delta = 360.0 - delta
        max_turn_deg = max(max_turn_deg, delta)
        if delta > turn_threshold_deg:
            turn_count += 1

    return RouteProfile(
        xy_distance=xy_distance,
        distance_3d=distance_3d,
        ideal_time=simulate_straight(distance_3d, weapon_speed, move_profile).time,
        stop_go_time=stop_go_time,
        vertical_up=vertical_up,
        vertical_down=vertical_down,
        max_rise=max_rise,
        max_drop=max_drop,
        vertical_transitions=vertical_transitions,
        rise_segments=rise_segments,
        drop_segments=drop_segments,
        jump_up_candidates=jump_up_candidates,
        ramp_rises=ramp_rises,
        jump_budget=jump_up_candidates * jump_airtime(move_profile),
        turn_count=turn_count,
        max_turn_deg=max_turn_deg,
    )
