from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from protocol import BridgeClient, BridgeState, ProtocolError
from reward import RewardWeights, profile_weights, RewardEngine
from telemetry import OBSERVATION_NAMES, ObservationBuilder, Telemetry, observation_names
from topgear_config import ACTION_NAMES, ProjectConfig
from transition_errors import LapSentinelRegression
from turbo_strategy import TurboUsage
from driving_strategy import PROFILE as DRIVING_PROFILE, opportunity


class TopGearEnv(gym.Env[np.ndarray, int]):
    """Ambiente síncrono para Top Gear (USA) no BizHawk.

    Cada step envia uma sequência, o Lua aplica a ação por uma quantidade fixa
    de frames e responde com o mesmo ack. Treinos são bloqueados enquanto o
    perfil de memória/controles não estiver marcado como validado.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        project_dir: str | Path | None = None,
        *,
        require_validated: bool = True,
        reward_profile: str | None = None,
        expected_reset: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        self.config = ProjectConfig.load(project_dir)
        self.require_validated = bool(require_validated)
        self.expected_reset = expected_reset
        if self.require_validated:
            self.config.assert_training_ready()

        self.action_space = spaces.Discrete(self.config.action_count)
        self.observation_space = spaces.Box(
            low=ObservationBuilder.low(self.config),
            high=ObservationBuilder.high(self.config),
            dtype=np.float32,
        )

        self.bridge = BridgeClient(self.config)
        host, port = self.bridge.address
        print(f"Servidor da ponte pronto em {host}:{port}; aguardando BizHawk/Lua...")
        try:
            ready = self.bridge.wait_ready()
            # O hello pode vir do menu/contagem. A prontidao de corrida e
            # conferida depois do reset, nunca antes de carregar o save.
            Telemetry.from_fields(ready.fields)
        except Exception:
            self.bridge.close()
            raise

        self.observations = ObservationBuilder(self.config)
        self.reward_profile = reward_profile or self.config.text("experiment", "reward_profile")
        self.weights = profile_weights(RewardWeights.from_config(self.config), self.reward_profile)
        self._reward_engine = RewardEngine(self.weights, self.reward_profile)
        self.max_steps = self.config.integer("episode", "max_steps")
        self.no_progress_limit = self.config.integer(
            "episode", "no_progress_steps"
        )
        self.progress_epsilon = self.config.integer("episode", "progress_epsilon")

        self._previous: Telemetry | None = None
        self._prestart_steps = 0
        self._step_count = 0
        self._no_progress_count = 0
        self._collision_count = 0
        self._overtake_count = 0
        self._closed = False
        self._done = True
        self._net_progress = 0
        self._offtrack_steps = 0
        self._speed_sum = 0
        self._unknown_steps = 0
        self._stopped_steps = 0
        self._reset_frame = 0
        self._turbo_usage = TurboUsage()

    @property
    def observation_names(self) -> tuple[str, ...]:
        return observation_names(self.config)

    def enable_road_reward_v1(self) -> None:
        if self._previous is not None:
            raise ProtocolError("Selecione o experimento antes do primeiro reset")
        self.weights = profile_weights(RewardWeights.from_config(self.config), "road_v1")
        self.reward_profile = "road_v1"
        self._reward_engine = RewardEngine(self.weights, self.reward_profile)
        print("REWARD EXPERIMENTAL road_v1: progresso na pista=20; parado=0.02 apos 15 passos")

    def _telemetry(self, state: BridgeState) -> Telemetry:
        telemetry = Telemetry.from_fields(state.fields)
        if self.require_validated:
            telemetry.assert_runtime_ready(allow_prestart=True, require_detector=True)
            if telemetry.track_length != self.config.integer("experiment", "track_length_expected") or telemetry.total_laps != 3:
                raise ProtocolError("Perfil validado somente para Las Vegas com tres voltas")
        return telemetry

    def _info(
        self,
        telemetry: Telemetry,
        *,
        reward_components: dict[str, float] | None = None,
        collision_event: bool = False,
        termination_reason: str = "",
    ) -> dict[str, Any]:
        info: dict[str, Any] = {
            "frame": telemetry.frame,
            "objective_profile": self.reward_profile,
            "speed": telemetry.speed,
            "lateral": telemetry.lateral,
            "progress": telemetry.progress,
            "progress_total": telemetry.absolute_progress
            if telemetry.absolute_progress is not None
            else -1,
            "lap": telemetry.lap,
            "prestart": int(telemetry.lap == -1),
            "prestart_steps": self._prestart_steps,
            "rank": telemetry.rank,
            "final_rank": telemetry.final_rank,
            "race_ended": int(bool(telemetry.finished)),
            "finished": int(telemetry.race_completed),
            "race_completed": int(telemetry.race_completed),
            "total_laps": telemetry.total_laps,
            "track_length": telemetry.track_length,
            "is_first": int(telemetry.race_completed and telemetry.final_rank == 0),
            "collision": telemetry.collision,
            "collision_event": int(collision_event),
            "collisions_total": self._collision_count,
            "overtakes_total": self._overtake_count,
            "offtrack": telemetry.offtrack,
            "surface_raw": telemetry.surface_raw,
            "surface_unknown": telemetry.surface_unknown,
            "surface_state": telemetry.surface_state,
            "surface_direction": telemetry.surface_direction,
            "nitro": telemetry.nitro,
            "nitro_raw": telemetry.nitro_raw,
            "turbo_active": telemetry.turbo_active,
            "curve_progress": telemetry.curve_progress,
            "curve_current": telemetry.curve_current,
            "curve_ahead_512": telemetry.curve_ahead_512,
            "curve_ahead_1024": telemetry.curve_ahead_1024,
            "curve_ahead_2048": telemetry.curve_ahead_2048,
            "nearest_valid": telemetry.nearest_valid,
            "nearest_id": telemetry.nearest_id,
            "nearest_distance": telemetry.nearest_distance,
            "opponent_count": telemetry.opponent_count,
            "termination_reason": termination_reason,
            "net_progress": self._net_progress,
            "steps": self._step_count,
            "offtrack_fraction": self._offtrack_steps / max(1, self._step_count),
            "unknown_surface_fraction": self._unknown_steps / max(1, self._step_count),
            "stopped_fraction": self._stopped_steps / max(1, self._step_count),
            "mean_speed_raw": self._speed_sum / max(1, self._step_count),
            "collision_cause": "unknown",
            "raw_telemetry": asdict(telemetry),
            "detector_candidates": self.observations.detector_rows,
            "navigation": self.observations.navigation,
            "episode_elapsed_frames": telemetry.frame - self._reset_frame,
            **self._turbo_usage.info(),
        }
        for key, value in (reward_components or {}).items():
            info[f"reward_{key}"] = float(value)
        return info

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        if self._closed:
            raise ProtocolError("Ambiente fechado")
        del options
        self._prestart_steps = 0
        self._step_count = 0
        self._no_progress_count = 0
        self._collision_count = 0
        self._overtake_count = 0

        self._reward_engine = RewardEngine(self.weights, self.reward_profile)
        self._turbo_usage = TurboUsage()
        self._net_progress = self._offtrack_steps = self._unknown_steps = self._stopped_steps = self._speed_sum = 0
        telemetry = self._telemetry(self.bridge.reset())
        self._reset_frame = telemetry.frame
        if len(telemetry.detector_samples.split(";")) != 1 and self.require_validated:
            raise ProtocolError("Reset do detector exige uma amostra sem historico anterior")
        if telemetry.race_ended:
            raise ProtocolError("Savestate ja encerrado; salve no inicio de uma corrida ativa")
        if self.expected_reset is not None and asdict(telemetry) != self.expected_reset:
            raise ProtocolError("Savestate/telemetria inicial mudou desde o preflight; repita preflight_live.py")
        observation = self.observations.reset(telemetry)
        self._previous = telemetry
        self._done = False
        return observation, self._info(telemetry)

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._previous is None or self._done or self._closed:
            raise ProtocolError("Chame env.reset() antes de env.step()")
        if isinstance(action, (bool, np.bool_)) or not self.action_space.contains(action):
            raise ValueError(
                f"Ação {action!r} fora de Discrete({self.action_space.n})"
            )
        action_id = int(action)
        from manual_transmission import decode_action
        base_action, shift_command = decode_action(action_id) if self.config.manual_transmission else (action_id, 0)
        previous_navigation = self.observations.navigation
        driving_context = opportunity(self._previous, previous_navigation) if self.reward_profile == DRIVING_PROFILE else None

        self._step_count += 1
        wire = self.bridge.step(action_id)
        current = self._telemetry(wire)
        if self.require_validated and len(current.detector_samples.split(";")) != 4:
            raise ProtocolError("Step do detector exige quatro amostras reais")
        if self._previous.lap >= 0 and current.lap < 0:
            # Nao fabricar lap=0, recompensa, terminal ou observacao substituta.
            # O treinador pode descartar o rollout e carregar o save novamente.
            self._done = True  # Exige reset mesmo para um chamador sem recuperacao.
            raise LapSentinelRegression({
                "kind": "lap_sentinel_regression", "action": action_id,
                "episode_step_attempted": self._step_count,
                "previous": asdict(self._previous), "rejected": asdict(current),
                "wire_fields": dict(wire.fields),
            })
        if self._previous.lap < 0 and current.lap > 0:
            raise ProtocolError("Largada saltou a primeira volta")
        self._prestart_steps += int(current.lap == -1)
        observation = self.observations.build(current, shift_command=shift_command)
        if current.collision_events < self._previous.collision_events:
            raise ProtocolError("Contador de impactos regrediu sem reset")
        result = self._reward_engine.calculate(self._previous, current, action=base_action,
                                               navigation=previous_navigation)
        components = dict(result.components)
        reward = result.total
        if result.components["invalid_progress_jump"]:
            raise ProtocolError(
                "Salto de progresso fisicamente implausível; transição recusada para "
                "não contaminar o rollout"
            )

        self._net_progress += result.progress_delta
        self._turbo_usage.update(self._previous, current, self._step_count)
        self._offtrack_steps += current.offtrack
        self._unknown_steps += current.surface_unknown
        self._stopped_steps += int(current.speed == 0)
        self._speed_sum += current.speed

        if self._previous.lap < 0 or current.lap < 0:
            self._no_progress_count = 0
        elif result.progress_delta > self.progress_epsilon:
            self._no_progress_count = 0
        else:
            self._no_progress_count += 1
        if result.collision_event:
            self._collision_count += result.collision_count
        self._overtake_count += result.overtake_count

        failed_no_progress = (
            not current.finished
            and self._no_progress_count >= self.no_progress_limit
        )
        if failed_no_progress and self.reward_profile not in ("road_v2", "road_v3_turbo", "road_v4_driving", "road_v5_race", "road_v6_outcome"):
            components["failure"] = -self.weights.failure
            reward -= self.weights.failure

        prestart_timeout = current.lap == -1 and self._prestart_steps >= self.config.integer("episode", "prestart_max_steps")
        terminated = bool(current.race_ended or (failed_no_progress and self.reward_profile not in ("road_v2", "road_v3_turbo", "road_v4_driving", "road_v5_race", "road_v6_outcome")))
        truncated = bool(not terminated and (prestart_timeout or failed_no_progress or self._step_count >= self.max_steps))
        if truncated and not prestart_timeout and self.reward_profile not in ("road_v2", "road_v3_turbo", "road_v4_driving", "road_v5_race", "road_v6_outcome"):
            components["time_limit"] = -self.weights.failure
            reward -= self.weights.failure
        if current.finished:
            # Inclui o tempo esgotado observado pelo usuario; sem um sinal de
            # timer validado, nao atribuir causa exata a todos os encerramentos.
            reason = "finished" if current.race_completed else "race_ended_incomplete"
        elif prestart_timeout:
            reason = "prestart_timeout"
        elif failed_no_progress:
            reason = "no_progress"
        elif truncated:
            reason = "time_limit"
        else:
            reason = ""

        previous_gear = self._previous.gear
        previous_speed = self._previous.speed
        self._previous = current
        self._done = terminated or truncated
        if self._done:
            self._turbo_usage.end(reason)
        info = self._info(
            current,
            reward_components=components,
            collision_event=result.collision_event,
            termination_reason=reason,
        )
        info["action_name"] = self.config.action_names[action_id]
        if self.config.manual_transmission:
            info.update(base_action=base_action, shift_command=shift_command,
                        gear_before=previous_gear, gear=current.gear,
                        gear_changed=int(previous_gear != current.gear),
                        engine_gauge_raw=current.engine_gauge_raw,
                        speed_delta=current.speed - previous_speed)
        if driving_context is not None:
            info['driving_context_before_action'] = driving_context
        return observation, float(reward), terminated, truncated, info

    def close(self) -> None:
        if not self._closed:
            self.bridge.close()
            self._closed = True
        super().close()
