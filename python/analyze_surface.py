from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_rows(path: Path) -> list[dict[str, int]]:
    required = {
        "sample", "emu_frame", "speed", "lateral", "progress", "lap", "rank",
        "collision_flags", "input_left", "input_right", "input_accelerate",
        "surface_0727", "surface_0A67", "mirror_equal",
        *(f"a{index}" for index in range(7)),
        *(f"b{index}" for index in range(7)),
    }
    rows: list[dict[str, int]] = []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"colunas ausentes: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, 2):
            try:
                parsed = {key: int(row[key]) for key in required}
            except (TypeError, ValueError) as exc:
                raise ValueError(f"linha {line_number} invalida: {exc}") from exc
            rows.append(parsed)
    if not rows:
        raise ValueError("arquivo vazio")
    return rows


def transition_groups(rows: list[dict[str, int]]) -> dict[str, list[dict[str, int]]]:
    groups: dict[str, list[dict[str, int]]] = {
        "road_to_left": [], "left_to_road": [],
        "road_to_right": [], "right_to_road": [], "other": [],
    }
    mapping = {
        (1, 0): "road_to_left", (0, 1): "left_to_road",
        (1, 2): "road_to_right", (2, 1): "right_to_road",
    }
    for previous, current in zip(rows, rows[1:]):
        before = previous["surface_0727"]
        after = current["surface_0727"]
        if before != after:
            groups[mapping.get((before, after), "other")].append(current)
    return groups


def analyze(path: Path) -> str:
    rows = load_rows(path)
    frames = [row["emu_frame"] for row in rows]
    gaps = sum(current != previous + 1 for previous, current in zip(frames, frames[1:]))
    mirror_mismatches = sum(
        row["surface_0727"] != row["surface_0A67"] or not row["mirror_equal"]
        for row in rows
    )
    counts = Counter(row["surface_0727"] for row in rows)
    transitions = transition_groups(rows)
    lines = [
        "DIAGNOSTICO DE SUPERFICIE — RESULTADO",
        "",
        f"Arquivo: {path.name}",
        f"Frames: {len(rows)} ({frames[0]}..{frames[-1]}), lacunas={gaps}",
        f"Divergencias entre 0x0727 e 0x0A67/buffers: {mirror_mismatches}",
        "Valores do candidato: " + ", ".join(
            f"{value}={count}" for value, count in sorted(counts.items())
        ),
        "",
        "Transicoes relevantes:",
    ]
    for name in ("road_to_left", "left_to_road", "road_to_right", "right_to_road"):
        events = transitions[name]
        lines.append(f"  {name}: {len(events)}")
        if events:
            lateral = [event["lateral"] for event in events]
            lines.append(
                f"    lateral minimo={min(lateral)}, mediana={statistics.median(lateral):g}, "
                f"maximo={max(lateral)}"
            )
            lines.append(
                "    frames=" + ",".join(str(event["emu_frame"]) for event in events[:20])
            )
    lines.append(f"  outras: {len(transitions['other'])}")

    unknown = sum(value not in (0, 1, 2) for value in counts.elements())
    enough = all(
        len(transitions[name]) >= 2
        for name in ("road_to_left", "left_to_road", "road_to_right", "right_to_road")
    )
    lines.extend(("", "Validacao automatica:"))
    lines.append(f"  frames_consecutivos={'SIM' if gaps == 0 else 'NAO'}")
    lines.append(f"  espelhos_identicos={'SIM' if mirror_mismatches == 0 else 'NAO'}")
    lines.append(f"  somente_valores_0_1_2={'SIM' if unknown == 0 else 'NAO'}")
    lines.append(f"  transicoes_suficientes_nos_dois_lados={'SIM' if enough else 'NAO'}")
    lines.extend(
        (
            "",
            "Ainda obrigatorio informar visualmente:",
            "  O texto PISTA/FORA ESQUERDA/FORA DIREITA mudou exatamente quando o carro",
            "  cruzou cada borda? A aprovacao final depende dessa resposta e do CSV.",
        )
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "diagnostico_superficie.csv"
    if not path.is_file():
        raise SystemExit(f"Arquivo nao encontrado: {path}")
    try:
        report = analyze(path)
    except ValueError as exc:
        raise SystemExit(f"Captura invalida: {exc}") from exc
    output = ROOT / "diagnostico_superficie_resultado.txt"
    output.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Resultado salvo em: {output}")


if __name__ == "__main__":
    main()
