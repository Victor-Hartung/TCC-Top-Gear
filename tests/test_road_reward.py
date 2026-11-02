import unittest
from test_reward import ROOT, telemetry
from reward import RewardWeights, calculate_reward, road_reward_v1, IdleTracker
from topgear_config import ProjectConfig


class RoadRewardTests(unittest.TestCase):
    def setUp(self):
        self.legacy = RewardWeights.from_config(ProjectConfig.load(ROOT))
        self.weights = road_reward_v1(self.legacy)

    def test_opt_in_leaves_original_unchanged(self):
        self.assertEqual(self.legacy.progress, 2)
        self.assertEqual(self.legacy.idle_penalty, 0)
        self.assertEqual(self.weights.progress, 20)

    def test_progress_on_road_is_stronger(self):
        before, after = telemetry(progress=1000), telemetry(progress=1100)
        old = calculate_reward(before, after, self.legacy)
        new = calculate_reward(before, after, self.weights)
        self.assertAlmostEqual(new.components['progress'], old.components['progress'] * 10)

    def test_no_positive_progress_reward_on_offtrack_transition(self):
        for before_off, after_off in ((0, 1), (1, 1), (1, 0)):
            result = calculate_reward(telemetry(progress=1000, offtrack=before_off),
                                      telemetry(progress=1100, offtrack=after_off), self.weights)
            self.assertEqual(result.components['progress'], 0)
            self.assertEqual(result.progress_delta, 100)

    def test_reverse_outside_is_still_negative(self):
        result = calculate_reward(telemetry(progress=1100, offtrack=1),
                                  telemetry(progress=1000, offtrack=1), self.weights)
        self.assertLess(result.components['progress'], 0)

    def test_idle_grace_and_reset_on_movement_or_impact(self):
        idle = IdleTracker()
        stopped = telemetry(speed=0)
        for _ in range(15):
            self.assertEqual(idle.penalty(stopped, stopped, 0, self.weights), 0)
        self.assertEqual(idle.penalty(stopped, stopped, 0, self.weights), -.02)
        self.assertEqual(idle.penalty(stopped, telemetry(speed=0, collision_events=1), 0, self.weights), 0)
        self.assertEqual(idle.consecutive_steps, 0)
        idle.consecutive_steps = 100
        self.assertEqual(idle.penalty(stopped, telemetry(speed=20), 1, self.weights), 0)
        self.assertEqual(idle.consecutive_steps, 0)

    def test_end_has_no_idle_penalty_or_false_finish(self):
        idle = IdleTracker(100)
        end = telemetry(speed=0, finished=1, final_rank=19, lap=0)
        self.assertEqual(idle.penalty(telemetry(), end, 0, self.weights), 0)
        self.assertEqual(calculate_reward(telemetry(), end, self.weights).components['finish'], 0)

    def test_collision_and_victory_weights_preserved(self):
        for key in ('collision', 'offtrack', 'finish', 'finish_rank', 'first_place', 'failure'):
            self.assertEqual(getattr(self.weights, key), getattr(self.legacy, key))


if __name__ == '__main__':
    unittest.main()
