"""Correcao por ablacao: resultado da corrida sem regras de momento do turbo."""
PROFILE = 'road_v5_race'
SETTINGS = dict(version=1, base_objective='road_v2', launch_elapsed_cost=0.005,
                turbo_activation_cost=0.0, turbo_reserve_cost=0.0,
                turbo_opportunity_gate=False, turbo_specific_progress_bonus=0.0,
                action_cost=0.0, sensor_controls_reward=False,
                unspent_terminal_cost=0.0, action_override=False)
