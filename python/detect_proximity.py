"""Detector exploratorio offline. Nao importado pelo ambiente PPO."""
from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from opponent_analysis import signed_track_gap
from experiment import atomic_json, unique_name, sha256

@dataclass(frozen=True)
class Limits:
    sensor_fraction: float = 0.1
    alongside_gap: int = 32
    longitudinal_warning: int = 100
    lateral_warning: int = 4096
    horizon_frames: int = 30
    max_relative_delta: int = 100

class Detector:
    def __init__(self, limits=Limits()):
        self.limits = limits
        self.previous = {}
        self.frame = None

    def update(self, player, racers):
        frame, length = player['frame'], player['track_length']
        if self.frame is not None and frame != self.frame + 1:
            raise ValueError('Frames nao consecutivos: separar coletas/reset')
        ids = [r['id'] for r in racers if 2 <= r['id'] <= 19]
        if len(racers) != 20 or sorted(ids) != list(range(2,20)):
            raise ValueError('Tabela incompleta ou IDs duplicados')
        result=[]; new={}
        for racer in racers:
            identity=racer['id']
            if not 2 <= identity <= 19: continue
            gap=signed_track_gap(player['progress'],racer['progress'],length)
            lateral=racer['lateral']-player['lateral']
            old=self.previous.get(identity)
            valid=old is not None and old[2]==length and abs(gap-old[0])<=self.limits.max_relative_delta
            closing=(abs(old[0])-abs(gap)) if valid else None
            # Este tempo e ate alinhamento longitudinal, nao tempo de colisao fisica.
            eta=abs(gap)/closing if closing is not None and closing>0 else None
            region='alongside' if abs(gap)<=self.limits.alongside_gap else 'front' if gap>0 else 'rear'
            aligned=abs(lateral)<=self.limits.lateral_warning
            warning=aligned and (abs(gap)<=self.limits.longitudinal_warning or (eta is not None and eta<=self.limits.horizon_frames))
            new[identity]=(gap,lateral,length)
            if abs(gap)<=length*self.limits.sensor_fraction:
                result.append(dict(frame=frame,id=identity,gap=gap,lateral_delta=lateral,
                    region_candidate=region,closing_valid=int(valid),closing_raw=closing,
                    frames_to_longitudinal_alignment=eta,proximity_warning=int(warning),
                    validated=False))
        self.previous=new;self.frame=frame
        return sorted(result,key=lambda r:(abs(r['gap']),r['id']))

def replay(path):
    from collections import defaultdict
    states=list(csv.DictReader(path.open(encoding='utf-8-sig',newline='')))
    entity_path=path.with_name(path.stem+'_racers.csv')
    groups=defaultdict(list)
    with entity_path.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            r={k:int(v) for k,v in row.items()};groups[r['frame']].append(r)
    detector=Detector();output=[];events=[];warnings={};previous=None
    for row in states:
        state={k:int(v) for k,v in row.items()}
        candidates=detector.update(state,groups.pop(state['frame'],[]));output.extend(candidates)
        warnings[state['frame']]=[r['id'] for r in candidates if r['proximity_warning']]
        hit=bool(state['collision_raw']&128) and (previous is None or not previous['collision_raw']&128)
        passed=previous is not None and previous['rank']==15 and state['rank']==14
        if hit or passed:
            before=[{'frame':f,'ids':warnings[f]} for f in range(state['frame']-60,state['frame']) if warnings.get(f)]
            events.append({'frame':state['frame'],'event':'impact_pulse' if hit else 'rank_16_to_15',
                           'nearest_candidates':candidates[:3],'warnings_previous_60_frames':before})
        previous=state
    if not states or groups:raise ValueError('Coleta vazia ou frames de entidades sem jogador')
    destination=path.parent/unique_name('detector_'+path.stem)
    csv_path=destination.with_suffix('.csv')
    with csv_path.open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['frame','id','gap','lateral_delta','region_candidate','closing_valid','closing_raw','frames_to_longitudinal_alignment','proximity_warning','validated']);writer.writeheader();writer.writerows(output)
    summary={'execution':'offline_replay_of_live_capture','capture':str(path.resolve()),
             'source_sha256':{p.name:sha256(p) for p in [path,entity_path]},
             'frames':len(states),'thresholds':vars(detector.limits),'events':events,
             'warning_frames':sum(bool(v) for v in warnings.values()),
             'candidate_csv':str(csv_path.resolve()),'validated':False,'ppo_changed':False,
             'limits':['Exploratory thresholds, not fitted physical hitboxes.','Same captures used for development: no independent validation.',
                       'Warnings indicate proximity, not inevitable collision.','No precision/recall without synchronized independent labels.',
                       'Modulo ignores lap differences; physical visibility/activity remains unproven.']}
    atomic_json(destination.with_suffix('.json'),summary)
    print(destination.with_suffix('.json').resolve())
    for e in events:print(e['event'],e['frame'],'warning frames before',len(e['warnings_previous_60_frames']))
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',type=Path,required=True)
    replay(parser.parse_args().capture)
