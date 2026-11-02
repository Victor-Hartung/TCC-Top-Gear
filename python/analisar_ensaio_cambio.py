"""Compara duas repeticoes de quarta/quinta no mesmo ponto, sem liberar treino."""
import argparse
import csv
from pathlib import Path
from statistics import mean
from experiment import atomic_json, sha256, unique_name


def analyze(rows):
    errors=[]
    measurements=[]
    prefixes=[]
    expected_variants=[0,1,1,0]
    report=dict(status='incomplete',errors=errors,comparisons=[],interferences=[],training_authorized=False,
                manual_vs_automatic_validated=False,optimal_shift_point_validated=False,
                note='Ensaio local no ponto testado; dados brutos, nao km/h ou RPM. Ambas as variantes usam modo manual.')
    if not rows or sorted({r['trial'] for r in rows})!=[1,2,3,4]:
        errors.append('Exige quatro execucoes ABBA completas');return report
    version=rows[0].get('capture_version',1)
    prep_frames=rows[0].get('prep_frames',240)
    measure_frames=rows[0].get('measure_frames',180)
    schedule=(version,prep_frames,measure_frames)
    if schedule not in ((1,240,180),(2,420,60),(3,240,60),(4,300,60),(5,240,60),(6,300,60),(7,360,24),(8,0,60),(9,0,180),(10,0,120)) or any(
        (r.get('capture_version',1),r.get('prep_frames',240),r.get('measure_frames',180))!=schedule for r in rows):
        errors.append('Cronograma desconhecido ou metadados inconsistentes');return report
    expected_car=48 if version>=5 else (16 if version>=3 else 0)
    rolling=version>=8
    expected_slot=3 if rolling else 2
    report.update(capture_version=version,prep_frames=prep_frames,measure_frames=measure_frames,
                  car_table_offset_raw=expected_car,car={0:'red',16:'white',48:'blue'}[expected_car],
                  savestate_slot=expected_slot,rolling_start=rolling)
    if [r['trial'] for r in rows]!=sorted(r['trial'] for r in rows):
        errors.append('Execucoes fora de ordem');return report
    for trial,variant in enumerate(expected_variants,1):
        part=[r for r in rows if r['trial']==trial]
        launch=[r for r in part if r['phase']==0]
        prep=[r for r in part if r['phase']==1]
        measured=[r for r in part if r['phase']==2]
        valid_launch=not launch if rolling else 8<=len(launch)<=1200
        if not valid_launch or len(prep)!=prep_frames or len(measured)!=measure_frames:
            errors.append(f'Execucao {trial} incompleta');return report
        phases=[(0,i) for i in range(len(launch))]+[(1,i) for i in range(prep_frames)]+[(2,i) for i in range(measure_frames)]
        if [(r['phase'],r['phase_frame']) for r in part]!=phases or [r['frame'] for r in part]!=list(range(len(part))):
            errors.append(f'Execucao {trial}: frames/fases incorretos')
        if any(b['emu_frame']!=a['emu_frame']+1 or b['gear_before']!=a['gear_after'] or b['speed_before']!=a['speed_after']
               for a,b in zip(part,part[1:])):
            errors.append(f'Execucao {trial}: telemetria descontinua')
        for r in part:
            up=(r['phase']==1 and any(f<=r['phase_frame']<f+4 for f in (60,120,180))) or (r['phase']==2 and variant==1 and r['phase_frame']<4)
            if (r['variant'],r['slot'],r['car_raw'],r['accelerate'],r['shift_up'],r['shift_down'])!=(variant,expected_slot,expected_car,1,int(up),0):
                errors.append(f'Execucao {trial}: configuracao/comandos inesperados');break
        stable=0;ready_at=None
        for i,r in enumerate(launch):
            stable=stable+1 if r['speed_after']>=1500 else 0
            if stable>=8:ready_at=i+1;break
        if not rolling and ready_at!=len(launch):errors.append(f'Execucao {trial}: largada nao respeita prontidao')
        if rolling and (part[0]['gear_before']!=3 or part[0]['speed_before']<=7312):
            errors.append(f'Execucao {trial}: inicio lancado exige quarta e velocidade bruta >7312')
        if not rolling and (part[0]['gear_before']!=0 or any(r['gear_after']!=0 for r in launch+prep[:60])):
            errors.append(f'Execucao {trial}: primeira marcha mudou sem comando')
        for f in (() if rolling else (60,120,180)):
            window=prep[f:f+12]
            changes=[r for r in window if r['gear_after']!=r['gear_before']]
            if len(changes)!=1 or window[-1]['gear_after']-window[0]['gear_before']!=1:
                errors.append(f'Execucao {trial}: subida de preparacao falhou no frame {f}')
        allowed={i for f in (60,120,180) for i in range(f,f+12)}
        if any(r['gear_after']!=r['gear_before'] and r['phase_frame'] not in allowed for r in prep):
            errors.append(f'Execucao {trial}: troca espontanea na preparacao')
        transitions=[r for r in measured if r['gear_before']!=r['gear_after']]
        if measured[0]['gear_before']!=3 or any(r['gear_after']!=3+variant for r in measured[12:]):
            errors.append(f'Execucao {trial}: marcha medida incorreta')
        if variant==0 and transitions or variant==1 and (len(transitions)!=1 or transitions[0]['phase_frame']>=12 or transitions[0]['gear_after']!=4):
            errors.append(f'Execucao {trial}: resposta a troca incorreta')
        if len({r['reset_wram_adler32'] for r in part})!=1 or len({r['branch_wram_adler32'] for r in measured})!=1:
            errors.append(f'Execucao {trial}: fingerprints inconsistentes')
        # Zero frames contaminados exigidos; nao escolher so trechos favoraveis.
        interference=False
        for kind,detect in (
            ('offroad',lambda r:r['surface_before']!=1 or r['surface_after']!=1),
            ('impact',lambda r:(r['impact_before']|r['impact_after'])&128),
            ('nitro',lambda r:r['nitro_before']!=3 or r['nitro_after']!=3),
        ):
            first=next((r for r in part if detect(r)),None)
            if first is not None:
                interference=True
                report['interferences'].append(dict(trial=trial,kind=kind,frame=first['frame'],
                    emu_frame=first['emu_frame'],speed_before=first['speed_before'],speed_after=first['speed_after']))
        if interference:
            errors.append(f'Execucao {trial}: impacto, fora da pista ou nitro; comparacao inconclusiva')
        prefixes.append([{k:v for k,v in r.items() if k not in ('trial','variant')} for r in launch+prep])
        measurements.append(measured)
        report['comparisons'].append(dict(trial=trial,variant='hold_4' if variant==0 else 'shift_5',
            frames=measure_frames,start_speed_raw=measured[0]['speed_before'],end_speed_raw=measured[-1]['speed_after'],
            speed_gain_raw=measured[-1]['speed_after']-measured[0]['speed_before'],
            mean_speed_raw=mean(r['speed_after'] for r in measured),
            fuel_consumed_raw=measured[0]['fuel_before']-measured[-1]['fuel_after']))
    if any(p!=prefixes[0] for p in prefixes):errors.append('Preparacao divergiu entre execucoes')
    if len({m[0]['branch_wram_adler32'] for m in measurements})!=1:
        errors.append('WRAM no ponto de comparacao divergiu entre execucoes')
    if len({m[0]['reset_wram_adler32'] for m in measurements})!=1:
        errors.append('WRAM inicial divergiu entre execucoes')
    for i,j in ((0,3),(1,2)):
        normalize=lambda m:[{k:v for k,v in r.items() if k!='trial'} for r in m]
        if normalize(measurements[i])!=normalize(measurements[j]):
            errors.append('Repeticoes da mesma variante divergiram')
    report['status']='paired_measurement_ok' if not errors else 'inconclusive'
    if not errors:
        hold=report['comparisons'][0];shift=report['comparisons'][1]
        report['hold_minus_shift']=dict(speed_gain_raw=hold['speed_gain_raw']-shift['speed_gain_raw'],
            mean_speed_raw=hold['mean_speed_raw']-shift['mean_speed_raw'],
            fuel_consumed_raw=hold['fuel_consumed_raw']-shift['fuel_consumed_raw'])
    return report


def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--csv',type=Path)
    args=p.parse_args()
    files=sorted((root/'runs/diagnostics').glob('ensaio_cambio_*.csv'),key=lambda x:x.stat().st_mtime_ns)
    path=args.csv or (files[-1] if files else None)
    if path is None:p.error('Rode primeiro lua/ensaio_cambio.lua na Lua Console')
    with path.open(encoding='utf-8-sig',newline='') as f:rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
    report=analyze(rows)
    report.update(source=str(path.resolve()),source_sha256=sha256(path),
                  analysis_source_sha256=sha256(Path(__file__)))
    output=path.with_name(path.stem+'_'+unique_name('analysis')+'.json');atomic_json(output,report)
    print(report['status']);print('RELATORIO:',output)
    for r in report['comparisons']:
        print(f"Execucao {r['trial']} {r['variant']}: velocidade {r['start_speed_raw']} -> {r['end_speed_raw']}; combustivel gasto {r['fuel_consumed_raw']} (valores brutos)")
    for e in report['errors']:print(e)
    if report['status']!='paired_measurement_ok':raise SystemExit(1)


if __name__=='__main__':main()
