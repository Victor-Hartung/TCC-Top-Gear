from __future__ import annotations

import unittest
import argparse
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from test_reward import ROOT, telemetry
from env_topgear import TopGearEnv
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
import smoke_test_env


class FakeBridge:
    address = ("127.0.0.1", 55355)

    def __init__(self, final):
        from dataclasses import replace
        self.final = replace(final,track_length=22528)
        self.resets = 0
        self.closed = False

    def wait_ready(self):
        from types import SimpleNamespace
        from dataclasses import asdict
        return SimpleNamespace(fields={k: str(v) for k, v in asdict(telemetry()).items()})

    def reset(self):
        self.resets += 1
        return telemetry(track_length=22528)

    def step(self, action):
        from test_live_detector import packet
        from dataclasses import replace
        return replace(self.final,detector_samples=packet(self.final))

    def close(self):
        self.closed = True


class EpisodeEndTests(unittest.TestCase):
    def check_end(self, final, expected_reason, completed):
        bridge = FakeBridge(final)
        with patch("env_topgear.BridgeClient", return_value=bridge):
            env = TopGearEnv(ROOT)
        env._telemetry = lambda state: state
        vec = DummyVecEnv([lambda: Monitor(env, info_keywords=(
            "race_ended", "race_completed", "lap", "total_laps", "termination_reason"
        ))])
        try:
            vec.reset()
            for episode in range(2):
                obs, rewards, dones, infos = vec.step([0])
                info = infos[0]
                self.assertTrue(dones[0])
                self.assertEqual(info["termination_reason"], expected_reason)
                self.assertEqual(info["finished"], completed)
                self.assertEqual(info["race_ended"], 1)
                self.assertEqual(info["is_first"], completed)
                self.assertEqual(info["episode"]["race_completed"], completed)
                self.assertIn("terminal_observation", info)
                self.assertEqual(bridge.resets, episode + 2)
                self.assertEqual(int(obs[0, -1]), 0)
                if not completed:
                    self.assertEqual(info["reward_finish"], 0)
        finally:
            vec.close()
        self.assertTrue(bridge.closed)

    def test_incomplete_race_resets_automatically_without_finish_bonus(self):
        self.check_end(telemetry(frame=104, finished=1, final_rank=0, lap=0),
                       "race_ended_incomplete", 0)

    def test_completed_race_resets_automatically_and_counts_win(self):
        self.check_end(telemetry(frame=104, finished=1, final_rank=0, lap=3),
                       "finished", 1)

    def test_smoke_preserves_terminal_evidence_with_optional_reset(self):
        for auto_reset in (False, True):
            with self.subTest(auto_reset=auto_reset), tempfile.TemporaryDirectory() as directory:
                bridge = FakeBridge(telemetry(frame=104, finished=1, final_rank=19, lap=0))
                with patch("env_topgear.BridgeClient", return_value=bridge):
                    env = TopGearEnv(ROOT)
                env._telemetry = lambda state: state
                args = argparse.Namespace(steps=3, log_every=20, random=False, auto_reset=auto_reset)
                fake_path = str(Path(directory) / "python" / "smoke_test_env.py")
                with patch.object(smoke_test_env, "TopGearEnv", return_value=env), \
                     patch.object(smoke_test_env, "arguments", return_value=args), \
                     patch.object(smoke_test_env, "__file__", fake_path), \
                     contextlib.redirect_stdout(io.StringIO()):
                    smoke_test_env.main()
                report = json.loads(next(Path(directory).rglob("*.json")).read_text())
                expected = 3 if auto_reset else 1
                self.assertEqual(bridge.resets, expected)
                self.assertTrue(bridge.closed)
                self.assertEqual(len(report["episode_endings"]), expected)
                for ending in report["episode_endings"]:
                    self.assertEqual(ending["state"]["termination_reason"], "race_ended_incomplete")
                    self.assertEqual(ending["state"]["reward_finish"], 0)


if __name__ == "__main__":
    unittest.main()
