"""Refinamento explicito: somente reduzir learning_rate do contrato manual.

Nao e conversao de observacoes/acoes/recompensa. Conserva ator, critico,
momentos Adam e contador; comeca um rollout novo e altera somente a taxa.
"""
from copy import deepcopy
from pathlib import Path
import math

from experiment import validate_checkpoint


def validate_contract_change(source: dict, target: dict) -> tuple[float, float]:
    if (source.get('observation_schema') != 11 or target.get('observation_schema') != 11
            or source.get('action_schema') != 3 or target.get('action_schema') != 3
            or source.get('reward_profile') != 'road_v5_race'
            or source.get('reward_version') != 7):
        raise ValueError('Refinamento exige contrato azul/manual conhecido')
    old = float(source['ppo']['learning_rate'])
    new = float(target['ppo']['learning_rate'])
    if not math.isfinite(old) or not math.isfinite(new) or not 0 < new < old:
        raise ValueError('Refinamento exige taxa positiva menor que a origem')
    adjusted = deepcopy(source)
    adjusted['ppo']['learning_rate'] = new
    if adjusted != target:
        raise ValueError('Refinamento recusado: diferencas alem de learning_rate')
    return old, new


def validate_refinement_source(path: Path, expected: dict) -> dict:
    metadata = validate_checkpoint(path)
    validate_contract_change(metadata['contract'], expected)
    return metadata


def apply_optimizer_rate(model, metadata: dict, expected: dict) -> dict:
    from stable_baselines3.common.utils import FloatSchedule
    old, new = validate_contract_change(metadata['contract'], expected)
    # O carregamento dos momentos Adam restaura a taxa antiga nos param_groups.
    # Atualiza tambem esses grupos antes do primeiro treino, sem zerar momentos.
    model.learning_rate = new
    model.lr_schedule = FloatSchedule(new)
    for group in model.policy.optimizer.param_groups:
        group['lr'] = new
    return dict(semantics='actor_critic_adam_moments_and_counter_preserved; fresh_rollout; lower_learning_rate',
                source_model_sha256=metadata['model_sha256'],
                source_contract_sha256=metadata['contract_sha256'],
                source_num_timesteps=metadata['num_timesteps'],
                source_learning_rate=old, target_learning_rate=new)


def validate_inference_source(path: Path, expected: dict, *, allow_lower_rate_source=False) -> dict:
    """Excecao explicita apenas para inferencia; nunca autoriza resume comum."""
    metadata = validate_checkpoint(path)
    if metadata['contract'] != expected:
        if not allow_lower_rate_source:
            raise ValueError('Modelo incompativel com contrato da avaliacao')
        validate_contract_change(metadata['contract'], expected)
    return metadata
