"""Confere respostas a pulsos R/L; nao promove RPM nem libera treinamento."""
import argparse
import csv
from pathlib import Path
from experiment import atomic_json, sha256, unique_name

LEGACY_PULSES = [(180,1),(300,1),(420,1),(540,1),(660,-1),(780,1),(900,-1)]
PULSES = [(60,1),(120,1),(180,1),(240,1),(300,-1),(360,1),(420,-1)]
LIMITS = dict(hud_mapping_validated=False, rpm_calibrated=False,
              performance_advantage_validated=False, training_authorized=False)


def incomplete(reason):
    return dict(status='incomplete', errors=[reason], **LIMITS)

def analyze(rows):
    errors=[]
    if not rows or [r['relative_frame'] for r in rows]!=list(range(len(rows))):
        return incomplete('Captura incompleta ou frames relativos incorretos')
    version=rows[0].get('capture_version',1)
    if version not in (1,2) or any(r.get('capture_version',1)!=version for r in rows):
        return incomplete('Versao da captura desconhecida ou inconsistente')
    offset=0
    if version==1:
        if len(rows)!=1020: return incomplete('Captura legada incompleta: exige 1020 frames')
        pulses=LEGACY_PULSES
    else:
        warmup=[r for r in rows if r.get('phase')==0]
        offset=len(warmup)
        if not 8<=offset<=1200 or len(rows)!=offset+480:
            return incomplete('Largada ou sequencia incompleta; exige movimento e 480 frames de teste')
        if any((r.get('phase'),r.get('sequence_frame')) != ((0,-1) if i<offset else (1,i-offset))
               for i,r in enumerate(rows)):
            return incomplete('Fases ou frames da sequencia incorretos')
        stable=0
        ready_at=None
        for i,r in enumerate(warmup):
            stable=stable+1 if r['speed_after']>=1500 else 0
            if stable>=8:
                ready_at=i+1
                break
        if ready_at!=offset:
            errors.append('Sequencia nao iniciou apos os primeiros oito frames de movimento estavel')
        pulses=[(offset+f,d) for f,d in PULSES]
    if any(b['emu_frame']!=a['emu_frame']+1 for a,b in zip(rows,rows[1:])):
        errors.append('Frames do emulador descontinuos')
    if any(b['gear_before']!=a['gear_after'] for a,b in zip(rows,rows[1:])):
        errors.append('Estado de marcha descontinuo')
    if any(r['accelerate']!=1 for r in rows): errors.append('Acelerador nao permaneceu ativo')
    if any(r.get('savestate_slot')!=2 for r in rows): errors.append('Captura precisa identificar o slot 2 manual')
    if any(r['gear_before'] not in range(5) or r['gear_after'] not in range(5) for r in rows):
        errors.append('Marcha fora de 0..4')
    if rows[0]['gear_before']!=0 or any(r['gear_after']!=0 for r in rows[:pulses[0][0]]):
        errors.append('Marcha mudou sem comando inicial: conferir MANUAL')
    events=[]
    allowed=set()
    for frame,direction in pulses:
        window=rows[frame:frame+12]
        allowed.update(range(frame,frame+12))
        delta=window[-1]['gear_after']-window[0]['gear_before']
        transitions=[r for r in window if r['gear_after']!=r['gear_before']]
        passed=delta==direction and len(transitions)==1
        if not passed: errors.append(f'Pulso no frame {frame}: resposta inesperada')
        events.append(dict(frame=frame,sequence_frame=frame-offset,direction=direction,delta=delta,transitions=len(transitions),passed=passed))
    if any(r['gear_after']!=r['gear_before'] and r['relative_frame'] not in allowed for r in rows):
        errors.append('Troca fora das janelas de comando')
    for r in rows:
        up=any(f<=r['relative_frame']<f+4 and d==1 for f,d in pulses)
        down=any(f<=r['relative_frame']<f+4 and d==-1 for f,d in pulses)
        if (r['shift_up'],r['shift_down'])!=(int(up),int(down)):
            errors.append('Sequencia de botoes diverge do protocolo do teste');break
    gears=sorted({r['gear_after'] for r in rows})
    if gears!=list(range(5)): errors.append('Nao foram observados todos os estados brutos 0..4')
    return dict(status='controls_observed_ok' if not errors else 'failed',errors=errors,pulses=events,
                capture_version=version,warmup_frames=offset,gears_raw_observed=gears,
                savestate_slot=2,car_table_offsets_raw=sorted({r.get('car_table_offset_raw') for r in rows if r.get('car_table_offset_raw') is not None}),
                engine_gauge_raw_range=[min(r['engine_gauge_raw'] for r in rows),max(r['engine_gauge_raw'] for r in rows)],
                **LIMITS,
                note='Confere estados brutos por comando; nao confirma numeros no painel GEAR, nao compara manual/automatico, nao identifica escala RPM ou ponto otimo de troca.')

def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--csv',type=Path)
    args=p.parse_args()
    candidates=sorted((root/'runs/diagnostics').glob('cambio_manual_*.csv'),key=lambda f:f.stat().st_mtime_ns)
    path=args.csv or (candidates[-1] if candidates else None)
    if path is None: p.error('Nenhum CSV; rode primeiro lua/diagnostico_cambio_manual.lua')
    with path.open(encoding='utf-8-sig',newline='') as f: rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
    report=analyze(rows);report.update(source=str(path.resolve()),source_sha256=sha256(path))
    index=path.with_name(path.stem+'_hud.tsv')
    report['hud_evidence']=dict(index=str(index),status='missing',images=[])
    if index.exists():
        with index.open(encoding='utf-8-sig',newline='') as f: snapshots=list(csv.DictReader(f,delimiter='\t'))
        images=[]
        for shot in snapshots:
            name=shot['filename']
            if Path(name).name!=name: raise ValueError('Nome de imagem invalido no indice HUD')
            img=path.parent/name
            images.append(dict(**shot,exists=img.is_file(),sha256=sha256(img) if img.is_file() else None))
        complete=len(images)==8 and all(img['exists'] for img in images)
        report['hud_evidence'].update(status='awaiting_visual_review' if complete else 'incomplete',
                                      index_sha256=sha256(index),images=images)
    output=path.with_name(path.stem+'_'+unique_name('analysis')+'.json');atomic_json(output,report)
    print(report['status']);print('RELATORIO:',output)
    print('PAINEL GEAR: correspondencia visual ainda nao validada; valor bruto nao confirma numero exibido.')
    for error in report['errors']:print(error)
    if report['status']!='controls_observed_ok':raise SystemExit(1)

if __name__=='__main__':main()
