"""Exact known reward revisions for the blue automatic objective."""
from __future__ import annotations

import copy

from outcome_objective import (
    GAE_LAMBDA, LEGACY_SETTINGS, LEGACY_VERSION, PREVIOUS_SETTINGS,
    PREVIOUS_VERSION, PRIOR_SETTINGS, PRIOR_VERSION, PREVIOUS_REWARD_SETTINGS,
    PREVIOUS_REWARD_VERSION, PREVIOUS_TIME_SETTINGS, PREVIOUS_TIME_VERSION,
    PROFILE, REWARD_VERSION, SETTINGS,
)


TARGET_SETTINGS = {
    PREVIOUS_VERSION: PREVIOUS_SETTINGS,
    PRIOR_VERSION: PRIOR_SETTINGS,
    PREVIOUS_REWARD_VERSION: PREVIOUS_REWARD_SETTINGS,
    PREVIOUS_TIME_VERSION: PREVIOUS_TIME_SETTINGS,
    REWARD_VERSION: SETTINGS,
}


def _assert_canonical_target(expected: dict) -> None:
    if not isinstance(expected, dict):
        raise ValueError('Revisao de recompensa exige contrato de destino valido')
    version = expected.get('reward_version')
    settings = TARGET_SETTINGS.get(version)
    weights = expected.get('reward_weights')
    controls = expected.get('settings', {}).get('controls', {})
    expected_idle = settings.get('idle_penalty') if isinstance(settings, dict) else None
    expected_finish = settings.get('finish_bonus', 20.0) if isinstance(settings, dict) else None
    expected_failure = settings.get('failure_penalty', 5.0) if isinstance(settings, dict) else None
    if (REWARD_VERSION != 14 or PREVIOUS_TIME_VERSION != 13
            or PREVIOUS_REWARD_VERSION != 12
            or PRIOR_VERSION != 11 or PREVIOUS_VERSION != 10 or LEGACY_VERSION != 8
            or expected.get('reward_profile') != PROFILE
            or settings is None
            or expected.get('outcome_objective') != settings
            or expected.get('reward_elapsed') != settings.get('elapsed_cost', 0.002)
            or SETTINGS.get('version') != 7
            or PREVIOUS_TIME_SETTINGS.get('version') != 6
            or PREVIOUS_REWARD_SETTINGS.get('version') != 5
            or PRIOR_SETTINGS.get('version') != 4
            or PREVIOUS_SETTINGS.get('version') != 3
            or LEGACY_SETTINGS.get('version') != 1
            or expected.get('savestate_slot') != 3
            or expected.get('observation_schema') != 10
            or expected.get('bridge_revision') != 5
            or len(expected.get('observation_names', [])) != 61
            or len(expected.get('actions', [])) != 10
            or 'manual_transmission' in expected or 'race_objective' in expected
            or controls.get('blue_auto_expected') != 'true'
            or expected.get('ppo', {}).get('gae_lambda') != GAE_LAMBDA
            or not isinstance(weights, dict)
            or weights.get('idle_penalty') != expected_idle
            or weights.get('finish') != expected_finish
            or weights.get('failure') != expected_failure
            or weights.get('idle_grace_steps') != 15
            or weights.get('rank_delta') != 0.50):
        raise ValueError('Destino nao e uma revisao canonica azul de recompensa conhecida')


def _restore_previous_finish_weights(contract: dict) -> dict:
    contract['reward_weights']['finish'] = 20.0
    contract['reward_weights']['failure'] = 5.0
    return contract


def _restore_previous_elapsed_cost(contract: dict, settings: dict) -> dict:
    contract['reward_elapsed'] = settings.get('elapsed_cost', 0.002)
    return contract


def legacy_outcome_contract(expected: dict) -> dict:
    """Reconstruct v8 exactly from a canonical blue v10-v14 target."""
    _assert_canonical_target(expected)
    previous = copy.deepcopy(expected)
    previous['reward_version'] = LEGACY_VERSION
    previous['outcome_objective'] = copy.deepcopy(LEGACY_SETTINGS)
    previous['reward_weights']['idle_penalty'] = 0.02
    _restore_previous_elapsed_cost(previous, LEGACY_SETTINGS)
    return _restore_previous_finish_weights(previous)


def previous_outcome_contract(expected: dict) -> dict:
    """Reconstruct v10 exactly from a canonical blue v11-v14 target."""
    _assert_canonical_target(expected)
    if expected['reward_version'] not in (PRIOR_VERSION, PREVIOUS_REWARD_VERSION,
                                           PREVIOUS_TIME_VERSION, REWARD_VERSION):
        raise ValueError('Reconstrucao da recompensa anterior exige destino v11, v12, v13 ou v14')
    previous = copy.deepcopy(expected)
    previous['reward_version'] = PREVIOUS_VERSION
    previous['outcome_objective'] = copy.deepcopy(PREVIOUS_SETTINGS)
    previous['reward_weights']['idle_penalty'] = PREVIOUS_SETTINGS['idle_penalty']
    _restore_previous_elapsed_cost(previous, PREVIOUS_SETTINGS)
    return _restore_previous_finish_weights(previous)


def prior_outcome_contract(expected: dict) -> dict:
    """Reconstruct v11 exactly from a canonical blue v12-v14 target."""
    _assert_canonical_target(expected)
    if expected['reward_version'] not in (PREVIOUS_REWARD_VERSION,
                                           PREVIOUS_TIME_VERSION, REWARD_VERSION):
        raise ValueError('Reconstrucao da recompensa v11 exige destino v12, v13 ou v14')
    previous = copy.deepcopy(expected)
    previous['reward_version'] = PRIOR_VERSION
    previous['outcome_objective'] = copy.deepcopy(PRIOR_SETTINGS)
    previous['reward_weights']['idle_penalty'] = PRIOR_SETTINGS['idle_penalty']
    _restore_previous_elapsed_cost(previous, PRIOR_SETTINGS)
    return _restore_previous_finish_weights(previous)


def previous_reward_outcome_contract(expected: dict) -> dict:
    """Reconstruct v12 exactly from a canonical blue v13 or v14 target."""
    _assert_canonical_target(expected)
    if expected['reward_version'] not in (PREVIOUS_TIME_VERSION, REWARD_VERSION):
        raise ValueError('Reconstrucao da recompensa v12 exige destino v13 ou v14')
    previous = copy.deepcopy(expected)
    previous['reward_version'] = PREVIOUS_REWARD_VERSION
    previous['outcome_objective'] = copy.deepcopy(PREVIOUS_REWARD_SETTINGS)
    previous['reward_weights']['idle_penalty'] = PREVIOUS_REWARD_SETTINGS['idle_penalty']
    _restore_previous_elapsed_cost(previous, PREVIOUS_REWARD_SETTINGS)
    return _restore_previous_finish_weights(previous)


def previous_time_outcome_contract(expected: dict) -> dict:
    """Reconstruct v13 exactly before the elapsed-cost increase."""
    _assert_canonical_target(expected)
    if expected['reward_version'] != REWARD_VERSION:
        raise ValueError('Reconstrucao da recompensa v13 exige destino v14')
    previous = copy.deepcopy(expected)
    previous['reward_version'] = PREVIOUS_TIME_VERSION
    previous['outcome_objective'] = copy.deepcopy(PREVIOUS_TIME_SETTINGS)
    _restore_previous_elapsed_cost(previous, PREVIOUS_TIME_SETTINGS)
    return previous


def is_outcome_reward_revision(source: dict, expected: dict) -> bool:
    """Allow only exact, known sequential blue-auto reward revisions."""
    try:
        _assert_canonical_target(expected)
        version = expected['reward_version']
        if version in (PREVIOUS_VERSION, PRIOR_VERSION, PREVIOUS_REWARD_VERSION,
                       PREVIOUS_TIME_VERSION, REWARD_VERSION):
            if source == legacy_outcome_contract(expected):
                return True
        if version in (PRIOR_VERSION, PREVIOUS_REWARD_VERSION,
                       PREVIOUS_TIME_VERSION, REWARD_VERSION):
            if source == previous_outcome_contract(expected):
                return True
        if version in (PREVIOUS_REWARD_VERSION, PREVIOUS_TIME_VERSION, REWARD_VERSION):
            if source == prior_outcome_contract(expected):
                return True
        if version in (PREVIOUS_TIME_VERSION, REWARD_VERSION):
            if source == previous_reward_outcome_contract(expected):
                return True
        if version == REWARD_VERSION:
            return source == previous_time_outcome_contract(expected)
        if version == PREVIOUS_REWARD_VERSION:
            return source == prior_outcome_contract(expected)
        return False
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
