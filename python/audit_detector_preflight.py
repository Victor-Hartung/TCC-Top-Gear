"""Auditoria offline do pacote de preflight, sem renovar autorizacao de treino."""
import argparse,json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from live_detector import evaluate,parse_samples,REGIONS,VERSION
from experiment import atomic_json,unique_name,sha256

def audit(path):
    receipt=json.loads(path.read_text(encoding='utf-8'));stats=Counter();changed=[]
    for name,b in receipt['branches'].items():
        previous=None
        for s in [b['initial']]+b['launch_states']+b['states']:
            t=SimpleNamespace(**s);samples=parse_samples(t.detector_samples,t)
            if previous is None:assert len(samples)==1
            else:assert len(samples)==4 and samples[0][0]==previous+1 and t.frame==previous+4
            previous=t.frame
            features,rows=evaluate(t.detector_samples,t);assert len(features)==21
            stats['packets']+=1;stats['packets_before_lap_zero']+=t.lap==-1
            for i,region in enumerate(REGIONS):
                group=[r for r in rows if r['region']==region]
                selected=[r for r in group if r['selected_for_observation']]
                assert len(selected)==int(bool(group))
                if not selected:assert features[i*7:i*7+7]==[0.]*7;continue
                chosen=selected[0];stats[region+'_packets']+=1
                assert features[i*7+6]==chosen['risk']
                assert features[i*7+2]==max(-1.,min(1.,chosen['lateral_delta']/65536))
                assert chosen['risk']==max(r['risk'] for r in group)
                nearest=group[0]
                if chosen['id']!=nearest['id']:
                    stats['packets_selecting_different_threat']+=1
                    if len(changed)<10:changed.append(dict(branch=name,frame=t.frame,region=region,nearest_id=nearest['id'],selected_id=chosen['id'],nearest_lateral=nearest['lateral_delta'],selected_lateral=chosen['lateral_delta'],risk=chosen['risk']))
    result={'execution':'offline_review_of_live_preflight_packets','source':str(path.resolve()),'source_sha256':sha256(path),'detector_version':VERSION,'statistics':dict(stats),'examples':changed,'checks':'frame_continuity_reset_and_same_car_feature_consistency_passed','new_live_preflight':False,'training_authorization_changed':False}
    output=path.parent/(unique_name('detector_review')+'.json');atomic_json(output,result);print(output.resolve());print(dict(stats));return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);audit(p.parse_args().report)
