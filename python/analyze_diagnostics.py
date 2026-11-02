from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def execution_report() -> None:
    path = ROOT / "diagnostico_execucao.txt"
    if not path.is_file():
        print(f"PENDENTE: {path.name}")
        return
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    print(
        "EXECUÇÃO:",
        f"rom_ok={values.get('rom_ok')}",
        f"domain={values.get('domain')}",
        f"domain_size={values.get('domain_size')}",
    )


def memory_report() -> None:
    path = ROOT / "diagnostico_memoria.csv"
    if not path.is_file():
        print(f"PENDENTE: {path.name}")
        return
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    malformed = 0
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            try:
                scenario = row["scenario"]
                for key in ("speed_s16", "lateral_s16", "progress"):
                    int(row[key])
            except (KeyError, TypeError, ValueError):
                malformed += 1
                continue
            groups[scenario].append(row)
    print("MEMÓRIA/CONTROLES:")
    for scenario, rows in groups.items():
        first, last = rows[0], rows[-1]
        print(
            f"  {scenario}: frames={len(rows) - 1} "
            f"speed {first['speed_s16']}->{last['speed_s16']} "
            f"lateral {first['lateral_s16']}->{last['lateral_s16']} "
            f"progress {first['progress']}->{last['progress']}"
        )
    if malformed:
        print(f"  AVISO: {malformed} linha(s) incompleta(s) ignorada(s)")


def turbo_report() -> None:
    path = ROOT / "diagnostico_turbo.csv"
    if not path.is_file():
        print(f"PENDENTE: {path.name}")
        return
    groups: dict[str, list[dict[str, int]]] = defaultdict(list)
    malformed = 0
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            try:
                scenario = row["scenario"]
                parsed = {
                    key: int(row[key])
                    for key in (
                        "relative_frame",
                        "speed_s16",
                        "progress",
                        "nitro_u16",
                    )
                }
                for key in ("nitro_available_candidate", "turbo_active_candidate"):
                    if row.get(key) not in (None, ""):
                        parsed[key] = int(row[key])
                groups[scenario].append(parsed)
            except (KeyError, TypeError, ValueError):
                malformed += 1
    print("TURBO:")
    for scenario, rows in groups.items():
        first, last = rows[0], rows[-1]
        print(
            f"  {scenario}: frames={last['relative_frame']} "
            f"nitro {first['nitro_u16']}->{last['nitro_u16']} "
            f"speed {first['speed_s16']}->{last['speed_s16']} "
            f"progress {first['progress']}->{last['progress']}"
        )
        if "nitro_available_candidate" in last:
            print(
                "    candidato_disponivel "
                f"{first['nitro_available_candidate']}->"
                f"{last['nitro_available_candidate']} "
                f"ativo_final={last['turbo_active_candidate']}"
            )
    if malformed:
        print(f"  AVISO: {malformed} linha(s) incompleta(s) ignorada(s)")


def opponents_report() -> None:
    path = ROOT / "diagnostico_adversarios.csv"
    if not path.is_file():
        print(f"PENDENTE: {path.name}")
        return
    ids: dict[int, dict[str, list[int]]] = defaultdict(
        lambda: {"lateral": [], "progress": [], "motion": [], "flags": []}
    )
    samples: set[int] = set()
    malformed = 0
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        motion_column = (
            "longitudinal_motion_raw"
            if "longitudinal_motion_raw" in columns
            else "speed_raw"
        )
        for row in reader:
            try:
                racer_id = int(row["id"])
                sample = int(row["sample"])
                lateral = int(row["lateral"])
                progress = int(row["progress"])
                motion = int(row[motion_column])
                flags = int(row["status_flags"])
            except (KeyError, TypeError, ValueError):
                malformed += 1
                continue
            samples.add(sample)
            ids[racer_id]["lateral"].append(lateral)
            ids[racer_id]["progress"].append(progress)
            ids[racer_id]["motion"].append(motion)
            ids[racer_id]["flags"].append(flags)
    print(f"ADVERSÁRIOS: samples={len(samples)}, IDs={sorted(ids)}")
    for racer_id in sorted(ids):
        values = ids[racer_id]
        print(
            f"  id={racer_id:02d} "
            f"lat=[{min(values['lateral'])},{max(values['lateral'])}] "
            f"progress=[{min(values['progress'])},{max(values['progress'])}] "
            f"motion_raw=[{min(values['motion'])},{max(values['motion'])}] "
            f"flags={len(set(values['flags']))} valores"
        )
    expected = set(range(20))
    missing = sorted(expected.difference(ids))
    if missing:
        print(f"  AVISO: IDs não observados: {missing}")
    if malformed:
        print(f"  AVISO: {malformed} linha(s) incompleta(s) ignorada(s)")


def track_report() -> None:
    path = ROOT / "diagnostico_pista.csv"
    if not path.is_file():
        print(f"PENDENTE: {path.name}")
        return
    legacy_columns = (
        "a_plus_p_s8",
        "a_plus_2p_u16",
        "b_plus_p_s8",
        "b_plus_p_u16",
        "b_plus_2p_u16",
    )
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fieldnames = set(reader.fieldnames or ())
        rows = list(reader)

    if "track_index" in fieldnames:
        grade_column = "grade_s16" if "grade_s16" in fieldnames else "curve_s16"
        report_version = "v4" if "lateral_curve_s16" in fieldnames else "v3"
        parsed_rows: list[dict[str, int]] = []
        required = [
            "sample",
            "emu_frame",
            "speed",
            "lateral",
            "progress",
            "lap_s16",
            "rank_u16",
            "collision_edge",
            "track_index",
            grade_column,
            "road_lower_lateral",
            "road_upper_lateral",
            "road_inside_candidate",
            "opponent_count",
            "nearest_valid",
            "nearest_forward",
        ]
        if report_version == "v4":
            required.extend(
                (
                    "final_rank_s16",
                    "total_laps",
                    "finished_candidate",
                    "lateral_curve_s16",
                    "road_type_raw",
                    "nearest_any_valid",
                )
            )
        malformed = 0
        for row in rows:
            try:
                parsed_rows.append({column: int(row[column]) for column in required})
            except (KeyError, TypeError, ValueError):
                malformed += 1
        if not parsed_rows:
            print("PISTA v3: nenhuma linha válida")
            return
        frames = [row["emu_frame"] for row in parsed_rows]
        gaps = sum(b != a + 1 for a, b in zip(frames, frames[1:]))
        collisions = [row for row in parsed_rows if row["collision_edge"]]
        inside = sum(row["road_inside_candidate"] for row in parsed_rows)
        nearest = [row for row in parsed_rows if row["nearest_valid"]]
        print(
            f"PISTA {report_version}: samples={len(parsed_rows)}, frame_gaps={gaps}, "
            f"laps={dict(sorted(Counter(row['lap_s16'] for row in parsed_rows).items()))}, "
            f"ranks={dict(sorted(Counter(row['rank_u16'] for row in parsed_rows).items()))}"
        )
        print(
            f"  progresso=[{min(row['progress'] for row in parsed_rows)},"
            f"{max(row['progress'] for row in parsed_rows)}] "
            f"indices={len(set(row['track_index'] for row in parsed_rows))} "
            f"grade_valores={len(set(row[grade_column] for row in parsed_rows))}"
        )
        if report_version == "v4":
            finished_rows = [row for row in parsed_rows if row["finished_candidate"]]
            print(
                "  curva_lateral_valores="
                f"{len(set(row['lateral_curve_s16'] for row in parsed_rows))} "
                f"tipos_pista={len(set(row['road_type_raw'] for row in parsed_rows))} "
                "adversario_qualquer_lado="
                f"{sum(row['nearest_any_valid'] for row in parsed_rows)}/{len(parsed_rows)}"
            )
            print(
                "  chegada_candidata="
                f"{len(finished_rows)}/{len(parsed_rows)} "
                "posicoes_finais="
                f"{dict(sorted(Counter(row['final_rank_s16'] for row in finished_rows).items()))} "
                "total_laps="
                f"{dict(sorted(Counter(row['total_laps'] for row in parsed_rows).items()))}"
            )
        print(
            f"  corredor_dentro_candidato={inside}/{len(parsed_rows)} "
            f"limite_inferior=[{min(row['road_lower_lateral'] for row in parsed_rows)},"
            f"{max(row['road_lower_lateral'] for row in parsed_rows)}] "
            f"limite_superior=[{min(row['road_upper_lateral'] for row in parsed_rows)},"
            f"{max(row['road_upper_lateral'] for row in parsed_rows)}]"
        )
        print(
            f"  colisoes_borda={len(collisions)} "
            f"adversario_proximo_valido={len(nearest)}/{len(parsed_rows)} "
            f"opponent_count={dict(sorted(Counter(row['opponent_count'] for row in parsed_rows).items()))}"
        )
        for row in collisions:
            print(
                "  impacto: "
                f"frame={row['emu_frame']} lap={row['lap_s16']} "
                f"progress={row['progress']} lateral={row['lateral']} "
                f"inside={row['road_inside_candidate']} "
                f"nearest={row['nearest_valid']} d={row['nearest_forward']}"
            )
        if malformed:
            print(f"  AVISO: {malformed} linha(s) incompleta(s) ignorada(s)")
        return

    values: dict[str, list[int]] = {column: [] for column in legacy_columns}
    samples = 0
    malformed = 0
    for row in rows:
        try:
            parsed = {column: int(row[column]) for column in legacy_columns}
        except (KeyError, TypeError, ValueError):
            malformed += 1
            continue
        samples += 1
        for column, value in parsed.items():
            if value != -999:
                values[column].append(value)
    print(f"PISTA legado: samples={samples}")
    for column, observed in values.items():
        if observed:
            print(
                f"  {column}: min={min(observed)} max={max(observed)} "
                f"valores_unicos={len(set(observed))}"
            )
        else:
            print(f"  {column}: fora do domínio em todas as amostras")
    if malformed:
        print(f"  AVISO: {malformed} linha(s) incompleta(s) ignorada(s)")


def main() -> None:
    execution_report()
    memory_report()
    turbo_report()
    opponents_report()
    track_report()
    print(
        "\nEste resumo não valida automaticamente o perfil. "
        "Compare valores com HUD, vídeo e posições visuais antes de mudar as flags."
    )


if __name__ == "__main__":
    main()
