"""Auditoria offline de logs reais: nao executa emulador nem modifica pesos."""
import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

from experiment import atomic_json, sha256, unique_name
from live_detector import evaluate


def aggregate(rows):
    finished = [r for r in rows if r['final_state']['race_completed']]
    actions = Counter()
    for row in rows:
        actions.update(row['actions'])
    return {
        'episodes': len(rows), 'completed': len(finished),
        'wins': sum(r['final_state']['is_first'] for r in rows),
        'reward_mean': mean(r['reward'] for r in rows),
        'offtrack_episode_mean': mean(r['final_state']['offtrack_fraction'] for r in rows),
        'collisions_mean': mean(r['final_state']['collisions_total'] for r in rows),
        'net_progress_mean': mean(r['final_state']['net_progress'] for r in rows),
        'finish_position_mean': mean(r['final_state']['final_rank']+1 for r in finished) if finished else None,
        'actions': dict(actions),
    }


def audit(run, out):
    events = [json.loads(s) for s in (run/'episodes.jsonl').read_text(encoding='utf-8').splitlines()]
    episodes = [r for r in events if r['event']=='episode_end']
    counts, actions, lap_changes, presence, warnings = (Counter() for _ in range(5))
    hist, lap_examples, end_steps, last_rows = deque(), [], {}, deque(maxlen=8)
    previous = first_reset = None
    digest = hashlib.sha256()
    for line in (run/'steps.jsonl').open('rb'):
        digest.update(line)
        r = json.loads(line)
        s = r['state']; raw = s['raw_telemetry']
        counts[r['event']] += 1
        last_rows.append({k:s[k] for k in ('frame','lap','progress','speed','steps','collision','nitro')})
        if r['event']=='reset':
            hist.clear()
            if first_reset is None:first_reset=raw
            counts['reset_mismatch'] += int(raw != first_reset)
        else:
            actions[s['action_name']] += 1
            counts['offtrack'] += s['offtrack']
            counts['unknown_surface'] += s['surface_unknown']
            counts['stopped'] += int(s['speed']==0)
            counts['prestart'] += int(s['lap']==-1)
            counts['frame_delta_error'] += int(s['frame']-previous['frame'] != 4)
            if s['lap'] != previous['lap']:
                lap_changes[f"{previous['lap']}->{s['lap']}"] += 1
                if s['lap'] < previous['lap'] and len(lap_examples)<25:
                    lap_examples.append({'episode':r['episode_id'],'before':previous['raw_telemetry'], 'after':raw})
            counts['incomplete_finish_bonus'] += int(not s['race_completed'] and s.get('reward_finish',0)>0)
            impact = raw['collision_events']-previous['raw_telemetry']['collision_events']
            if impact>0:
                counts['impact_windows'] += 1
                counts['impact_events'] += impact
                counts['impact_windows_with_prior_warning_32frames'] += int(any(flag for _,flag in hist))
            if r['terminated'] or r['truncated']:
                end_steps[r['episode_id']] = counts['step']
        rows=s.get('detector_candidates',[])
        for region in ('front','rear','alongside'):
            presence[region] += int(any(c['region']==region for c in rows))
            warnings[region] += int(any(c['region']==region and c['predicted_warning'] for c in rows))
        # Recalculo amostral explicito; nao afirma replay de todos os candidatos.
        if r['event']=='reset' or counts['step']%1000==0 or s['collision_event']:
            features,recomputed=evaluate(raw['detector_samples'],SimpleNamespace(**raw))
            counts['detector_packets_replayed'] += 1
            counts['detector_replay_mismatch'] += int(recomputed != rows)
            counts['detector_feature_bounds_error'] += int(any(not -1<=v<=1 for v in features))
        hist.append((s['frame'],any(c['predicted_warning'] for c in rows)))
        while hist and s['frame']-hist[0][0]>=32:hist.popleft()
        previous=s
        if counts['step'] and counts['step']%50000==0 and r['event']=='step':
            print(f"Auditados {counts['step']} passos",flush=True)
    blocks=[]
    for i in range(0,len(episodes),20):
        chunk=episodes[i:i+20]
        blocks.append({'first_episode':chunk[0]['episode_id'],'last_episode':chunk[-1]['episode_id'], **aggregate(chunk)})
    result={'run':str(run.resolve()), 'execution':'offline_analysis_of_recorded_live_training',
        'source_hashes':{'steps.jsonl':digest.hexdigest(), 'episodes.jsonl':sha256(run/'episodes.jsonl'),
                         'analysis_script':sha256(Path(__file__))},
        'counts':dict(counts),'lap_changes':dict(lap_changes),'lap_regression_examples':lap_examples,
        'detector_presence_packets':dict(presence),'detector_warning_packets':dict(warnings),
        'all':aggregate(episodes),'first20':aggregate(episodes[:20]),'last20':aggregate(episodes[-20:]),
        'last100':aggregate(episodes[-100:]),'blocks20':blocks,'actions_all_steps':dict(actions),
        'wins':[{'episode':e['episode_id'],'run_step':end_steps[e['episode_id']],
                 'reward':e['reward'],'final_state':e['final_state']} for e in episodes if e['final_state']['is_first']],
        'failure_events':[e for e in events if e['event']!='episode_end'],
        'last_accepted_states':list(last_rows),
        'notes':['Rates are training results from one savestate, not independent policy evaluation.',
                 'Prior detector warning at an impact is association, not collision cause or sensor recall.',
                 'Rejected packet from the original failure was not logged and cannot be reconstructed.']}
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    tb={}
    for folder in run.glob('PPO_*'):
        ea=EventAccumulator(str(folder),size_guidance={'scalars':0});ea.Reload()
        tb[folder.name]={tag:[{'step':e.step,'value':e.value,'wall_time':e.wall_time} for e in ea.Scalars(tag)]
                         for tag in ea.Tags()['scalars']}
    atomic_json(out/'tensorboard_scalars.json',tb)
    atomic_json(out/'analysis.json',result)
    plot(episodes,out,json.loads((run/'status.json').read_text(encoding='utf-8'))['timesteps'])
    print(json.dumps({k:result[k] for k in ('counts','lap_changes','first20','last20','last100')},ensure_ascii=False))
    print('RELATORIO:',out/'analysis.json')
    return result


def plot(episodes,out,timesteps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs=list(range(1,len(episodes)+1))
    rolling=lambda values:[mean(values[max(0,i-19):i+1]) for i in range(len(values))]
    fig,axes=plt.subplots(3,2,figsize=(13,10),constrained_layout=True)
    fig.suptitle(f'Top Gear PPO — contador final: {timesteps:,} passos\n'
                 f'{len(episodes)} episódios encerrados | médias móveis de 20 episódios | dados de treinamento',fontsize=15)
    plots=[('Recompensa por episódio',[e['reward'] for e in episodes],'Recompensa'),
           ('Decisões fora da pista',[100*e['final_state']['offtrack_fraction'] for e in episodes],'%'),
           ('Corridas completas',[100*e['final_state']['race_completed'] for e in episodes],'%'),
           ('Impactos registrados',[e['final_state']['collisions_total'] for e in episodes],'Eventos'),
           ('Posição final nas corridas completas',None,'Posição (1 é melhor)'),
           ('Uso das ações de direção e aceleração',None,'% das decisões')]
    for ax,(title,values,ylabel) in zip(axes.flat,plots):
        ax.set_title(title);ax.set_xlabel('Episódio');ax.set_ylabel(ylabel);ax.grid(alpha=.2)
        if values is not None:
            ax.plot(xs,values,color='#94a3b8',alpha=.45,lw=.8)
            ax.plot(xs,rolling(values),color='#087e8b',lw=2)
    ranks=[(x,e['final_state']['final_rank']+1) for x,e in zip(xs,episodes) if e['final_state']['race_completed']]
    axes[2,0].scatter(*zip(*ranks),s=12,color='#087e8b');axes[2,0].set_ylim(20.5,.5)
    for keys,label,color in [(['LEFT_ACCELERATE','RIGHT_ACCELERATE'],'Virar + acelerar','#087e8b'),
                             (['ACCELERATE','TURBO_ACCELERATE'],'Acelerar / turbo','#e69500'),
                             (['BRAKE','LEFT_BRAKE','RIGHT_BRAKE'],'Frear','#ad3c60')]:
        values=[100*sum(e['actions'].get(k,0) for k in keys)/sum(e['actions'].values()) for e in episodes]
        axes[2,1].plot(xs,rolling(values),label=label,color=color)
    axes[2,1].legend(fontsize=8)
    fig.savefig(out/'curvas_treino.png',dpi=150)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args()
    output=args.run.parent/'analysis'/unique_name(args.run.name)
    output.mkdir(parents=True,exist_ok=False)
    audit(args.run,output)
