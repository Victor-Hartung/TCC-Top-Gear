"""Equivalencia offline de historicos reais com detector previo; nao valida TCP real."""
import csv
from collections import defaultdict,deque
from pathlib import Path
from types import SimpleNamespace
from predict_proximity import PredictiveDetector
from live_detector import evaluate
from experiment import atomic_json,unique_name,sha256

def check(path):
    groups=defaultdict(list)
    entity=path.with_name(path.stem+'_racers.csv')
    with entity.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            r={k:int(v) for k,v in r.items()};groups[r['frame']].append(r)
    offline=PredictiveDetector();history=deque(maxlen=4);count=0;compared=0;decision_samples=0
    with path.open(newline='',encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            s={k:int(v) for k,v in row.items()};rs=groups.pop(s['frame']);baseline=offline.update(s,rs)
            values=[s[k] for k in ['frame','progress','lateral','track_length']]
            for r in rs:
                if 2<=r['id']<=19:values.extend([r['id'],r['progress'],r['lateral']])
            history.append(','.join(map(str,values)));count+=1
            if len(history) not in (1,4):continue
            features,live=evaluate(';'.join(history),SimpleNamespace(**s));reference={r['id']:r for r in baseline}
            assert len(live)==len(baseline)
            for r in live:
                old=reference[r['id']]
                assert (r['prediction_valid'],r['predicted_warning'],r['predicted_entry_frames'])==(old['prediction_valid'],old['predicted_warning'],old['predicted_entry_frames']),(s['frame'],r,old)
                compared+=1
            assert len(features)==21 and all(-1<=v<=1 for v in features)
            if (count-1)%4==0:decision_samples+=1
    assert not groups
    return dict(capture=path.name,frames=count,candidate_comparisons=compared,decision_samples=decision_samples,equivalent=True,sha256={p.name:sha256(p) for p in [path,entity]})

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];directory=root/'runs/diagnostics'
    names=['081729_3338','082010_5500','082719_6017','083426_5369','084321_5525']
    result={'execution':'offline_parity_on_live_recordings','live_bizhawk_preflight':False,'captures':[]}
    for name in names:
        row=check(directory/('contexto_20260912_'+name+'.csv'));result['captures'].append(row);print(row)
    path=directory/(unique_name('integrated_detector_parity')+'.json');atomic_json(path,result);print(path.resolve())
