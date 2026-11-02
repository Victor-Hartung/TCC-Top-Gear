from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from analyze_surface import transition_groups  # noqa: E402


class SurfaceAnalysisTests(unittest.TestCase):
    def test_groups_two_sided_road_transitions(self) -> None:
        sequence = [1, 0, 1, 2, 1]
        rows = [
            {"surface_0727": value, "lateral": index * 10, "emu_frame": index}
            for index, value in enumerate(sequence)
        ]
        groups = transition_groups(rows)
        self.assertEqual(len(groups["road_to_left"]), 1)
        self.assertEqual(len(groups["left_to_road"]), 1)
        self.assertEqual(len(groups["road_to_right"]), 1)
        self.assertEqual(len(groups["right_to_road"]), 1)
        self.assertEqual(groups["other"], [])


if __name__ == "__main__":
    unittest.main()
