from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from analyze_offtrack import score_bit  # noqa: E402


class OfftrackAnalysisTests(unittest.TestCase):
    def test_finds_bit_that_is_zero_on_track_and_one_outside(self) -> None:
        values = {
            "on_track": [0x00, 0x00, 0x00],
            "off_left": [0x20, 0x20, 0x20],
            "off_right": [0x20, 0x20, 0x20],
        }
        candidate = score_bit(0x1234, 5, values)
        self.assertEqual(candidate.score, 1.0)
        self.assertEqual(candidate.orientation, "0=pista, 1=fora")

    def test_rejects_one_sided_bit_as_perfect_offtrack_signal(self) -> None:
        values = {
            "on_track": [0x00, 0x00, 0x00],
            "off_left": [0x08, 0x08, 0x08],
            "off_right": [0x00, 0x00, 0x00],
        }
        candidate = score_bit(0x1234, 3, values)
        self.assertLess(candidate.score, 0.90)


if __name__ == "__main__":
    unittest.main()
