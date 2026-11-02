"""Avaliacao deterministica com registro completo; nao treina nem salva a rede."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import time
from pathlib import Path

from stable_baselines3 import PPO
from terminal_progress import write_progress, clear_progress, finish_progress
from env_topgear import TopGearEnv
from topgear_config import ACTION_NAMES
from topgear_config import ProjectConfig
from experiment import assert_live_preflight, validate_reward_compatible_checkpoint, contract, atomic_json, environment_versions, source_hashes


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def show_evaluation_progress(report: dict, controller: str, steps: int) -> None:
    total = report['requested_episodes'] * (2 if report.get('compare_accelerate') else 1)
    done = sum(bool(ep.get('completed')) for ep in report['episodes'])
    fraction = min(1.0, done / max(1, total))
    filled = int(30 * fraction)
    bar = '#' * filled + '-' * (30 - filled)
    write_progress(f'AVALIACAO [{bar}] {fraction:6.1%} | {done}/{total} episodios avaliados | '
          f'{controller}: {steps:,} steps nesta corrida | '
          'percentual por episodios, nao por tempo')


def evaluate(env, model, episodes: int, report: dict, log_every: int = 100,
             controller: str = "model") -> None:
    if controller not in ("model", "accelerate"):
        raise ValueError("Controlador desconhecido")
    for episode in range(1, episodes + 1):
        obs, info = env.reset()
        if "race_completed" not in info:
            raise RuntimeError("Ambiente sem semantica v3 de encerramento; confira a pasta aberta")
        record = {"episode": episode, "controller": controller,
                  "initial_state": dict(info), "steps": [], "completed": False}
        if controller == "accelerate":
            reference = next((r for r in report["episodes"]
                              if r.get("controller") == "model" and r["episode"] == episode), None)
            if reference is not None:
                record["same_initial_state_as_model"] = reference["initial_state"] == info
        report["episodes"].append(record)
        counts = Counter()
        reward_sum = 0.0
        discounted_reward = 0.0
        component_sums = Counter()
        offtrack_steps = 0
        speed_sum = 0
        accelerate_streak = longest_accelerate = 0
        terminated = truncated = False
        print(f"EPISODIO {episode}: controller={controller}, sem treinamento", flush=True)
        show_evaluation_progress(report, controller, 0)
        last_progress = time.monotonic()
        while not (terminated or truncated):
            observation_before = obs.tolist()
            if controller == "model":
                action, _ = model.predict(obs, deterministic=True)
                action_id = int(action)
            else:
                action_id = ACTION_NAMES.index("ACCELERATE")
            previous = dict(info)
            obs, reward, terminated, truncated, info = env.step(action_id)
            name = info["action_name"]
            counts[name] += 1
            reward_sum += float(reward)
            discounted_reward += (float(report.get("gamma", 0.99)) ** len(record["steps"])) * float(reward)
            for key, value in info.items():
                if key.startswith("reward_"):
                    component_sums[key] += float(value)
            offtrack_steps += int(info["offtrack"])
            speed_sum += int(info["speed"])
            accelerate_streak = accelerate_streak + 1 if "ACCELERATE" in name else 0
            longest_accelerate = max(longest_accelerate, accelerate_streak)
            step = len(record["steps"]) + 1
            record["steps"].append({
                "step": step, "action": action_id, "action_name": name,
                "reward": float(reward), "terminated": bool(terminated),
                "truncated": bool(truncated), "observation_before": observation_before,
                "before": previous, "after": dict(info),
            })
            now = time.monotonic()
            if now - last_progress >= 0.5:
                show_evaluation_progress(report, controller, step)
                last_progress = now
            if step % log_every == 0 or info["collision_event"] or terminated or truncated:
                clear_progress()
                print(f"controller={controller} episode={episode} step={step} action={name} "
                      f"speed={info['speed']} progress={info['progress']} lap={info['lap']} "
                      f"offtrack={info['offtrack']} collisions={info['collisions_total']}", flush=True)
        count = len(record["steps"])
        record["completed"] = True  # Avaliacao do episodio encerrada; nao significa chegada.
        show_evaluation_progress(report, controller, count)
        finish_progress()
        record["summary"] = {
            "steps": count, "reward": reward_sum,
            "discounted_reward": discounted_reward,
            "reward_component_sums": dict(component_sums),
            "action_counts": dict(counts),
            "accelerate_action_fraction": sum(v for k, v in counts.items() if "ACCELERATE" in k) / count,
            "brake_action_fraction": sum(v for k, v in counts.items() if "BRAKE" in k) / count,
            "longest_accelerate_streak_steps": longest_accelerate,
            "offtrack_fraction": offtrack_steps / count,
            "mean_speed_raw": speed_sum / count,
            "final_state": dict(info),
            "race_completed": info['race_completed'],
            "is_first": info['is_first'],
            "net_progress": info['net_progress'],
        }
        print(f"Resumo: concluida={info['race_completed']}, primeiro={info['is_first']}, "
              f"progresso liquido={info['net_progress']}, fora={offtrack_steps/count:.1%}", flush=True)
        print("RESULTADO", json.dumps(record["summary"], ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia o modelo salvo sem aprendizado")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--compare-accelerate", action="store_true",
                        help="Depois do modelo, repete o save apenas acelerando, sem direcao nem turbo")
    parser.add_argument('--scenario-id', default='las_vegas_slot1', help='Rotulo da condicao de avaliacao; nao altera o save')
    parser.add_argument("--require-preflight", action="store_true",
                        help="Exige preflight atual e o mesmo save em cada reset")
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes deve ser positivo")
    model_path = args.model.resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Modelo nao encontrado: {model_path}")
    root = Path(__file__).resolve().parents[1]
    cfg = ProjectConfig.load(root)
    expected = contract(cfg)
    receipt = assert_live_preflight(cfg, expected) if args.require_preflight else None
    metadata = validate_reward_compatible_checkpoint(model_path, expected)
    before_hash = file_hash(model_path)
    # Carrega antes de abrir o servidor para detectar problemas de modelo primeiro.
    model = PPO.load(model_path, device="cpu")
    model.policy.set_training_mode(False)
    output_dir = root / "runs" / "avaliacao_modelo"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (datetime.now().strftime("avaliacao_%Y%m%d_%H%M%S_%f") + ".json")
    report = {
        "evaluation_version": 3, "model_path": str(model_path),
        "scenario_id": args.scenario_id, 'contract': expected,
        'model_contract_sha256': metadata['contract_sha256'],
        'model_reward_version': metadata['contract']['reward_version'],
        'model_num_timesteps': metadata['num_timesteps'],
        'environment': environment_versions(), 'source_hashes': source_hashes(root),
        "model_sha256_before": before_hash, "deterministic": True,
        "training_enabled": False, "requested_episodes": args.episodes,
        "compare_accelerate": args.compare_accelerate,
        "gamma": float(model.gamma),
        "note": "Colisoes nao distinguem impacto traseiro/frontal. Velocidade em unidades brutas. "
                "Cada transicao registra antes/depois de uma acao; nao todos os frames. "
                "Mesmo save e politica deterministica podem repetir o mesmo resultado. "
                "Controlador accelerate e referencia de aceleracao, nao um piloto capaz de fazer curvas.",
        "episodes": [], "status": "starting",
        "preflight_required": args.require_preflight, "preflight_receipt": receipt,
    }
    env = None
    try:
        env = TopGearEnv(root, require_validated=True,
                         expected_reset=receipt["reset_fingerprint"] if receipt else None)
        profile = metadata['contract']['reward_profile']
        report["reward_profile"] = profile
        if model.observation_space != env.observation_space or model.action_space != env.action_space:
            raise ValueError("Espacos de observacao/acao do modelo e ambiente sao diferentes")
        report["observation_names"] = list(env.observation_names)
        evaluate(env, model, args.episodes, report)
        if args.compare_accelerate:
            evaluate(env, model, args.episodes, report, controller="accelerate")
        report["status"] = "completed"
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        print("Avaliacao interrompida; registros parciais serao preservados.")
    except Exception as exc:
        report["status"] = "error"
        report["error"] = repr(exc)
        raise
    finally:
        clear_progress()
        try:
            if env is not None:
                env.close()
        finally:
            report["model_sha256_after"] = file_hash(model_path)
            report["model_file_unchanged"] = report["model_sha256_after"] == before_hash
            atomic_json(output_path, report)
            print(f"AVALIACAO SALVA EM: {output_path.resolve()}", flush=True)
            print(f"Arquivo do modelo preservado: {report['model_file_unchanged']}", flush=True)


if __name__ == "__main__":
    main()
