from __future__ import annotations

import csv
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABELS = ("straight", "left", "right")
LEGACY_CURVE_COLUMNS = (
    "curve_0",
    "curve_256",
    "curve_512",
    "curve_1024",
    "curve_2048",
)
RUNTIME_CURVE_COLUMNS = tuple(
    f"runtime_curve_s8_{ahead}"
    for ahead in (0, 128, 256, 512, 768, 1024, 1536, 2048)
)
CURVE_COLUMNS = LEGACY_CURVE_COLUMNS


@dataclass(frozen=True)
class CurveFit:
    column: str
    threshold: int
    positive_label: str
    correct: int
    total: int

    @property
    def score(self) -> float:
        return self.correct / self.total


def classify(value: int, threshold: int, positive_label: str) -> str:
    if abs(value) <= threshold:
        return "straight"
    if value > 0:
        return positive_label
    return "right" if positive_label == "left" else "left"


def best_fit(column: str, rows: list[dict[str, int | str]]) -> CurveFit:
    magnitudes = sorted({abs(int(row[column])) for row in rows})
    thresholds = {0}
    thresholds.update(magnitudes)
    thresholds.update(
        (before + after) // 2
        for before, after in zip(magnitudes, magnitudes[1:])
    )
    candidates: list[CurveFit] = []
    for threshold in sorted(thresholds):
        for positive_label in ("left", "right"):
            correct = sum(
                classify(int(row[column]), threshold, positive_label) == row["label"]
                for row in rows
            )
            candidates.append(
                CurveFit(
                    column=column,
                    threshold=threshold,
                    positive_label=positive_label,
                    correct=correct,
                    total=len(rows),
                )
            )
    return max(
        candidates,
        key=lambda fit: (fit.score, -fit.threshold, fit.positive_label == "left"),
    )


def load_capture(path: Path) -> list[dict[str, int | str]]:
    required = {
        "capture",
        "label",
        "emu_frame",
        "speed",
        "lateral",
        "surface_state",
        "progress",
        "lap",
        "total_laps",
        "track_index",
    }
    rows: list[dict[str, int | str]] = []
    captures: set[int] = set()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"colunas ausentes: {', '.join(sorted(missing))}")
        fieldnames = set(reader.fieldnames or ())
        if set(RUNTIME_CURVE_COLUMNS).issubset(fieldnames):
            curve_columns = RUNTIME_CURVE_COLUMNS
        elif set(LEGACY_CURVE_COLUMNS).issubset(fieldnames):
            curve_columns = LEGACY_CURVE_COLUMNS
        else:
            raise ValueError("colunas de curva reconhecidas não foram encontradas")
        numeric_columns = required | set(curve_columns)
        for line_number, raw in enumerate(reader, 2):
            try:
                label = raw["label"]
                if label not in LABELS:
                    raise ValueError(f"rótulo desconhecido {label!r}")
                row: dict[str, int | str] = {"label": label}
                for key in numeric_columns.difference({"label"}):
                    row[key] = int(raw[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"linha {line_number} inválida: {exc}") from exc
            capture = int(row["capture"])
            if capture in captures:
                raise ValueError(f"captura duplicada: {capture}")
            captures.add(capture)
            if row["surface_state"] != 1:
                raise ValueError(f"captura {capture} foi feita fora do asfalto")
            if not 0 <= int(row["lap"]) < int(row["total_laps"]):
                raise ValueError(f"captura {capture} fora de uma volta ativa")
            rows.append(row)
    counts = {label: sum(row["label"] == label for row in rows) for label in LABELS}
    if counts["straight"] < 6 or max(counts["left"], counts["right"]) < 6:
        raise ValueError(
            f"amostras insuficientes: {counts}; são necessárias 6 retas e "
            "6 curvas de pelo menos uma direção"
        )
    return rows


def analyze(path: Path) -> str:
    rows = load_capture(path)
    curve_columns = (
        RUNTIME_CURVE_COLUMNS
        if RUNTIME_CURVE_COLUMNS[0] in rows[0]
        else LEGACY_CURVE_COLUMNS
    )
    counts = {label: sum(row["label"] == label for row in rows) for label in LABELS}
    fits = [best_fit(column, rows) for column in curve_columns]
    fits.sort(key=lambda fit: (-fit.score, curve_columns.index(fit.column)))

    lines = [
        "DIAGNÓSTICO DE CURVA — RESULTADO PRELIMINAR",
        "",
        f"Arquivo: {path.name}",
        f"Capturas: reta={counts['straight']}, esquerda={counts['left']}, "
        f"direita={counts['right']}",
        "",
        "Valores por rótulo e distância:",
    ]
    for column in curve_columns:
        lines.append(f"  {column}:")
        for label in LABELS:
            values = [int(row[column]) for row in rows if row["label"] == label]
            if not values:
                lines.append(f"    {label}: sem amostras nesta pista")
                continue
            lines.append(
                f"    {label}: mínimo={min(values)}, "
                f"mediana={statistics.median(values):g}, máximo={max(values)}, "
                f"valores={','.join(map(str, sorted(values)))}"
            )

    lines.extend(("", "Melhor separação automática por distância:"))
    for fit in fits:
        negative_label = "right" if fit.positive_label == "left" else "left"
        lines.append(
            f"  {fit.column}: {fit.correct}/{fit.total} ({fit.score:.1%}); "
            f"reta se |valor| <= {fit.threshold}; positivo={fit.positive_label}; "
            f"negativo={negative_label}"
        )

    best = fits[0]
    missing_directions = [label for label in ("left", "right") if counts[label] < 6]
    lines.extend(
        (
            "",
            "Interpretação obrigatória:",
            "  O resultado mede correlação com os rótulos visuais desta pista.",
            "  A ROM comprova que 0x4C00 é indexado pela posição suavizada e participa da",
            "  atualização lateral, mas esta coleta ainda deve confirmar sinal e",
            "  distância útil de antecipação antes da integração na observação.",
            f"  Melhor candidato desta captura: {best.column}, "
            f"score={best.score:.1%}.",
            "  Cobertura direcional incompleta: " + ", ".join(missing_directions)
            if missing_directions
            else "  Cobertura direcional completa nesta captura.",
            "  Não altere curve_telemetry_validated manualmente.",
        )
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "diagnostico_curva.csv"
    if not path.is_file():
        raise SystemExit(f"Arquivo não encontrado: {path}")
    try:
        report = analyze(path)
    except ValueError as exc:
        raise SystemExit(f"Captura inválida: {exc}") from exc
    output = ROOT / "diagnostico_curva_resultado.txt"
    output.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Resultado salvo em: {output}")


if __name__ == "__main__":
    main()
