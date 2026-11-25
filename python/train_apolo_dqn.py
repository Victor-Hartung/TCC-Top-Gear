from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import torch
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor

from apolo_dqn import (APOLO_BRAIN_NAMES, RECOVERY_POLICY, ApoloDQN, ApoloDQNCallback,
                       DQNProgressCallback,
                       attach_exploration_schedule, dqn_contract, dqn_options,
                       dqn_policy_kwargs, load_replay_buffer_snapshot,
                       save_dqn_checkpoint, save_replay_buffer_snapshot)
from checkpoint_provenance import preflight_reference
from env_topgear import TopGearEnv
from experiment import (assert_live_preflight, atomic_json, contract,
                        environment_versions, source_hashes, unique_name)
from named_brain import NamedBrain
from recording import RecordingEnv
from terminal_progress import clear_progress
from topgear_config import ProjectConfig


def arguments():
    parser = argparse.ArgumentParser(
        description="Treina o Apolo DQN ou retoma a sua copia Apolo v2."
    )
    parser.add_argument("--timesteps", type=int, default=1_000_000,
                        help="Passos adicionais nesta execucao (padrao: 1 milhao)")
    parser.add_argument("--checkpoint-every", type=int, default=25_000,
                        help="Intervalo de publicacao segura do modelo e replay buffer")
    parser.add_argument("--named-brain", choices=APOLO_BRAIN_NAMES, default="apolo",
                        help="Cerebro DQN que sera atualizado (padrao: apolo)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-step-log", action="store_true",
                        help="Desativa somente o log JSONL por decisao")
    parser.add_argument("--skip-env-check", action="store_true")
    return parser.parse_args()


def _checkpoint_provenance(base: dict, brain: NamedBrain, reference: dict) -> dict:
    provenance = dict(base)
    provenance["named_brain"] = {
        "name": brain.name,
        "source_sha256": brain.source_sha256,
    }
    provenance["replay_buffer"] = reference
    return provenance


def train(args, cfg: ProjectConfig):
    if args.timesteps < 1 or args.checkpoint_every < 1:
        raise ValueError("Quantidade de steps e intervalo de checkpoint devem ser positivos")
    cfg.assert_training_ready()
    preflight_contract = contract(cfg)
    receipt = assert_live_preflight(cfg, preflight_contract)
    expected = dqn_contract(cfg)
    torch.set_num_threads(cfg.integer("ppo", "torch_threads"))

    brain_name = args.named_brain
    run = unique_name(f"{brain_name}-dqn")
    run_dir = cfg.project_dir / "runs" / run
    model_dir = cfg.project_dir / "models" / run
    run_dir.mkdir(parents=True, exist_ok=False)
    model_dir.mkdir(parents=True, exist_ok=False)
    provenance = {
        "algorithm": "DQN",
        "seed": args.seed,
        "source_hashes": source_hashes(cfg.project_dir),
        "preflight": preflight_reference(run_dir, receipt),
        "environment": environment_versions(),
        "training_recovery": RECOVERY_POLICY,
    }
    shutil.copy2(cfg.path, run_dir / "game_profile.ini")
    for filename in ("requirements.txt", "requirements-dev.txt", "constraints.txt", "VERSION.txt"):
        shutil.copy2(cfg.project_dir / filename, run_dir / filename)

    env = None
    model = None
    reason = "final"
    callback = None
    saved_path = None
    buffer_reference = None

    with NamedBrain(cfg.project_dir, brain_name, expected) as brain:
        from_scratch = brain.metadata is None
        if from_scratch and brain_name == "apolo-v2":
            raise FileNotFoundError(f"Copia do Apolo v2 nao encontrada: {brain.path}")
        initial_timesteps = 0 if from_scratch else int(brain.metadata["num_timesteps"])
        if not from_scratch:
            provenance["named_brain"] = {
                "name": brain.name,
                "source_sha256": brain.source_sha256,
            }
        atomic_json(run_dir / "run_config.json", {
            "run": run,
            "brain": brain_name,
            "algorithm": "DQN",
            "contract": expected,
            "provenance": provenance,
            "seed": args.seed,
            "timesteps_requested": args.timesteps,
            "checkpoint_every": args.checkpoint_every,
            "step_log": not args.no_step_log,
            "from_scratch": from_scratch,
            "starting_num_timesteps": initial_timesteps,
            "replay_buffer_resumed": not from_scratch,
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
                print("APOLO DQN DO ZERO: rede Q, alvo, Adam, contador e replay buffer novos.", flush=True)
                model = ApoloDQN(
                    "MlpPolicy", env, verbose=1, tensorboard_log=str(run_dir),
                    **dqn_options(cfg), policy_kwargs=dqn_policy_kwargs(),
                    seed=args.seed, device="cpu",
                )
                model.configure_recovery(run_dir / "recoveries")
            else:
                model = ApoloDQN.load(
                    brain.path, env=env, device="cpu", tensorboard_log=str(run_dir)
                )
                model.configure_recovery(run_dir / "recoveries")
                reference = brain.metadata.get("provenance", {}).get("replay_buffer")
                if reference is None:
                    raise ValueError(
                        f"O {brain.path.name} nao tem replay buffer registrado; retomada DQN recusada."
                    )
                buffer_path = load_replay_buffer_snapshot(model, cfg.project_dir, reference)
                print(f"RETOMADA APOLO DQN: Q/target/Adam e replay buffer preservados ({buffer_path}).", flush=True)
                model.set_random_seed(args.seed)

            attach_exploration_schedule(model, args.timesteps)
            callback = ApoloDQNCallback(
                model_dir, expected, run, args.checkpoint_every, provenance,
                brain, cfg.project_dir,
            )
            progress = DQNProgressCallback()
            print(
                "Azul automatico / save 3 / road_v6_outcome / 61 features / 10 acoes / DQN.",
                flush=True,
            )
            print(
                f"Cerebro: {brain.path.resolve()} / replay buffer proprio.",
                flush=True,
            )
            print(
                "DQN: lr 0.0003 / gamma 0.999 / batch 64 / Q-network 64x64 Tanh / CPU.",
                flush=True,
            )
            model.learn(
                total_timesteps=args.timesteps,
                callback=[callback, progress],
                tb_log_name="DQN",
                reset_num_timesteps=from_scratch,
            )
        except KeyboardInterrupt:
            reason = "interrupted"
            clear_progress()
            print("Interrompido; salvando a ultima atualizacao DQN completa e o replay buffer.", flush=True)
        except Exception:
            reason = "failed"
            raise
        finally:
            clear_progress()
            try:
                if model is not None:
                    try:
                        buffer_reference = save_replay_buffer_snapshot(
                            model, cfg.project_dir, run, brain_name=brain.name
                        )
                        final_provenance = _checkpoint_provenance(provenance, brain, buffer_reference)
                        final_provenance["dqn_update"] = {
                            "gradient_updates": int(model._n_updates),
                            "num_timesteps": int(model.num_timesteps),
                            "update_interrupted": bool(model._update_interrupted),
                        }
                        saved_path = save_dqn_checkpoint(
                            model, model_dir / f"{reason}_{model.num_timesteps}_steps.zip",
                            expected, run=run, reason=reason, provenance=final_provenance,
                        )
                        print(f"CHECKPOINT DQN: {saved_path.resolve()}", flush=True)
                    except Exception as save_error:
                        reason = "failed"
                        atomic_json(run_dir / "save_error.json", {"error": repr(save_error)})
                        raise
                atomic_json(run_dir / "status.json", {
                    "status": reason,
                    "algorithm": "DQN",
                    "brain": brain_name,
                    "timesteps": int(model.num_timesteps) if model else 0,
                    "trained_steps_this_run": max(
                        0, int(model.num_timesteps) - initial_timesteps
                    ) if model else 0,
                    "gradient_updates_this_run": int(model.gradient_steps_this_run) if model else 0,
                    "last_update_timesteps_this_run": int(model.last_update_timesteps_this_run)
                    if model and model.last_update_timesteps_this_run is not None else None,
                    "recovery_count": int(model.recovery_count) if model else 0,
                    "invalid_transitions": int(model.invalid_transitions) if model else 0,
                    "replay_buffer": buffer_reference,
                })
                if callback is not None and saved_path is not None:
                    if callback.publish_final(saved_path, reason, buffer_reference):
                        print(f"CEREBRO FIXO APOLO DQN: {brain.path.resolve()}", flush=True)
                    elif reason in {"final", "interrupted"}:
                        if brain.metadata is not None:
                            print(
                                f"APOLO PRESERVADO na ultima atualizacao valida: {brain.path.resolve()}",
                                flush=True,
                            )
                        else:
                            print(
                                "Nenhuma atualizacao DQN completa para publicar; o ZIP de diagnostico "
                                f"ficou em {saved_path.resolve()}.", flush=True,
                            )
            finally:
                if env is not None:
                    env.close()
                print(f"REGISTROS DQN: {run_dir.resolve()}", flush=True)


def main():
    args = arguments()
    cfg = ProjectConfig.load()
    train(args, cfg)


if __name__ == "__main__":
    main()
