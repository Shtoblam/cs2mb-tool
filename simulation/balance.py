"""Time-only map balance verdict.

This is deliberately a heuristic, not a combat or win-probability model.  It
compares median spawn-to-site AK route times for the targets available on the
map.  Positive ``ct_advantage_s`` means CT routes are faster than T routes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BalanceVerdict:
    side: str
    verdict: str
    ct_advantage_s: float
    relative_pct: float
    targets: tuple[str, ...]
    basis: str

    def as_dict(self) -> dict:
        return {
            "side": self.side,
            "verdict": self.verdict,
            "ct_advantage_s": round(self.ct_advantage_s, 2),
            "relative_pct": round(self.relative_pct, 2),
            "targets": list(self.targets),
            "basis": self.basis,
        }


def time_only_balance(routes: dict[str, dict]) -> BalanceVerdict | None:
    """Compare median low route times across common T/CT targets.

    ``routes`` shape: ``{"T": {"A": {"time_low": ...}}, "CT": {...}}``.
    The verdict is a route-time heuristic; it must not be presented as a
    predicted win rate or a combat-strength result.
    """
    t_routes = routes.get("T") or {}
    ct_routes = routes.get("CT") or {}
    targets = tuple(
        target
        for target in ("Mid", "A", "B")
        if target in t_routes and target in ct_routes
    )
    if not targets:
        return None

    deltas = []
    times = []
    for target in targets:
        t_time = float(t_routes[target]["time_low"])
        ct_time = float(ct_routes[target]["time_low"])
        deltas.append(t_time - ct_time)
        times.extend((t_time, ct_time))
    ct_advantage = sum(deltas) / len(deltas)
    mean_time = sum(times) / len(times)
    relative = 100.0 * ct_advantage / mean_time if mean_time else 0.0

    if abs(ct_advantage) <= 1.0:
        side = "balanced"
        verdict = "balanced"
    elif ct_advantage > 0:
        side = "CT"
        verdict = "ct_slight" if ct_advantage < 3.0 else "ct_clear"
    else:
        side = "T"
        verdict = "t_slight" if ct_advantage > -3.0 else "t_clear"

    return BalanceVerdict(
        side=side,
        verdict=verdict,
        ct_advantage_s=ct_advantage,
        relative_pct=relative,
        targets=targets,
        basis="AK median low, time-only; no combat",
    )
