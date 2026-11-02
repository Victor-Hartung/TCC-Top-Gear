"""Contrafactuais de recompensa; nao e estimacao causal do desempenho da politica."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import fields
import json
from pathlib import Path
from reward import RewardEngine, RewardWeights, profile_weights, PROFILES
from telemetry import Telemetry
from topgear_config import ProjectConfig
from experiment import atomic_json, sha256, unique_name
from driving_strategy import PROFILE as DRIVING_PROFILE


def reward_state(row: dict) -> Telemetry:
    # Os JSONs antigos nao possuem todos os sensores. Somente campos usados pela
    # recompensa sao reconstruidos; isto NAO pode alimentar observacao/treino.
    raw = {f.name: 0 for f in fields(Telemetry)}
    raw.update({k: v for k, v in row.items() if k in raw and isinstance(v, int)})
    raw['finished'] = int(row.get('race_ended', row.get('finished', 0)))
    raw['collision_events'] = int(row.get('collisions_total', row.get('collision_events', 0)))
    raw['track_length'] = int(row.get('track_length', 22528))
    raw['total_laps'] = int(row.get('total_laps', 3))
    raw['final_rank'] = int(row.get('final_rank', -1))
    raw['surface_unknown'] = int(row.get('surface_unknown', 0))
    return Telemetry(**raw)


def replay(steps: list[dict], cfg, profile: str, gamma: float) -> dict:
    if profile == DRIVING_PROFILE:
        raise ValueError('Use audit_driving_reward.py: este perfil exige acoes e navegacao reais, ausentes no replay legado')
    weights = profile_weights(RewardWeights.from_config(cfg), profile)
    engine = RewardEngine(weights, profile)
    sums = Counter()
    total = discounted = 0.0
    invalid = 0
    for index, step in enumerate(steps):
        before, after = reward_state(step['before']), reward_state(step['after'])
        result = engine.calculate(before, after)
        components = dict(result.components)
        invalid += bool(components['invalid_progress_jump'])
        if profile not in ('road_v2', 'road_v3_turbo', 'road_v5_race', 'road_v6_outcome'):
            # Reproduz exatamente o encerramento do ambiente legado na mesma serie.
            if after.finished == 0 and step['after'].get('termination_reason') in ('no_progress', 'time_limit'):
                components['failure'] = -weights.failure
        reward = sum(v for k, v in components.items() if k != 'invalid_progress_jump')
        sums.update(components)
        total += reward
        discounted += gamma ** index * reward
    return {'profile': profile, 'gamma': gamma, 'steps': len(steps), 'return': total,
            'discounted_return': discounted, 'components': dict(sums), 'invalid_transitions': invalid,
            'bootstrap_value_included': False}


def analyze(path: Path, cfg) -> dict:
    source = json.loads(path.read_text(encoding='utf-8'))
    output = {'source': path.name, 'sha256': sha256(path), 'method': 'fixed_recorded_trajectories',
              'limitations': ['Sem previsao de novas acoes', 'Sem estimativa de valor no truncamento',
                              'Eventos traseiros nao rotulados', 'Não ha validação independente dos pesos'],
              'episodes': []}
    for episode in source['episodes']:
        rows = episode['steps']
        output['profiles_not_evaluated'] = {DRIVING_PROFILE: 'Arquivo legado sem navegacao; nao fabricar sensores'}
        results = [replay(rows, cfg, profile, gamma) for profile in PROFILES if profile != DRIVING_PROFILE for gamma in (0.99, 0.995, 0.999)]
        original = next(r for r in results if r['profile'] == 'legacy_corrigido' and r['gamma'] == 0.99)
        error = original['return'] - episode['summary']['reward']
        if abs(error) > 1e-7:
            raise ValueError(f'Replay legado nao reconcilia: {error}')
        output['episodes'].append({'controller': episode['controller'], 'results': results,
                                   'legacy_reconciliation_error': error})
    return output


def main():
    cfg = ProjectConfig.load()
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=cfg.project_dir / 'archive/evidence/avaliacao_20260908_181515_799660.json')
    parser.add_argument('--output', type=Path, default=cfg.project_dir / 'runs/replay' / (unique_name('rewards')+'.json'))
    args = parser.parse_args()
    output = analyze(args.input, cfg)
    if args.output.exists():
        raise FileExistsError(f'Resultado preservado: {args.output}; escolha um novo nome')
    atomic_json(args.output, output)
    for episode in output['episodes']:
        print(episode['controller'])
        for r in episode['results']:
            print(f"  {r['profile']} gamma={r['gamma']}: R={r['return']:.6f} G={r['discounted_return']:.6f}")
    print(f'REPLAY: {args.output.resolve()}')


if __name__ == '__main__':
    main()
