"""Assiste a um ator ou compara varios no mesmo save, sem aprender ou salvar pesos."""
import argparse
from pathlib import Path

import torch
import numpy as np
from stable_baselines3 import PPO

from avaliar_modelo import evaluate
from check_navigation_migration import ContractSpaces
from env_topgear import TopGearEnv
from experiment import (atomic_json, unique_name, contract, assert_live_preflight,
                        ppo_options, source_hashes, sha256)
from policy_transfer import validate_policy_source, initialize_actor
from topgear_config import ProjectConfig


class BrakeAblation:
    """Intervencao diagnostica declarada; nao altera a politica salva."""
    mapping = {2: 1, 7: 3, 8: 4}

    def __init__(self, model):
        self.model = model
        self.steps = 0
        self.interventions = []

    def predict(self, observation, deterministic=True):
        action, state = self.model.predict(observation, deterministic=deterministic)
        self.steps += 1
        requested = int(action)
        applied = self.mapping.get(requested, requested)
        if applied != requested:
            self.interventions.append(dict(step=self.steps, requested_action=requested,
                                           applied_action=applied))
        return np.asarray(applied, dtype=np.asarray(action).dtype), state


class ThrottleAblation(BrakeAblation):
    """Referencia com aceleracao continua e direcao original; nao e PPO puro."""
    mapping = {0: 1, 2: 1, 5: 3, 6: 4, 7: 3, 8: 4}


class ThrottleWithoutTurboAblation(ThrottleAblation):
    mapping = {**ThrottleAblation.mapping, 9: 1}


DIAGNOSTIC_CONTROLLERS = {
    'diagnostic_without_brake': BrakeAblation,
    'diagnostic_continuous_throttle': ThrottleAblation,
    'diagnostic_continuous_throttle_without_turbo': ThrottleWithoutTurboAblation,
}


def main():
    cfg = ProjectConfig.load()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', type=Path, default=[
        cfg.project_dir/'models/hermes-ppo_20260915_031924_155890/final_10240_steps.zip'])
    diagnostic = parser.add_mutually_exclusive_group()
    diagnostic.add_argument('--diagnose-braking', action='store_true',
                        help='Um modelo: corrida original e corrida com freio trocado por aceleracao, preservando direcao; somente diagnostico')
    diagnostic.add_argument('--diagnose-pace', action='store_true',
                            help='Quatro corridas: original, sem freio, acelerando sempre, acelerando sempre sem turbo; sem treino')
    args = parser.parse_args()
    if (args.diagnose_braking or args.diagnose_pace) and len(args.models) != 1:
        parser.error('Diagnostico exige exatamente um modelo')
    expected = contract(cfg)
    receipt = assert_live_preflight(cfg, expected)
    torch.set_num_threads(1)
    prepared = []
    # Valida todos os arquivos antes de abrir o servidor. A importacao abaixo
    # e apenas em memoria; o critico novo nunca sera treinado nem consultado.
    for source in args.models:
        validate_policy_source(source, expected)
        model = PPO('MlpPolicy', ContractSpaces(expected), **ppo_options(cfg), seed=42,
                    device='cpu', policy_kwargs={'net_arch': {'pi': [64,64], 'vf': [64,64]}})
        transfer = initialize_actor(model, source, expected)
        model.policy.set_training_mode(False)
        prepared.append((source, model, transfer, 'original'))
        if args.diagnose_braking or args.diagnose_pace:
            prepared.append((source, model, transfer, 'diagnostic_without_brake'))
        if args.diagnose_pace:
            prepared.append((source, model, transfer, 'diagnostic_continuous_throttle'))
            prepared.append((source, model, transfer, 'diagnostic_continuous_throttle_without_turbo'))
    path = cfg.project_dir/'runs/avaliacao_modelo'/(unique_name('comparacao_correcao')+'.json')
    execution = ('live_bizhawk_pace_ablation' if args.diagnose_pace else
                 'live_bizhawk_brake_ablation' if args.diagnose_braking else 'live_bizhawk_actor_comparison')
    report = dict(execution=execution, training_enabled=False,
                  deterministic=True, contract=expected, source_hashes=source_hashes(cfg.project_dir),
                  preflight_receipt=receipt, status='starting', comparisons=[])
    env = None
    try:
        env = TopGearEnv(cfg.project_dir, expected_reset=receipt['reset_fingerprint'])
        for source, model, transfer, variant in prepared:
            controller = DIAGNOSTIC_CONTROLLERS[variant](model) if variant in DIAGNOSTIC_CONTROLLERS else model
            child = dict(source_model=str(source.resolve()), transfer=transfer,
                         requested_episodes=1, compare_accelerate=False, gamma=model.gamma,
                         training_enabled=False, episodes=[], variant=variant,
                         action_override=variant != 'original',
                         interventions=controller.interventions if isinstance(controller, BrakeAblation) else [])
            if isinstance(controller, BrakeAblation):
                child['override_mapping'] = controller.mapping
                child['note'] = 'Intervencao diagnostica declarada no mapping; direcao preservada. Resultado nao representa pilotagem autonoma do PPO original.'
            report['comparisons'].append(child)
            print('POLITICA:', source, 'VARIANTE:', variant, flush=True)
            evaluate(env, controller, 1, child)
            if model.num_timesteps != 0 or model.policy.optimizer.state:
                raise RuntimeError('Comparacao nao pode aprender')
        initials = [c['episodes'][0]['initial_state'] for c in report['comparisons']]
        report['identical_initial_state'] = all(s == initials[0] for s in initials)
        if not report['identical_initial_state']:
            raise ValueError('Comparacao partiu de estados diferentes')
        report['summary'] = []
        for child in report['comparisons']:
            s = child['episodes'][0]['summary']
            f = s['final_state']
            report['summary'].append(dict(variant=child['variant'], steps=s['steps'],
                completed=bool(f['race_completed']), position=f['rank']+1,
                collisions=f['collisions_total'], offtrack_fraction=s['offtrack_fraction'],
                mean_speed_raw=s['mean_speed_raw'], nitro_remaining=f['nitro'],
                interventions=len(child['interventions'])))
        print('RESUMO DAS CORRIDAS:', flush=True)
        for row in report['summary']:
            print(row, flush=True)
        report['status'] = 'completed'
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
    except Exception as exc:
        report['status'] = 'failed'; report['error'] = repr(exc)
        raise
    finally:
        try:
            if env is not None: env.close()
        finally:
            report['source_models_preserved'] = all(sha256(source) == transfer['source_model_sha256'] for source, _, transfer, _ in prepared)
            atomic_json(path, report)
            print('COMPARACAO SALVA:', path, flush=True)


if __name__ == '__main__':
    main()
