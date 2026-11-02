"""Reprocessa WRAM gravada com o leitor Lua atual; nao executa BizHawk."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from pathlib import Path

from lupa import LuaRuntime

from experiment import atomic_json, sha256, unique_name
from live_detector import evaluate_samples
from native_navigation import augment_samples, evaluate, SETTINGS


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=root / 'runs/diagnostics/contexto_20260912_084321_5525_snapshots.csv')
    args = parser.parse_args()
    index = args.index.resolve()
    binary = index.with_name(index.name.replace('_snapshots.csv', '.wram.bin'))
    module = root / 'lua/native_navigation.lua'
    lua = LuaRuntime(unpack_returned_tuples=True)
    reader = lua.execute(module.read_text(encoding='utf-8'))
    report = {'execution': 'offline_recorded_wram', 'new_bizhawk_validation': False,
              'prediction_validation': False, 'settings': SETTINGS,
              'sources': {str(p): sha256(p) for p in [index, binary, module, Path(__file__),
                          root/'python/native_navigation.py', root/'python/live_detector.py']},
              'frames': []}
    with index.open(encoding='utf-8-sig', newline='') as stream, binary.open('rb') as data:
        for record in csv.DictReader(stream):
            frame, offset, size = (int(record[key]) for key in ('frame', 'byte_offset', 'size'))
            if size != 131072:
                raise ValueError('Snapshot nao possui WRAM completa')
            data.seek(offset)
            wram = data.read(size)
            if len(wram) != size:
                raise ValueError('Snapshot truncado')
            def u8(address): return wram[int(address)]
            def u16(address): return int.from_bytes(wram[int(address):int(address)+2], 'little')
            def s16(address): return int.from_bytes(wram[int(address):int(address)+2], 'little', signed=True)
            racers = {}
            for slot in range(20):
                base = 0x0212 + 18 * slot
                identity = u8(base) % 32
                if 2 <= identity <= 19:
                    if identity in racers:
                        raise ValueError('ID repetido na captura')
                    racers[identity] = (u16(base+7), s16(base+2))
            if len(racers) != 18:
                raise ValueError('Captura nao possui os 18 registros tradicionais')
            samples = [(frame, u16(0x1ED7), s16(0x1E8A), u16(0x0200), racers)]
            packet = reader.capture(frame, u8, u16, s16)
            augmented, parsed = augment_samples(packet, samples)
            _, rows = evaluate_samples(augmented)
            features, navigation = evaluate(parsed, samples, rows)
            report['frames'].append({'frame': frame, 'packet': packet, 'decoded': parsed[0],
                                     'features': features, 'navigation': navigation,
                                     'p2_raw_id': u8(0x0212+u16(0x0206)) % 32})
    frames = report['frames']
    report['summary'] = {
        'snapshots': len(frames),
        'identity_matches': sum(f['decoded']['identity_valid'] for f in frames),
        'corridor_valid': sum(f['decoded']['corridor_valid'] for f in frames),
        'p2_raw_ids': dict(Counter(f['p2_raw_id'] for f in frames)),
        'navigation_valid': sum(f['navigation']['navigation_valid'] for f in frames),
        'target_candidates': sum(f['navigation']['target_valid'] for f in frames),
        'p2_nearby': sum(f['navigation']['p2_present'] for f in frames),
        'limitation': 'Amostras espacadas: sem validacao de velocidade, previsao ou desvio real.',
    }
    destination = root / 'runs/analysis/native_navigation' / (unique_name('snapshot_audit')+'.json')
    atomic_json(destination, report)
    print(report['summary'])
    print('RELATORIO OFFLINE:', destination)


if __name__ == '__main__':
    main()
