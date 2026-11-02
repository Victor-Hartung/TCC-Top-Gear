"""Prioriza candidatos de RAM a partir de snapshots; nunca valida semantica sozinho."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import numpy as np
from experiment import atomic_json, unique_name, sha256


def analyze(binary: Path, index: Path) -> dict:
    with index.open(newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    data = binary.read_bytes()
    if not rows or len(data) != len(rows)*131072:
        raise ValueError('Quantidade de snapshots/tamanho binario inconsistente')
    for i, row in enumerate(rows):
        if int(row['size']) != 131072 or int(row['byte_offset']) != i*131072:
            raise ValueError('Offset/tamanho de snapshot invalido')
    ram = np.frombuffer(data, dtype=np.uint8).reshape(len(rows), 131072)
    periodic = [(int(row['frame']), i) for i, row in enumerate(rows) if row['reason'] == 'periodic']
    # Apenas series consecutivas e no mesmo episodio; voltar save invalida ranking temporal.
    if len(periodic)<5 or any(b[0]<=a[0] for a,b in zip(periodic,periodic[1:])):
        raise ValueError('Poucas amostras ou frames repetidos; envie uma corrida por coleta')
    seq = ram[[i for _,i in periodic]].astype(np.int32)
    # Tempo pode usar u8, u16, BCD ou varios campos. Resultado apenas prioriza inspeção.
    delta = np.diff(seq, axis=0)
    changed = np.count_nonzero(delta, axis=0)
    decreases = np.count_nonzero(delta<0, axis=0)
    increases = np.count_nonzero(delta>0, axis=0)
    candidates = []
    for address in np.flatnonzero(changed >= 3):
        score = int(decreases[address]) / max(1, int(changed[address]))
        if score >= .8:
            candidates.append({'domain':'WRAM', 'address':f'0x{address:05X}', 'size':1,
                'hypothesis':'decreasing_byte_not_proven_timer', 'changes':int(changed[address]),
                'decreases':int(decreases[address]), 'increases':int(increases[address]),
                'score':score, 'first':int(seq[0,address]), 'last':int(seq[-1,address]), 'validated':False})
    candidates.sort(key=lambda r:(-r['score'],-r['changes'],r['address']))
    return {'binary_sha256':sha256(binary), 'snapshots':len(rows), 'frames':[f for f,_ in periodic],
            'candidates':candidates[:100], 'manual_events':[r for r in rows if r['reason']!='periodic'],
            'note':'Combustivel, animacao e progresso podem correlacionar. Nao atualizar game_profile automaticamente.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--index',type=Path,required=True)
    args=parser.parse_args()
    result=analyze(args.binary,args.index)
    path=args.index.parent/(unique_name('candidatos')+'.json')
    atomic_json(path,result)
    print(f'CANDIDATOS (NAO VALIDADOS): {path.resolve()}')


if __name__=='__main__':
    main()
