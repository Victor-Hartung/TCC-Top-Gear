from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from analyze_curve_map import REQUIRED_COLUMNS, analyze, load_map  # noqa: E402


class CurveMapAnalysisTests(unittest.TestCase):
    def write_map(
        self,
        path: Path,
        indices: list[int],
        *,
        track_length: int = 128,
        entry_count: int = 4,
    ) -> None:
        columns = sorted(REQUIRED_COLUMNS | {"live_progress", "runtime_progress"})
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for index in indices:
                low_u8 = (0, 16, 16, 0)[index % 4]
                word = low_u8
                writer.writerow(
                    {
                        "track_length": track_length,
                        "entry_count": entry_count,
                        "live_progress": 10,
                        "runtime_progress": 8,
                        "index": index,
                        "progress_start": index * 32,
                        "progress_end": index * 32 + 31,
                        "offset": index * 2,
                        "curve_word_u16": word,
                        "curve_word_s16": word,
                        "curve_low_u8": low_u8,
                        "curve_low_s8": low_u8,
                        "curve_high_u8": 0,
                        "curve_high_s8": 0,
                        "grade_word_u16": 0,
                        "grade_word_s16": 0,
                        "road_word_u16": 0,
                        "road_low_u8": 0,
                        "road_high_u8": 0,
                    }
                )

    def test_complete_map_generates_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostico_mapa_curvas.csv"
            self.write_map(path, [0, 1, 2, 3])
            report = analyze(path)
        self.assertIn("Entradas válidas: 4", report)
        self.assertIn("índices 1..2", report)
        self.assertIn("generalização para pistas com curvas à direita", report)

    def test_rejects_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostico_mapa_curvas.csv"
            self.write_map(path, [0, 1, 3])
            with self.assertRaisesRegex(ValueError, "esperadas 4 entradas"):
                load_map(path)

    def test_labels_use_progress_divided_by_32_and_report_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            map_path = Path(directory) / "diagnostico_mapa_curvas.csv"
            labels_path = Path(directory) / "diagnostico_curva.csv"
            self.write_map(map_path, [0, 1, 2, 3])
            with labels_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["label", "progress", "track_index"])
                writer.writeheader()
                writer.writerow({"label": "straight", "progress": 1, "track_index": 99})
                writer.writerow({"label": "left", "progress": 40, "track_index": 99})
            report = analyze(map_path, labels_path)
        self.assertIn("straight: índice=0", report)
        self.assertIn("left: índice=1", report)
        self.assertIn("Separação direta dos rótulos: 2/2 (100.0%)", report)

    def test_recovers_first_half_of_legacy_doubled_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostico_mapa_curvas.csv"
            self.write_map(path, list(range(8)), entry_count=8)
            rows = load_map(path)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]["progress_start"], 96)
        self.assertEqual(rows[-1]["progress_end"], 127)


if __name__ == "__main__":
    unittest.main()
