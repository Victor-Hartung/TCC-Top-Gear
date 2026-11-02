"""Comparacoes reais pareadas, sem aprendizado. Intervencoes sao so diagnosticos."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from experiment import atomic_json, assert_live_preflight, contract, sha256, validate_checkpoint
from topgear_config import ProjectConfig
from transition_errors import LapSentinelRegression


class FirstNitroGate:
    """Suprime somente A antes da primeira carga e do limiar experimental.

    O limiar usa velocidade RAM bruta; nao equivale ao GO nem a RPM/km/h.
    Depois de atingir o limiar, nao volta a bloquear. Nao decide usar nitro.
    """
    def __init__(self, minimum_speed: int = 0):
        if minimum_speed < 0:
            raise ValueError('minimum_speed deve ser nao negativo')
        self.minimum_speed = minimum_speed
        self.released = minimum_speed == 0

    def apply(self, action: int, state: dict) -> int:
        if not 0 <= action < 30:
            raise ValueError('Acao fora do contrato manual')
        if (state.get('turbo_charges_used', 0) > 0 or state.get('turbo_active', 0)
                or state['speed'] >= self.minimum_speed):
            self.released = True
        if not self.released and action % 10 == 9:
            return action // 10 * 10 + 1  # Mesmo acelerador/marcha, sem A.
        return action


def load_plan(path: Path, root: Path) -> list[dict]:
    plan = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(plan, list) or not plan:
        raise ValueError('Plano deve conter uma lista nao vazia')
    names = set()
    for case in plan:
        name = case['id']
        if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name) or name in names:
            raise ValueError('ID de caso invalido/duplicado')
        names.add(name)
        if type(case['seed']) is not int or type(case['deterministic']) is not bool:
            raise ValueError('Seed/modo invalido')
        speed = case.get('first_nitro_min_speed', 0)
        if type(speed) is not int or speed < 0:
            raise ValueError('Limiar invalido')
        case['model'] = str((root / case['model']).resolve())
    return plan


def worker(root: Path, out: Path):
    import numpy as np
    import torch
    from stable_baselines3 import PPO
    from env_topgear import TopGearEnv

    torch.set_num_threads(1)
    cfg = ProjectConfig.load(root)
    if not cfg.manual_transmission:
        raise ValueError('Benchmark exige perfil manual')
    expected = contract(cfg)
    receipt = assert_live_preflight(cfg, expected)
    plan = load_plan(out / 'plan.json', root)
    models, weights, counters, hashes = {}, {}, {}, {}
    for case in plan:
        path = case['model']
        if path not in models:
            from manual_refinement import validate_inference_source
            validate_inference_source(Path(path), expected,
                allow_lower_rate_source=case.get('allow_learning_rate_difference', False))
            model = PPO.load(path, device='cpu')
            model.policy.set_training_mode(False)
            models[path] = model
            weights[path] = {k: v.clone() for k, v in model.policy.state_dict().items()}
            counters[path] = model.num_timesteps
            hashes[path] = sha256(Path(path))
    report = dict(status='starting', execution='live_bizhawk', training_enabled=False,
                  contract=expected, preflight=receipt, cases=[], model_hashes_before=hashes,
                  benchmark_source_sha256=sha256(Path(__file__)),
                  note='Mesmo savestate; sementes controlam a amostragem da politica, nao o trafego inicial. '
                       'Nitro gate e intervencao externa experimental, nao capacidade aprendida.')
    atomic_json(out / 'results.json', report)
    env = None
    try:
        env = TopGearEnv(root, expected_reset=receipt['reset_fingerprint'])
        report['status'] = 'running'
        for case in plan:
            if (out / 'STOP').exists():
                raise KeyboardInterrupt()
            model = models[case['model']]
            if model.observation_space != env.observation_space or model.action_space != env.action_space:
                raise ValueError('Espacos incompativeis')
            random.seed(case['seed']); np.random.seed(case['seed']); torch.manual_seed(case['seed'])
            obs, info = env.reset()
            gate = FirstNitroGate(case.get('first_nitro_min_speed', 0))
            actions, components = Counter(), Counter()
            steps = changes = overrides = 0
            reward_total = 0.0
            invalid_telemetry = False
            start = time.monotonic()
            print('CASE_STARTED', case['id'], flush=True)
            with (out / (case['id'] + '.jsonl')).open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(event='reset', state=info, case=case))+'\n')
                while True:
                    if (out / 'STOP').exists():
                        raise KeyboardInterrupt()
                    previous_obs = obs.tolist()
                    with torch.inference_mode():
                        predicted, _ = model.predict(obs, deterministic=case['deterministic'])
                    requested = int(predicted)
                    applied = gate.apply(requested, info)
                    overrides += applied != requested
                    try:
                        obs, reward, terminated, truncated, info = env.step(applied)
                    except LapSentinelRegression as exc:
                        # O pacote recusado nao e resultado de corrida nem passo aceito.
                        invalid_telemetry = True
                        result = dict(**case, status='invalid_telemetry',
                            steps=steps, attempted_step=steps+1,
                            race_completed=None, position=None,
                            diagnostic=exc.diagnostic,
                            wall_seconds=time.monotonic()-start)
                        stream.write(json.dumps(dict(event='invalid_telemetry',
                            summary=result), ensure_ascii=False)+'\n')
                        stream.flush()
                        report['cases'].append(result)
                        atomic_json(out / 'results.json', report)
                        print('CASE_INVALID_TELEMETRY', json.dumps({
                            'id': case['id'], 'attempted_step': steps+1}), flush=True)
                        break
                    steps += 1
                    actions[info['action_name']] += 1
                    changes += int(info['gear_changed'])
                    reward_total += float(reward)
                    components.update({k: float(v) for k,v in info.items() if k.startswith('reward_')})
                    stream.write(json.dumps(dict(event='step', step=steps, requested_action=requested,
                        applied_action=applied, observation_before=previous_obs, reward=float(reward),
                        terminated=bool(terminated), truncated=bool(truncated), state=info))+'\n')
                    if steps % 100 == 0:
                        stream.flush()
                    if terminated or truncated:
                        break
                if invalid_telemetry:
                    continue
                result = dict(**case, steps=steps, wall_seconds=time.monotonic()-start,
                    race_completed=info['race_completed'], position=info['final_rank']+1 if info['race_completed'] else None,
                    final_state=info, action_counts=dict(actions), reward=reward_total,
                    reward_components=dict(components), gear_changes=changes, overrides=overrides,
                    assisted_diagnostic=case.get('first_nitro_min_speed', 0)>0,
                    accelerate_fraction=sum(v for k,v in actions.items() if 'ACCELERATE' in k)/steps,
                    brake_fraction=sum(v for k,v in actions.items() if 'BRAKE' in k)/steps)
                stream.write(json.dumps(dict(event='end', summary=result))+'\n')
            report['cases'].append(result)
            atomic_json(out / 'results.json', report)
            print('CASE_FINISHED', json.dumps({k:result[k] for k in ['id','steps','race_completed','position','overrides','wall_seconds']}), flush=True)
        report['status'] = ('completed_with_invalid_cases' if any(
            c.get('status') == 'invalid_telemetry' for c in report['cases']) else 'completed')
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
    except BaseException as exc:
        report.update(status='error', error=repr(exc))
        raise
    finally:
        try:
            if env is not None:
                env.close()
        finally:
            report['model_integrity'] = {p: dict(file_unchanged=sha256(Path(p))==hashes[p],
                weights_unchanged=all(torch.equal(v, models[p].policy.state_dict()[k]) for k,v in weights[p].items()),
                counter_unchanged=models[p].num_timesteps==counters[p]) for p in models}
            atomic_json(out / 'results.json', report)
            print('BENCHMARK_RESULT', out / 'results.json', flush=True)


def launch(root: Path, out: Path, bizhawk: Path, speed: int):
    cfg = ProjectConfig.load(root)
    if not bizhawk.is_file():
        raise FileNotFoundError(bizhawk)
    # Somente o lancador diagnostico muda a velocidade de exibicao. Mesmo Lua/frames.
    profile = cfg.path.as_posix()
    bridge = (root / 'lua/Top Gear (USA).lua').as_posix()
    loader = out / 'start_benchmark.lua'
    loader.write_text(f'_G.TOPGEAR_PROFILE_OVERRIDE = [[{profile}]]\nclient.speedmode({speed})\ndofile([[{bridge}]])\n', encoding='utf-8')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    emulator = None
    with (out / 'stdout.log').open('x', encoding='utf-8') as so, (out / 'stderr.log').open('x', encoding='utf-8') as se:
        process = subprocess.Popen([sys.executable, '-u', __file__, '--worker', '--output', str(out), '--profile', cfg.path.name],
            cwd=root, stdout=so, stderr=se, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic()+90
            while process.poll() is None and time.monotonic()<deadline:
                if 'Servidor da ponte pronto' in (out/'stdout.log').read_text(encoding='utf-8', errors='replace'):
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('Servidor nao iniciou; consulte stderr.log')
            emulator = subprocess.Popen([str(bizhawk), '--socket-ip', cfg.text('protocol','socket_host'),
                '--socket-port', str(cfg.integer('protocol','socket_port')), '--load-slot', '2',
                '--lua', str(loader), str(root/'assets/rom/Top-Gear-USA.sfc')], cwd=bizhawk.parent,
                startupinfo=startup, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            atomic_json(out/'processes.json',dict(python_pid=process.pid, emulator_pid=emulator.pid, speed_percent=speed))
            print('BENCHMARK_STARTED',out,flush=True)
            seen = set()
            while process.poll() is None:
                for line in (out/'stdout.log').read_text(encoding='utf-8',errors='replace').splitlines():
                    if line.startswith(('CASE_STARTED','CASE_FINISHED','CASE_INVALID_TELEMETRY')) and line not in seen:
                        print(line,flush=True); seen.add(line)
                time.sleep(.5)
            if process.returncode:
                raise RuntimeError((out/'stderr.log').read_text(encoding='utf-8', errors='replace'))
        finally:
            if process.poll() is None:
                (out/'STOP').touch()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate(); process.wait(timeout=10)
            if emulator is not None and emulator.poll() is None:
                emulator.terminate(); emulator.wait(timeout=10)
    print('BENCHMARK_RESULT',out/'results.json',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bizhawk',type=Path)
    parser.add_argument('--speed-percent',type=int,default=100)
    parser.add_argument('--profile', choices=('game_profile_manual.ini','game_profile_manual_refine.ini'),default='game_profile_manual.ini')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.speed_percent not in (100,200,400):
        parser.error('Velocidade deve ser 100, 200 ou 400')
    os.environ['TOPGEAR_PROFILE']=args.profile
    root=Path(__file__).resolve().parents[1]
    out=args.output.resolve()
    if args.worker:
        worker(root,out)
    else:
        if args.plan is None or args.bizhawk is None:
            parser.error('--plan e --bizhawk sao obrigatorios')
        plan=load_plan(args.plan,root)
        out.mkdir(parents=True,exist_ok=False)
        atomic_json(out/'plan.json',plan)
        launch(root,out,args.bizhawk.resolve(),args.speed_percent)


if __name__=='__main__':
    main()
