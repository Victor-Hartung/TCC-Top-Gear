"""Migracoes explicitas somente do ator; nunca sao uma retomada de checkpoint."""
import copy
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.torch_layers import FlattenExtractor

from experiment import validate_checkpoint
from reward_revision import is_outcome_reward_revision, legacy_outcome_contract
from turbo_strategy import PROFILE, SETTINGS as TURBO_SETTINGS


def _changed(source: dict, expected: dict) -> set:
    return {key for key in set(source) | set(expected) if source.get(key) != expected.get(key)}


def _race_reward_correction(source: dict, expected: dict) -> bool:
    from race_objective import PROFILE as RACE_PROFILE, SETTINGS as RACE_SETTINGS
    from driving_strategy import PROFILE as DRIVING_PROFILE, SETTINGS as DRIVING_SETTINGS
    if (expected.get('reward_profile') != RACE_PROFILE or expected.get('reward_version') != 7
            or expected.get('race_objective') != RACE_SETTINGS
            or source.get('observation_schema') != 10 or expected.get('observation_schema') != 10
            or len(source.get('observation_names', [])) != 61):
        return False
    profiles = {PROFILE: (5, 'turbo_strategy', TURBO_SETTINGS),
                DRIVING_PROFILE: (6, 'driving_strategy', DRIVING_SETTINGS)}
    permitted = profiles.get(source.get('reward_profile'))
    if permitted is None:
        return False
    version, key, settings = permitted
    return (source.get('reward_version') == version and source.get(key) == settings
            and _changed(source, expected) == {'reward_profile', 'reward_version', key, 'race_objective'})


def _blue_auto_race_transfer(source: dict, expected: dict) -> bool:
    """Ator 61/10 do vermelho automatico para azul automatico, com recompensa nova.

    O save, o carro e o objetivo mudam: critico/Adam/contador nao sao portados.
    A identidade do novo save e checada separadamente pelo preflight real.
    """
    from race_objective import PROFILE as RACE_PROFILE, SETTINGS as RACE_SETTINGS
    if (source.get('savestate_slot') != 1 or expected.get('savestate_slot') != 3
            or source.get('reward_profile') != PROFILE or source.get('reward_version') != 5
            or source.get('turbo_strategy') != TURBO_SETTINGS
            or expected.get('reward_profile') != RACE_PROFILE
            or expected.get('reward_version') != 7
            or expected.get('race_objective') != RACE_SETTINGS
            or source.get('observation_schema') != 10 or expected.get('observation_schema') != 10
            or source.get('bridge_revision') != 5 or expected.get('bridge_revision') != 5
            or len(source.get('observation_names', [])) != 61
            or len(source.get('actions', [])) != 10):
        return False
    source_settings = source.get('settings')
    expected_settings = expected.get('settings')
    if not isinstance(source_settings, dict) or not isinstance(expected_settings, dict):
        return False
    normalized = copy.deepcopy(source_settings)
    if not isinstance(normalized.get('controls'), dict):
        return False
    if 'blue_auto_expected' in normalized['controls']:
        return False
    normalized['controls']['blue_auto_expected'] = 'true'
    return (expected_settings == normalized and
            _changed(source, expected) == {
                'reward_profile', 'reward_version', 'turbo_strategy',
                'race_objective', 'savestate_slot', 'settings'})


def _blue_auto_outcome_transfer(source: dict, expected: dict) -> bool:
    """Extensao exata do piloto azul: somente objetivo e lambda mudam.

    Aceita tambem a origem vermelha ja autorizada pela migracao anterior.
    Transfere somente o ator; a retomada da revisao de recompensa usa outro validador.
    """
    from outcome_objective import (PROFILE as OUTCOME_PROFILE, LEGACY_SETTINGS,
                                   LEGACY_VERSION, PREVIOUS_VERSION, PRIOR_VERSION,
                                   PREVIOUS_REWARD_VERSION, PREVIOUS_TIME_VERSION,
                                   REWARD_VERSION, GAE_LAMBDA,
                                   SOURCE_GAE_LAMBDA)
    from race_objective import PROFILE as RACE_PROFILE, SETTINGS as RACE_SETTINGS
    if expected.get('reward_version') in (PREVIOUS_VERSION, PRIOR_VERSION,
                                          PREVIOUS_REWARD_VERSION, PREVIOUS_TIME_VERSION,
                                          REWARD_VERSION):
        if is_outcome_reward_revision(source, expected):
            return True
        try:
            expected = legacy_outcome_contract(expected)
        except ValueError:
            return False
    if (expected.get('reward_profile') != OUTCOME_PROFILE
            or 'race_objective' in expected
            or expected.get('reward_version') != LEGACY_VERSION
            or expected.get('outcome_objective') != LEGACY_SETTINGS
            or expected.get('savestate_slot') != 3
            or expected.get('observation_schema') != 10
            or expected.get('bridge_revision') != 5
            or len(expected.get('observation_names', [])) != 61
            or len(expected.get('actions', [])) != 10
            or expected.get('settings', {}).get('controls', {}).get('blue_auto_expected') != 'true'
            or expected.get('ppo', {}).get('gae_lambda') != GAE_LAMBDA):
        return False
    previous = copy.deepcopy(expected)
    previous.pop('outcome_objective')
    previous.update(reward_profile=RACE_PROFILE, reward_version=7, race_objective=RACE_SETTINGS)
    previous['ppo']['gae_lambda'] = SOURCE_GAE_LAMBDA
    return source == previous or _blue_auto_race_transfer(source, previous)


def _navigation_migration(source: dict, expected: dict) -> bool:
    """Somente o contrato conhecido de 47 features pode receber as 14 novas."""
    if (source.get('observation_schema'), expected.get('observation_schema'),
            source.get('bridge_revision'), expected.get('bridge_revision')) != (9, 10, 4, 5):
        return False
    if any(value.get('reward_profile') != PROFILE or value.get('reward_version') != 5
           or value.get('turbo_strategy') != TURBO_SETTINGS for value in (source, expected)):
        return False
    allowed = {'observation_schema', 'observation_names', 'observation_low',
               'observation_high', 'bridge_revision', 'detector', 'navigation'}
    if _changed(source, expected) != allowed or 'navigation' in source:
        return False
    # Os modulos atuais fixam o significado e os limites das features adicionadas.
    from live_detector import SETTINGS as DETECTOR_SETTINGS
    from native_navigation import SETTINGS as NAVIGATION_SETTINGS
    from telemetry import OBSERVATION_NAMES, ObservationBuilder

    if expected.get('navigation') != NAVIGATION_SETTINGS or expected.get('detector') != DETECTOR_SETTINGS:
        return False
    detector = dict(expected['detector'])
    if detector.pop('p2_identity', None) != 'dynamic_record_offset' or detector.get('version') != 3:
        return False
    detector['version'] = 2
    if source.get('detector') != detector:
        return False
    current = {'observation_names': list(OBSERVATION_NAMES),
               'observation_low': ObservationBuilder.low().tolist(),
               'observation_high': ObservationBuilder.high().tolist()}
    for key, values in current.items():
        if len(values) != 61 or expected.get(key) != values or source.get(key) != values[:47]:
            return False
    return True


def validate_policy_source(path: Path, expected: dict) -> dict:
    metadata = validate_checkpoint(path)
    source = metadata['contract']
    reward_migration = (
        source.get('reward_profile') == 'road_v2' and source.get('reward_version') == 4
        and 'turbo_strategy' not in source
        and expected.get('reward_profile') == PROFILE and expected.get('reward_version') == 5
        and expected.get('turbo_strategy') == TURBO_SETTINGS
        and _changed(source, expected) == {'reward_profile', 'reward_version', 'turbo_strategy'})
    if (not reward_migration and not _navigation_migration(source, expected)
            and not _race_reward_correction(source, expected)
            and not _blue_auto_race_transfer(source, expected)
            and not _blue_auto_outcome_transfer(source, expected)):
        raise ValueError('Transferencia recusada: migracao nao autorizada ou diferencas de contrato inesperadas: '
                         + ', '.join(sorted(_changed(source, expected))))
    return metadata


def _assert_spaces(model, expected: dict, label: str) -> None:
    try:
        low = np.asarray(expected['observation_low'], dtype=np.float32)
        high = np.asarray(expected['observation_high'], dtype=np.float32)
        names = expected['observation_names']
        if (low.ndim != 1 or low.shape != high.shape or len(names) != len(low)
                or not np.all(np.isfinite(low)) or not np.all(np.isfinite(high))
                or np.any(low > high)):
            raise ValueError('limites invalidos')
        obs = model.observation_space
        if (not isinstance(obs, gym.spaces.Box) or obs.dtype != np.dtype(np.float32)
                or obs.shape != low.shape or not np.array_equal(obs.low, low)
                or not np.array_equal(obs.high, high)):
            raise ValueError('observacoes/bounds')
        actions = model.action_space
        if (not isinstance(actions, gym.spaces.Discrete) or actions.start != 0
                or actions.n != len(expected['actions'])):
            raise ValueError('acoes')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f'Espacos reais do {label} divergem de seu contrato: {exc}') from exc


def initialize_actor(model, path: Path, expected: dict) -> dict:
    metadata = validate_policy_source(path, expected)
    if model.num_timesteps != 0 or model.policy.optimizer.state:
        raise ValueError('Destino deve ser modelo novo, com contador e otimizador vazios')
    source = PPO.load(path, device='cpu')
    _assert_spaces(source, metadata['contract'], 'ZIP de origem')
    _assert_spaces(model, expected, 'destino')
    for network, label in ((source, 'origem'), (model, 'destino')):
        if (network.policy.activation_fn is not torch.nn.Tanh
                or network.policy.net_arch != {'pi': [64, 64], 'vf': [64, 64]}):
            raise ValueError('Arquitetura/ativacao real do ator diverge do contrato: ' + label)
    if source.action_space != model.action_space:
        raise ValueError('Espacos de acao do ZIP divergem do destino')
    expanded = metadata['contract']['observation_schema'] != expected['observation_schema']
    old, new = source.policy.state_dict(), model.policy.state_dict()
    prefixes = ('mlp_extractor.policy_net.', 'action_net.')
    keys = {k for k in new if k.startswith(prefixes)}
    if not keys or keys != {k for k in old if k.startswith(prefixes)}:
        raise ValueError('Arquitetura do ator diverge')
    first = 'mlp_extractor.policy_net.0.weight'
    for key in keys:
        if not torch.isfinite(old[key]).all():
            raise ValueError('Ator de origem contem pesos nao finitos')
        if expanded and key == first:
            if tuple(old[key].shape) != (64, 47) or tuple(new[key].shape) != (64, 61):
                raise ValueError('Dimensoes da primeira camada do ator divergem')
        elif old[key].shape != new[key].shape:
            raise ValueError('Dimensoes dos pesos do ator divergem')
    if expanded and first not in keys:
        raise ValueError('Primeira camada linear do ator ausente')
    # O contrato admite somente FlattenExtractor sem parametros compartilhados.
    if (any(k.startswith(('features_extractor.', 'pi_features_extractor.')) for k in old | new)
            or type(source.policy.features_extractor) is not FlattenExtractor
            or type(model.policy.features_extractor) is not FlattenExtractor):
        raise ValueError('Extrator compartilhado nao suportado por esta transferencia')
    for key in keys:
        if expanded and key == first:
            new[key] = torch.zeros_like(new[key])
            new[key][:, :47] = old[key].detach().to(new[key].device)
        else:
            new[key] = old[key].detach().clone()
    model.policy.load_state_dict(new, strict=True)
    return {'source_model': str(path.resolve()), 'source_model_sha256': metadata['model_sha256'],
            'source_reward_profile': metadata['contract']['reward_profile'],
            'target_reward_profile': expected['reward_profile'],
            'source_contract_sha256': metadata['contract_sha256'],
            'source_num_timesteps': metadata['num_timesteps'], 'copied_actor_keys': sorted(keys),
            'source_gae_lambda': metadata['contract']['ppo']['gae_lambda'],
            'target_gae_lambda': expected['ppo']['gae_lambda'],
            'zero_initialized_observation_columns': list(range(47, 61)) if expanded else [],
            'semantics': ('actor_only; fresh_value_network_optimizer_and_counter; '
                          + ('navigation_observation_expansion' if expanded else
                             'blue_auto_idle_and_rank_reward_revision' if is_outcome_reward_revision(metadata['contract'], expected) else
                             'blue_auto_outcome_and_gae_experiment' if _blue_auto_outcome_transfer(metadata['contract'], expected) else
                             'blue_auto_new_save_and_reward' if _blue_auto_race_transfer(metadata['contract'], expected)
                             else 'new_reward_experiment'))}
