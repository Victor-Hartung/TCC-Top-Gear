"""Confere importacao do ator em memoria, sem BizHawk, treino ou salvar modelo."""
from __future__ import annotations

import argparse
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO

from experiment import contract, atomic_json, unique_name, sha256, ppo_options
from policy_transfer import validate_policy_source, initialize_actor
from topgear_config import ProjectConfig


class ContractSpaces(gym.Env):
    def __init__(self, expected):
        self.observation_space = gym.spaces.Box(np.array(expected['observation_low'], dtype=np.float32),
                                                np.array(expected['observation_high'], dtype=np.float32))
        self.action_space = gym.spaces.Discrete(len(expected['actions']))

    def reset(self, **kwargs):
        raise RuntimeError('Auditoria nao permite executar episodios')

    def step(self, action):
        raise RuntimeError('Auditoria nao permite executar passos')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    args = parser.parse_args()
    cfg = ProjectConfig.load()
    expected = contract(cfg)
    metadata = validate_policy_source(args.model, expected)
    torch.set_num_threads(1)
    original = PPO.load(args.model, device='cpu')
    destination = PPO('MlpPolicy', ContractSpaces(expected), **ppo_options(cfg), seed=42,
                      device='cpu', policy_kwargs={'net_arch': {'pi': [64,64], 'vf': [64,64]}})
    critic = {k: v.clone() for k, v in destination.policy.state_dict().items()
              if k.startswith(('value_net.', 'mlp_extractor.value_net.'))}
    transfer = initialize_actor(destination, args.model, expected)
    rng = np.random.default_rng(42)
    old_count = len(metadata['contract']['observation_names'])
    observations = rng.uniform(expected['observation_low'], expected['observation_high'],
                               size=(256, len(expected['observation_names']))).astype(np.float32)
    with torch.no_grad():
        before = original.policy.get_distribution(torch.as_tensor(observations[:,:old_count])).distribution.probs
        after = destination.policy.get_distribution(torch.as_tensor(observations)).distribution.probs
    checks = {
        'actor_probabilities_close': bool(torch.allclose(before, after, rtol=1e-5, atol=1e-6)),
        'fresh_critic_unchanged': all(torch.equal(value, destination.policy.state_dict()[key]) for key, value in critic.items()),
        'counter_zero': destination.num_timesteps == 0,
        'optimizer_empty': not destination.policy.optimizer.state,
        'source_file_preserved': sha256(args.model) == metadata['model_sha256'],
    }
    report = {'execution': 'offline_weight_migration_audit', 'training_enabled': False,
              'new_bizhawk_validation': False, 'model_saved': False,
              'target_contract': expected, 'transfer': transfer, 'checks': checks,
              'probability_max_absolute_difference': float((before-after).abs().max()),
              'comparison_input': f'256 synthetic observations; identical first {old_count} source features, random appended features if any; not driving evaluation'}
    output = cfg.project_dir / 'runs/analysis/native_navigation' / (unique_name('migration_audit')+'.json')
    atomic_json(output, report)
    print(checks)
    print('RELATORIO OFFLINE:', output)
    if not all(checks.values()):
        raise ValueError('Importacao do ator reprovada; consulte relatorio')


if __name__ == '__main__':
    main()
