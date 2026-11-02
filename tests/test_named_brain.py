"""Fixed brain names preserve real PPO state and reject unsafe publications."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import torch

from test_reward import ROOT
from callbacks import RaceMetricsCallback
from experiment import atomic_json, contract, save_checkpoint, sha256, validate_checkpoint
from named_brain import NamedBrain, NamedBrainCallback
from resilient_ppo import ResilientPPO
from test_policy_transfer import SpaceEnvironment
from topgear_config import ProjectConfig


class NamedBrainTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.expected = copy.deepcopy(contract(ProjectConfig.load(ROOT)))
        self.expected["ppo"].update(n_steps=8, batch_size=4, n_epochs=1)
        torch.set_num_threads(1)
        self.model = ResilientPPO("MlpPolicy", SpaceEnvironment(self.expected),
            **self.expected["ppo"], seed=7, device="cpu",
            policy_kwargs={"net_arch": {"pi": [64, 64], "vf": [64, 64]}})
        self.model.configure_recovery(self.root / "recoveries")
        with contextlib.redirect_stdout(io.StringIO()):
            self.model.learn(8)
        self.original = save_checkpoint(self.model, self.root / "original.zip",
            self.expected, run="seed", reason="interrupted")
        self.original_bytes = self.original.read_bytes()
        self.original_metadata = self.original.with_suffix(".zip.json").read_bytes()
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            brain.initialize(self.original, {"last_update_timesteps": 8})

    def provenance(self, brain):
        return {"named_brain": {"name": brain.name, "source_sha256": brain.source_sha256}}

    def save(self, brain, name, reason="final", provenance=None):
        return save_checkpoint(self.model, self.root / name, self.expected,
            run="continued", reason=reason,
            provenance=self.provenance(brain) if provenance is None else provenance)

    def test_resume_real_weights_adam_and_counter_and_publish_updates(self):
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            self.assertEqual(sha256(brain.path), sha256(self.original))
            model = ResilientPPO.load(brain.path, env=SpaceEnvironment(self.expected), device="cpu")
            self.assertEqual(model.num_timesteps, 8)
            for key, tensor in self.model.policy.state_dict().items():
                self.assertTrue(torch.equal(tensor, model.policy.state_dict()[key]))
            original_optimizer = self.model.policy.optimizer.state_dict()
            restored_optimizer = model.policy.optimizer.state_dict()
            self.assertEqual(original_optimizer["param_groups"], restored_optimizer["param_groups"])
            for key, state in original_optimizer["state"].items():
                for item, value in state.items():
                    restored = restored_optimizer["state"][key][item]
                    self.assertTrue(torch.equal(value, restored) if torch.is_tensor(value) else value == restored)
            model.configure_recovery(self.root / "new_recoveries")
            model_dir = self.root / "snapshots"
            race = RaceMetricsCallback(model_dir, self.expected, "continued", 8, self.provenance(brain))
            named = NamedBrainCallback(brain, model_dir)
            with contextlib.redirect_stdout(io.StringIO()):
                model.learn(16, reset_num_timesteps=False, callback=[race, named])
            self.assertEqual(model.num_timesteps, 24)
            self.assertEqual(validate_checkpoint(brain.path)["num_timesteps"], 16)
            final = save_checkpoint(model, model_dir / "final_24_steps.zip",
                self.expected, run="continued", reason="final", provenance=self.provenance(brain))
            self.assertTrue(named.publish_final(final, "final"))
            self.assertEqual(validate_checkpoint(brain.path)["num_timesteps"], 24)
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        self.assertEqual(self.original.with_suffix(".zip.json").read_bytes(), self.original_metadata)
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            self.assertEqual(brain.metadata["num_timesteps"], 24)

    def test_rejects_other_lineage_old_checkpoint_candidates_and_failed(self):
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            old_hash = sha256(brain.path)
            unrelated = self.save(brain, "unrelated.zip", provenance={})
            with self.assertRaisesRegex(ValueError, "linhagem"):
                brain.publish(unrelated)
            for reason in ("training_candidate_not_evaluation", "failed"):
                source = self.save(brain, reason + ".zip", reason=reason)
                with self.assertRaisesRegex(ValueError, "Somente"):
                    brain.publish(source)
            self.model.num_timesteps = 4
            older = self.save(brain, "older.zip")
            with self.assertRaisesRegex(ValueError, "regredir"):
                brain.publish(older)
            self.assertEqual(sha256(brain.path), old_hash)

    def test_exclusive_training_and_explicit_source_guard(self):
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            brain.require_current(self.original)
            with self.assertRaisesRegex(RuntimeError, "bloqueado"):
                with NamedBrain(self.root, "hermes-ppo", self.expected):
                    pass
            self.model.num_timesteps = 16
            with torch.no_grad():
                next(self.model.policy.parameters()).add_(1)
            different = self.save(brain, "different.zip")
            with self.assertRaisesRegex(ValueError, "versao atual"):
                brain.require_current(different)

    def test_second_replace_failure_restores_valid_previous_pair(self):
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            old_hash = sha256(brain.path)
            self.model.num_timesteps = 16
            source = self.save(brain, "next.zip")
            original_replace = os.replace
            failed = False
            def fail_once(src, dst):
                nonlocal failed
                if Path(dst) == brain.path.with_suffix(".zip.json") and not failed:
                    failed = True
                    raise OSError("simulated metadata write failure")
                return original_replace(src, dst)
            with patch("named_brain.os.replace", side_effect=fail_once):
                with self.assertRaisesRegex(OSError, "simulated"):
                    brain.publish(source)
            self.assertTrue(failed)
            self.assertEqual(validate_checkpoint(brain.path)["model_sha256"], old_hash)
            self.assertFalse(brain.journal.exists())

    def test_recover_previous_pair_after_simulated_process_crash(self):
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            old_hash = sha256(brain.path)
            shutil.copy2(brain.path, brain.previous)
            shutil.copy2(brain.path.with_suffix(".zip.json"), brain.previous.with_suffix(".zip.json"))
            self.model.num_timesteps = 16
            changed = self.save(brain, "changed.zip")
            shutil.copy2(changed, brain.path)
            atomic_json(brain.journal, {"had_previous": True})
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            self.assertEqual(validate_checkpoint(brain.path)["model_sha256"], old_hash)

    def test_collection_interrupt_publishes_but_optimizer_interrupt_keeps_alias(self):
        class InterruptDuringUpdate(ResilientPPO):
            def train(self):
                with torch.no_grad():
                    next(self.policy.parameters()).add_(1)
                raise KeyboardInterrupt
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            old_hash = sha256(brain.path)
            model = InterruptDuringUpdate.load(brain.path, env=SpaceEnvironment(self.expected), device="cpu")
            model.configure_recovery(self.root / "interrupt_recovery")
            named = NamedBrainCallback(brain, self.root / "snapshots")
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    model.learn(8, reset_num_timesteps=False, callback=named)
            interrupted = save_checkpoint(model, self.root / "partial_update.zip",
                self.expected, run="interrupted", reason="interrupted", provenance=self.provenance(brain))
            self.assertFalse(named.publish_final(interrupted, "interrupted"))
            self.assertEqual(sha256(brain.path), old_hash)
            stable = ResilientPPO.load(brain.path, env=SpaceEnvironment(self.expected), device="cpu")
            stable.configure_recovery(self.root / "stable_recovery")
            stable.num_timesteps += 3
            named = NamedBrainCallback(brain, self.root / "other_snapshots")
            named.init_callback(stable)
            stopped = save_checkpoint(stable, self.root / "collection_interrupt.zip",
                self.expected, run="collection", reason="interrupted", provenance=self.provenance(brain))
            self.assertTrue(named.publish_final(stopped, "interrupted"))
            self.assertEqual(validate_checkpoint(brain.path)["num_timesteps"], 11)

    def test_completed_update_preserved_when_periodic_interval_is_longer(self):
        class InterruptSecondUpdate(ResilientPPO):
            def train(self):
                if self.trained_steps_this_run:
                    with torch.no_grad():
                        next(self.policy.parameters()).add_(1)
                    raise KeyboardInterrupt
                super().train()
        with NamedBrain(self.root, "hermes-ppo", self.expected) as brain:
            model = InterruptSecondUpdate.load(brain.path, env=SpaceEnvironment(self.expected), device="cpu")
            model.configure_recovery(self.root / "long_interval_recovery")
            model_dir = self.root / "long_interval_snapshots"
            race = RaceMetricsCallback(model_dir, self.expected, "continued", 16, self.provenance(brain))
            named = NamedBrainCallback(brain, model_dir)
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    model.learn(16, reset_num_timesteps=False, callback=[race, named])
            self.assertFalse((model_dir / "checkpoint_16_steps.zip").exists())
            self.assertTrue((model_dir / "named_update_16_steps.zip").exists())
            self.assertEqual(validate_checkpoint(brain.path)["num_timesteps"], 16)
            interrupted = save_checkpoint(model, model_dir / "interrupted_24_steps.zip",
                self.expected, run="interrupted", reason="interrupted", provenance=self.provenance(brain))
            self.assertFalse(named.publish_final(interrupted, "interrupted"))
            self.assertEqual(validate_checkpoint(brain.path)["num_timesteps"], 16)

    def test_invalid_names_and_contract_rejected(self):
        for name in ("../other", "CON", "hermes/ppo", ""):
            with self.assertRaises(ValueError):
                NamedBrain(self.root, name, self.expected)
        incompatible = copy.deepcopy(self.expected)
        incompatible["action_schema"] += 1
        with self.assertRaisesRegex(ValueError, "incompativel"):
            with NamedBrain(self.root, "hermes-ppo", incompatible):
                pass


if __name__ == "__main__":
    unittest.main()
