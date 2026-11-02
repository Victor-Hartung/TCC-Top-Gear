"""Recalcula recompensa sobre um prefixo registrado; nao preve nova pilotagem."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

from driving_strategy import PROFILE, SETTINGS, opportunity, ACCELERATING_ACTIONS
from reward import RewardEngine, RewardWeights, profile_weights
from telemetry import Telemetry
from topgear_config import ProjectConfig
from experiment import atomic_json, unique_name, source_hashes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();cfg=ProjectConfig.load()
    source=args.run/'steps.jsonl'
    # Snapshot limitado ao tamanho observado; um treino ainda em curso pode
    # acrescentar dados depois. O hash identifica exatamente os bytes lidos.
    with source.open('rb') as stream:
        snapshot=stream.read(source.stat().st_size)
    report=dict(execution='offline_fixed_recorded_actions',new_bizhawk_validation=False,
                predicts_learning=False,source=str(source.resolve()),source_bytes=len(snapshot),
                source_prefix_sha256=hashlib.sha256(snapshot).hexdigest(),settings=SETTINGS,
                source_hashes=source_hashes(cfg.project_dir),activations=[],episodes=[])
    counts=Counter();actions=Counter();total_components=Counter();before=None
    old_profile=json.loads((args.run/'run_config.json').read_text(encoding='utf-8'))['contract']['reward_profile']
    if old_profile!='road_v3_turbo':raise ValueError('Esta auditoria compara o piloto road_v3_turbo com road_v4_driving')
    error=0.0
    for line in snapshot.splitlines():
        try:row=json.loads(line)
        except json.JSONDecodeError:continue
        if row.get('event')=='reset':
            before=row['state'];old=RewardEngine(profile_weights(RewardWeights.from_config(cfg),old_profile),old_profile)
            new=RewardEngine(profile_weights(RewardWeights.from_config(cfg),PROFILE),PROFILE)
            old_sum=new_sum=0.0
            continue
        if row.get('event')!='step' or before is None:continue
        after=row['state']
        p=Telemetry.from_fields({k:str(v) for k,v in before['raw_telemetry'].items()})
        c=Telemetry.from_fields({k:str(v) for k,v in after['raw_telemetry'].items()})
        action=row['action'];nav=before.get('navigation',{})
        a=old.calculate(p,c);b=new.calculate(p,c,action=action,navigation=nav)
        error=max(error,abs(a.total-row['reward']))
        old_sum+=a.total;new_sum+=b.total
        counts['steps']+=1;actions[action]+=1;total_components.update(b.components)
        context=opportunity(p,nav)
        if action not in ACCELERATING_ACTIONS:
            counts['non_accelerating_actions']+=1
            counts['unnecessary_lift_penalized']+=b.components['unnecessary_lift']<0
            counts['non_accelerating_with_sensor_risk']+=any(r['risk']>0 for r in before.get('detector_candidates',[]))
            counts['non_accelerating_curve_above8']+=abs(p.curve_current)>8
        if p.nitro>c.nitro:
            report['activations'].append(dict(episode=row['episode_id'],step=after['steps'],
                speed_before=p.speed,lap_before=p.lap,curve_before=p.curve_current,**context,
                costs={k:v for k,v in b.components.items() if k.startswith('turbo_')}))
        if row.get('terminated') or row.get('truncated'):
            report['episodes'].append(dict(episode=row['episode_id'],old_return=old_sum,new_return=new_sum,
                finished=bool(c.race_completed),final_rank=c.final_rank,collisions=c.collision_events))
        before=after
    report.update(counts=dict(counts),actions=dict(actions),new_components=dict(total_components),
                  old_reward_max_absolute_reconciliation_error=error)
    path=cfg.project_dir/'runs/analysis/driving_reward'/(unique_name('reward_audit')+'.json')
    atomic_json(path,report)
    print(json.dumps({'counts':report['counts'],'old_reward_reconciliation_error':error,
                      'activations':len(report['activations']),
                      'bad_opportunity_activations':sum(not r['turbo_opportunity'] for r in report['activations']),
                      'completed_episodes':len(report['episodes'])},indent=2))
    print('RELATORIO OFFLINE:',path)
    if error>1e-7:raise ValueError('Recompensa antiga nao reconciliou; investigar o relatorio')


if __name__=='__main__':main()
