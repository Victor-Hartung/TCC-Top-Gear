"""Custo experimental de recurso; usa consumo real, nunca o botao escolhido."""
from dataclasses import dataclass, field

PROFILE = 'road_v3_turbo'
SETTINGS = {
    'version': 1,
    'activation_cost': 0.25,
    'early_reserve_cost': 1.0,
    'offroad_activation_cost': 0.75,
    'offroad_active_step_cost': 0.01,
    'remaining_distance_source': 'reward_high_water_over_three_laps',
    'unspent_terminal_cost': 0.0,
}


def turbo_costs(previous, current, high_water):
    spent = max(0, previous.nitro - current.nitro)
    distance = max(1, current.track_length * current.total_laps)
    remaining = 1.0 - min(1.0, max(0.0, high_water / distance))
    unsafe_before = bool(previous.offtrack or previous.surface_unknown)
    wasted_now = bool((previous.turbo_active or current.turbo_active)
                      and (current.offtrack or current.surface_unknown))
    return {
        'turbo_activation': -spent * SETTINGS['activation_cost'],
        'turbo_reserve': -spent * SETTINGS['early_reserve_cost'] * remaining,
        'turbo_offroad_activation': -spent * SETTINGS['offroad_activation_cost'] * unsafe_before,
        'turbo_offroad_active': -SETTINGS['offroad_active_step_cost'] * wasted_now,
    }


@dataclass
class TurboUsage:
    events: list = field(default_factory=list)
    active_steps: int = 0
    offroad_active_steps: int = 0
    net_distance: int = 0
    high_water: int = 0

    def update(self, previous, current, step):
        # Diagnostico independente da recompensa, inclusive com lap=-1.
        # Nao estima o beneficio causal de usar turbo vs. nao usar.
        delta = current.progress - previous.progress
        length = current.track_length
        if length > 0:
            if delta < -length / 2: delta += length
            elif delta > length / 2: delta -= length
        valid_delta = length > 0 and previous.track_length == length and abs(delta) <= length * .1
        new_distance = 0
        if valid_delta:
            self.net_distance += delta
            new_distance = max(0, self.net_distance-self.high_water)
            self.high_water = max(self.high_water, self.net_distance)
        impacts = max(0, current.collision_events-previous.collision_events)
        clean = not (previous.offtrack or current.offtrack or previous.surface_unknown
                     or current.surface_unknown or previous.collision or current.collision or impacts)
        spent = max(0, previous.nitro - current.nitro)
        if spent:
            self.events.append({'step': step, 'frame': current.frame,
                'lap': current.lap, 'progress': current.progress, 'charges': spent,
                'speed_before': previous.speed, 'offtrack_before': previous.offtrack,
                'prestart': int(previous.lap < 0 or current.lap < 0),
                'observed_steps': 0, 'observed_frames': 0,
                'net_progress_units': 0, 'clean_new_progress_units': 0,
                'collision_events': 0, 'offtrack_or_unknown_steps': 0,
                'invalid_progress_samples': 0, 'window_status': 'active'})
        active = bool(previous.turbo_active or current.turbo_active or spent)
        self.active_steps += int(active)
        self.offroad_active_steps += int(active and (current.offtrack or current.surface_unknown))
        if active and self.events and self.events[-1]['window_status'] == 'active':
            event = self.events[-1]
            event['observed_steps'] += 1
            event['observed_frames'] += max(0, current.frame-previous.frame)
            event['net_progress_units'] += delta if valid_delta else 0
            event['clean_new_progress_units'] += new_distance if clean else 0
            event['collision_events'] += impacts
            event['offtrack_or_unknown_steps'] += int(bool(current.offtrack or current.surface_unknown))
            event['invalid_progress_samples'] += int(not valid_delta)
            if current.race_ended:
                event['window_status'] = 'race_ended_during_boost'
            elif not current.turbo_active:
                event['window_status'] = 'boost_ended'

    def end(self, reason):
        if self.events and self.events[-1]['window_status'] == 'active':
            self.events[-1]['window_status'] = 'censored_' + reason

    def info(self):
        return {
            'turbo_charges_used': sum(e['charges'] for e in self.events),
            'turbo_prestart_charges': sum(e['charges'] for e in self.events if e['prestart']),
            # Nome anterior mantido nos logs; lap sentinela nao significa "antes do GO".
            'turbo_lap_sentinel_charges': sum(e['charges'] for e in self.events if e['prestart']),
            'turbo_first_activation_step': self.events[0]['step'] if self.events else -1,
            'turbo_active_steps': self.active_steps,
            'turbo_offroad_active_steps': self.offroad_active_steps,
            'turbo_activations': [dict(e) for e in self.events],
        }
