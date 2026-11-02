"""Recalcula evidencias preservadas, sem executar modelo legado ou alterar entradas."""
from __future__ import annotations
import csv
from collections import Counter,defaultdict
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import zipfile
import zlib
from analyze_curve_map import load_map,load_labels,nonzero_runs
from experiment import atomic_json,sha256,unique_name
from replay_rewards import analyze,reward_state
from reward import RewardEngine,RewardWeights,profile_weights
from topgear_config import ProjectConfig


def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))


def collect(root:Path) -> dict:
    ev=root/'archive/evidence'
    result={'scope':'Read-only recalculation of available user artifacts; no live emulator',
            'sources':{p.name:sha256(p) for p in sorted(ev.iterdir()) if p.is_file()}}
    rom=(root/'assets/rom/Top-Gear-USA.sfc').read_bytes()
    result['rom']={'size':len(rom),'sha1':hashlib.sha1(rom).hexdigest(),'sha256':hashlib.sha256(rom).hexdigest(),
                   'header_title':rom[0x7fc0:0x7fd5].decode('ascii'),
                   'curve_index_code_008592':rom[0x592:0x5BA].hex()}
    m=load_map(ev/'diagnostico_mapa_curvas.csv'); labels=load_labels(ev/'diagnostico_curva.csv')
    values=[r['curve_low_s8'] for r in m]
    result['curve']={'raw_rows':len(rows(ev/'diagnostico_mapa_curvas.csv')),'valid_rows':len(m),
        'values':dict(Counter(values)),'low_bytes_adler32':zlib.adler32(bytes(r['curve_low_u8'] for r in m)),
        'runs':[{'index_start':a,'index_end':b,'progress_start':a*32,'progress_end':b*32+31,
                 'min':min(v),'max':max(v),'sum':sum(v)} for a,b,v in nonzero_runs(m)],
        'manual_labels':[{'label':label,'index':idx,'curve':values[idx],
                         'matched':label==('straight' if values[idx]==0 else 'left' if values[idx]>0 else 'right')}
                          for label,idx in labels]}
    s=rows(ev/'diagnostico_superficie.csv')
    result['surface']={'frames':len(s),'values':dict(Counter(r['surface_0727'] for r in s)),
                      'mirror_disagreements':sum(r['surface_0727']!=r['surface_0A67'] for r in s),
                      'frame_gaps':sum(int(b['emu_frame'])-int(a['emu_frame'])!=1 for a,b in zip(s,s[1:]))}
    result['offtrack_labels']=[]
    for name in ('diagnostico_offtrack.csv','diagnostico_offtrack(1).csv'):
        with (ev/name).open(encoding='utf-8-sig',newline='') as stream:
            labeled=[r for r in csv.DictReader(stream) if r['address_hex']=='0x0727']
        result['offtrack_labels'].append({'source':name,'samples':len(labeled),
            'matched':sum(int(r['value_u8'])=={'on_track':1,'off_left':0,'off_right':2}[r['label']] for r in labeled)})
    turbo=defaultdict(list)
    for r in rows(ev/'diagnostico_turbo(1).csv'):turbo[r['scenario']].append(r)
    result['turbo']={}
    for name,rr in turbo.items():
        active=[int(r['relative_frame']) for r in rr if int(r['turbo_active_candidate'])]
        result['turbo'][name]={'samples':len(rr),'active_relative_frames':[min(active),max(active)] if active else [],
            'raw_counts':dict(Counter(r['nitro_u16'] for r in rr)),
            'first_nitro_raw':int(rr[0]['nitro_u16']),'last_nitro_raw':int(rr[-1]['nitro_u16']),
            'speed_min':min(int(r['speed_s16']) for r in rr),'speed_max':max(int(r['speed_s16']) for r in rr)}
    p=rows(ev/'diagnostico_pista(3).csv')
    transitions=[{'frame':int(b['emu_frame']),'lap_before':int(a['lap_s16']),'lap_after':int(b['lap_s16']),
                  'progress_before':int(a['progress']),'progress_after':int(b['progress']),
                  'final_rank_before':int(a['final_rank_s16']),'final_rank_after':int(b['final_rank_s16'])}
                  for a,b in zip(p,p[1:]) if a['lap_s16']!=b['lap_s16'] or a['final_rank_s16']!=b['final_rank_s16']]
    result['victory']={'frames':len(p),'range':[int(p[0]['emu_frame']),int(p[-1]['emu_frame'])],
        'transitions':transitions,'collision_edges':sum(int(r['collision_edge']) for r in p),
        'speed_min':min(int(r['speed']) for r in p),'speed_max':max(int(r['speed']) for r in p),
        'surface_recorded':False,'full_reward_replay_possible':False,
        'note':'road_inside_candidate is an obsolete unvalidated geometry estimate, not actual surface',
        'valid_finish_terminal_components':{'finish':20,'finish_rank':10,'first_place':30},
        'complete_reward_counterfactual':'indeterminate_without_valid_surface; terminal bonus = 60 in all corrected profiles'}
    cfg=ProjectConfig.load(root)
    result['reward_replay']=analyze(ev/'avaliacao_20260908_181515_799660.json',cfg)
    evaluation=json.loads((ev/'avaliacao_20260908_181515_799660.json').read_text())
    result['policy_and_reference']=[]
    for ep in evaluation['episodes']:
        steps=ep['steps']
        result['policy_and_reference'].append({'controller':ep['controller'],'steps':len(steps),
            'action_counts':dict(Counter(s['action_name'] for s in steps)),
            'offtrack_fraction':sum(s['after']['offtrack'] for s in steps)/len(steps),
            'last_state':steps[-1]['after'],'initial_state':ep['initial_state'],
            'mean_speed':sum(s['after']['speed'] for s in steps)/len(steps)})
    # Sensibilidade nos mesmos dois trajetos: custo de impactos e fora da pista.
    result['weight_sensitivity']=[]
    for collision in (0,.25,.5,1.5):
        for offtrack in (0,.005,.02):
            score={}
            for ep in evaluation['episodes']:
                weights=replace(profile_weights(RewardWeights.from_config(cfg),'road_v2'),collision=collision,offtrack=offtrack)
                engine=RewardEngine(weights,'road_v2')
                rewards=[engine.calculate(reward_state(s['before']),reward_state(s['after'])).total for s in ep['steps']]
                score[ep['controller']]=sum(.999**i*r for i,r in enumerate(rewards))
            result['weight_sensitivity'].append({'collision':collision,'offtrack':offtrack,'gamma':.999,
                'scores':score,'accelerate_preferred':score['accelerate']>score['model']})
    result['historical_monitors']=[]
    for name in ('runs.zip','hermes-rl-ppo_20260908_174024.zip'):
        path=ev/name
        if not path.exists():continue
        with zipfile.ZipFile(path) as z:
            for entry in z.namelist():
                if not entry.endswith('monitor.csv'):continue
                raw=z.read(entry).decode('utf-8-sig')
                lines=[l for l in raw.splitlines() if not l.startswith('#')]
                rr=list(csv.DictReader(lines))
                result['historical_monitors'].append({'archive':name,'entry':entry,'rows':rr})
    return result


def main():
    root=Path(__file__).resolve().parents[1]
    out=root/'runs/evidence_audit'/(unique_name('evidence')+'.json')
    atomic_json(out,collect(root))
    print(f'EVIDENCIAS: {out.resolve()}')


if __name__=='__main__':main()
