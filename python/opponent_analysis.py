"""Sensores circulares candidatos. Nao sao importados pela politica ativa."""
from __future__ import annotations
from dataclasses import dataclass


def signed_track_gap(player_progress: int, other_progress: int, length: int) -> int:
    if length <= 0 or not 0 <= player_progress < length or not 0 <= other_progress < length:
        raise ValueError('Progresso/comprimento fora do dominio')
    return (other_progress - player_progress + length // 2) % length - length // 2


@dataclass(frozen=True)
class Racer:
    identity: int
    progress: int
    lateral: int
    lap: int


def decode_records(raw: bytes) -> list[Racer]:
    if len(raw) != 20 * 0x12:
        raise ValueError('Tabela incompleta')
    result = []
    for index in range(20):
        r = raw[index * 18:(index + 1) * 18]
        identity = r[0] & 31
        if 2 <= identity <= 19:
            result.append(Racer(identity, int.from_bytes(r[7:9], 'little'),
                                int.from_bytes(r[2:4], 'little', signed=True),
                                int.from_bytes(r[9:10], 'little', signed=True) - 1))
    if len(result) != 18 or len({r.identity for r in result}) != 18:
        raise ValueError('IDs ausentes ou repetidos')
    return result


def candidates(racers: list[Racer], progress: int, lateral: int, length: int, fraction=0.1) -> list[dict]:
    if not 0 < fraction < .5:
        raise ValueError('Raio ambiguo')
    output = []
    for racer in racers:
        gap = signed_track_gap(progress, racer.progress, length)
        if abs(gap) <= length * fraction:
            output.append({'id': racer.identity, 'gap': gap, 'lateral_delta': racer.lateral - lateral,
                           'region_candidate': 'front' if gap > 0 else 'rear' if gap < 0 else 'alongside',
                           'validated': False})
    return sorted(output, key=lambda row: (abs(row['gap']), row['id']))
