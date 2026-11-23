"""Synthetic navigation tests. No game files required."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from nav_inspect import (  # noqa: E402
    Area,
    NavMesh,
    dijkstra_edges,
    edge_midpoint,
    find_area,
    find_area_verbose,
    kosaraju_scc,
    point_in_poly_xy,
    undirected_components,
    vertical_layers,
)


def square(area_id: int, x: float, y: float, z: float = 0.0) -> Area:
    corners = [
        (x, y, z),
        (x + 1.0, y, z),
        (x + 1.0, y + 1.0, z),
        (x, y + 1.0, z),
    ]
    return Area(
        area_id=area_id,
        attribute_flags=0,
        hull_index=0,
        corner_gravity=None,
        corners=corners,
        connections=[],
        hiding_spots=0,
        ladders_above=[],
        ladders_below=[],
    )


def chain() -> NavMesh:
    a = square(1, 0.0, 0.0)
    b = square(2, 1.0, 0.0)
    c = square(3, 2.0, 0.0)
    # Destination edge ids: A->B enters B's left edge (3);
    # B->A enters A's right edge (1); B->C enters C's left edge (3);
    # C->B enters B's right edge (1).
    a.connections = [(2, 3)]
    b.connections = [(1, 1), (3, 3)]
    c.connections = [(2, 1)]
    return NavMesh(
        version=36,
        sub_version=1,
        is_analyzed=True,
        places=[],
        has_unnamed_areas=False,
        areas=[a, b, c],
        ladders=[],
    )


class NavSyntheticTests(unittest.TestCase):
    def test_point_in_polygon(self) -> None:
        a = square(1, 0.0, 0.0)
        self.assertTrue(point_in_poly_xy(a, 0.5, 0.5))
        self.assertFalse(point_in_poly_xy(a, 1.5, 0.5))
        self.assertFalse(point_in_poly_xy(a, 0.5, 1.5))

    def test_find_area_by_xy_and_z(self) -> None:
        nav = chain()
        self.assertEqual(find_area(nav, (0.5, 0.5, 0.0)).area_id, 1)
        self.assertEqual(find_area(nav, (1.5, 0.5, 0.0)).area_id, 2)
        self.assertEqual(find_area(nav, (2.5, 0.5, 0.0)).area_id, 3)
        self.assertIsNone(find_area(nav, (9.0, 9.0, 0.0)))

    def test_edge_midpoint(self) -> None:
        a = square(1, 0.0, 0.0)
        self.assertEqual(edge_midpoint(a, 0), (0.5, 0.0, 0.0))
        self.assertEqual(edge_midpoint(a, 1), (1.0, 0.5, 0.0))
        self.assertEqual(edge_midpoint(a, 3), (0.0, 0.5, 0.0))

    def test_line_graph_shortest_path_and_length(self) -> None:
        nav = chain()
        path, cost, points = dijkstra_edges(
            nav, 1, 3, (0.5, 0.5, 0.0), (2.5, 0.5, 0.0)
        )
        self.assertEqual(path, [1, 2, 3])
        self.assertAlmostEqual(cost, 2.0, places=6)
        self.assertEqual(points[0], (0.5, 0.5, 0.0))
        self.assertEqual(points[-1], (2.5, 0.5, 0.0))

    def test_reverse_path(self) -> None:
        nav = chain()
        path, cost, _ = dijkstra_edges(
            nav, 3, 1, (2.5, 0.5, 0.0), (0.5, 0.5, 0.0)
        )
        self.assertEqual(path, [3, 2, 1])
        self.assertAlmostEqual(cost, 2.0, places=6)

    def test_missing_direction_returns_no_path(self) -> None:
        nav = chain()
        nav.by_id()[2].connections = [(3, 3)]  # remove B -> A
        path, cost, points = dijkstra_edges(
            nav, 3, 1, (2.5, 0.5, 0.0), (0.5, 0.5, 0.0)
        )
        self.assertEqual(path, [])
        self.assertFalse(math.isfinite(cost))
        self.assertEqual(points, [])

    def test_components_and_scc(self) -> None:
        nav = chain()
        self.assertEqual(undirected_components(nav), [3])
        scc, largest = kosaraju_scc(nav)
        # A <-> B <-> C, so all three are one strongly connected component.
        self.assertEqual(scc, [3])
        self.assertEqual(largest, 3)

    def test_scc_one_way_chain(self) -> None:
        nav = chain()
        nav.by_id()[2].connections = [(3, 3)]  # A -> B -> C
        nav.by_id()[3].connections = []       # no C -> B
        scc, largest = kosaraju_scc(nav)
        self.assertEqual(sorted(scc), [1, 1, 1])
        self.assertEqual(largest, 1)

    def test_start_equals_goal(self) -> None:
        nav = chain()
        path, cost, points = dijkstra_edges(
            nav, 2, 2, (1.2, 0.5, 0.0), (1.8, 0.5, 0.0)
        )
        self.assertEqual(path, [2])
        self.assertAlmostEqual(cost, 0.6, places=6)
        self.assertEqual(len(points), 2)

    def test_stacked_floors_are_disambiguated_by_z(self) -> None:
        lower = square(11, 0.0, 0.0, z=0.0)
        upper = square(12, 0.0, 0.0, z=100.0)
        nav = NavMesh(
            version=36,
            sub_version=1,
            is_analyzed=True,
            places=[],
            has_unnamed_areas=False,
            areas=[lower, upper],
            ladders=[],
        )
        self.assertEqual(find_area(nav, (0.5, 0.5, 5.0)).area_id, 11)
        self.assertEqual(find_area(nav, (0.5, 0.5, 95.0)).area_id, 12)
        self.assertEqual(find_area(nav, (0.5, 0.5, 50.0)).area_id, 11)

        verbose = find_area_verbose(nav, (0.5, 0.5, 50.0), ambiguity=64.0)
        self.assertTrue(verbose["ambiguous"])
        self.assertEqual(len(verbose["candidates"]), 2)
        self.assertEqual(
            sorted(c["area_id"] for c in verbose["candidates"]), [11, 12]
        )

        layers = vertical_layers(nav, 0.5, 0.5)
        self.assertEqual(len(layers), 2)
        self.assertEqual([round(layer["z"]) for layer in layers], [0, 100])
        self.assertEqual(layers[0]["area_ids"], [11])
        self.assertEqual(layers[1]["area_ids"], [12])


if __name__ == "__main__":
    unittest.main()
