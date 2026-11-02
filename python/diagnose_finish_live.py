"""Reproduz episodio registrado e observa 240 frames apos o resultado, sem treino.

Nao altera encerramento do ambiente. O trecho posterior usa somente aceleracao
para verificar os sinais; movimento residual nao prova que a corrida segue ativa.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from experiment import atomic_json, contract, sha256, unique_name
from protocol import BridgeClient
from telemetry import Telemetry
from topgear_config import ProjectConfig
from terminal_progress import write_progress, clear_progress
from native_finish_probe import NativeFinishBridge, parse_samples, summarize, FIELDS


def load_episode(run, episode, expected):
    source=json.loads((run/'run_config.json').read_text(encoding='utf-8'))
    if source['contract'] != expected:
        raise ValueError('Contrato do replay difere do protocolo/sensores atuais')
    start=None;steps=[]
    with (run/'steps.jsonl').open('rb') as stream:
        for line in stream:
            row=json.loads(line)
            if row['episode_id']>episode:break
            if row['episode_id']!=episode:continue
            if row['event']=='reset':start=row['state']['raw_telemetry']
            elif row['event']=='step':steps.append(row)
    if start is None or not steps or not steps[-1]['state']['race_ended']:
        raise ValueError('Replay exige episodio completo com resultado publicado')
    return start,steps


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=Path('runs/hermes-ppo_20260912_175046_376997'))
    parser.add_argument('--episode',type=int,default=270)
    parser.add_argument('--tail-steps',type=int,default=60)
    parser.add_argument('--native-probe',action='store_true',
                        help='Exige Lua diagnostico_fim_corrida.lua; captura candidatos da ROM por frame')
    args=parser.parse_args()
    if not 1<=args.tail_steps<=300:parser.error('tail-steps deve estar entre 1 e 300')
    cfg=ProjectConfig.load();run=args.run.resolve()
    source=json.loads((run/'run_config.json').read_text(encoding='utf-8'))
    expected=contract(cfg,source['contract']['reward_profile'])
    print('Preparando replay das acoes registradas; nao usa nem treina modelo.',flush=True)
    start,steps=load_episode(run,args.episode,expected)
    path=cfg.project_dir/'runs/diagnostico_termino'/(unique_name('finish_replay')+'.json')
    report={'execution':'live_bizhawk_diagnostic_no_training','status':'running',
        'source_run':str(run),'source_episode':args.episode,
        'source_run_config_sha256':sha256(run/'run_config.json'),
        'script_sha256':sha256(Path(__file__)), 'tail_action':1,'tail_steps':args.tail_steps,
        'replay_states':[],'tail_states':[], 'note':'Frames nao equivalem a leitura do cronometro do HUD.'}
    if args.native_probe:
        report.update(native_probe_version=1, native_samples=[], native_fields=FIELDS,
                      probe_lua_sha256=sha256(cfg.project_dir/'lua/diagnostico_fim_corrida.lua'),
                      main_lua_sha256=sha256(cfg.project_dir/'lua/Top Gear (USA).lua'))
    bridge=None
    try:
        bridge=(NativeFinishBridge if args.native_probe else BridgeClient)(cfg)
        lua_script='diagnostico_fim_corrida.lua' if args.native_probe else 'Top Gear (USA).lua'
        print(f'Servidor em {bridge.address}. Abra BizHawk e somente lua/{lua_script}.',flush=True)
        bridge.wait_ready()
        reset_state=bridge.reset()
        if args.native_probe:report['native_samples'].extend(parse_samples(reset_state.fields))
        initial=Telemetry.from_fields(reset_state.fields)
        initial.assert_runtime_ready(allow_prestart=True,require_detector=True)
        report['initial']=asdict(initial)
        if asdict(initial)!=start:raise ValueError('Savestate diferente do episodio de origem')
        previous_frame=initial.frame
        for i,row in enumerate(steps):
            received=bridge.step(row['action'])
            if args.native_probe:report['native_samples'].extend(parse_samples(received.fields, previous_frame))
            current=Telemetry.from_fields(received.fields)
            previous_frame=current.frame
            current.assert_runtime_ready(allow_prestart=True,require_detector=True)
            report['replay_states'].append({'action':row['action'],'state':asdict(current)})
            if asdict(current)!=row['state']['raw_telemetry']:
                report['expected_at_divergence']=row['state']['raw_telemetry']
                raise ValueError(f'Replay divergiu no passo {i+1}; diagnostico preservado')
            write_progress(f'Replay do episodio {args.episode}: {i+1}/{len(steps)} passos')
            if current.race_ended:
                report['first_result']=asdict(current)
                break
        if 'first_result' not in report:raise ValueError('Resultado registrado nao foi reproduzido')
        for i in range(args.tail_steps):
            received=bridge.step(1)
            if args.native_probe:report['native_samples'].extend(parse_samples(received.fields, previous_frame))
            current=Telemetry.from_fields(received.fields)
            previous_frame=current.frame
            report['tail_states'].append(asdict(current))
            write_progress(f'Observando depois do resultado: {i+1}/{args.tail_steps} passos; lap={current.lap}')
        report['status']='completed'
        report['tail_final']=asdict(current)
        report['frames_after_first_result']=current.frame-report['first_result']['frame']
    except BaseException as exc:
        report.update(status='failed',error=repr(exc))
        raise
    finally:
        clear_progress()
        try:
            if bridge is not None:bridge.close()
        finally:
            if args.native_probe:report['native_summary']=summarize(report['native_samples'])
            atomic_json(path,report)
            print('DIAGNOSTICO:',path.resolve(),flush=True)
            print('Nao e preflight nem validacao de aprendizado.',flush=True)


if __name__=='__main__':main()
