"""DQN-specific setup for the independent Apolo brain."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import uuid

import numpy as np
import torch
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import BaseCallback

from callbacks import RaceMetricsCallback
from experiment import (atomic_json, contract as environment_contract, save_checkpoint,
                        sha256, validate_checkpoint, unique_name)
from protocol import ProtocolError
from terminal_progress import clear_progress, finish_progress, write_progress
from transition_errors import LapSentinelRegression


EXPLORATION_DECAY_STEPS = 200_000
REPLAY_BUFFER_DIRECTORY = Path("models") / "apolo-replay-buffers"
RECOVERY_POLICY = {
    "version": 1,
    "error": "LapSentinelRegression",
    "strategy": "keep_valid_replay_transitions_mark_episode_boundary_and_reset_savestate",
    "max_recoveries": 3,
    "window_steps": 10_000,
}


def dqn_options(config) -> dict:
    """Keep PPO-shared hyperparameters where meaningful; add DQN-only settings."""
    return {
        "learning_rate": config.number("ppo", "learning_rate"),
        "buffer_size": 100_000,
        "learning_starts": 10_000,
        "batch_size": config.integer("ppo", "batch_size"),
        "tau": 1.0,
        "gamma": config.number("ppo", "gamma"),
        "train_freq": 4,
        "gradient_steps": 1,
        "exploration_fraction": 1.0,
        "exploration_initial_eps": 1.0,
        "exploration_final_eps": 0.05,
        "target_update_interval": 1_000,
        "max_grad_norm": config.number("ppo", "max_grad_norm"),
    }


def dqn_policy_kwargs() -> dict:
    """Match Hermes' 64x64 Tanh MLP using DQN's single Q-network."""
    return {"net_arch": [64, 64], "activation_fn": torch.nn.Tanh}


def dqn_contract(config) -> dict:
    """Bind the named Apolo model to the same game/reward and a DQN algorithm."""
    value = environment_contract(config)
    value.pop("ppo")
    value["algorithm"] = "DQN"
    value["dqn"] = {
        **dqn_options(config),
        "exploration_decay_steps": EXPLORATION_DECAY_STEPS,
        "device": "cpu",
    }
    value["policy"] = {
        "class": "MlpPolicy",
        "q_net": [64, 64],
        "activation": "Tanh",
        "wrappers": ["Monitor", "DummyVecEnv"],
        "vecnormalize": False,
    }
    return value


class AbsoluteExplorationSchedule:
    """Linear epsilon decay tied to lifetime steps, so resume does not restart it."""

    def __init__(self, start_step: int, steps_this_run: int,
                 decay_steps: int = EXPLORATION_DECAY_STEPS,
                 initial: float = 1.0, final: float = 0.05):
        if start_step < 0 or steps_this_run < 1 or decay_steps < 1:
            raise ValueError("Passos da exploracao devem ser positivos")
        self.start_step = int(start_step)
        self.steps_this_run = int(steps_this_run)
        self.decay_steps = int(decay_steps)
        self.initial = float(initial)
        self.final = float(final)

    def __call__(self, progress_remaining: float) -> float:
        progress = min(1.0, max(0.0, float(progress_remaining)))
        elapsed_this_run = (1.0 - progress) * self.steps_this_run
        fraction = min(1.0, (self.start_step + elapsed_this_run) / self.decay_steps)
        if fraction >= 1.0:
            return self.final
        return self.initial + fraction * (self.final - self.initial)


def attach_exploration_schedule(model: DQN, steps_this_run: int) -> None:
    schedule = AbsoluteExplorationSchedule(model.num_timesteps, steps_this_run)
    model.exploration_schedule = schedule
    model.exploration_rate = schedule(1.0)


class ApoloDQN(DQN):
    """DQN with bounded recovery for the project's rejected lap-sentinel sample."""

    def configure_recovery(self, directory: Path) -> None:
        self._recovery_dir = Path(directory)
        self._recovery_steps = []
        self.recovery_count = 0
        self.invalid_transitions = 0
        self.gradient_steps_this_run = 0
        self.last_update_timesteps_this_run = None
        self._update_interrupted = False

    def _excluded_save_params(self):
        return super()._excluded_save_params() + [
            "_recovery_dir", "_recovery_steps", "_update_interrupted"
        ]

    def train(self, gradient_steps: int, batch_size: int = 100) -> None:
        self._update_interrupted = True
        previous_updates = int(self._n_updates)
        super().train(gradient_steps, batch_size)
        self.gradient_steps_this_run += max(0, int(self._n_updates) - previous_updates)
        self.last_update_timesteps_this_run = int(self.num_timesteps)
        self._update_interrupted = False

    def collect_rollouts(self, env, callback, train_freq, replay_buffer,
                         action_noise=None, learning_starts=0, log_interval=None):
        while True:
            attempt_start = int(self.num_timesteps)
            try:
                return super().collect_rollouts(
                    env, callback, train_freq, replay_buffer,
                    action_noise=action_noise,
                    learning_starts=learning_starts,
                    log_interval=log_interval,
                )
            except LapSentinelRegression as exc:
                if env.num_envs != 1 or not hasattr(self, "_recovery_dir"):
                    raise
                now = int(self.num_timesteps)
                self._recovery_steps = [
                    step for step in self._recovery_steps
                    if now - step < RECOVERY_POLICY["window_steps"]
                ]
                allowed = len(self._recovery_steps) < RECOVERY_POLICY["max_recoveries"]
                accepted = max(0, now - attempt_start)
                boundary_marked = False
                if accepted:
                    # The invalid action is never stored. End the last accepted
                    # transition so replay cannot bootstrap across the reset.
                    index = (replay_buffer.pos - 1) % replay_buffer.buffer_size
                    replay_buffer.dones[index, 0] = 1.0
                    if hasattr(replay_buffer, "timeouts"):
                        replay_buffer.timeouts[index, 0] = 0.0
                    boundary_marked = True
                self.invalid_transitions += 1
                record = {
                    "event": "lap_sentinel_recovery",
                    "num_timesteps": now,
                    "policy": RECOVERY_POLICY,
                    "diagnostic": exc.diagnostic,
                    "invalid_transition_stored": False,
                    "accepted_transitions_kept": accepted,
                    "last_transition_marked_terminal": boundary_marked,
                    "status": "reset_pending" if allowed else "rate_limit_exceeded",
                }
                path = self._recovery_dir / (unique_name("recovery") + ".json")
                atomic_json(path, record)
                if not allowed:
                    raise ProtocolError(
                        "Regressao de lap repetida: limite de 3 recuperacoes em 10000 passos; "
                        "diagnostico: " + str(path)
                    ) from exc
                self._recovery_steps.append(now)
                clear_progress()
                print(
                    f"RECUPERACAO DQN: transicao invalida descartada; {accepted} "
                    f"transicoes validas preservadas. Recarregando savestate. Diagnostico: {path}",
                    flush=True,
                )
                try:
                    self._last_obs = env.reset()
                except Exception as reset_error:
                    record.update(status="reset_failed", reset_error=repr(reset_error))
                    atomic_json(path, record)
                    raise
                self.recovery_count += 1
                record.update(status="reset_ok", recovery_count=self.recovery_count)
                atomic_json(path, record)
                self.logger.record("recovery/count", self.recovery_count)
                self.logger.record("recovery/invalid_transitions", self.invalid_transitions)


def save_replay_buffer_snapshot(model: DQN, project_root: Path, run: str) -> dict:
    directory = project_root / REPLAY_BUFFER_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    step = int(model.num_timesteps)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{run}_{step}_", suffix=".tmp", dir=directory
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        model.save_replay_buffer(str(temporary))
        digest = sha256(temporary)
        filename = f"apolo_{step}_{digest[:16]}.pkl"
        destination = directory / filename
        if destination.exists():
            temporary.unlink()
        else:
            os.replace(temporary, destination)
        relative = destination.relative_to(project_root.resolve()).as_posix()
        return {
            "path": relative,
            "sha256": digest,
            "num_timesteps": step,
            "transitions": int(model.replay_buffer.size()),
            "capacity": int(model.replay_buffer.buffer_size),
        }
    finally:
        temporary.unlink(missing_ok=True)


def load_replay_buffer_snapshot(model: DQN, project_root: Path, reference: dict) -> Path:
    if not isinstance(reference, dict):
        raise ValueError("O cerebro Apolo nao tem referencia valida para seu replay buffer DQN")
    relative = reference.get("path")
    pure = PurePosixPath(relative) if isinstance(relative, str) else None
    if (pure is None or pure.is_absolute() or ".." in pure.parts or "\\" in relative
            or not pure.parts):
        raise ValueError("Caminho inseguro ou ausente no replay buffer do Apolo")
    root = project_root.resolve()
    path = root.joinpath(*pure.parts).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Replay buffer DQN do Apolo ausente ou fora do projeto")
    expected_hash = reference.get("sha256")
    if not isinstance(expected_hash, str) or sha256(path) != expected_hash:
        raise ValueError("SHA-256 do replay buffer DQN diverge dos metadados do Apolo")
    model.load_replay_buffer(str(path))
    actual = int(model.replay_buffer.size())
    if actual != int(reference.get("transitions", -1)):
        raise ValueError("Quantidade de transicoes no replay buffer do Apolo nao confere")
    return path


def save_dqn_checkpoint(model: DQN, path: Path, expected: dict, *, run: str,
                        reason: str, provenance: dict) -> Path:
    saved = save_checkpoint(model, path, expected, run=run, reason=reason,
                            provenance=provenance)
    metadata_path = saved.with_suffix(".zip.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["resume_semantics"] = (
        "DQN Q/target networks, optimizer and counter in ZIP; replay buffer in the "
        "SHA-256-verified sidecar referenced by provenance"
    )
    atomic_json(metadata_path, metadata)
    validate_checkpoint(saved, expected)
    return saved


def cleanup_replay_buffer_snapshots(project_root: Path, brain) -> None:
    """Keep only buffers referenced by the current and rollback model pair."""
    directory = project_root / REPLAY_BUFFER_DIRECTORY
    if not directory.is_dir():
        return
    keep: set[Path] = set()
    for metadata_path in (
        brain.path.with_suffix(".zip.json"),
        brain.previous.with_suffix(".zip.json"),
    ):
        if not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            relative = metadata.get("provenance", {}).get("replay_buffer", {}).get("path")
            if isinstance(relative, str):
                candidate = (project_root / Path(*PurePosixPath(relative).parts)).resolve()
                if candidate.is_relative_to(directory.resolve()):
                    keep.add(candidate)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    for path in directory.glob("apolo_*.pkl"):
        if path.resolve() not in keep:
            path.unlink(missing_ok=True)


class ApoloDQNCallback(RaceMetricsCallback):
    """Training metrics plus atomic named-brain/replay-buffer checkpoints."""

    def __init__(self, model_dir: Path, expected: dict, run: str, checkpoint_every: int,
                 provenance: dict, brain, project_root: Path, verbose=1):
        super().__init__(model_dir, expected, run, checkpoint_every, provenance, verbose)
        self.brain = brain
        self.project_root = project_root
        self.last_published_updates = 0

    def _on_training_start(self):
        super()._on_training_start()
        self.last_published_updates = int(self.model._n_updates)

    def _on_rollout_start(self):
        updates = int(self.model._n_updates)
        if updates <= self.last_published_updates:
            return
        if self.brain.metadata is not None and self.num_timesteps - self.last_checkpoint < self.checkpoint_every:
            return
        self._publish("periodic_after_update")

    def _provenance_with_buffer(self, reference: dict) -> dict:
        provenance = dict(self.provenance)
        provenance["named_brain"] = {
            "name": self.brain.name,
            "source_sha256": self.brain.source_sha256,
        }
        provenance["replay_buffer"] = reference
        provenance["dqn_update"] = {
            "gradient_updates": int(self.model._n_updates),
            "num_timesteps": int(self.model.num_timesteps),
        }
        return provenance

    def _publish(self, reason: str, *, final_path: Path | None = None,
                 reference: dict | None = None) -> bool:
        if self.model._update_interrupted:
            return False
        reference = reference or save_replay_buffer_snapshot(
            self.model, self.project_root, self.run
        )
        provenance = self._provenance_with_buffer(reference)
        path = final_path or save_dqn_checkpoint(
            self.model,
            self.model_dir / f"named_update_{self.num_timesteps}_steps.zip",
            self.expected,
            run=self.run,
            reason=reason,
            provenance=provenance,
        )
        progress = {
            "last_update_timesteps": int(self.model.last_update_timesteps_this_run)
            if self.model.last_update_timesteps_this_run is not None else None,
            "gradient_updates_this_run": int(self.model.gradient_steps_this_run),
            "replay_buffer": reference,
        }
        if self.brain.metadata is None:
            self.brain.initialize(path, progress)
        else:
            self.brain.publish(path, progress)
        self.provenance["named_brain"] = {
            "name": self.brain.name,
            "source_sha256": self.brain.source_sha256,
        }
        self.last_published_updates = int(self.model._n_updates)
        self.last_checkpoint = int(self.model.num_timesteps)
        cleanup_replay_buffer_snapshots(self.project_root, self.brain)
        print(f"CEREBRO APOLO DQN: {self.brain.path.resolve()}", flush=True)
        return True

    def publish_final(self, path: Path, reason: str, reference: dict) -> bool:
        if reason not in {"final", "interrupted"}:
            return False
        return self._publish(reason, final_path=path, reference=reference)


class DQNProgressCallback(BaseCallback):
    """Show progress using DQN transitions rather than PPO rollout blocks."""

    def _on_training_start(self):
        import time
        self.started_at = time.monotonic()
        self.last_display = self.started_at
        self.start_steps = int(self.num_timesteps)
        self.target_steps = max(1, int(self.model._total_timesteps) - self.start_steps)
        print(f"Passos DQN solicitados nesta execucao: {self.target_steps:,}.", flush=True)
        self._display()

    def _display(self):
        import time
        done = max(0, int(self.num_timesteps) - self.start_steps)
        fraction = min(1.0, done / self.target_steps)
        filled = int(30 * fraction)
        bar = "#" * filled + "-" * (30 - filled)
        elapsed = max(time.monotonic() - self.started_at, 0.001)
        rate = done / elapsed
        eta = f"{max(0, self.target_steps - done) / rate / 60:.1f} min" if rate else "--"
        write_progress(
            f"DQN [{bar}] {fraction:6.1%} | {done:,}/{self.target_steps:,} steps | "
            f"{rate:.1f} steps/s | restante estimado: {eta}"
        )

    def _on_step(self):
        import time
        now = time.monotonic()
        if now - self.last_display >= 0.5:
            self._display()
            self.last_display = now
        return True

    def _on_rollout_end(self):
        clear_progress()

    def _on_training_end(self):
        self._display()
        finish_progress()
        print("Aprendizado DQN encerrado; salvando cerebro e replay buffer.", flush=True)
