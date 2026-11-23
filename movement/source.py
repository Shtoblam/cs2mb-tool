"""First-pass Source-style ground movement model for CS2.

The constants in config/movement_profile.json were measured from a local CS2
listen server on 2026-10-19. The acceleration/friction formulas follow the
Source SDK `CGameMovement::Accelerate` / `Friction` code, which is a model of
Source 1. CS2 has not been proven to use identical code; the steady-state
speeds below are nevertheless matched against in-game `cl_showpos` values.

This module handles straight-line ground movement only. It deliberately does
not claim to model stairs, ramps, collisions, air control or turning.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "config" / "movement_profile.json"


@dataclass(frozen=True)
class MoveProfile:
    accelerate: float = 5.5
    friction: float = 5.2
    stopspeed: float = 80.0
    maxspeed: float = 320.0
    gravity: float = 800.0
    jump_impulse: float = 301.993
    air_accelerate: float = 12.0
    air_max_wishspeed: float = 30.0
    ladder_scale_speed: float = 0.78
    walk_modifier: float = 0.52
    crouch_modifier: float = 0.34

    @classmethod
    def from_file(cls, path: Path = PROFILE_PATH) -> "MoveProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        g = data["global"]
        m = data["modifiers"]
        return cls(
            accelerate=float(g["sv_accelerate"]),
            friction=float(g["sv_friction"]),
            stopspeed=float(g["sv_stopspeed"]),
            maxspeed=float(g["sv_maxspeed"]),
            gravity=float(g["sv_gravity"]),
            jump_impulse=float(g["sv_jump_impulse"]),
            air_accelerate=float(g["sv_airaccelerate"]),
            air_max_wishspeed=float(g["sv_air_max_wishspeed"]),
            ladder_scale_speed=float(g["sv_ladder_scale_speed"]),
            walk_modifier=float(m["walk"]),
            crouch_modifier=float(m["crouch"]),
        )


@dataclass(frozen=True)
class TravelResult:
    time: float
    distance: float
    final_speed: float
    average_speed: float
    ticks: int


def apply_friction(
    velocity: float,
    dt: float,
    profile: MoveProfile,
    surface_friction: float = 1.0,
    control_floor: float | None = None,
) -> float:
    speed = abs(velocity)
    if speed < 0.1:
        return 0.0
    floor = profile.stopspeed if control_floor is None else control_floor
    control = max(speed, floor)
    drop = control * profile.friction * surface_friction * dt
    newspeed = max(0.0, speed - drop)
    return math.copysign(newspeed, velocity) if newspeed != 0 else 0.0


def apply_acceleration(
    velocity: float,
    wishspeed: float,
    dt: float,
    profile: MoveProfile,
    surface_friction: float = 1.0,
) -> float:
    currentspeed = velocity
    addspeed = wishspeed - currentspeed
    if addspeed <= 0:
        return velocity
    accelspeed = profile.accelerate * dt * wishspeed * surface_friction
    return velocity + min(accelspeed, addspeed)


def effective_max_speed(
    weapon_speed: float,
    profile: MoveProfile,
    modifier: float = 1.0,
) -> float:
    return min(weapon_speed, profile.maxspeed) * modifier


def simulate_straight(
    distance: float,
    weapon_speed: float,
    profile: MoveProfile | None = None,
    modifier: float = 1.0,
    dt: float = 1.0 / 128.0,
    surface_friction: float = 1.0,
    max_time: float = 120.0,
) -> TravelResult:
    """Simulate standing start, friction + acceleration, straight ground run."""
    profile = profile or MoveProfile.from_file()
    target_speed = effective_max_speed(weapon_speed, profile, modifier)
    # CS2 reaches crouch speeds below the nominal stopspeed (measured 73.1
    # for AK crouch), which the textbook Source friction formula would not.
    # The effective floor is therefore min(stopspeed, target speed); this is
    # calibrated to the measured steady state, not claimed as engine code.
    friction_floor = min(profile.stopspeed, target_speed)
    velocity = 0.0
    travelled = 0.0
    time = 0.0
    ticks = 0
    while travelled < distance and time < max_time:
        velocity = apply_friction(
            velocity, dt, profile, surface_friction, control_floor=friction_floor
        )
        velocity = apply_acceleration(
            velocity, target_speed, dt, profile, surface_friction
        )
        travelled += velocity * dt
        time += dt
        ticks += 1
    return TravelResult(
        time=time,
        distance=travelled,
        final_speed=velocity,
        average_speed=travelled / time if time > 0 else 0.0,
        ticks=ticks,
    )


def steady_state_speed(
    weapon_speed: float,
    profile: MoveProfile | None = None,
    modifier: float = 1.0,
    dt: float = 1.0 / 128.0,
    seconds: float = 5.0,
) -> float:
    result = simulate_straight(
        distance=1e9,
        weapon_speed=weapon_speed,
        profile=profile,
        modifier=modifier,
        dt=dt,
        max_time=seconds,
    )
    return result.final_speed


def jump_airtime(profile: MoveProfile | None = None) -> float:
    profile = profile or MoveProfile.from_file()
    return 2.0 * profile.jump_impulse / profile.gravity


def jump_height(profile: MoveProfile | None = None) -> float:
    profile = profile or MoveProfile.from_file()
    return profile.jump_impulse * profile.jump_impulse / (2.0 * profile.gravity)


def ladder_speed(weapon_speed: float, profile: MoveProfile | None = None) -> float:
    """Hypothesis from community cs2-nav: base * 2 * ladder scale."""
    profile = profile or MoveProfile.from_file()
    return min(weapon_speed, profile.maxspeed) * 2.0 * profile.ladder_scale_speed
