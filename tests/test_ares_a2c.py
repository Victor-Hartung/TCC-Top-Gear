import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gymnasium as gym
import numpy as np
import torch

from test_reward import ROOT
from ares_a2c import a2c_contract, a2c_options, a2c_policy_kwargs
from experiment import contract as environment_contract, save_checkpoint, validate_checkpoint
from jogar_continuo import load_agent
from named_brain import NamedBrain, NamedBrainCallback
from resilient_a2c import ResilientA2C
from topgear_config import ProjectConfig
from transition_errors import LapSentinelRegression


class SmallEnvironment(gym.Env):
    def __init__(self, expected, *, fail_once=False):
        self.observation_space = gym.spaces.Box(
            np.asarray(expected["observation_low"], dtype=np.float32),
            np.asarray(expected["observation_high"], dtype=np.float32),
        )
        self.action_space = gym.spaces.Discrete(len(expected["actions"]))
        self.fail_once = fail_once
        self.failed = False
        self.resets = 0
        self.steps = 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.resets += 1
        self.steps = 0
        return np.zeros(self.observation_space.shape, dtype=np.float32), {}

    def step(self, action):
        if self.fail_once and not self.failed and self.steps == 2:
            self.failed = True
            raise LapSentinelRegression({
                "previous": {"lap": 0}, "rejected": {"lap": -1}
            })
        self.steps += 1
        done = self.steps >= 8
        return np.zeros(self.observation_space.shape, dtype=np.float32), 0.1, done, False, {}


class AresA2CTests(unittest.TestCase):
    def setUp(self):
        self.profile = patch.dict(os.environ, {"TOPGEAR_PROFILE": "game_profile_blue_auto.ini"})
        self.profile.start()
        self.cfg = ProjectConfig.load(ROOT)
        self.base = environment_contract(self.cfg)
        self.expected = a2c_contract(self.cfg)
        torch.set_num_threads(1)

    def tearDown(self):
        self.profile.stop()

    def make_model(self, env):
        options = a2c_options(self.cfg)
        options["n_steps"] = 8
        model = ResilientA2C(
            "MlpPolicy", env, **options, policy_kwargs=a2c_policy_kwargs(),
            seed=7, device="cpu",
        )
        return model

    def test_contract_reuses_game_scenario_and_only_a2c_settings(self):
        self.assertEqual(self.expected["algorithm"], "A2C")
        self.assertNotIn("ppo", self.expected)
        self.assertNotIn("dqn", self.expected)
        self.assertEqual(self.expected["reward_profile"], self.base["reward_profile"])
        self.assertEqual(self.expected["reward_weights"], self.base["reward_weights"])
        self.assertEqual(self.expected["actions"], self.base["actions"])
        self.assertEqual(self.expected["settings"], self.base["settings"])
        self.assertEqual(self.expected["a2c"]["n_steps"], self.base["ppo"]["n_steps"])
        self.assertEqual(self.expected["a2c"]["gamma"], self.base["ppo"]["gamma"])
        self.assertEqual(self.expected["a2c"]["gae_lambda"], self.base["ppo"]["gae_lambda"])
        self.assertEqual(self.expected["a2c"]["learning_rate"], self.base["ppo"]["learning_rate"])
        self.assertTrue(self.expected["a2c"]["use_rms_prop"])
        self.assertEqual(a2c_policy_kwargs()["net_arch"], {"pi": [64, 64], "vf": [64, 64]})
        self.assertIs(a2c_policy_kwargs()["activation_fn"], torch.nn.Tanh)

    def test_named_brain_resumes_optimizer_and_loads_for_play(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.make_model(SmallEnvironment(self.expected))
            model.configure_recovery(root / "initial_recoveries")
            with NamedBrain(root, "ares", self.expected) as brain:
                provenance = {"named_brain": {"name": "ares", "source_sha256": None}}
                named = NamedBrainCallback(
                    brain, root / "snapshots", run="ares-test", provenance=provenance
                )
                with contextlib.redirect_stdout(io.StringIO()):
                    model.learn(total_timesteps=16, callback=named)
                self.assertIsNotNone(brain.metadata)
                final = save_checkpoint(
                    model, root / "final_16_steps.zip", self.expected,
                    run="ares-test", reason="final", provenance=provenance,
                )
                self.assertTrue(named.publish_final(final, "final"))
                self.assertEqual(validate_checkpoint(brain.path, self.expected)["num_timesteps"], 16)

                metadata = validate_checkpoint(brain.path, self.expected)
                loaded, algorithm, contract, epsilon, play_provenance = load_agent(
                    brain.path, metadata, self.cfg, "fiel", 0.05, self.base
                )
                self.assertEqual(algorithm, "A2C")
                self.assertEqual(contract, self.expected)
                self.assertEqual(epsilon, 0.0)
                self.assertEqual(play_provenance["semantics"], "unchanged_current_contract_a2c")
                self.assertEqual(loaded.num_timesteps, 16)
                for left, right in zip(model.policy.parameters(), loaded.policy.parameters()):
                    self.assertTrue(torch.equal(left, right))
                saved_optimizer = model.policy.optimizer.state_dict()
                loaded_optimizer = loaded.policy.optimizer.state_dict()
                self.assertEqual(saved_optimizer["param_groups"], loaded_optimizer["param_groups"])
                for key, state in saved_optimizer["state"].items():
                    for item, value in state.items():
                        restored = loaded_optimizer["state"][key][item]
                        self.assertTrue(torch.equal(value, restored) if torch.is_tensor(value) else value == restored)

    def test_recovery_discards_incomplete_rollout_before_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = SmallEnvironment(self.expected, fail_once=True)
            model = self.make_model(env)
            model.configure_recovery(root / "recoveries")
            with contextlib.redirect_stdout(io.StringIO()):
                model.learn(total_timesteps=8)
            self.assertEqual(model.recovery_count, 1)
            self.assertEqual(model.discarded_rollout_steps, 2)
            self.assertEqual(model.trained_steps_this_run, 8)
            self.assertEqual(model.num_timesteps, 10)
            self.assertGreaterEqual(env.resets, 2)
            record = json.loads(next((root / "recoveries").glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "reset_ok")
            self.assertEqual(record["discarded_rollout_steps"], 2)


if __name__ == "__main__":
    unittest.main()

