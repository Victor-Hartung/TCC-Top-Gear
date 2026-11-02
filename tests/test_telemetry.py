from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from protocol import ProtocolError  # noqa: E402
from telemetry import (  # noqa: E402
    OBSERVATION_NAMES,
    OBSERVATION_SCHEMA_VERSION,
    ObservationBuilder,
    Telemetry,
)
from topgear_config import ProjectConfig  # noqa: E402


def telemetry(**changes: int) -> Telemetry:
    values = {
        "frame": 100,
        "speed": 3200,
        "lateral": 0,
        "progress_fraction": 0,
        "progress": 1000,
        "lap": 0,
        "rank": 10,
        "final_rank": -1,
        "finished": 0,
        "collision": 0,
        "collision_events": 0,
        "offtrack": 0,
        "surface_raw": 1,
        "surface_unknown": 0,
        "surface_state": 1,
        "surface_direction": 0,
        "fuel": 30000,
        "nitro": 2,
        "nitro_raw": 2,
        "turbo_active": 0,
        "gear": 3,
        "total_laps": 3,
        "track_length": 10000,
        "curve_progress": 1000,
        "curve_current": 0,
        "curve_ahead_512": 16,
        "curve_ahead_1024": 24,
        "curve_ahead_2048": 32,
        "nearest_valid": 1,
        "nearest_id": 7,
        "nearest_distance": 500,
        "nearest_lateral": 100,
        "nearest_motion_raw": 2000,
        "lane_negative_distance": -1,
        "lane_center_distance": 500,
        "lane_positive_distance": 900,
        "opponent_count": 18,
        "profile_validated": 1,
        "opponent_telemetry_validated": 1,
        "surface_telemetry_validated": 1,
        "curve_telemetry_validated": 1,
        "controls_validated": 1,
        "rom_ok": 1,
        "domain_ok": 1,
    }
    values.update(changes)
    return Telemetry(**values)


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ObservationBuilder(ProjectConfig.load(ROOT))

    def test_observation_has_named_bounded_features(self) -> None:
        obs = self.builder.reset(telemetry())
        self.assertEqual(OBSERVATION_SCHEMA_VERSION, 10)
        self.assertEqual(obs.shape, (len(OBSERVATION_NAMES),))
        self.assertTrue(np.all(np.isfinite(obs)))
        self.assertTrue(np.all(obs >= self.builder.low()))
        self.assertTrue(np.all(obs <= self.builder.high()))

    def test_turbo_inventory_and_active_state_are_separate_features(self) -> None:
        obs = self.builder.reset(
            telemetry(nitro=2, nitro_raw=0x8003, turbo_active=1)
        )
        self.assertAlmostEqual(
            float(obs[OBSERVATION_NAMES.index("nitro_norm")]), 2.0 / 3.0
        )
        self.assertEqual(obs[OBSERVATION_NAMES.index("turbo_active")], 1.0)

    def test_rejects_inconsistent_turbo_decode(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "Campos de turbo inconsistentes"):
            telemetry(nitro=3, nitro_raw=0x8003, turbo_active=1).validate()

    def test_surface_direction_distinguishes_both_sides(self) -> None:
        left = self.builder.reset(
            telemetry(offtrack=1, surface_state=0, surface_direction=-1)
        )
        right = self.builder.reset(
            telemetry(offtrack=1, surface_state=2, surface_direction=1)
        )
        direction = OBSERVATION_NAMES.index("surface_direction")
        self.assertEqual(left[direction], -1)
        self.assertEqual(right[direction], 1)

    def test_rejects_inconsistent_surface_fields(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "Campos de superfície inconsistentes"):
            telemetry(offtrack=0, surface_state=0, surface_direction=-1).validate()

    def test_unknown_surface_raw_is_audited_and_kept_offtrack(self) -> None:
        sample = telemetry(
            offtrack=1,
            surface_raw=255,
            surface_unknown=1,
            surface_state=0,
            surface_direction=-1,
        )
        sample.validate()
        obs = self.builder.reset(sample)
        self.assertEqual(obs[OBSERVATION_NAMES.index("offtrack")], 1)
        self.assertEqual(obs[OBSERVATION_NAMES.index("surface_direction")], -1)

    def test_unknown_surface_cannot_be_mapped_to_road(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "Fallback de superfície"):
            telemetry(surface_raw=255, surface_unknown=1).validate()

    def test_closing_rate_uses_same_opponent(self) -> None:
        self.builder.reset(telemetry(frame=100, nearest_distance=500))
        obs = self.builder.build(telemetry(frame=104, nearest_distance=400))
        closing_index = OBSERVATION_NAMES.index("closing_rate_norm")
        self.assertGreater(obs[closing_index], 0)

    def test_missing_opponent_uses_mask(self) -> None:
        obs = self.builder.reset(
            telemetry(
                nearest_valid=0,
                nearest_id=-1,
                nearest_distance=-1,
                lane_center_distance=-1,
                lane_positive_distance=-1,
            )
        )
        self.assertEqual(obs[OBSERVATION_NAMES.index("nearest_valid")], 0)
        self.assertEqual(obs[OBSERVATION_NAMES.index("nearest_distance_norm")], 1)

    def test_runtime_rejects_unvalidated_opponent_telemetry(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "opponent_telemetry_validated=0"):
            telemetry(opponent_telemetry_validated=0).assert_runtime_ready()

    def test_runtime_rejects_unvalidated_surface_telemetry(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "surface_telemetry_validated=0"):
            telemetry(surface_telemetry_validated=0).assert_runtime_ready()

    def test_curve_features_are_signed_and_normalized(self) -> None:
        obs = self.builder.reset(
            telemetry(
                curve_current=-32,
                curve_ahead_512=0,
                curve_ahead_1024=16,
                curve_ahead_2048=32,
            )
        )
        self.assertEqual(obs[OBSERVATION_NAMES.index("curve_current_norm")], -1)
        self.assertEqual(obs[OBSERVATION_NAMES.index("curve_ahead_512_norm")], 0)
        self.assertEqual(obs[OBSERVATION_NAMES.index("curve_ahead_1024_norm")], 0.5)
        self.assertEqual(obs[OBSERVATION_NAMES.index("curve_ahead_2048_norm")], 1)

    def test_runtime_rejects_unvalidated_curve_telemetry(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "curve_telemetry_validated=0"):
            telemetry(curve_telemetry_validated=0).assert_runtime_ready()


if __name__ == "__main__":
    unittest.main()
