"""Objetivo experimental de ritmo e turbo oportuno; nao altera os botoes."""
from dataclasses import dataclass

PROFILE = 'road_v4_driving'
SETTINGS = dict(
    version=1, unnecessary_lift_cost=0.015, launch_elapsed_cost=0.005,
    throttle_curve_limit=8, turbo_curve_limit=4,
    turbo_min_speed=4000, turbo_max_speed=11000,
    corridor_clearance=1024, turbo_activation_cost=0.10,
    turbo_bad_activation_cost=2.0, turbo_reserve_deficit_cost=1.5,
    turbo_useful_progress_weight=4.0, turbo_bonus_per_charge_cap=0.75,
    turbo_offroad_step_cost=0.03, turbo_collision_cost=0.5,
    reserve_rule='remaining_distance_fraction_minus_remaining_inventory_fraction',
    action_override=False, unspent_terminal_cost=0.0,
)
ACCELERATING_ACTIONS = (1, 3, 4, 9)


def opportunity(previous, navigation):
    """Somente informacao anterior a acao. Limites do corredor sao candidatos."""
    ready = (previous.lap >= 0 and not previous.race_ended and previous.fuel > 0
             and not previous.offtrack and not previous.surface_unknown
             and not previous.collision and navigation.get('navigation_valid', False)
             and navigation.get('target_valid', False))
    margin = SETTINGS['corridor_clearance']
    blocked = any(low-margin <= previous.lateral <= high+margin
                  for low, high in navigation.get('blocked_intervals', []))
    clear = bool(ready and not blocked)
    curve = max(abs(previous.curve_current), abs(previous.curve_ahead_512))
    return dict(throttle_opportunity=clear and curve <= SETTINGS['throttle_curve_limit'],
                turbo_opportunity=clear and curve <= SETTINGS['turbo_curve_limit']
                    and SETTINGS['turbo_min_speed'] <= previous.speed <= SETTINGS['turbo_max_speed'])


@dataclass
class DrivingObjective:
    bonus_remaining: float = 0.0

    def calculate(self, previous, current, result, high_water, *, action, navigation):
        if action not in range(10) or isinstance(action, bool):
            raise ValueError('Novo objetivo exige a acao real 0..9')
        context = opportunity(previous, navigation or {})
        spent = max(0, previous.nitro-current.nitro)
        active = bool(previous.turbo_active or current.turbo_active or spent)
        collision_count = max(0, current.collision_events-previous.collision_events)
        clean_now = not (current.offtrack or current.surface_unknown or current.collision or collision_count)
        c = dict(unnecessary_lift=0.0, launch_elapsed=0.0, turbo_activation=0.0,
                 turbo_bad_activation=0.0, turbo_reserve_deficit=0.0,
                 turbo_useful_progress=0.0, turbo_offroad_active=0.0, turbo_collision=0.0)
        # Nao penalizar controles apos resultado, impacto ou sinal de necessidade
        # de manobra; nem pagar recompensa so por manter acelerador apertado.
        if (context['throttle_opportunity'] and clean_now and not current.race_ended
                and action not in ACCELERATING_ACTIONS):
            c['unnecessary_lift'] = -SETTINGS['unnecessary_lift_cost']
        if previous.lap < 0 and not current.race_ended:
            c['launch_elapsed'] = -SETTINGS['launch_elapsed_cost']
        if spent:
            c['turbo_activation'] = -spent*SETTINGS['turbo_activation_cost']
            c['turbo_bad_activation'] = -spent*SETTINGS['turbo_bad_activation_cost']*int(not context['turbo_opportunity'])
            remaining = 1-min(1., max(0., high_water/max(1,current.track_length*current.total_laps)))
            deficit = max(0., remaining-current.nitro/3.)
            c['turbo_reserve_deficit'] = -spent*SETTINGS['turbo_reserve_deficit_cost']*deficit
            self.bonus_remaining = SETTINGS['turbo_bonus_per_charge_cap']*spent if context['turbo_opportunity'] else 0.0
        if active:
            c['turbo_offroad_active'] = -SETTINGS['turbo_offroad_step_cost']*int(bool(current.offtrack or current.surface_unknown))
            c['turbo_collision'] = -SETTINGS['turbo_collision_cost']*collision_count
            # So progresso novo ja elegivel no reward base; sem ciclos, bonus por
            # botao ou pagamento por ativacao. Cap evita prolongar boost p/ farmar.
            if clean_now and context['throttle_opportunity'] and result.components.get('progress',0)>0:
                useful_distance = result.components['progress']/20.0
                bonus = min(self.bonus_remaining, useful_distance*SETTINGS['turbo_useful_progress_weight'])
                c['turbo_useful_progress'] = bonus
                self.bonus_remaining -= bonus
        if not current.turbo_active:
            self.bonus_remaining = 0.0
        return c
