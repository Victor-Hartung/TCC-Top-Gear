from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import torch
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

from ares_a2c import a2c_contract, a2c_options, a2c_policy_kwargs
from callbacks import RaceMetricsCallback, TrainingProgressCallback
from checkpoint_provenance import preflight_reference
from env_topgear import TopGearEnv
from experiment import (
    assert_live_preflight,
    atomic_json,
    contract as environment_contract,
    environment_versions,
    save_checkpoint,
    source_hashes,
    unique_name,
)
from named_brain import NamedBrain, NamedBrainCallback
from recording import RecordingEnv
from resilient_a2c import RECOVERY_POLICY, ResilientA2C
from terminal_progress import clear_progress
from topgear_config import ProjectConfig


def arguments():
    parser = argparse.ArgumentParser(
        description="Treina ou retoma o cerebro Ares A2C, separado dos demais modelos."
    )
    parser.add_argument("--timesteps", type=int, default=100_000,
                        help="Passos adicionais nesta execucao (padrao: 100 mil)")
    parser.add_argument("--checkpoint-every", type=int, default=25_000,
                        help="Intervalo minimo entre publicacoes seguras do Ares")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-step-log", action="store_true",
                        help="Desativa somente o log JSONL por decisao")
    parser.add_argument("--skip-env-check", action="store_true")
    return parser.parse_args()


def train(args, cfg: ProjectConfig):
    if args.timesteps < 1 or args.checkpoint_every < 1:
        raise ValueError("Passos e intervalo de checkpoint devem ser positivos")
    cfg.assert_training_ready()
    receipt = assert_live_preflight(cfg, environment_contract(cfg))
    expected = a2c_contract(cfg)
    torch.set_num_threads(cfg.integer("ppo", "torch_threads"))

    run = unique_name("ares-a2c")
    run_dir = cfg.project_dir / "runs" / run
    model_dir = cfg.project_dir / "models" / run
    run_dir.mkdir(parents=True, exist_ok=False)
    model_dir.mkdir(parents=True, exist_ok=False)
    provenance = {
        "algorithm": "A2C",
        "seed": args.seed,
        "source_hashes": source_hashes(cfg.project_dir),
        "preflight": preflight_reference(run_dir, receipt),
        "environment": environment_versions(),
        "training_recovery": RECOVERY_POLICY,
    }
    shutil.copy2(cfg.path, run_dir / "game_profile.ini")
    for filename in ("requirements.txt", "requirements-dev.txt", "constraints.txt", "VERSION.txt"):
        source = cfg.project_dir / filename
        if source.is_file():
            shutil.copy2(source, run_dir / filename)

    env = None
    model = None
    reason = "final"
    named_callback = None
    saved_path = None

    with NamedBrain(cfg.project_dir, "ares", expected) as brain:
        from_scratch = brain.metadata is None
        initial_timesteps = 0 if from_scratch else int(brain.metadata["num_timesteps"])
        provenance["named_brain"] = {
            "name": brain.name,
            "source_sha256": brain.source_sha256,
        }
        atomic_json(run_dir / "run_config.json", {
            "run": run,
            "brain": "ares",
            "algorithm": "A2C",
            "contract": expected,
            "provenance": provenance,
            "seed": args.seed,
            "timesteps_requested": args.timesteps,
            "checkpoint_every": args.checkpoint_every,
            "step_log": not args.no_step_log,
            "from_scratch": from_scratch,
            "starting_num_timesteps": initial_timesteps,
            "optimizer_resumed": not from_scratch,
            "on_policy_rollout_resumed": False,
        })

        try:
            raw = TopGearEnv(cfg.project_dir, expected_reset=receipt["reset_fingerprint"])
            env = raw
            if not args.skip_env_check:
                check_env(raw, warn=True, skip_render_check=True)
            recorded = RecordingEnv(raw, run_dir, log_steps=not args.no_step_log)
            env = recorded
            info_keys = (
                "race_ended", "race_completed", "lap", "total_laps", "progress",
                "rank", "final_rank", "is_first", "collisions_total", "overtakes_total",
                "net_progress", "offtrack_fraction", "stopped_fraction", "termination_reason",
            )
            env = Monitor(recorded, filename=str(run_dir / "monitor.csv"), info_keywords=info_keys)

            if from_scratch:
                print(
                    "NOVO ARES A2C DO ZERO: ator, critico, RMSprop e contador novos; "
                    "nenhum peso de PPO ou DQN sera importado.",
                    flush=True,
                )
                model = ResilientA2C(
                    "MlpPolicy", env, verbose=1, tensorboard_log=str(run_dir),
                    **a2c_options(cfg), policy_kwargs=a2c_policy_kwargs(),
                    seed=args.seed, device="cpu",
                )
            else:
                model = ResilientA2C.load(
                    brain.path, env=env, device="cpu", tensorboard_log=str(run_dir)
                )
                model.set_random_seed(args.seed)
                print(
                    "RETOMADA ARES A2C: pesos, critico, otimizador RMSprop e contador preservados; "
                    "um rollout novo sera coletado. A2C nao usa replay buffer.",
                    flush=True,
                )

            model.configure_recovery(run_dir / "recoveries")
            race_callback = RaceMetricsCallback(
                model_dir, expected, run, args.checkpoint_every, provenance
            )
            progress_callback = TrainingProgressCallback()
            named_callback = NamedBrainCallback(
                brain, model_dir, run, provenance
            )
            print(
                "Azul automatico / save 3 / road_v6_outcome / GAE 0.995 / "
                "61 features / 10 acoes / A2C.",
                flush=True,
            )
            print(
                "Ares usa models/ares.zip e seu proprio estado; Hermes PPO e Apolo DQN ficam separados.",
                flush=True,
            )
            print(
                "A2C: RMSprop / learning rate 0.0003 / gamma 0.999 / "
                "rollout de 2048 passos / ator-critico 64x64 Tanh / CPU.",
                flush=True,
            )
            model.learn(
                total_timesteps=args.timesteps,
                callback=[race_callback, progress_callback, named_callback],
                log_interval=1,
                tb_log_name="A2C",
                reset_num_timesteps=from_scratch,
            )
        except KeyboardInterrupt:
            reason = "interrupted"
            clear_progress()
            print("Interrompido; salvando a ultima atualizacao A2C completa e os registros.", flush=True)
        except Exception:
            reason = "failed"
            raise
        finally:
            clear_progress()
            try:
                if model is not None:
                    saved_path = save_checkpoint(
                        model,
                        model_dir / f"{reason}_{model.num_timesteps}_steps.zip",
                        expected,
                        run=run,
                        reason=reason,
                        provenance=provenance,
                    )
                    print(f"CHECKPOINT A2C: {saved_path.resolve()}", flush=True)
                atomic_json(run_dir / "status.json", {
                    "status": reason,
                    "algorithm": "A2C",
                    "brain": "ares",
                    "timesteps": int(model.num_timesteps) if model else 0,
                    "trained_steps_this_run": int(getattr(model, "trained_steps_this_run", 0)) if model else 0,
                    "last_update_timesteps_this_run": getattr(model, "last_update_timesteps_this_run", None) if model else None,
                    "recovery_count": int(getattr(model, "recovery_count", 0)) if model else 0,
                    "discarded_rollout_steps": int(getattr(model, "discarded_rollout_steps", 0)) if model else 0,
                })
                if named_callback is not None and saved_path is not None:
                    if named_callback.publish_final(saved_path, reason):
                        print(f"CEREBRO FIXO ARES A2C: {brain.path.resolve()}", flush=True)
                    else:
                        print(
                            f"CEREBRO ARES PRESERVADO: {brain.path.resolve()}; "
                            "a ultima atualizacao nao foi promovida.",
                            flush=True,
                        )
            finally:
                if env is not None:
                    env.close()
                print(f"REGISTROS: {run_dir.resolve()}", flush=True)


def main():
    args = arguments()
    cfg = ProjectConfig.load()
    train(args, cfg)


if __name__ == "__main__":
    main()
