from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from reward import RewardWeights, calculate_reward  # noqa: E402
from telemetry import Telemetry  # noqa: E402
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
        "nearest_valid": 0,
        "nearest_id": -1,
        "nearest_distance": -1,
        "nearest_lateral": 0,
        "nearest_motion_raw": 0,
        "lane_negative_distance": -1,
        "lane_center_distance": -1,
        "lane_positive_distance": -1,
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


class RewardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.weights = RewardWeights.from_config(ProjectConfig.load(ROOT))

    def test_progress_beats_standing_still(self) -> None:
        before = telemetry(progress=1000)
        moving = calculate_reward(before, telemetry(progress=1100), self.weights)
        still = calculate_reward(before, telemetry(progress=1000), self.weights)
        self.assertGreater(moving.total, still.total)

    def test_overtake_is_positive_and_losing_rank_is_negative(self) -> None:
        before = telemetry(rank=10)
        pass_car = calculate_reward(before, telemetry(rank=9), self.weights)
        lose_place = calculate_reward(before, telemetry(rank=11), self.weights)
        self.assertGreater(pass_car.total, 0)
        self.assertLess(lose_place.total, 0)

    def test_losing_and_recovering_same_rank_cannot_farm_reward(self) -> None:
        lose = calculate_reward(
            telemetry(rank=9), telemetry(rank=10), self.weights
        )
        recover = calculate_reward(
            telemetry(rank=10), telemetry(rank=9), self.weights
        )
        self.assertAlmostEqual(lose.total + recover.total, 0.0)

    def test_collision_penalty_uses_accumulated_event_counter(self) -> None:
        before = telemetry(collision=0, collision_events=4)
        impact = calculate_reward(
            before, telemetry(collision=1, collision_events=5), self.weights
        )
        held = calculate_reward(
            telemetry(collision=1, collision_events=5),
            telemetry(collision=0, collision_events=5),
            self.weights,
        )
        self.assertLess(impact.total, held.total)
        self.assertTrue(impact.collision_event)
        self.assertFalse(held.collision_event)

    def test_native_surface_state_drives_offtrack_penalty(self) -> None:
        road = telemetry(offtrack=0, surface_state=1, surface_direction=0)
        left = telemetry(offtrack=1, surface_state=0, surface_direction=-1)
        result = calculate_reward(road, left, self.weights)
        self.assertEqual(result.components["offtrack"], -self.weights.offtrack)

    def test_lap_transient_does_not_create_progress_jump(self) -> None:
        result = calculate_reward(
            telemetry(progress=22025, lap=0),
            telemetry(progress=22025, lap=1),
            self.weights,
        )
        self.assertEqual(result.progress_delta, 0)
        self.assertEqual(result.components["invalid_progress_jump"], 0)

    def test_progress_wrap_remains_positive(self) -> None:
        result = calculate_reward(
            telemetry(progress=9900, lap=0),
            telemetry(progress=100, lap=1),
            self.weights,
        )
        self.assertEqual(result.progress_delta, 200)
        self.assertGreater(result.components["progress"], 0)

    def test_first_place_dominates_second_place(self) -> None:
        before = telemetry(finished=0, final_rank=-1)
        first = calculate_reward(
            before, telemetry(finished=1, final_rank=0, rank=0, lap=3), self.weights
        )
        second = calculate_reward(
            before, telemetry(finished=1, final_rank=1, rank=1, lap=3), self.weights
        )
        self.assertGreater(first.total, second.total)
        self.assertGreater(first.components["first_place"], 0)

    def test_recorded_timeout_receives_no_finish_bonus(self) -> None:
        before = telemetry(frame=9942, progress=14806, lap=0, rank=19,
                           track_length=22528, offtrack=1)
        after = telemetry(frame=9946, progress=14809, lap=0, rank=19,
                          track_length=22528, offtrack=1, finished=1, final_rank=19)
        result = calculate_reward(before, after, self.weights)
        self.assertFalse(result.finish_event)
        self.assertAlmostEqual(result.total, -0.019733664772727273)
        for key in ("finish", "finish_rank", "first_place"):
            self.assertEqual(result.components[key], 0)

    def test_first_rank_without_completed_laps_is_not_a_win(self) -> None:
        state = telemetry(lap=0, finished=1, final_rank=0, rank=0)
        self.assertFalse(state.race_completed)
        result = calculate_reward(telemetry(rank=0), state, self.weights)
        self.assertEqual(result.components["first_place"], 0)

    def test_laps_alone_or_invalid_total_do_not_confirm_finish(self) -> None:
        self.assertFalse(telemetry(lap=3).race_completed)
        self.assertFalse(telemetry(lap=3, total_laps=0, finished=1, final_rank=0).race_completed)

    def test_real_finish_wrap_and_bonus_only_once(self) -> None:
        before = telemetry(lap=2, progress=22498, track_length=22528, rank=0)
        after = telemetry(lap=3, progress=22, track_length=22528, rank=0,
                          finished=1, final_rank=0)
        result = calculate_reward(before, after, self.weights)
        self.assertEqual(result.progress_delta, 52)
        self.assertTrue(result.finish_event)
        self.assertEqual(result.components["finish"], self.weights.finish)
        self.assertEqual(result.components["first_place"], self.weights.first_place)
        held = calculate_reward(after, after, self.weights)
        self.assertEqual(held.total, 0)

    def test_implausible_progress_jump_is_not_rewarded(self) -> None:
        result = calculate_reward(
            telemetry(progress=100), telemetry(progress=5000), self.weights
        )
        self.assertEqual(result.components["progress"], 0)
        self.assertEqual(result.components["invalid_progress_jump"], 1)


if __name__ == "__main__":
    unittest.main()
