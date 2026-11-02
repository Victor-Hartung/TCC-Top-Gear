"""Exact reward revision, full PPO state and recoverable named-brain publication."""
import contextlib
import copy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from stable_baselines3.common.callbacks import BaseCallback

from experiment import (atomic_json, contract, contract_hash, save_checkpoint,
                        validate_checkpoint, validate_reward_compatible_checkpoint)
from named_brain import NamedBrain, NamedBrainCallback
from resilient_ppo import ResilientPPO
from policy_transfer import initialize_actor
from reward_revision import (is_outcome_reward_revision, legacy_outcome_contract,
                             previous_outcome_contract, prior_outcome_contract,
                             previous_reward_outcome_contract, previous_time_outcome_contract)
from test_policy_transfer import SpaceEnvironment
from test_reward import ROOT
from topgear_config import ProjectConfig


def blue_target():
    with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_blue_auto.ini'):
        cfg = ProjectConfig.load(ROOT)
    return cfg, copy.deepcopy(contract(cfg))


class RewardRevisionContractTests(unittest.TestCase):
    def setUp(self):
        _, self.target = blue_target()
        self.legacy = legacy_outcome_contract(self.target)
        self.previous = previous_outcome_contract(self.target)
        self.prior = prior_outcome_contract(self.target)
        self.current_previous = previous_reward_outcome_contract(self.target)
        self.latest_previous = previous_time_outcome_contract(self.target)

    def test_only_the_exact_legacy_reward_is_reconstructed_without_mutating_target(self):
        before = copy.deepcopy(self.target)
        self.assertEqual(self.legacy['reward_version'], 8)
        self.assertEqual(self.target['reward_version'], 14)
        self.assertEqual(self.legacy['outcome_objective']['version'], 1)
        self.assertEqual(self.target['outcome_objective']['version'], 7)
        self.assertEqual(self.legacy['reward_weights']['idle_penalty'], .02)
        self.assertTrue(is_outcome_reward_revision(self.legacy, self.target))
        self.legacy['settings']['memory']['progress_address'] = 'changed'
        self.assertEqual(self.target, before)

    def test_exact_previous_revision_and_historical_target_remain_supported(self):
        before = copy.deepcopy(self.target)
        self.assertEqual(self.previous['reward_version'], 10)
        self.assertEqual(self.previous['outcome_objective']['version'], 3)
        self.assertNotIn('rank_loss_multiplier', self.previous['outcome_objective'])
        self.assertEqual(self.previous['reward_weights']['idle_penalty'], .10)
        self.assertTrue(is_outcome_reward_revision(self.previous, self.target))
        self.assertEqual(self.prior['reward_version'], 11)
        self.assertEqual(self.prior['outcome_objective']['version'], 4)
        self.assertEqual(self.prior['reward_weights']['idle_penalty'], .10)
        self.assertEqual(self.prior['outcome_objective']['rank_loss_multiplier'], 2.0)
        self.assertTrue(is_outcome_reward_revision(self.prior, self.target))
        self.assertEqual(self.current_previous['reward_version'], 12)
        self.assertEqual(self.current_previous['reward_weights']['finish'], 20.0)
        self.assertEqual(self.current_previous['reward_weights']['failure'], 5.0)
        self.assertTrue(is_outcome_reward_revision(self.current_previous, self.target))
        self.assertEqual(self.latest_previous['reward_version'], 13)
        self.assertEqual(self.latest_previous['outcome_objective']['version'], 6)
        self.assertEqual(self.latest_previous['reward_elapsed'], .002)
        self.assertEqual(self.latest_previous['reward_weights']['finish'], 40.0)
        self.assertEqual(self.latest_previous['reward_weights']['failure'], 10.0)
        self.assertTrue(is_outcome_reward_revision(self.latest_previous, self.target))
        self.assertTrue(is_outcome_reward_revision(self.legacy, self.current_previous))
        self.assertEqual(legacy_outcome_contract(self.previous), self.legacy)
        self.assertTrue(is_outcome_reward_revision(self.legacy, self.previous))
        self.assertFalse(is_outcome_reward_revision(self.target, self.previous))
        self.assertFalse(is_outcome_reward_revision(self.previous, self.legacy))
        self.assertFalse(is_outcome_reward_revision(self.target, self.target))
        with self.assertRaises(ValueError):
            previous_outcome_contract(self.previous)
        self.previous['outcome_objective']['idle_penalty'] = 99
        self.assertEqual(self.target, before)

    def test_revision_rejects_every_unrelated_contract_difference(self):
        mutations = {
            'observation_names': lambda c: c['observation_names'].__setitem__(0, 'other'),
            'observation_bounds': lambda c: c['observation_low'].__setitem__(0, -99),
            'observation_schema': lambda c: c.__setitem__('observation_schema', 9),
            'actions': lambda c: c['actions'].reverse(),
            'action_schema': lambda c: c.__setitem__('action_schema', 99),
            'ppo_gamma': lambda c: c['ppo'].__setitem__('gamma', .5),
            'ppo_lambda': lambda c: c['ppo'].__setitem__('gae_lambda', .95),
            'ppo_rate': lambda c: c['ppo'].__setitem__('learning_rate', .123),
            'rom': lambda c: c.__setitem__('rom_sha1', 'other-rom'),
            'save': lambda c: c.__setitem__('savestate_slot', 2),
            'frame_repeat': lambda c: c.__setitem__('frame_repeat', 99),
            'collision_weight': lambda c: c['reward_weights'].__setitem__('collision', 99),
            'elapsed_cost': lambda c: c.__setitem__('reward_elapsed', .005),
            'rank_weight': lambda c: c['reward_weights'].__setitem__('rank_delta', 1.),
            'grace': lambda c: c['reward_weights'].__setitem__('idle_grace_steps', 99),
            'old_idle': lambda c: c['reward_weights'].__setitem__('idle_penalty', .20),
            'memory': lambda c: c['settings']['memory'].__setitem__('progress_address', '0x1234'),
            'episode': lambda c: c['settings']['episode'].__setitem__('max_steps', '123'),
            'detector': lambda c: c['detector'].__setitem__('version', 99),
            'navigation': lambda c: c['navigation'].__setitem__('version', 99),
            'legacy_version_9': lambda c: c.__setitem__('reward_version', 9),
            'old_gain_setting': lambda c: c['outcome_objective'].__setitem__('rank_gain_multiplier', 3.),
            'old_loss_setting': lambda c: c['outcome_objective'].__setitem__('rank_loss_multiplier', 3.),
            'unexpected_field': lambda c: c.__setitem__('unrecognized', True),
        }
        for old in (self.legacy, self.previous, self.prior, self.current_previous, self.latest_previous):
            for name, mutate in mutations.items():
                with self.subTest(name=name, source_version=old['reward_version']):
                    source = copy.deepcopy(old)
                    mutate(source)
                    self.assertFalse(is_outcome_reward_revision(source, self.target))

    def test_invalid_target_never_enables_legacy_compatibility(self):
        for mutate in (
            lambda c: c.__setitem__('reward_version', 9),
            lambda c: c.__setitem__('savestate_slot', 1),
            lambda c: c['outcome_objective'].__setitem__('version', 2),
            lambda c: c['outcome_objective'].__setitem__('rank_loss_multiplier', 3.),
            lambda c: c['outcome_objective'].__setitem__('rank_gain_multiplier', 3.),
            lambda c: c['reward_weights'].__setitem__('idle_penalty', .20),
            lambda c: c['reward_weights'].__setitem__('rank_delta', 1.),
            lambda c: c['reward_weights'].__setitem__('finish', 20.0),
            lambda c: c['reward_weights'].__setitem__('failure', 5.0),
            lambda c: c.__setitem__('reward_elapsed', .002),
            lambda c: c['settings']['controls'].__setitem__('blue_auto_expected', 'false'),
        ):
            target = copy.deepcopy(self.target)
            mutate(target)
            with self.subTest(target=target['reward_version']):
                self.assertFalse(is_outcome_reward_revision(self.legacy, target))
                with self.assertRaises(ValueError):
                    legacy_outcome_contract(target)
                with self.assertRaises(ValueError):
                    previous_outcome_contract(target)


class NoopCallback(BaseCallback):
    def _on_step(self):
        return True


class RewardRevisionCheckpointTests(unittest.TestCase):
    @staticmethod
    def source_contract(target):
        return legacy_outcome_contract(target)

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='reward_revision_')))
        self.cfg, self.target = blue_target()
        self.target['ppo'].update(n_steps=8, batch_size=4, n_epochs=1)
        self.legacy = self.source_contract(self.target)
        torch.set_num_threads(1)
        self.model = ResilientPPO('MlpPolicy', SpaceEnvironment(self.legacy),
            **self.legacy['ppo'], seed=7, device='cpu',
            policy_kwargs={'net_arch': {'pi': [64, 64], 'vf': [64, 64]}})
        self.model.configure_recovery(self.root / 'legacy_recoveries')
        # Eight synthetic steps create a real nonempty Adam state; no game is used.
        with contextlib.redirect_stdout(io.StringIO()):
            self.model.learn(8)
        self.source = save_checkpoint(self.model, self.root / f"immutable_v{self.legacy['reward_version']}.zip",
                                     self.legacy, run='legacy', reason='interrupted')
        self.source_bytes = self.source.read_bytes()
        self.source_json = self.source.with_suffix('.zip.json').read_bytes()
        with NamedBrain(self.root, 'hermes-ppo', self.legacy) as brain:
            brain.initialize(self.source, {'last_update_timesteps': 8})
        self.alias = self.root / 'models/hermes-ppo.zip'
        self.alias_bytes = self.alias.read_bytes()
        self.alias_json = self.alias.with_suffix('.zip.json').read_bytes()

    def tearDown(self):
        self.assertEqual(self.source.read_bytes(), self.source_bytes)
        self.assertEqual(self.source.with_suffix('.zip.json').read_bytes(), self.source_json)

    def resumed(self):
        model = ResilientPPO.load(self.alias, env=SpaceEnvironment(self.target), device='cpu')
        model.configure_recovery(self.root / 'new_recoveries')
        return model

    def updated_checkpoint(self, brain, name='new_v11.zip'):
        model = self.resumed()
        with contextlib.redirect_stdout(io.StringIO()):
            model.learn(8, reset_num_timesteps=False)
        path = save_checkpoint(model, self.root / name, self.target, run='revision', reason='final',
            provenance={'named_brain': {'name': brain.name, 'source_sha256': brain.source_sha256}})
        return model, path

    def test_default_validation_remains_strict_and_revision_validation_preserves_metadata(self):
        metadata = validate_checkpoint(self.source)
        with self.assertRaisesRegex(ValueError, 'incompativel'):
            validate_checkpoint(self.source, self.target)
        self.assertEqual(validate_reward_compatible_checkpoint(self.source, self.target), metadata)
        self.assertEqual(metadata['contract'], self.legacy)
        self.assertEqual(metadata['num_timesteps'], 8)

    def test_revision_compatibility_cannot_bypass_zip_integrity(self):
        corrupt = self.root / 'corrupt.zip'
        corrupt.write_bytes(self.source_bytes + b'changed')
        corrupt.with_suffix('.zip.json').write_bytes(self.source_json)
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            validate_reward_compatible_checkpoint(corrupt, self.target)

    def test_resume_preserves_actor_critic_adam_and_counter_byte_exactly(self):
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain:
            brain.require_current(self.source)
            model = self.resumed()
            self.assertEqual(model.num_timesteps, self.model.num_timesteps)
            for key, tensor in self.model.policy.state_dict().items():
                self.assertTrue(torch.equal(tensor, model.policy.state_dict()[key]), key)
            old = self.model.policy.optimizer.state_dict()
            new = model.policy.optimizer.state_dict()
            self.assertTrue(old['state'])
            self.assertEqual(old['param_groups'], new['param_groups'])
            for key, state in old['state'].items():
                for item, value in state.items():
                    restored = new['state'][key][item]
                    self.assertTrue(torch.equal(value, restored) if torch.is_tensor(value)
                                    else value == restored, (key, item))
            self.assertEqual(brain.metadata['contract'], self.legacy)
        self.assertEqual(self.alias.read_bytes(), self.alias_bytes)
        self.assertEqual(self.alias.with_suffix('.zip.json').read_bytes(), self.alias_json)

    def test_play_actor_transfer_preserves_probabilities_without_learning(self):
        play = ResilientPPO('MlpPolicy', SpaceEnvironment(self.target),
            **self.target['ppo'], seed=19, device='cpu',
            policy_kwargs={'net_arch': {'pi': [64, 64], 'vf': [64, 64]}})
        report = initialize_actor(play, self.source, self.target)
        rng = np.random.default_rng(31)
        samples = rng.uniform(self.target['observation_low'], self.target['observation_high'],
                              size=(128, 61)).astype(np.float32)
        with torch.no_grad():
            observations = torch.from_numpy(samples)
            original = self.model.policy.get_distribution(observations).distribution.probs
            copied = play.policy.get_distribution(observations).distribution.probs
        self.assertTrue(torch.equal(original, copied))
        self.assertEqual(play.num_timesteps, 0)
        self.assertFalse(play.policy.optimizer.state)
        self.assertEqual(report['source_num_timesteps'], 8)
        self.assertIn('reward_revision', report['semantics'])

    def test_legacy_checkpoint_cannot_initialize_new_alias_or_be_published_as_new(self):
        with NamedBrain(self.root, 'other', self.target) as other:
            with self.assertRaisesRegex(ValueError, 'incompativel'):
                other.initialize(self.source)
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain:
            with self.assertRaisesRegex(ValueError, 'incompativel'):
                brain.publish(self.source)

    def test_first_new_publication_and_failed_json_replace_restore_exact_legacy_pair(self):
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain:
            model, source = self.updated_checkpoint(brain)
            original_replace = os.replace
            failed = False

            def fail_once(src, dst):
                nonlocal failed
                if Path(dst) == brain.path.with_suffix('.zip.json') and not failed:
                    failed = True
                    raise OSError('simulated revision metadata failure')
                return original_replace(src, dst)

            with patch('named_brain.os.replace', side_effect=fail_once):
                with self.assertRaisesRegex(OSError, 'simulated revision'):
                    brain.publish(source)
            self.assertTrue(failed)
            self.assertEqual(self.alias.read_bytes(), self.alias_bytes)
            self.assertEqual(self.alias.with_suffix('.zip.json').read_bytes(), self.alias_json)
            self.assertFalse(brain.journal.exists())
            brain.publish(source)
            self.assertEqual(validate_checkpoint(self.alias, self.target)['num_timesteps'], 16)
            self.assertEqual(model.num_timesteps, 16)
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain:
            self.assertEqual(brain.metadata['contract'], self.target)

    def test_recovery_after_crash_between_old_zip_and_new_json_restores_legacy(self):
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain:
            shutil.copy2(brain.path, brain.previous)
            shutil.copy2(brain.path.with_suffix('.zip.json'), brain.previous.with_suffix('.zip.json'))
            _, changed = self.updated_checkpoint(brain)
            shutil.copy2(changed, brain.path)
            atomic_json(brain.journal, {'had_previous': True})
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain:
            self.assertEqual(brain.metadata['contract'], self.legacy)
            self.assertFalse(brain.journal.exists())
        self.assertEqual(self.alias.read_bytes(), self.alias_bytes)
        self.assertEqual(self.alias.with_suffix('.zip.json').read_bytes(), self.alias_json)

    def test_collection_without_new_update_keeps_legacy_alias_unchanged(self):
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain:
            model = self.resumed()
            model.num_timesteps += 3
            named = NamedBrainCallback(brain, self.root / 'snapshots')
            named.init_callback(model)
            stopped = save_checkpoint(model, self.root / 'collection_only.zip', self.target,
                run='no_update', reason='interrupted',
                provenance={'named_brain': {'name': brain.name, 'source_sha256': brain.source_sha256}})
            self.assertFalse(named.publish_final(stopped, 'interrupted'))
        self.assertEqual(self.alias.read_bytes(), self.alias_bytes)
        self.assertEqual(self.alias.with_suffix('.zip.json').read_bytes(), self.alias_json)

    def test_trainer_uses_same_resume_path_and_records_full_revision_provenance(self):
        import train_hermes_ppo as trainer

        for filename in ('requirements.txt', 'requirements-dev.txt', 'constraints.txt', 'VERSION.txt'):
            shutil.copy2(ROOT / filename, self.root / filename)
        cfg = replace(self.cfg, project_dir=self.root)
        args = SimpleNamespace(resume=self.alias, refine_from=None, initialize_policy_from=None,
            seed=7, timesteps=8, checkpoint_every=8, no_step_log=True, skip_env_check=True)
        receipt = {'reset_fingerprint': {}, 'contract_sha256': contract_hash(self.target),
                   'status': 'passed', 'execution': 'synthetic_unit_test'}
        with NamedBrain(self.root, 'hermes-ppo', self.target) as brain, \
                patch.object(trainer, 'TopGearEnv', return_value=SpaceEnvironment(self.target)), \
                patch.object(trainer, 'RecordingEnv', side_effect=lambda env, *a, **k: env), \
                patch.object(trainer, 'Monitor', side_effect=lambda env, **k: env), \
                patch.object(trainer, 'RaceMetricsCallback', side_effect=lambda *a, **k: NoopCallback()), \
                patch.object(trainer, 'TrainingProgressCallback', side_effect=NoopCallback), \
                contextlib.redirect_stdout(io.StringIO()):
            trainer.train(args, cfg, self.target, receipt, brain)
        metadata = validate_checkpoint(self.alias, self.target)
        self.assertEqual(metadata['num_timesteps'], 16)
        revision = metadata['provenance']['reward_revision']
        self.assertEqual(revision['source_contract'], self.legacy)
        self.assertEqual(revision['target_contract'], self.target)
        self.assertEqual(revision['source_contract_sha256'], contract_hash(self.legacy))
        self.assertEqual(revision['target_contract_sha256'], contract_hash(self.target))
        self.assertEqual(revision['source_num_timesteps'], 8)
        self.assertIn(f"exact_reward_revision_{self.legacy['reward_version']}_to_14", revision['semantics'])
        self.assertEqual(revision['counter_at_save'], 16)
        self.assertEqual(revision['trained_steps_this_run'], 8)
        self.assertEqual(revision['last_update_timesteps_this_run'], 16)
        self.assertEqual(revision['discarded_rollout_steps'], 0)
        self.assertEqual(revision['recovery_count'], 0)
        for flag in ('actor_preserved', 'critic_preserved', 'optimizer_state_preserved', 'counter_preserved'):
            self.assertTrue(revision[flag])
        run = self.root / 'runs' / metadata['run']
        recorded = json.loads((run / 'run_config.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(recorded['resume']), self.alias)
        self.assertFalse(recorded['from_scratch'])
        for key, value in recorded['provenance']['reward_revision'].items():
            self.assertEqual(revision[key], value)
        self.assertEqual(json.loads((run / 'reward_revision.json').read_text()), revision)
        self.assertEqual(json.loads((run / 'status.json').read_text())['trained_steps_this_run'], 8)


class PreviousRewardRevisionCheckpointTests(RewardRevisionCheckpointTests):
    """The v10 brain keeps full PPO state through the v14 change."""

    @staticmethod
    def source_contract(target):
        return previous_outcome_contract(target)


class PriorRewardRevisionCheckpointTests(RewardRevisionCheckpointTests):
    """The v11 brain keeps full PPO state through the v14 change."""

    @staticmethod
    def source_contract(target):
        return prior_outcome_contract(target)


class PreviousCurrentRewardRevisionCheckpointTests(RewardRevisionCheckpointTests):
    """The v12 brain keeps full PPO state through the v14 change."""

    @staticmethod
    def source_contract(target):
        return previous_reward_outcome_contract(target)


class PreviousElapsedRewardRevisionCheckpointTests(RewardRevisionCheckpointTests):
    """The v13 brain keeps full PPO state through the v14 change."""

    @staticmethod
    def source_contract(target):
        return previous_time_outcome_contract(target)


if __name__ == '__main__':
    unittest.main()
