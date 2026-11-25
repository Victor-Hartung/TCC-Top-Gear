"""Objetivo por efeitos observados, inclusive antes da primeira linha.

lap=-1 nao e um sensor de GO. Nenhuma decisao depende de velocidade ideal,
volta de consumo, quantidade de cargas reservadas ou acao de turbo.
"""
PROFILE = 'road_v6_outcome'
REWARD_VERSION = 14
LEGACY_VERSION = 8
PREVIOUS_VERSION = 10
PRIOR_VERSION = 11
PREVIOUS_REWARD_VERSION = 12
PREVIOUS_TIME_VERSION = 13
LEGACY_SETTINGS = dict(
    version=1,
    base_objective='road_v5_race',
    progress_source='bounded_modular_position_delta_including_lap_sentinel',
    progress_credit='new_high_water_distance_on_known_asphalt_without_impact',
    preline_collision_and_surface_costs=True,
    preline_rank_requires_valid_previous_rank=True,
    elapsed_cost=0.002,
    activation_cost=0.0,
    reserve_cost=0.0,
    unspent_terminal_cost=0.0,
    turbo_specific_bonus=0.0,
    action_override=False,
)
PREVIOUS_SETTINGS = dict(
    LEGACY_SETTINGS,
    version=3,
    idle_penalty=0.10,
    idle_grace_steps=15,
    preline_idle_grace_steps=30,
    preline_idle_grace_basis='consecutive_stationary_observations_not_go_detection',
    rank_gain_multiplier=2.0,
)
PRIOR_SETTINGS = dict(
    PREVIOUS_SETTINGS,
    version=4,
    rank_loss_multiplier=2.0,
)
PREVIOUS_REWARD_SETTINGS = dict(
    PRIOR_SETTINGS,
    version=5,
    idle_penalty=0.25,
    rank_gain_multiplier=2.2,
)
PREVIOUS_TIME_SETTINGS = dict(
    PREVIOUS_REWARD_SETTINGS,
    version=6,
    finish_bonus=40.0,
    failure_penalty=10.0,
)
SETTINGS = dict(
    PREVIOUS_TIME_SETTINGS,
    version=7,
    elapsed_cost=0.005,
)

# Experimento de atribuicao temporal; estes valores nao definem quando usar turbo.
GAE_LAMBDA = 0.995
SOURCE_GAE_LAMBDA = 0.95
