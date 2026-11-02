from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABELS = ("on_track", "off_left", "off_right")


@dataclass(frozen=True)
class BitCandidate:
    score: float
    address: int
    bit: int
    orientation: str
    on_rate: float
    left_rate: float
    right_rate: float


def score_bit(address: int, bit: int, values: dict[str, list[int]]) -> BitCandidate:
    rates = {
        label: sum((value >> bit) & 1 for value in values[label]) / len(values[label])
        for label in LABELS
    }
    zero_on = ((1.0 - rates["on_track"]) + rates["off_left"] + rates["off_right"]) / 3.0
    one_on = (rates["on_track"] + (1.0 - rates["off_left"]) + (1.0 - rates["off_right"])) / 3.0
    if zero_on >= one_on:
        score, orientation = zero_on, "0=pista, 1=fora"
    else:
        score, orientation = one_on, "1=pista, 0=fora"
    return BitCandidate(
        score=score,
        address=address,
        bit=bit,
        orientation=orientation,
        on_rate=rates["on_track"],
        left_rate=rates["off_left"],
        right_rate=rates["off_right"],
    )


def load_capture(path: Path) -> tuple[dict[int, dict[str, list[int]]], dict[int, dict[str, int | str]]]:
    values: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    contexts: dict[int, dict[str, int | str]] = {}
    seen: set[tuple[int, int]] = set()
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {
            "capture", "label", "emu_frame", "address_hex", "value_u8", "speed",
            "lateral", "progress", "lap", "rank", "collision_flags", "total_laps",
        }
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"colunas ausentes: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, 2):
            try:
                capture = int(row["capture"])
                label = row["label"]
                if label not in LABELS:
                    raise ValueError(f"rotulo desconhecido {label!r}")
                address = int(row["address_hex"], 16)
                value = int(row["value_u8"])
                context: dict[str, int | str] = {
                    "label": label,
                    **{
                        key: int(row[key])
                        for key in (
                            "emu_frame", "speed", "lateral", "progress", "lap", "rank",
                            "collision_flags", "total_laps",
                        )
                    },
                }
            except (TypeError, ValueError) as exc:
                raise ValueError(f"linha {line_number} invalida: {exc}") from exc
            if not 0 <= address <= 0x1FFF or not 0 <= value <= 0xFF:
                raise ValueError(f"linha {line_number}: endereco/valor fora da faixa")
            key = (capture, address)
            if key in seen:
                raise ValueError(f"linha {line_number}: byte duplicado na captura {capture}")
            seen.add(key)
            previous = contexts.setdefault(capture, context)
            if previous != context:
                raise ValueError(f"linha {line_number}: contexto mudou dentro da captura {capture}")
            values[address][label].append(value)
    return values, contexts


def analyze(path: Path) -> str:
    values, contexts = load_capture(path)
    counts = {label: sum(ctx["label"] == label for ctx in contexts.values()) for label in LABELS}
    if any(counts[label] < 3 for label in LABELS):
        raise ValueError(f"amostras insuficientes: {counts}; sao necessarias pelo menos 3 de cada")
    expected_addresses = set(range(0x2000))
    if set(values) != expected_addresses:
        missing = len(expected_addresses.difference(values))
        raise ValueError(f"captura incompleta: faltam {missing} enderecos")
    for address in expected_addresses:
        for label in LABELS:
            if len(values[address][label]) != counts[label]:
                raise ValueError(f"quantidade inconsistente em 0x{address:04X}/{label}")

    candidates = [
        score_bit(address, bit, values[address])
        for address in range(0x2000)
        for bit in range(8)
    ]
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.address, candidate.bit))

    lines = [
        "DIAGNOSTICO OFFTRACK — RESULTADO PRELIMINAR",
        "",
        f"Arquivo: {path.name}",
        f"Capturas: pista={counts['on_track']}, fora_esquerda={counts['off_left']}, "
        f"fora_direita={counts['off_right']}",
        "",
        "Coordenada lateral por rotulo:",
    ]
    for label in LABELS:
        lateral = [int(ctx["lateral"]) for ctx in contexts.values() if ctx["label"] == label]
        lines.append(
            f"  {label}: minimo={min(lateral)}, mediana={statistics.median(lateral):g}, "
            f"maximo={max(lateral)}, valores={','.join(map(str, sorted(lateral)))}"
        )

    lines.extend(("", "Melhores bits correlacionados (ainda nao sao enderecos validados):"))
    strong = [candidate for candidate in candidates if candidate.score >= 0.90][:30]
    if not strong:
        lines.append("  Nenhum bit atingiu 90% de separacao entre pista e os dois lados externos.")
        strong = candidates[:10]
        lines.append("  Dez maiores pontuacoes para inspecao:")
    for candidate in strong:
        lines.append(
            f"  0x{candidate.address:04X} bit {candidate.bit}: "
            f"score={candidate.score:.3f}; {candidate.orientation}; "
            f"taxa1 pista={candidate.on_rate:.2f}, esq={candidate.left_rate:.2f}, "
            f"dir={candidate.right_rate:.2f}"
        )
    lines.extend(
        (
            "",
            "Interpretacao obrigatoria:",
            "  Correlacao nesta captura nao prova semantica. Um candidato so pode entrar no",
            "  ambiente depois de repeticao causal em outros trechos e verificacao visual das",
            "  transicoes exatas de entrada/saida do asfalto.",
            "  As amostras totalmente fora separam classes, mas nao medem ainda a borda exata.",
        )
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "diagnostico_offtrack.csv"
    if not path.is_file():
        raise SystemExit(f"Arquivo nao encontrado: {path}")
    try:
        report = analyze(path)
    except ValueError as exc:
        raise SystemExit(f"Captura invalida: {exc}") from exc
    output = ROOT / "diagnostico_offtrack_resultado.txt"
    output.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Resultado salvo em: {output}")


if __name__ == "__main__":
    main()
