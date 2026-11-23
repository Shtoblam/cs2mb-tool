"""Time-only 5-player rush envelope.

This is deliberately not a 5v5 strategy or balance model.  It answers a
narrow question: if five players occupy distinct spawns and all run to the
same target, what is the distribution of the team's median arrival time?

Spawn sampling is exact over all ``C(15, 5)`` subsets; no random seed is
needed.  Target splits, combat, blocking and jump delays are not modelled.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from itertools import combinations, permutations
from statistics import median


@dataclass(frozen=True)
class RushEnvelope:
    n_teams: int
    team_size: int
    low_p10: float
    low_median: float
    low_p90: float
    high_median: float
    high_p90: float


@dataclass(frozen=True)
class TargetArrival:
    n: int
    low_p10: float
    low_median: float
    low_p90: float
    high_median: float
    high_p90: float


@dataclass(frozen=True)
class SplitEnvelope:
    n_teams: int
    n_samples: int
    n_assignments: int
    policy: str
    targets: dict[str, TargetArrival]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def rush_envelope(
    low_times: list[float],
    high_times: list[float],
    team_size: int = 5,
) -> RushEnvelope:
    """Median arrival envelope over all distinct-spawn teams.

    ``low_times`` and ``high_times`` are per-spawn route-time bounds.  For every
    team subset, the median of its bounds is computed; the result summarizes
    those team medians.  This assumes every player runs to the same target.
    """
    if len(low_times) != len(high_times):
        raise ValueError("low/high time arrays must have equal length")
    if team_size < 1 or team_size > len(low_times):
        raise ValueError("team_size must be between 1 and spawn count")

    low_medians: list[float] = []
    high_medians: list[float] = []
    for team in combinations(range(len(low_times)), team_size):
        low_medians.append(sorted(low_times[i] for i in team)[team_size // 2])
        high_medians.append(sorted(high_times[i] for i in team)[team_size // 2])
    return RushEnvelope(
        n_teams=len(low_medians),
        team_size=team_size,
        low_p10=_percentile(low_medians, 0.10),
        low_median=_percentile(low_medians, 0.50),
        low_p90=_percentile(low_medians, 0.90),
        high_median=_percentile(high_medians, 0.50),
        high_p90=_percentile(high_medians, 0.90),
    )


def split_envelope(
    spawn_times: list[dict[str, tuple[float, float]]],
    quotas: dict[str, int],
    policy: str = "optimal",
    seed: int = 0,
    samples_per_team: int = 8,
    temperature: float = 5.0,
) -> SplitEnvelope:
    """Time-only split scenario with optimal, random or softmax assignment.

    ``policy="optimal"`` chooses the assignment with the lowest sum of low
    times (best-case coordination).  ``random`` and ``softmax`` are seeded
    baselines: random is uniform, softmax samples assignments weighted by
    ``exp(-(score - min_score) / temperature)``.

    ``spawn_times[i][target] = (low, high)``.  Group arrival is the median of
    the assigned players' low/high bounds; for a two-player group this is their
    mean.  This is not a combat or human-behavior model.
    """
    if not spawn_times:
        raise ValueError("spawn_times must not be empty")
    if not quotas or any(count < 1 for count in quotas.values()):
        raise ValueError("quotas must contain positive counts")
    team_size = sum(quotas.values())
    if team_size > len(spawn_times):
        raise ValueError("sum(quotas) exceeds spawn count")
    if policy not in {"optimal", "random", "softmax"}:
        raise ValueError(f"unknown assignment policy: {policy}")
    if samples_per_team < 1:
        raise ValueError("samples_per_team must be positive")
    if policy == "softmax" and temperature <= 0:
        raise ValueError("temperature must be positive")

    targets = sorted(quotas)
    for times in spawn_times:
        missing = set(targets) - set(times)
        if missing:
            raise ValueError(f"spawn is missing target times: {sorted(missing)}")

    labels = [target for target in targets for _ in range(quotas[target])]
    assignments = sorted(set(permutations(labels)))
    values: dict[str, list[tuple[float, float]]] = {target: [] for target in targets}
    rng = random.Random(seed)
    n_samples = 0

    def evaluate(
        team: tuple[int, ...],
        assignment: tuple[str, ...],
    ) -> tuple[float, float, dict[str, tuple[float, float]]]:
        total_low = 0.0
        total_high = 0.0
        groups: dict[str, list[tuple[float, float]]] = {
            target: [] for target in targets
        }
        for spawn_index, target in zip(team, assignment):
            low, high = spawn_times[spawn_index][target]
            total_low += low
            total_high += high
            groups[target].append((low, high))
        medians = {
            target: (
                median(low for low, _ in groups[target]),
                median(high for _, high in groups[target]),
            )
            for target in targets
        }
        return total_low, total_high, medians

    for team in combinations(range(len(spawn_times)), team_size):
        if policy == "optimal":
            best_key: tuple[float, float] | None = None
            best_median: dict[str, tuple[float, float]] | None = None
            for assignment in assignments:
                low, high, medians = evaluate(team, assignment)
                key = (low, high)
                if best_key is None or key < best_key:
                    best_key = key
                    best_median = medians
            assert best_median is not None
            sampled = [best_median]
        else:
            scores = []
            for assignment in assignments:
                low, high, _medians = evaluate(team, assignment)
                scores.append((low, high))
            if policy == "random":
                chosen = [rng.choice(assignments) for _ in range(samples_per_team)]
            else:
                min_low = min(low for low, _ in scores)
                weights = [
                    math.exp(-((low - min_low) / temperature))
                    for low, _ in scores
                ]
                chosen = rng.choices(
                    assignments, weights=weights, k=samples_per_team
                )
            sampled = [evaluate(team, assignment)[2] for assignment in chosen]
        for median_values in sampled:
            for target, (low, high) in median_values.items():
                values[target].append((low, high))
        n_samples += len(sampled)

    arrivals = {}
    for target in targets:
        target_values = values[target]
        arrivals[target] = TargetArrival(
            n=len(target_values),
            low_p10=_percentile([v[0] for v in target_values], 0.10),
            low_median=_percentile([v[0] for v in target_values], 0.50),
            low_p90=_percentile([v[0] for v in target_values], 0.90),
            high_median=_percentile([v[1] for v in target_values], 0.50),
            high_p90=_percentile([v[1] for v in target_values], 0.90),
        )
    return SplitEnvelope(
        n_teams=math.comb(len(spawn_times), team_size),
        n_samples=n_samples,
        n_assignments=len(assignments),
        policy=policy,
        targets=arrivals,
    )
