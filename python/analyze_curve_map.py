from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = {
    "track_length",
    "entry_count",
    "index",
    "progress_start",
    "progress_end",
    "offset",
    "curve_word_u16",
    "curve_word_s16",
    "curve_low_u8",
    "curve_low_s8",
    "curve_high_u8",
    "curve_high_s8",
    "grade_word_u16",
    "grade_word_s16",
    "road_word_u16",
    "road_low_u8",
    "road_high_u8",
}


def load_map(path: Path) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"colunas ausentes: {', '.join(sorted(missing))}")
        for line_number, raw in enumerate(reader, 2):
            try:
                rows.append({key: int(value) for key, value in raw.items()})
            except (TypeError, ValueError) as exc:
                raise ValueError(f"linha {line_number} inválida: {exc}") from exc
    if not rows:
        raise ValueError("mapa vazio")

    track_lengths = {row["track_length"] for row in rows}
    entry_counts = {row["entry_count"] for row in rows}
    if len(track_lengths) != 1 or len(entry_counts) != 1:
        raise ValueError("metadados de pista mudaram durante a exportação")
    declared_count = next(iter(entry_counts))
    if len(rows) != declared_count:
        raise ValueError(f"esperadas {declared_count} entradas; recebidas {len(rows)}")
    track_length = next(iter(track_lengths))
    expected_count = (track_length + 31) // 32
    # A v2.0.25 exportou duas vezes mais linhas por interpretar
    # (progress >> 4) & 0xFFFE como multiplicação após a divisão. As primeiras
    # expected_count linhas já contêm toda a tabela válida e podem ser recuperadas.
    if declared_count == expected_count * 2:
        rows = rows[:expected_count]
        for row in rows:
            row["entry_count"] = expected_count
            row["progress_start"] = row["index"] * 32
            row["progress_end"] = min(track_length - 1, row["index"] * 32 + 31)
    elif declared_count != expected_count:
        raise ValueError(
            f"quantidade incompatível com a indexação /32: {declared_count}; "
            f"esperado {expected_count}"
        )
    if [row["index"] for row in rows] != list(range(expected_count)):
        raise ValueError("índices ausentes, duplicados ou fora de ordem")

    for row in rows:
        low = row["curve_word_u16"] & 0xFF
        high = (row["curve_word_u16"] >> 8) & 0xFF
        if low != row["curve_low_u8"] or high != row["curve_high_u8"]:
            raise ValueError(f"decomposição inconsistente no índice {row['index']}")
    return rows


def nonzero_runs(rows: list[dict[str, int]]) -> list[tuple[int, int, list[int]]]:
    runs: list[tuple[int, int, list[int]]] = []
    start: int | None = None
    values: list[int] = []
    for row in rows:
        value = row["curve_low_s8"]
        if value != 0:
            if start is None:
                start = row["index"]
                values = []
            values.append(value)
        elif start is not None:
            runs.append((start, row["index"] - 1, values))
            start = None
            values = []
    if start is not None:
        runs.append((start, rows[-1]["index"], values))
    return runs


def load_labels(path: Path) -> list[tuple[str, int]]:
    if not path.is_file():
        return []
    labels: list[tuple[str, int]] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fieldnames = set(reader.fieldnames or ())
        if "label" not in fieldnames or not ({"progress", "track_index"} & fieldnames):
            return []
        for row in reader:
            index = int(row["progress"]) // 32 if "progress" in fieldnames else int(row["track_index"])
            labels.append((row["label"], index))
    return labels


def analyze(path: Path, labels_path: Path | None = None) -> str:
    rows = load_map(path)
    values = [row["curve_low_s8"] for row in rows]
    counts = Counter(values)
    runs = nonzero_runs(rows)
    track_length = rows[0]["track_length"]
    labels = load_labels(labels_path) if labels_path else []

    lines = [
        "DIAGNÓSTICO DO MAPA COMPLETO DE CURVAS",
        "",
        f"Arquivo: {path.name}",
        f"Comprimento da pista: {track_length}",
        f"Entradas válidas: {len(rows)} (uma a cada 32 unidades)",
        f"Coeficiente s8 baixo: mínimo={min(values)}, "
        f"mediana={statistics.median(values):g}, máximo={max(values)}",
        f"Entradas: zero={counts[0]}, positivas={sum(v > 0 for v in values)}, "
        f"negativas={sum(v < 0 for v in values)}, valores distintos={len(counts)}",
        f"Sequências brutas não zero: {len(runs)}",
        "",
        "Maiores sequências brutas não zero:",
    ]
    ordered_runs = sorted(runs, key=lambda item: (-(item[1] - item[0] + 1), item[0]))
    for start, end, run_values in ordered_runs[:20]:
        lines.append(
            f"  índices {start}..{end}; progresso {start * 32}.."
            f"{min(track_length - 1, end * 32 + 31)}; entradas={len(run_values)}; "
            f"soma={sum(run_values)}; faixa={min(run_values)}..{max(run_values)}"
        )

    if labels:
        lines.extend(("", "Rótulos manuais anteriores sobre o mapa exportado:"))
        matches = 0
        for label, index in labels:
            if 0 <= index < len(rows):
                row = rows[index]
                curve = row["curve_low_s8"]
                predicted = "straight" if curve == 0 else "left" if curve > 0 else "right"
                matches += predicted == label
                lines.append(
                    f"  {label}: índice={index}, progresso={row['progress_start']}, "
                    f"curve_low_s8={curve}, classe={predicted}"
                )
        lines.append(
            f"  Separação direta dos rótulos: {matches}/{len(labels)} "
            f"({100.0 * matches / len(labels):.1f}%)"
        )

    lines.extend(
        (
            "",
            "Interpretação:",
            "  Esta análise contém toda a tabela ativa de Las Vegas, sem",
            "  depender da velocidade, do foco da janela ou de pontos pulados.",
            "  O byte baixo é separado do word porque é o byte entregue ao",
            "  multiplicador na rotina localizada na ROM.",
            "  O sinal e a intensidade podem ser promovidos à observação de",
            "  Las Vegas quando os rótulos manuais forem separados sem erro.",
            "  A generalização para pistas com curvas à direita exige nova coleta.",
        )
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "diagnostico_mapa_curvas.csv"
    if not path.is_file():
        raise SystemExit(f"Arquivo não encontrado: {path}")
    labels_path = ROOT / "diagnostico_curva.csv"
    try:
        report = analyze(path, labels_path if labels_path.is_file() else None)
    except ValueError as exc:
        raise SystemExit(f"Mapa inválido: {exc}") from exc
    output = ROOT / "diagnostico_mapa_curvas_resultado.txt"
    output.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Resultado salvo em: {output}")


if __name__ == "__main__":
    main()
