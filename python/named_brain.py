"""A fixed algorithm-specific checkpoint backed by immutable snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil

from stable_baselines3.common.callbacks import BaseCallback

from experiment import (atomic_json, save_checkpoint, validate_checkpoint,
                        validate_reward_compatible_checkpoint)


class NamedBrain:
    """Serializes one named model and recovers its previous ZIP/JSON pair."""

    def __init__(self, root: Path, name: str, expected: dict):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name):
            raise ValueError("Nome de cerebro invalido; use letras minusculas, numeros e hifen.")
        if name.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
            raise ValueError("Nome de cerebro reservado pelo Windows.")
        self.name, self.expected = name, expected
        self.path = Path(root) / "models" / f"{name}.zip"
        self.directory = Path(root) / "runs" / "operations" / "named_brains" / name
        self.lock = self.directory / "training.lock"
        self.journal = self.directory / "pending.json"
        self.previous = self.directory / "previous.zip"
        self.staged = self.directory / "next.zip"
        self.metadata = None
        self.source_sha256 = None
        self.current_sha256 = None
        self._locked = False
        self._lock_stream = None

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock_stream = self.lock.open("a+b")
        if self.lock.stat().st_size == 0:
            self._lock_stream.write(b" ")
            self._lock_stream.flush()
        self._lock_stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock_stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_stream.close()
            self._lock_stream = None
            raise RuntimeError(f"Cerebro {self.name} bloqueado por outro treino: {self.lock}") from exc
        self._locked = True
        try:
            self._recover()
            if self.path.exists() or self.path.with_suffix(".zip.json").exists():
                self.metadata = validate_reward_compatible_checkpoint(self.path, self.expected)
                named = self.metadata.get("named_brain", {})
                if named.get("name") != self.name:
                    raise ValueError("Arquivo fixo pertence a outro cerebro ou nao foi registrado.")
                self.current_sha256 = self.metadata["model_sha256"]
                self.source_sha256 = self.current_sha256
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self._locked:
            self._lock_stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_stream.fileno(), fcntl.LOCK_UN)
            self._lock_stream.close()
            self._lock_stream = None
            self._locked = False

    def _require_lock(self):
        if not self._locked:
            raise RuntimeError("Atualizacao do cerebro exige bloqueio exclusivo.")

    def _replace_pair(self, source: Path):
        temporary = self.directory / "restore.zip"
        shutil.copy2(source, temporary)
        shutil.copy2(source.with_suffix(".zip.json"), temporary.with_suffix(".zip.json"))
        validate_reward_compatible_checkpoint(temporary, self.expected)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, self.path)
        os.replace(temporary.with_suffix(".zip.json"), self.path.with_suffix(".zip.json"))

    def _recover(self):
        if not self.journal.exists():
            return
        transaction = json.loads(self.journal.read_text(encoding="utf-8"))
        if transaction["had_previous"]:
            validate_reward_compatible_checkpoint(self.previous, self.expected)
            self._replace_pair(self.previous)
        else:
            source = Path(transaction["source_checkpoint"])
            validate_checkpoint(source, self.expected)
            shutil.copy2(source, self.staged)
            atomic_json(self.staged.with_suffix(".zip.json"), transaction["metadata"])
            validate_checkpoint(self.staged, self.expected)
            self._replace_pair(self.staged)
        validate_reward_compatible_checkpoint(self.path, self.expected)
        self.journal.unlink()
        self.staged.unlink(missing_ok=True)
        self.staged.with_suffix(".zip.json").unlink(missing_ok=True)

    def initialize(self, source: Path, learning_progress: dict | None = None):
        self._require_lock()
        if self.metadata is not None:
            raise FileExistsError(f"Cerebro ja registrado: {self.path}")
        metadata = validate_checkpoint(source, self.expected)
        self._publish(source, metadata, learning_progress)
        self.source_sha256 = self.current_sha256

    def require_current(self, source: Path):
        self._require_lock()
        if self.metadata is None:
            raise FileNotFoundError(f"Cerebro fixo ausente: {self.path}")
        metadata = validate_reward_compatible_checkpoint(source, self.expected)
        if metadata["model_sha256"] != self.source_sha256:
            raise ValueError("A retomada precisa usar a versao atual do cerebro escolhido.")

    def publish(self, source: Path, learning_progress: dict | None = None):
        self._require_lock()
        metadata = validate_checkpoint(source, self.expected)
        origin = metadata.get("provenance", {}).get("named_brain", {})
        if origin != {"name": self.name, "source_sha256": self.source_sha256}:
            raise ValueError("Checkpoint pertence a outra linhagem de cerebro.")
        if metadata["num_timesteps"] < self.metadata["num_timesteps"]:
            raise ValueError("Checkpoint antigo; contador do cerebro nao pode regredir.")
        if metadata["reason"] not in {"periodic_after_update", "final", "interrupted"}:
            raise ValueError("Somente atualizacoes concluidas e paradas seguras podem atualizar o cerebro.")
        self._publish(source, metadata, learning_progress)

    def _publish(self, source: Path, metadata: dict, learning_progress: dict | None):
        source = Path(source).resolve()
        if source == self.path.resolve():
            raise ValueError("Origem deve ser um checkpoint preservado.")
        if self.metadata is not None:
            current = validate_reward_compatible_checkpoint(self.path, self.expected)
            if current["model_sha256"] != self.current_sha256:
                raise ValueError("Cerebro mudou durante o treino; publicacao recusada.")
        next_metadata = dict(metadata)
        next_metadata["named_brain"] = {
            "name": self.name,
            "source_checkpoint": str(source),
            "parent_model_sha256": self.current_sha256,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "learning_progress": learning_progress or {},
        }
        shutil.copy2(source, self.staged)
        atomic_json(self.staged.with_suffix(".zip.json"), next_metadata)
        validate_checkpoint(self.staged, self.expected)
        had_previous = self.metadata is not None
        if had_previous:
            shutil.copy2(self.path, self.previous)
            shutil.copy2(self.path.with_suffix(".zip.json"), self.previous.with_suffix(".zip.json"))
            validate_reward_compatible_checkpoint(self.previous, self.expected)
        atomic_json(self.journal, {
            "had_previous": had_previous,
            "source_checkpoint": str(source),
            "metadata": next_metadata,
        })
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(self.staged, self.path)
            os.replace(self.staged.with_suffix(".zip.json"), self.path.with_suffix(".zip.json"))
            validate_checkpoint(self.path, self.expected)
            self.journal.unlink()
        except BaseException:
            self._recover()
            raise
        self.metadata = next_metadata
        self.current_sha256 = next_metadata["model_sha256"]


class NamedBrainCallback(BaseCallback):
    """Publishes completed updates, never an interrupted optimizer update."""

    def __init__(self, brain: NamedBrain, model_dir: Path, run=None, provenance=None):
        super().__init__()
        self.brain, self.model_dir = brain, model_dir
        self.run = run or model_dir.name
        self.provenance = provenance or {'named_brain': {'name': brain.name, 'source_sha256': brain.source_sha256}}
        self.pending_update = None

    def _on_step(self):
        return True

    def _on_rollout_end(self):
        self.pending_update = self.num_timesteps

    def weights_are_stable(self):
        return self.pending_update is None or getattr(
            self.model, "last_update_timesteps_this_run", None) == self.pending_update

    def learning_progress(self):
        previous = (self.brain.metadata or {}).get("named_brain", {}).get("learning_progress", {})
        last_update = getattr(self.model, "last_update_timesteps_this_run", None)
        return {
            "last_update_timesteps": last_update if last_update is not None else previous.get("last_update_timesteps"),
            "trained_steps_this_run": getattr(self.model, "trained_steps_this_run", 0),
        }

    def _on_rollout_start(self):
        if not self.weights_are_stable():
            raise RuntimeError("Atualizacao do modelo pendente; cerebro fixo preservado.")
        completed_update = self.pending_update is not None
        self.pending_update = None
        path = self.model_dir / f"checkpoint_{self.num_timesteps}_steps.zip"
        if completed_update and not path.is_file():
            path = save_checkpoint(self.model, self.model_dir / f"named_update_{self.num_timesteps}_steps.zip",
                self.brain.expected, run=self.run, reason='periodic_after_update', provenance=self.provenance)
        if path.is_file():
            self._publish_checkpoint(path)

    def _publish_checkpoint(self, path: Path):
        progress = self.learning_progress()
        if self.brain.metadata is None:
            self.brain.initialize(path, progress)
        else:
            self.brain.publish(path, progress)
        self.provenance["named_brain"] = {
            "name": self.brain.name,
            "source_sha256": self.brain.source_sha256,
        }

    def publish_final(self, path: Path, reason: str):
        if reason not in {"final", "interrupted"} or not self.weights_are_stable():
            return False
        if (self.brain.metadata['contract'] != self.brain.expected
                and getattr(self.model, 'trained_steps_this_run', 0) == 0):
            # A collected rollout is not an optimizer update with the revised reward.
            return False
        self._publish_checkpoint(path)
        return True
