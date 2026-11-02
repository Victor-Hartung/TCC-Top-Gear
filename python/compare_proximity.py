"""Compara os detectores em coletas existentes, sem alterar PPO ou parametros."""
import argparse,csv
from collections import defaultdict
from pathlib import Path
from predict_proximity import PredictiveDetector
from experiment import atomic_json,unique_name,sha256

def compare(path):
    groups=defaultdict(list)
    entity=path.with_name(path.stem+'_racers.csv')
    with entity.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            r={k:int(v) for k,v in r.items()};groups[r['frame']].append(r)
    with path.open(newline='',encoding='utf-8-sig') as f:states=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
    detector=PredictiveDetector();frames={};events=[];output=[]
    for i,s in enumerate(states):
        candidates=detector.update(s,groups.pop(s['frame'],[]))
        frames[s['frame']]={r['id']:r for r in candidates};output.extend(candidates)
        hit=bool(s['collision_raw']&128) and (i==0 or not states[i-1]['collision_raw']&128)
        passed=i>0 and states[i-1]['rank']==15 and s['rank']==14
        if not (hit or passed) or not candidates:continue
        identity=candidates[0]['id'];event={'frame':s['frame'],'event':'impact_pulse' if hit else 'rank_16_to_15','candidate_id':identity,'candidate_at_event':candidates[0]}
        for key in ['proximity_warning','predicted_warning']:
            flags=[bool(frames.get(f,{}).get(identity,{}).get(key)) for f in range(s['frame']-60,s['frame'])]
            streak=0
            for flag in reversed(flags):
                if not flag:break
                streak+=1
            event[key]={'frames_in_prior_60':sum(flags),'continuous_frames_immediately_before':streak,'warning_at_event':candidates[0][key]}
        events.append(event)
    if not states or groups:raise ValueError('Frames vazios ou entidades sem jogador')
    output_base=path.parent/unique_name('comparison_'+path.stem)
    with output_base.with_suffix('.csv').open('x',encoding='utf-8',newline='') as f:
        if output:
            writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    summary={'capture':path.name,'execution':'offline_development_replay','source_sha256':{p.name:sha256(p) for p in [path,entity]},'detector_sha256':{n:sha256(Path(__file__).with_name(n)) for n in ['detect_proximity.py','predict_proximity.py','compare_proximity.py']},'thresholds':vars(detector.limits),'velocity_window_frames':3,'lateral_jump_rejection':4096,'frames':len(states),'events':events,'warning_frames':{k:sum(any(r[k] for r in rs.values()) for rs in frames.values()) for k in ['proximity_warning','predicted_warning']},'validated':False,'ppo_changed':False,'limitations':['All current captures now used for development, including prior independent capture.','Linear extrapolation is proximity, not measured physical collision prediction.','Nearest ID is not confirmed collider.','No false positive rate without labels; maneuver can avoid previously predicted proximity.']}
    atomic_json(output_base.with_suffix('.json'),summary)
    print(output_base.with_suffix('.json').resolve());print(summary['warning_frames'])
    for e in events:print(e['frame'],e['event'],e['proximity_warning'],e['predicted_warning'])
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',type=Path,required=True)
    compare(parser.parse_args().capture)
