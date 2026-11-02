"""Promocao exige avaliacao deterministica com diversificacao de estados iniciais."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from experiment import contract, contract_hash, validate_checkpoint, atomic_json
from topgear_config import ProjectConfig


def assess(reports: list[dict], model_hash: str, expected: dict) -> dict:
    episodes, scenarios, starts = [], set(), set()
    duplicate_starts = 0
    for report in reports:
        if (report.get('evaluation_version') != 3 or report.get('status') != 'completed'
                or not report.get('deterministic') or report.get('training_enabled')
                or report.get('model_sha256_before') != model_hash
                or report.get('model_sha256_after') != model_hash or report.get('contract') != expected):
            raise ValueError('Relatorio incompleto, modelo diferente ou contrato divergente')
        scenarios.add(report.get('scenario_id'))
        for ep in report['episodes']:
            if ep['controller'] != 'model' or not ep.get('completed'):
                continue
            # Duplicar o mesmo save com novos nomes não produz casos independentes.
            initial = ep['initial_state']
            fingerprint = {k: initial[k] for k in ('frame', 'speed', 'lateral', 'progress', 'lap', 'rank', 'nitro')}
            encoded = json.dumps(fingerprint, sort_keys=True)
            if encoded in starts:
                duplicate_starts += 1
                continue
            starts.add(encoded)
            episodes.append(ep['summary'])
    n = len(episodes)
    if not n:
        raise ValueError('Sem episodios avaliados')
    metrics = {'episodes': n, 'scenarios': len(scenarios), 'distinct_initial_states': len(starts),
               'duplicate_initial_states_ignored': duplicate_starts,
               'completion_rate': sum(e['race_completed'] for e in episodes) / n,
               'win_rate': sum(e['is_first'] for e in episodes) / n,
               'mean_offtrack_fraction': sum(e['offtrack_fraction'] for e in episodes) / n}
    metrics['approved'] = (n >= 20 and len(scenarios) >= 3 and len(starts) >= 3
        and metrics['completion_rate'] >= .95 and metrics['win_rate'] >= .8
        and metrics['mean_offtrack_fraction'] <= .05)
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--reports', nargs='+', required=True, type=Path)
    args = parser.parse_args()
    cfg = ProjectConfig.load()
    expected = contract(cfg)
    metadata = validate_checkpoint(args.model, expected)
    metrics = assess([json.loads(p.read_text(encoding='utf-8')) for p in args.reports], metadata['model_sha256'], expected)
    print(json.dumps(metrics, indent=2))
    if not metrics['approved']:
        raise SystemExit('Criterios de promocao ainda nao atingidos. Modelo preservado.')
    pointer = cfg.project_dir / 'models' / 'best_model.json'
    atomic_json(pointer, {'model': str(args.model.resolve().relative_to(cfg.project_dir)),
                         'sha256': metadata['model_sha256'], 'contract_sha256': contract_hash(expected),
                         'metrics': metrics, 'reports': [str(p.resolve()) for p in args.reports]})
    print(f'PROMOCAO: {pointer.resolve()}')


if __name__ == '__main__':
    main()
