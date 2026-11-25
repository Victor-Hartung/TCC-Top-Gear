"""A2C with bounded recovery for rejected lap-sentinel telemetry samples."""
from __future__ import annotations

import numpy as np
from pathlib import Path

from stable_baselines3 import A2C

from experiment import atomic_json, unique_name
from protocol import ProtocolError
from terminal_progress import clear_progress
from transition_errors import LapSentinelRegression


RECOVERY_POLICY = {
    "version": 1,
    "error": "LapSentinelRegression",
    "strategy": "discard_partial_rollout_then_validated_savestate_reset",
    "max_recoveries": 3,
    "window_steps": 10_000,
}


class ResilientA2C(A2C):
    """Discard incomplete on-policy rollouts after the known rejected sample."""

    def configure_recovery(self, directory: Path) -> None:
        self._recovery_dir = Path(directory)
        self._recovery_steps = []
        self.recovery_count = 0
        self.discarded_rollout_steps = 0
        self.trained_steps_this_run = 0
        self.last_update_timesteps_this_run = None

    def _excluded_save_params(self):
        return super()._excluded_save_params() + ["_recovery_dir", "_recovery_steps"]

    def train(self) -> None:
        super().train()
        self.trained_steps_this_run += self.rollout_buffer.size() * self.n_envs
        self.last_update_timesteps_this_run = int(self.num_timesteps)

    def collect_rollouts(self, env, callback, rollout_buffer, n_rollout_steps):
        while True:
            try:
                return super().collect_rollouts(env, callback, rollout_buffer, n_rollout_steps)
            except LapSentinelRegression as exc:
                if env.num_envs != 1 or not hasattr(self, "_recovery_dir"):
                    raise
                now = int(self.num_timesteps)
                self._recovery_steps = [
                    step for step in self._recovery_steps
                    if now - step < RECOVERY_POLICY["window_steps"]
                ]
                allowed = len(self._recovery_steps) < RECOVERY_POLICY["max_recoveries"]
                discarded = int(rollout_buffer.pos * env.num_envs)
                record = {
                    "event": "lap_sentinel_recovery",
                    "num_timesteps": now,
                    "policy": RECOVERY_POLICY,
                    "diagnostic": exc.diagnostic,
                    "discarded_rollout_steps": discarded,
                    "last_update_timesteps_this_run": self.last_update_timesteps_this_run,
                    "status": "reset_pending" if allowed else "rate_limit_exceeded",
                    "note": (
                        "The rejected action and incomplete on-policy rollout are not trained; "
                        "the validated savestate is reset before collecting a fresh rollout."
                    ),
                }
                path = self._recovery_dir / (unique_name("recovery") + ".json")
                atomic_json(path, record)
                if not allowed:
                    raise ProtocolError(
                        "Regressao de lap repetida: limite de 3 recuperacoes em 10000 passos; "
                        "diagnostico: " + str(path)
                    ) from exc
                self._recovery_steps.append(now)
                self.discarded_rollout_steps += discarded
                rollout_buffer.reset()
                clear_progress()
                print(
                    f"RECUPERACAO ARES A2C: rollout parcial de {discarded} passos descartado; "
                    f"recarregando savestate. Diagnostico: {path}",
                    flush=True,
                )
                try:
                    self._last_obs = env.reset()
                except Exception as reset_error:
                    record.update(status="reset_failed", reset_error=repr(reset_error))
                    atomic_json(path, record)
                    raise
                self._last_episode_starts = np.ones((env.num_envs,), dtype=bool)
                self.recovery_count += 1
                record.update(status="reset_ok", recovery_count=self.recovery_count)
                atomic_json(path, record)
                self.logger.record("recovery/count", self.recovery_count)
                self.logger.record("recovery/discarded_rollout_steps", self.discarded_rollout_steps)
