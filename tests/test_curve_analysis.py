from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from analyze_curve import analyze, best_fit  # noqa: E402


class CurveAnalysisTests(unittest.TestCase):
    def test_best_fit_recovers_sign_and_threshold(self) -> None:
        rows: list[dict[str, int | str]] = []
        for label, value in (("straight", 2), ("left", -100), ("right", 100)):
            rows.extend({"label": label, "curve_0": value} for _ in range(6))
        fit = best_fit("curve_0", rows)
        self.assertEqual(fit.correct, 18)
        self.assertEqual(fit.positive_label, "right")
        self.assertGreaterEqual(fit.threshold, 2)
        self.assertLess(fit.threshold, 100)

    def test_complete_capture_generates_report(self) -> None:
        columns = [
            "capture", "label", "emu_frame", "speed", "lateral",
            "surface_state", "progress", "lap", "total_laps", "track_index",
            "curve_0", "curve_256", "curve_512", "curve_1024", "curve_2048",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostico_curva.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                capture = 0
                for label, value in (("straight", 0), ("left", -64), ("right", 64)):
                    for index in range(6):
                        capture += 1
                        writer.writerow(
                            {
                                "capture": capture,
                                "label": label,
                                "emu_frame": 100 + capture * 20,
                                "speed": 4000,
                                "lateral": 0,
                                "surface_state": 1,
                                "progress": 1000 + capture * 256,
                                "lap": 0,
                                "total_laps": 3,
                                "track_index": 10 + capture,
                                **{column: value for column in columns if column.startswith("curve_")},
                            }
                        )
            report = analyze(path)
        self.assertIn("18/18 (100.0%)", report)
        self.assertIn("Cobertura direcional completa", report)
        self.assertIn("Não altere curve_telemetry_validated", report)

    def test_track_without_right_curves_is_accepted_but_reported(self) -> None:
        columns = [
            "capture", "label", "emu_frame", "speed", "lateral",
            "surface_state", "progress", "lap", "total_laps", "track_index",
            "curve_0", "curve_256", "curve_512", "curve_1024", "curve_2048",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostico_curva.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                capture = 0
                for label, value in (("straight", 0), ("left", -64)):
                    for index in range(6):
                        capture += 1
                        writer.writerow(
                            {
                                "capture": capture,
                                "label": label,
                                "emu_frame": 100 + capture * 20,
                                "speed": 4000,
                                "lateral": 0,
                                "surface_state": 1,
                                "progress": 1000 + capture * 256,
                                "lap": 0,
                                "total_laps": 3,
                                "track_index": 10 + capture,
                                **{
                                    column: value
                                    for column in columns
                                    if column.startswith("curve_")
                                },
                            }
                        )
            report = analyze(path)
        self.assertIn("direita=0", report)
        self.assertIn("right: sem amostras nesta pista", report)
        self.assertIn("Cobertura direcional incompleta: right", report)

    def test_runtime_s8_capture_schema_is_accepted(self) -> None:
        curve_columns = [
            f"runtime_curve_s8_{ahead}"
            for ahead in (0, 128, 256, 512, 768, 1024, 1536, 2048)
        ]
        columns = [
            "capture", "label", "emu_frame", "speed", "lateral",
            "surface_state", "progress", "lap", "total_laps", "track_index",
            *curve_columns,
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostico_curva.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                capture = 0
                for label, value in (("straight", 0), ("left", -16)):
                    for _ in range(6):
                        capture += 1
                        writer.writerow(
                            {
                                "capture": capture,
                                "label": label,
                                "emu_frame": capture * 20,
                                "speed": 4000,
                                "lateral": 0,
                                "surface_state": 1,
                                "progress": capture * 256,
                                "lap": 0,
                                "total_laps": 3,
                                "track_index": capture,
                                **{column: value for column in curve_columns},
                            }
                        )
            report = analyze(path)
        self.assertIn("runtime_curve_s8_0", report)
        self.assertIn("12/12 (100.0%)", report)


if __name__ == "__main__":
    unittest.main()
