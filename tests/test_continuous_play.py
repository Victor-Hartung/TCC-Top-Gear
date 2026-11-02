import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from test_reward import ROOT
from jogar_continuo import play
from protocol import ProtocolError
from transition_errors import LapSentinelRegression


class FrozenController:
    def __init__(self):
        self.modes = []

    def predict(self, observation, deterministic=True):
        self.modes.append(deterministic)
        return np.array(1), None


class RepeatingEnvironment:
    def __init__(self, stop_after=None):
        self.resets = 0
        self.stop_after = stop_after
        self.actions = []
        self.action_space = FixedActionSpace()

    def reset(self):
        if self.stop_after is not None and self.resets == self.stop_after:
            raise KeyboardInterrupt()
        self.resets += 1
        self.steps = 0
        return np.zeros(61), {}

    def step(self, action):
        self.actions.append(action)
        self.steps += 1
        return np.zeros(61), 99999.0, self.steps == 2, False, dict(
            action_name='ACCELERATE', lap=3, rank=0, final_rank=0,
            race_completed=1, collisions_total=0, nitro=3, termination_reason='finished')


class FixedActionSpace:
    def sample(self):
        return 7


class OneInvalidAttempt(RepeatingEnvironment):
    def step(self, action):
        if self.resets == 1 and self.steps == 1:
            raise LapSentinelRegression(dict(previous={'lap': 0}, rejected={'lap': -1}))
        return super().step(action)


class RepeatedInvalidAttempts(RepeatingEnvironment):
    def step(self, action):
        raise LapSentinelRegression(dict(previous={'lap': 0}, rejected={'lap': -1}))


class ContinuousPlayTests(unittest.TestCase):
    def test_repeated_races_keep_same_environment_and_policy_sampling(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            env = RepeatingEnvironment()
            model = FrozenController()
            self.assertEqual(play(env, model, Path(d), races=3), 3)
            self.assertEqual(env.resets, 3)
            self.assertEqual(model.modes, [False]*6)
            self.assertEqual(env.actions, [1]*6)
            rows = [json.loads(line) for line in (Path(d)/'corridas.jsonl').read_text().splitlines()]
            self.assertEqual([r['race'] for r in rows], [1,2,3])
            self.assertTrue(all(not r['training_enabled'] and not r['action_override'] for r in rows))

    def test_unlimited_play_keeps_completed_records_when_user_stops(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            env = RepeatingEnvironment(stop_after=3)
            with self.assertRaises(KeyboardInterrupt):
                play(env, FrozenController(), Path(d))
            self.assertEqual(env.resets, 3)
            self.assertEqual(len((Path(d)/'corridas.jsonl').read_text().splitlines()), 3)

    def test_optional_deterministic_mode_is_forwarded(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            model = FrozenController()
            play(RepeatingEnvironment(), model, Path(d), races=1, deterministic=True)
            self.assertEqual(model.modes, [True,True])

    def test_dqn_variado_uses_epsilon_random_actions(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            env = RepeatingEnvironment()
            model = FrozenController()
            play(env, model, Path(d), races=1, random_action_epsilon=1.0)
            self.assertEqual(env.actions, [7, 7])
            self.assertEqual(model.modes, [])

    def test_invalid_lap_is_recorded_and_not_counted_as_a_race(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            env = OneInvalidAttempt()
            self.assertEqual(play(env, FrozenController(), Path(d), races=1), 1)
            self.assertEqual(env.resets, 2)
            rows = [json.loads(line) for line in (Path(d)/'corridas.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['event'], 'invalid_telemetry')
            self.assertIsNone(rows[0]['race_completed'])
            self.assertFalse(rows[0]['counted_race'])
            self.assertEqual(rows[1]['race'], 1)
            self.assertTrue(Path(rows[0]['diagnostic']).is_file())

    def test_repeated_invalid_lap_stops_after_bounded_recoveries(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            env = RepeatedInvalidAttempts()
            with self.assertRaises(ProtocolError):
                play(env, FrozenController(), Path(d), races=1)
            self.assertEqual(env.resets, 4)
            self.assertEqual(len(list(Path(d).glob('lap_sentinel*.json'))), 4)
