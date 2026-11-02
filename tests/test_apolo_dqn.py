import contextlib
import copy
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gymnasium as gym
import numpy as np
import torch

from apolo_dqn import (AbsoluteExplorationSchedule, ApoloDQN,
                       attach_exploration_schedule, dqn_contract, dqn_options,
                       dqn_policy_kwargs, load_replay_buffer_snapshot,
                       save_dqn_checkpoint, save_replay_buffer_snapshot)
from experiment import contract as environment_contract
from named_brain import NamedBrain
from test_reward import ROOT
from topgear_config import ProjectConfig
from transition_errors import LapSentinelRegression


class ContractEnvironment(gym.Env):
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
        if self.fail_once and not self.failed and self.steps == 1:
            self.failed = True
            raise LapSentinelRegression({"previous": {"lap": 0}, "rejected": {"lap": -1}})
        self.steps += 1
        done = self.steps >= 8
        return (np.zeros(self.observation_space.shape, dtype=np.float32), 0.1,
                done, False, {})


class ApoloDQNTests(unittest.TestCase):
    def setUp(self):
        self.profile = patch.dict(os.environ, {"TOPGEAR_PROFILE": "game_profile_blue_auto.ini"})
        self.profile.start()
        self.cfg = ProjectConfig.load(ROOT)
        self.base = environment_contract(self.cfg)
        self.expected = dqn_contract(self.cfg)
        torch.set_num_threads(1)

    def tearDown(self):
        self.profile.stop()

    def tiny_model(self, env, **overrides):
        options = dqn_options(self.cfg)
        options.update(buffer_size=64, learning_starts=2, batch_size=4,
                       train_freq=2, gradient_steps=1, target_update_interval=8)
        options.update(overrides)
        model = ApoloDQN(
            "MlpPolicy", env, **options, policy_kwargs=dqn_policy_kwargs(),
            seed=7, device="cpu",
        )
        model.configure_recovery(Path(tempfile.gettempdir()) / "apolo-test-recoveries")
        attach_exploration_schedule(model, 16)
        return model

    def test_contract_and_shared_ppo_values_match_blue_auto_hermes(self):
        self.assertEqual(self.expected["algorithm"], "DQN")
        self.assertNotIn("ppo", self.expected)
        self.assertEqual(self.expected["reward_profile"], self.base["reward_profile"])
        self.assertEqual(self.expected["reward_elapsed"], 0.005)
        self.assertEqual(self.expected["actions"], self.base["actions"])
        self.assertEqual(self.expected["settings"], self.base["settings"])
        options = dqn_options(self.cfg)
        self.assertEqual(options["learning_rate"], self.base["ppo"]["learning_rate"])
        self.assertEqual(options["gamma"], self.base["ppo"]["gamma"])
        self.assertEqual(options["batch_size"], self.base["ppo"]["batch_size"])
        self.assertEqual(options["max_grad_norm"], self.base["ppo"]["max_grad_norm"])
        self.assertEqual(dqn_policy_kwargs()["net_arch"], [64, 64])
        self.assertIs(dqn_policy_kwargs()["activation_fn"], torch.nn.Tanh)

    def test_epsilon_schedule_stays_decayed_after_resume(self):
        schedule = AbsoluteExplorationSchedule(0, 1_000_000)
        self.assertEqual(schedule(1.0), 1.0)
        self.assertGreater(schedule(0.95), schedule(0.90))
        self.assertAlmostEqual(schedule(0.8), 0.05)
        resumed = AbsoluteExplorationSchedule(250_000, 1_000_000)
        self.assertEqual(resumed(1.0), 0.05)
        self.assertEqual(resumed(0.0), 0.05)

    def test_recovery_marks_last_valid_transition_terminal_and_restarts(self):
        env = ContractEnvironment(self.expected, fail_once=True)
        model = self.tiny_model(env)
        with contextlib.redirect_stdout(io.StringIO()):
            model.learn(total_timesteps=8)
        self.assertEqual(model.recovery_count, 1)
        self.assertEqual(model.invalid_transitions, 1)
        self.assertGreaterEqual(env.resets, 2)
        self.assertEqual(float(model.replay_buffer.dones[0, 0]), 1.0)

    def test_named_checkpoint_restores_dqn_weights_optimizer_counter_and_buffer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = ContractEnvironment(self.expected)
            model = self.tiny_model(env)
            with contextlib.redirect_stdout(io.StringIO()):
                model.learn(total_timesteps=16)
            reference = save_replay_buffer_snapshot(model, root, "test-apolo")
            source = save_dqn_checkpoint(
                model, root / "initial.zip", self.expected, run="test-apolo",
                reason="final", provenance={"replay_buffer": reference},
            )
            with NamedBrain(root, "apolo", self.expected) as brain:
                brain.initialize(source, {"replay_buffer": reference})
                restored = ApoloDQN.load(
                    brain.path, env=ContractEnvironment(self.expected), device="cpu"
                )
                restored.configure_recovery(root / "resume-recoveries")
                buffer_path = load_replay_buffer_snapshot(
                    restored, root, brain.metadata["provenance"]["replay_buffer"]
                )
                self.assertTrue(buffer_path.is_file())
                self.assertEqual(restored.num_timesteps, model.num_timesteps)
                self.assertEqual(restored.replay_buffer.size(), model.replay_buffer.size())
                for key, value in model.policy.state_dict().items():
                    self.assertTrue(torch.equal(value, restored.policy.state_dict()[key]))
                self.assertIn("replay buffer", brain.metadata["resume_semantics"])


if __name__ == "__main__":
    unittest.main()
