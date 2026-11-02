"""Migracao offline de observacoes: comportamento inicial preservado, sem treino real."""
import copy
from pathlib import Path
import tempfile
import unittest

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO

from test_reward import ROOT
from experiment import contract, save_checkpoint, sha256, validate_checkpoint
from policy_transfer import initialize_actor, validate_policy_source
from topgear_config import ProjectConfig
from turbo_strategy import PROFILE


class SpaceEnvironment(gym.Env):
    def __init__(self, expected, *, changed_bound=False, action_count=None):
        low = np.asarray(expected['observation_low'], dtype=np.float32).copy()
        if changed_bound:
            low[0] -= 1
        self.observation_space = gym.spaces.Box(
            low, np.asarray(expected['observation_high'], dtype=np.float32))
        self.action_space = gym.spaces.Discrete(action_count or len(expected['actions']))

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return np.zeros(self.observation_space.shape, dtype=np.float32), {}

    def step(self, action):
        return np.zeros(self.observation_space.shape, dtype=np.float32), 0., False, False, {}


class NavigationPolicyTransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.target = copy.deepcopy(contract(ProjectConfig.load(ROOT), PROFILE))
        self.assertEqual(len(self.target['observation_names']), 61)
        self.source = copy.deepcopy(self.target)
        self.source.update(observation_schema=9, bridge_revision=4)
        for key in ('observation_names', 'observation_low', 'observation_high'):
            self.source[key] = self.source[key][:47]
        self.source['detector']['version'] = 2
        self.source['detector'].pop('p2_identity')
        self.source.pop('navigation')
        for c in (self.source, self.target):
            c['ppo'].update(n_steps=8, batch_size=8, n_epochs=1)
        torch.set_num_threads(1)
        self.old = self.model(self.source, 4)
        self.new = self.model(self.target, 9)

    @staticmethod
    def model(expected, seed, **env_options):
        return PPO('MlpPolicy', SpaceEnvironment(expected, **env_options), seed=seed,
                   n_steps=8, batch_size=8, n_epochs=1, device='cpu')

    def save(self, model=None, expected=None, name='source'):
        return save_checkpoint(model or self.old, Path(self.tmp) / name,
                               expected or self.source, run='synthetic_transfer', reason='unit_test')

    def test_expansion_preserves_actor_for_any_new_features_with_fresh_critic(self):
        self.old.learn(8)
        path = self.save()
        before_hash = sha256(path)
        critic = {key: value.clone() for key, value in self.new.policy.state_dict().items()
                  if key.startswith(('value_net.', 'mlp_extractor.value_net.'))}
        with self.assertRaisesRegex(ValueError, 'incompativel'):
            validate_checkpoint(path, self.target)
        report = initialize_actor(self.new, path, self.target)
        self.assertEqual(report['zero_initialized_observation_columns'], list(range(47, 61)))
        self.assertEqual(report['source_num_timesteps'], 8)
        self.assertEqual(self.new.num_timesteps, 0)
        self.assertFalse(self.new.policy.optimizer.state)
        self.assertTrue(self.old.policy.optimizer.state)
        for key, value in critic.items():
            self.assertTrue(torch.equal(value, self.new.policy.state_dict()[key]))
        old_weight = self.old.policy.state_dict()['mlp_extractor.policy_net.0.weight']
        new_weight = self.new.policy.state_dict()['mlp_extractor.policy_net.0.weight']
        self.assertTrue(torch.equal(old_weight, new_weight[:, :47]))
        self.assertEqual(torch.count_nonzero(new_weight[:, 47:]).item(), 0)
        rng = np.random.default_rng(19)
        samples = rng.uniform(self.target['observation_low'], self.target['observation_high'],
                              size=(128, 61)).astype(np.float32)
        with torch.no_grad():
            old_logits = self.old.policy.get_distribution(torch.from_numpy(samples[:, :47].copy())).distribution.logits
            new_logits = self.new.policy.get_distribution(torch.from_numpy(samples)).distribution.logits
        # GEMM com 47 e 61 colunas pode diferir no ultimo arredondamento FP32.
        torch.testing.assert_close(new_logits, old_logits, rtol=1e-6, atol=1e-7)
        self.assertEqual(sha256(path), before_hash)

    def test_rejects_unrelated_contract_changes_and_unrecognized_navigation(self):
        path = self.save()
        changes = [
            ('reward', lambda c: c['reward_weights'].__setitem__('collision', 99)),
            ('actions', lambda c: c['actions'].reverse()),
            ('settings', lambda c: c['settings']['episode'].__setitem__('max_steps', '999')),
            ('ppo', lambda c: c['ppo'].__setitem__('gamma', .5)),
            ('prefix_names', lambda c: c['observation_names'].__setitem__(0, 'different')),
            ('prefix_low', lambda c: c['observation_low'].__setitem__(0, -9)),
            ('appended_bound', lambda c: c['observation_high'].__setitem__(60, 2)),
            ('navigation', lambda c: c['navigation'].__setitem__('unexpected_setting', True)),
            ('detector', lambda c: c['detector'].__setitem__('horizon_frames', 31)),
        ]
        for label, mutate in changes:
            with self.subTest(label=label):
                target = copy.deepcopy(self.target)
                mutate(target)
                with self.assertRaisesRegex(ValueError, 'recusada'):
                    validate_policy_source(path, target)

    def test_rejects_actual_zip_observation_bounds_or_actions_not_matching_metadata(self):
        for label, options in [('bounds', {'changed_bound': True}), ('actions', {'action_count': 11})]:
            with self.subTest(label=label):
                source = self.model(self.source, 4, **options)
                path = self.save(source, name=label)
                with self.assertRaisesRegex(ValueError, 'Espacos reais do ZIP'):
                    initialize_actor(self.new, path, self.target)

    def test_rejects_nonfinite_actor_before_modifying_destination(self):
        before = {key: value.clone() for key, value in self.new.policy.state_dict().items()}
        with torch.no_grad():
            self.old.policy.action_net.weight[0, 0] = float('nan')
        path = self.save()
        with self.assertRaisesRegex(ValueError, 'nao finitos'):
            initialize_actor(self.new, path, self.target)
        for key, value in before.items():
            self.assertTrue(torch.equal(value, self.new.policy.state_dict()[key]))

    def test_rejects_actual_relu_network_despite_tanh_metadata(self):
        other = PPO('MlpPolicy', SpaceEnvironment(self.source), n_steps=8, batch_size=8,
                    n_epochs=1, device='cpu', policy_kwargs={'activation_fn': torch.nn.ReLU})
        path = self.save(other, name='relu')
        with self.assertRaisesRegex(ValueError, 'ativacao real'):
            initialize_actor(self.new, path, self.target)

    def test_rejects_destination_with_existing_learning_state_or_wrong_bounds(self):
        path = self.save()
        self.new.num_timesteps = 1
        with self.assertRaisesRegex(ValueError, 'modelo novo'):
            initialize_actor(self.new, path, self.target)
        self.new.num_timesteps = 0
        self.new.policy.optimizer.state[0] = {'step': torch.tensor(1.)}
        with self.assertRaisesRegex(ValueError, 'modelo novo'):
            initialize_actor(self.new, path, self.target)
        bad = self.model(self.target, 9, changed_bound=True)
        with self.assertRaisesRegex(ValueError, 'Espacos reais do destino'):
            initialize_actor(bad, path, self.target)

    def test_refuses_chained_reward_and_observation_migration(self):
        source = copy.deepcopy(self.source)
        source.update(reward_profile='road_v2', reward_version=4)
        source.pop('turbo_strategy')
        path = self.save(expected=source)
        with self.assertRaisesRegex(ValueError, 'recusada'):
            validate_policy_source(path, self.target)

    def test_changed_source_metadata_or_zip_hash_is_refused(self):
        path = self.save()
        with path.open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            initialize_actor(self.new, path, self.target)


if __name__ == '__main__':
    unittest.main()
