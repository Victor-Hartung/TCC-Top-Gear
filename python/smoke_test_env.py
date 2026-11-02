from __future__ import annotations

import argparse
import json
from collections import deque
from datetime import datetime
from pathlib import Path

from env_topgear import TopGearEnv


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnostico de termino: para sem reset automatico")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--log-every", type=int, default=1)
    parser.add_argument("--auto-reset", action="store_true",
                        help="Reinicia episodios para verificar continuidade; padrao preserva a cena")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if args.steps < 1:
        raise ValueError("--steps deve ser >= 1")
    if args.log_every < 1:
        raise ValueError("--log-every deve ser >= 1")
    project_dir = Path(__file__).resolve().parents[1]
    output_dir = project_dir / "runs" / "diagnostico_termino"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (datetime.now().strftime("termino_%Y%m%d_%H%M%S_%f") + ".json")
    env = TopGearEnv(project_dir=project_dir, require_validated=True)
    report = {
        "diagnostic_version": 1,
        "note": "finished e o sinal existente; nao comprova que as voltas foram completadas.",
        "requested_steps": args.steps,
        "initial_state": None,
        "last_steps": [],
        "stop_reason": "not_started",
        "episode_endings": [],
    }
    history = deque(maxlen=100)
    completed_steps = 0
    try:
        obs, info = env.reset()
        report["initial_state"] = dict(info)
        print("RESET", dict(zip(env.observation_names, obs)), info)
        unknown_surface_steps = 0
        offtrack_steps = 0
        collision_events = 0
        for index in range(args.steps):
            action = env.action_space.sample() if args.random else index % env.action_space.n
            obs, reward, terminated, truncated, info = env.step(action)
            completed_steps = index + 1
            history.append({"step": completed_steps, "action": int(action),
                            "reward": float(reward), "terminated": bool(terminated),
                            "truncated": bool(truncated), "state": dict(info)})
            unknown_surface_steps += int(info["surface_unknown"])
            offtrack_steps += int(info["offtrack"])
            collision_events += int(info["collision_event"])
            should_log = (
                (index + 1) % args.log_every == 0
                or info["surface_unknown"]
                or info["collision_event"]
                or terminated
                or truncated
            )
            if should_log:
                print(
                    f"step={index + 1} action={info['action_name']} reward={reward:.4f} "
                    f"speed={info['speed']} progress={info['progress']} lap={info['lap']} "
                    f"frame={info['frame']} rank={info['rank']} "
                    f"final_rank={info['final_rank']} finished={info['finished']} "
                    f"race_ended={info['race_ended']} total_laps={info['total_laps']} "
                    f"surface={info['surface_state']} "
                    f"raw={info['surface_raw']} unknown={info['surface_unknown']} "
                    f"offtrack={info['offtrack']} curve={info['curve_current']}/"
                    f"{info['curve_ahead_512']}/{info['curve_ahead_1024']}/"
                    f"{info['curve_ahead_2048']} nitro={info['nitro']} "
                    f"nearest={info['nearest_distance']} collision={info['collision_event']}"
                )
            if terminated or truncated:
                print(f"EPISODE END: {info['termination_reason']}")
                report["stop_reason"] = info["termination_reason"]
                report["episode_endings"].append(dict(history[-1]))
                print("ESTADO FINAL", json.dumps(info, ensure_ascii=False))
                if args.auto_reset and completed_steps < args.steps:
                    obs, info = env.reset()
                    print("RESET AUTOMATICO CONFIRMADO", json.dumps(info, ensure_ascii=False))
                    continue
                print("Sem reset automatico. O fechamento da ponte solicita pausa na cena atual.")
                break
        else:
            report["stop_reason"] = "diagnostic_step_limit"
        print(
            f"DIAGNOSTICO CONCLUIDO: steps={completed_steps} offtrack_steps={offtrack_steps} "
            f"unknown_surface_steps={unknown_surface_steps} "
            f"collision_events={collision_events}"
        )
    except KeyboardInterrupt:
        report["stop_reason"] = "user_interrupt"
        print("Interrompido pelo usuario; sem reset automatico.")
    except Exception as exc:
        report["stop_reason"] = "error"
        report["error"] = repr(exc)
        raise
    finally:
        report["completed_steps"] = completed_steps
        report["last_steps"] = list(history)
        try:
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"RESULTADO SALVO EM: {output_path.resolve()}")
        finally:
            env.close()


if __name__ == "__main__":
    main()
