"""Cria copia ZIP64 verificavel; nao modifica modelos, logs ou emulador."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import zipfile


EXCLUDED_DIRS={'.venv','.git','__pycache__','.pytest_cache','.mypy_cache'}


def files(root):
    for directory, folders, names in os.walk(root, followlinks=False):
        folders[:]=sorted(n for n in folders if n not in EXCLUDED_DIRS and not (Path(directory)/n).is_symlink())
        for name in sorted(names):
            path=Path(directory)/name
            if path.suffix in ('.pyc','.pyo'):continue
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f'Arquivo fora da raiz de origem: {path}')
            yield path


def clean_emulator_config(value):
    # Limpa historicos de caminhos somente na copia, conservando core/sync settings.
    if isinstance(value,dict):return {k:clean_emulator_config(v) for k,v in value.items()}
    if isinstance(value,list):return [clean_emulator_config(v) for v in value if not (isinstance(v,str) and ':\\Users\\' in v)]
    if isinstance(value,str) and ':\\Users\\' in value:return ''
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    emulator=args.emulator_dir.resolve();output=args.output.resolve()
    if not (emulator/'EmuHawk.exe').is_file():raise FileNotFoundError('EmuHawk.exe ausente')
    if output.is_relative_to(root):raise ValueError('ZIP de destino deve ficar fora da raiz do projeto')
    partial=output.with_suffix('.zip.partial')
    report_path=output.with_suffix('.inventory.json')
    if output.exists() or partial.exists() or report_path.exists():raise FileExistsError('Destino ja existe; escolha nome novo')
    base='TCC-TopGear-RL_v3.0'
    sources=[(p,f'{base}/{p.relative_to(root).as_posix()}',False) for p in files(root)]
    # Somente estados/SaveRAM de Top Gear: outros jogos nao fazem parte do TCC.
    for p in files(emulator):
        rel=p.relative_to(emulator)
        if rel.parts[0] in ('Gameboy','NES'):continue
        if len(rel.parts)>1 and rel.parts[0]=='SNES' and rel.parts[1] in ('State','SaveRAM') and not p.name.startswith('Top Gear'):continue
        sources.append((p,f'{base}/emulator/BizHawk-2.11.1-win-x64/{rel.as_posix()}',rel.as_posix()=='config.ini'))
    total=sum(p.stat().st_size for p,_,_ in sources)
    print(f'Inventario: {len(sources)} arquivos, {total/1024**3:.3f} GiB de origem.',flush=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    entries=[];done=0;last=time.monotonic()
    with zipfile.ZipFile(partial,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
        for p,name,clean_config in sources:
            stat=p.stat();digest=hashlib.sha256();size=0
            info=zipfile.ZipInfo.from_file(p,arcname=name);info.compress_type=zipfile.ZIP_DEFLATED
            if clean_config:
                content=json.dumps(clean_emulator_config(json.loads(p.read_text(encoding='utf-8-sig'))),ensure_ascii=False,indent=2).encode('utf-8')
                archive.writestr(info,content,compress_type=zipfile.ZIP_DEFLATED,compresslevel=1)
                digest.update(content);size=len(content)
            else:
                info._compresslevel=1
                with p.open('rb') as source,archive.open(info,'w',force_zip64=True) as dest:
                    while block:=source.read(1024*1024):
                        dest.write(block);digest.update(block);size+=len(block)
                        if time.monotonic()-last>=15:
                            print(f'Compactando: {(done+size)/max(total,1):.1%} ({(done+size)/1024**3:.2f} GiB lidos)',flush=True);last=time.monotonic()
            after=p.stat()
            if (stat.st_size,stat.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise RuntimeError(f'Origem mudou durante compactacao; copia parcial preservada: {p}')
            entries.append({'path':name,'bytes':size,'sha256':digest.hexdigest(),
                            **({'copy_change':'Removed machine-specific recent paths; core settings preserved'} if clean_config else {})})
            done+=stat.st_size
        report={'created_utc':datetime.now(timezone.utc).isoformat(),'project_version':'3.0',
                'source_project':str(root),'source_emulator':str(emulator),
                'excluded':sorted(EXCLUDED_DIRS),
                'notes':['.venv must be recreated on destination Windows.',
                         'All project models/runs/archive included; only generated caches excluded.',
                         'Historical preflight receipts do not validate a different machine/current code.',
                         'Only copying/packaging; no live emulator or training executed.'],
                'source_bytes':total,'file_count':len(entries),'files':entries}
        archive.writestr(f'{base}/PACKAGE_INVENTORY.json',json.dumps(report,ensure_ascii=False,indent=2))
    print('Conferindo CRC de todos os arquivos do ZIP...',flush=True)
    with zipfile.ZipFile(partial) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise RuntimeError('Nomes duplicados no ZIP')
        if bad:=archive.testzip():raise RuntimeError(f'CRC invalido: {bad}')
    partial.rename(output)
    with output.open('rb') as stream:zip_hash=hashlib.file_digest(stream,'sha256').hexdigest()
    report.update(zip_path=str(output),zip_bytes=output.stat().st_size,zip_sha256=zip_hash,crc_all_files='passed')
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    output.with_suffix('.zip.sha256').write_text(zip_hash+'  '+output.name+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('zip_path','zip_bytes','zip_sha256','file_count','crc_all_files')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
