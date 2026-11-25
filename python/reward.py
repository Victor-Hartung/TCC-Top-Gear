from __future__ import annotations

from dataclasses import dataclass, replace

from telemetry import Telemetry
from topgear_config import ProjectConfig
from turbo_strategy import PROFILE as TURBO_PROFILE, turbo_costs
from driving_strategy import PROFILE as DRIVING_PROFILE, DrivingObjective
from race_objective import PROFILE as RACE_PROFILE, SETTINGS as RACE_SETTINGS
from outcome_objective import (PROFILE as OUTCOME_PROFILE, SETTINGS as OUTCOME_SETTINGS,
                               REWARD_VERSION as OUTCOME_REWARD_VERSION)


@dataclass(frozen=True)
class RewardWeights:
    progress: float
    rank_delta: float
    collision: float
    offtrack: float
    finish: float
    finish_rank: float
    first_place: float
    failure: float
    max_progress_fraction: float
    road_progress_only: bool = False
    idle_penalty: float = 0.0
    idle_grace_steps: int = 15

    @classmethod
    def from_config(cls, config: ProjectConfig) -> "RewardWeights":
        number = lambda key: config.number("reward", key)
        return cls(
            progress=number("progress_weight"),
            rank_delta=number("rank_delta_weight"),
            collision=number("collision_penalty"),
            offtrack=number("offtrack_penalty"),
            finish=number("finish_bonus"),
            finish_rank=number("finish_rank_bonus"),
            first_place=number("first_place_bonus"),
            failure=number("failure_penalty"),
            max_progress_fraction=number("max_progress_fraction_per_step"),
        )


@dataclass(frozen=True)
class RewardResult:
    total: float
    components: dict[str, float]
    progress_delta: int
    collision_event: bool
    collision_count: int
    overtake_count: int
    finish_event: bool


def road_reward_v1(weights: RewardWeights) -> RewardWeights:
    """Experimento opt-in; nao altera INI nem controles."""
    return replace(weights, progress=20.0, road_progress_only=True,
                   idle_penalty=0.02, idle_grace_steps=15)


@dataclass
class IdleTracker:
    consecutive_steps: int = 0

    def penalty(self, previous: Telemetry, current: Telemetry,
                progress_delta: int, weights: RewardWeights, *,
                grace_steps: int | None = None) -> float:
        stopped = (not current.finished and current.speed == 0
                   and progress_delta <= 0 and not current.collision
                   and current.collision_events <= previous.collision_events)
        self.consecutive_steps = self.consecutive_steps + 1 if stopped else 0
        grace = weights.idle_grace_steps if grace_steps is None else grace_steps
        if self.consecutive_steps > grace:
            return -weights.idle_penalty
        return 0.0


def calculate_reward(
    previous: Telemetry,
    current: Telemetry,
    weights: RewardWeights,
    *, include_lap_sentinel: bool = False,
) -> RewardResult:
    components = {
        "progress": 0.0,
        "rank_delta": 0.0,
        "collision": 0.0,
        "offtrack": 0.0,
        "finish": 0.0,
        "finish_rank": 0.0,
        "first_place": 0.0,
        "invalid_progress_jump": 0.0,
    }

    progress_delta = 0
    if (
        previous.lap >= (-1 if include_lap_sentinel else 0)
        and current.lap >= (-1 if include_lap_sentinel else 0)
        and current.track_length > 0
    ):
        # O contador de volta apresentou um transiente 0->1->0 antes da linha.
        # O delta modular do progresso ignora esse pulso e trata o wrap real.
        progress_delta = current.progress - previous.progress
        half_track = current.track_length / 2
        if progress_delta < -half_track:
            progress_delta += current.track_length
        elif progress_delta > half_track:
            progress_delta -= current.track_length
        max_delta = current.track_length * weights.max_progress_fraction
        if abs(progress_delta) <= max_delta:
            components["progress"] = (
                progress_delta / current.track_length
            ) * weights.progress
        else:
            components["invalid_progress_jump"] = 1.0

    # Recuo continua negativo inclusive fora da pista: impede ciclos de ida/volta.
    if (weights.road_progress_only and progress_delta > 0
            and (previous.offtrack or current.offtrack)):
        components["progress"] = 0.0

    rank_delta = 0
    if 0 <= previous.rank <= 19 and 0 <= current.rank <= 19:
        rank_delta = previous.rank - current.rank
        components["rank_delta"] = rank_delta * weights.rank_delta
        # A própria melhora de rank já recompensa a ultrapassagem. Um bônus
        # apenas na subida tornaria perder e recuperar a mesma posição lucrativo.

    collision_count = max(current.collision_events - previous.collision_events, 0)
    collision_event = collision_count > 0
    if collision_event:
        components["collision"] = -weights.collision * collision_count
    if current.offtrack:
        components["offtrack"] = -weights.offtrack

    finish_event = bool(current.race_completed and not previous.race_completed)
    if finish_event:
        components["finish"] = weights.finish
        if 0 <= current.final_rank <= 19:
            quality = (19 - current.final_rank) / 19.0
            components["finish_rank"] = quality * weights.finish_rank
            if current.final_rank == 0:
                components["first_place"] = weights.first_place

    # invalid_progress_jump é telemetria diagnóstica, não recompensa.
    total = float(
        sum(value for key, value in components.items() if key != "invalid_progress_jump")
    )
    return RewardResult(
        total=total,
        components=components,
        progress_delta=progress_delta,
        collision_event=collision_event,
        collision_count=collision_count,
        overtake_count=max(rank_delta, 0),
        finish_event=finish_event,
    )


REWARD_VERSION = 4
PROFILES = ("legacy_corrigido", "road_v1", "road_v2", TURBO_PROFILE, DRIVING_PROFILE, RACE_PROFILE, OUTCOME_PROFILE)


def reward_version(profile: str) -> int:
    if profile == OUTCOME_PROFILE:
        return OUTCOME_REWARD_VERSION
    if profile == RACE_PROFILE:
        return 7
    if profile == DRIVING_PROFILE:
        return 6
    return 5 if profile == TURBO_PROFILE else REWARD_VERSION


def profile_weights(base: RewardWeights, profile: str) -> RewardWeights:
    if profile == "legacy_corrigido":
        return base
    if profile == "road_v1":
        return road_reward_v1(base)
    if profile in ("road_v2", TURBO_PROFILE, DRIVING_PROFILE, RACE_PROFILE, OUTCOME_PROFILE):
        # Proposta para ablação, calibrada por replay; ainda não prova aprendizado.
        weights = replace(road_reward_v1(base), collision=0.25, offtrack=0.005)
        if profile == OUTCOME_PROFILE:
            return replace(weights, idle_penalty=OUTCOME_SETTINGS['idle_penalty'],
                           idle_grace_steps=OUTCOME_SETTINGS['idle_grace_steps'])
        return weights
    raise ValueError(f"Perfil de recompensa desconhecido: {profile}")


class RewardEngine:
    """Estado reiniciado por episodio; o perfil v4 inclui custo contextual de acao."""

    def __init__(self, weights: RewardWeights, profile: str):
        if profile not in PROFILES:
            raise ValueError(profile)
        self.weights = weights
        self.profile = profile
        self.idle = IdleTracker()
        self.net_progress = 0
        self.high_water = 0
        self.best_rank: int | None = None
        self.driving = DrivingObjective()

    def calculate(self, previous: Telemetry, current: Telemetry, *, action=None, navigation=None) -> RewardResult:
        result = self._calculate_base(previous, current)
        if self.profile == RACE_PROFILE and not result.components['invalid_progress_jump']:
            launch_cost = -RACE_SETTINGS['launch_elapsed_cost'] if previous.lap < 0 and not current.race_ended else 0.0
            return replace(result, total=result.total+launch_cost,
                           components={**result.components, 'launch_elapsed': launch_cost})
        if self.profile == DRIVING_PROFILE and not result.components['invalid_progress_jump']:
            costs = self.driving.calculate(previous, current, result, self.high_water,
                                          action=action, navigation=navigation)
            return replace(result, total=result.total + sum(costs.values()),
                           components={**result.components, **costs})
        if self.profile != TURBO_PROFILE or result.components['invalid_progress_jump']:
            return result
        # Custo da carga efetivamente consumida inclusive antes de lap=0.
        # Sem progresso/chegada inventados na largada, sem bloquear a acao.
        costs = turbo_costs(previous, current, self.high_water)
        return replace(result, total=result.total + sum(costs.values()),
                       components={**result.components, **costs})

    def _calculate_base(self, previous: Telemetry, current: Telemetry) -> RewardResult:
        outcome = self.profile == OUTCOME_PROFILE
        raw = calculate_reward(previous, current, self.weights, include_lap_sentinel=outcome)
        # lap=-1 nao identifica GO. PPO controla todos os frames, mas shaping
        # comeca somente apos estabelecer a primeira volta; sem bonus de largada.
        if not outcome and (previous.lap < 0 or current.lap < 0) and not current.race_ended:
            self.idle.consecutive_steps = 0
            self.best_rank = current.rank if current.lap >= 0 and current.rank >= 0 else None
            return replace(raw, total=0.0, components={k: 0.0 for k in raw.components},
                           progress_delta=0, collision_event=False, collision_count=0,
                           overtake_count=0, finish_event=False)
        if raw.components["invalid_progress_jump"]:
            return raw
        c = dict(raw.components)
        # Tolerancia para observacoes imoveis consecutivas; nao identifica GO
        # nem exige uma acao de aceleracao. Movimento e impacto zeram o contador.
        grace = self.weights.idle_grace_steps
        if outcome and (previous.lap < 0 or current.lap < 0):
            grace = OUTCOME_SETTINGS['preline_idle_grace_steps']
        c['idle'] = self.idle.penalty(previous, current, raw.progress_delta, self.weights,
                                     grace_steps=grace)
        if self.profile in ("road_v2", TURBO_PROFILE, DRIVING_PROFILE, RACE_PROFILE, OUTCOME_PROFILE):
            self.net_progress += raw.progress_delta
            new_distance = max(0, self.net_progress - self.high_water)
            self.high_water = max(self.high_water, self.net_progress)
            c['progress'] = 0.0
            eligible = (not previous.offtrack and not current.offtrack
                        and not previous.surface_unknown and not current.surface_unknown
                        and not previous.collision and not current.collision
                        and raw.collision_count == 0)
            if eligible and current.track_length > 0:
                c['progress'] = new_distance / current.track_length * self.weights.progress
            # High water avança mesmo fora/na colisão: recuperar o mesmo trecho não paga.
            # Não distingue a culpa nem remove todo impulso residual de batida traseira.
            if self.best_rank is None:
                self.best_rank = previous.rank if previous.rank >= 0 else (None if outcome else 19)
            if outcome and (previous.rank < 0 or self.best_rank is None):
                # Primeira leitura de rank nao e uma ultrapassagem.
                if current.rank >= 0:
                    self.best_rank = current.rank if self.best_rank is None else min(self.best_rank, current.rank)
                c['rank_delta'] = 0.0
            elif current.rank >= 0:
                gain = max(0, self.best_rank - current.rank)
                loss = min(0, previous.rank - current.rank) if previous.rank >= 0 else 0
                gain_multiplier = OUTCOME_SETTINGS['rank_gain_multiplier'] if outcome else 1.0
                loss_multiplier = OUTCOME_SETTINGS['rank_loss_multiplier'] if outcome else 1.0
                c['rank_delta'] = (gain * gain_multiplier + loss * loss_multiplier) * self.weights.rank_delta
                self.best_rank = min(self.best_rank, current.rank)
            c['elapsed'] = -OUTCOME_SETTINGS['elapsed_cost'] if outcome else -0.002
            if current.race_ended and not current.race_completed:
                c['incomplete'] = -self.weights.failure
        total = sum(v for k, v in c.items() if k != 'invalid_progress_jump')
        return replace(raw, total=float(total), components=c)
