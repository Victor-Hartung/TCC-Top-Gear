"""Read-only navigation hints inspired by the ROM's normal P2 controller.

The packed corridor is an internal trajectory constraint, not measured asphalt
edges. This module neither executes the native controller nor selects actions.
"""
from protocol import ProtocolError


VERSION = 1
SETTINGS = dict(
    version=VERSION, history_frames=4, p2_identity=1,
    identity_source="dynamic_offsets_and_global_record_agreement",
    corridor_source="normal_native_table_current_intersect_ahead128",
    corridor_is_physical_road_edge=False, ahead_progress=128,
    forward_gap=512, rear_gap=100, lateral_margin=5120, horizon_frames=30,
    max_relative_delta=100, max_lateral_delta=4096,
    forecast="bounded_absolute_lateral_sweep_during_longitudinal_window",
    target_selection="center_of_nearest_free_interval_then_left",
    addresses=dict(p1_offset=0x0204, p2_offset=0x0206,
                   p1_progress=0x1ED7, p1_lateral=0x1E8A,
                   p2_progress=0x1EDA, p2_lateral=0x1E8C,
                   racer_table=0x0212, racer_stride=18, racer_count=20,
                   track_length=0x0200, corridor_table=0x7002,
                   curve_table=0x4C00, p2_auto_word=0x1EF3, p2_mode=0x1F04),
)
FEATURE_NAMES = (
    "navigation_valid", "p2_present", "p2_gap", "p2_lateral",
    "p2_long_velocity", "p2_lateral_velocity", "p2_prediction_valid", "p2_risk",
    "corridor_low_delta", "corridor_high_delta", "left_free_width",
    "right_free_width", "target_delta", "target_valid",
)
LOW = [0, 0, -1, -1, -1, -1, 0, 0, -1, -1, 0, 0, -1, 0]
HIGH = [1] * len(FEATURE_NAMES)
_KEYS = (
    "frame", "p1_offset", "p2_offset", "p1_record_progress", "p1_record_lateral",
    "p2_progress", "p2_lateral", "p2_record_progress", "p2_record_lateral",
    "corridor_raw", "corridor_ahead_raw", "curve_ahead128", "p2_auto_word", "p2_mode",
)


def _clip(value):
    return max(-1.0, min(1.0, float(value)))


def decode_corridor(raw):
    """Expand signed packed bytes into the project's full lateral scale."""
    signed = lambda byte: byte - 256 if byte >= 128 else byte
    return (signed(raw & 255) * 256, signed(raw >> 8) * 256)


def parse_samples(text, detector_samples):
    """Validate transport strictly; mask inconsistent identities/geometry."""
    if not isinstance(text, str) or not text or len(text) > 4096:
        raise ProtocolError("Navegacao sem historico ou pacote excessivo")
    result = []
    try:
        parts = text.split(";")
        if len(parts) not in (1, 4) or len(parts) != len(detector_samples):
            raise ValueError("historico deve corresponder a 1 ou 4 frames do detector")
        for part, sample in zip(parts, detector_samples):
            values = [int(value) for value in part.split(",")]
            if len(values) != len(_KEYS):
                raise ValueError("tamanho de amostra")
            for index, value in enumerate(values):
                low, high = (-32768, 32767) if index in (4, 6, 8) else (0, 65535)
                if index == 0:
                    low, high = 0, 2147483647
                elif index == 11:
                    low, high = -128, 127
                if not low <= value <= high:
                    raise ValueError("campo fora do intervalo: " + _KEYS[index])
            row = dict(zip(_KEYS, values))
            frame, progress, lateral, length = sample[:4]
            if row["frame"] != frame:
                raise ValueError("frame diverge do detector")
            offsets = (row["p1_offset"], row["p2_offset"])
            reasons = []
            if offsets[0] == offsets[1] or any(value > 342 or value % 18 for value in offsets):
                reasons.append("player_offsets_invalid")
            if (row["p1_record_progress"], row["p1_record_lateral"]) != (progress, lateral):
                reasons.append("p1_record_mismatch")
            if not 0 <= row["p2_progress"] < length:
                reasons.append("p2_progress_invalid")
            if (row["p2_record_progress"], row["p2_record_lateral"]) != (row["p2_progress"], row["p2_lateral"]):
                reasons.append("p2_record_mismatch")
            row["identity_valid"] = not reasons
            row["identity_reasons"] = reasons
            row["p2_automatic_condition"] = row["p2_auto_word"] < 32768 and row["p2_mode"] == 0
            row["corridor"] = decode_corridor(row["corridor_raw"])
            row["corridor_ahead"] = decode_corridor(row["corridor_ahead_raw"])
            current, ahead = row["corridor"], row["corridor_ahead"]
            row["corridor_valid"] = current[0] < current[1] and ahead[0] < ahead[1] and max(current[0], ahead[0]) < min(current[1], ahead[1])
            result.append(row)
        if any(b["frame"] != a["frame"] + 1 for a, b in zip(result, result[1:])):
            raise ValueError("frames nao consecutivos")
    except (TypeError, ValueError, IndexError) as exc:
        raise ProtocolError("Historico de navegacao invalido: " + str(exc)) from exc
    return result


def augment_samples(text, samples):
    """Assign P2 ID 1 from validated offsets; never infer it from raw ID bits."""
    parsed = parse_samples(text, samples)
    augmented = []
    for sample, row in zip(samples, parsed):
        racers = dict(sample[4])
        if 1 in racers:
            raise ProtocolError("Detector base ja contem a identidade reservada P2")
        if row["identity_valid"]:
            racers[1] = (row["p2_progress"], row["p2_lateral"])
        augmented.append((*sample[:4], racers))
    return augmented, parsed


def _window(gap, velocity):
    low, high, horizon = -SETTINGS["rear_gap"], SETTINGS["forward_gap"], SETTINGS["horizon_frames"]
    if velocity == 0:
        return (0.0, float(horizon)) if low <= gap <= high else None
    entry, leave = sorted(((low - gap) / velocity, (high - gap) / velocity))
    entry, leave = max(0.0, entry), min(float(horizon), leave)
    return (entry, leave) if entry <= leave else None


def _free_intervals(low, high, occupied):
    merged = []
    for start, end in sorted(occupied):
        start, end = max(low, start), min(high, end)
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    free, cursor = [], low
    for start, end in merged:
        if start > cursor:
            free.append([cursor, start])
        cursor = max(cursor, end)
    if cursor < high:
        free.append([cursor, high])
    return free, merged


def evaluate(parsed, detector_samples, rows):
    """Return 14 masked features plus auditable hints; all coordinates are WRAM units.

    `rows` are the detector's per-car rows, including P2. All cars contribute to
    occupied intervals, irrespective of which three were selected by the sensor.
    """
    state, sample = parsed[-1], detector_samples[-1]
    _, progress, lateral, length = sample[:4]
    cars = dict(sample[4])
    if state["identity_valid"]:
        cars[1] = (state["p2_progress"], state["p2_lateral"])
    else:
        cars.pop(1, None)
    by_id = {row["id"]: row for row in rows}
    features = [0.0] * len(FEATURE_NAMES)
    p2 = by_id.get(1) if state["identity_valid"] else None
    if p2 is not None:
        features[1:8] = [
            1.0, _clip(p2["gap"] / (length * .1)), _clip(p2["lateral_delta"] / 65536.0),
            _clip(p2["long_velocity"] / 100.0), _clip(p2["lateral_velocity"] / 4096.0),
            float(p2["prediction_valid"]), max(0.0, min(1.0, p2["risk"])),
        ]
    current, ahead = state["corridor"], state["corridor_ahead"]
    reasons = list(state["identity_reasons"])
    if current[0] >= current[1] or ahead[0] >= ahead[1]:
        reasons.append("corridor_bounds_invalid")
    low, high = max(current[0], ahead[0]), min(current[1], ahead[1])
    if low >= high:
        reasons.append("corridor_intersection_empty")
    diagnostic = dict(
        version=VERSION, frame=sample[0], identity_valid=state["identity_valid"],
        p1_offset=state["p1_offset"], p2_offset=state["p2_offset"],
        p2_automatic_condition=state["p2_automatic_condition"],
        p2_present=bool(p2), corridor_raw=state["corridor_raw"],
        corridor_ahead_raw=state["corridor_ahead_raw"],
        current_bounds=list(current), ahead_bounds=list(ahead),
        intersection_bounds=[low, high], curve_ahead128=state["curve_ahead128"],
        is_physical_road_edge=False, bit_exact_native_controller=False,
        target_is_candidate_not_safety_guarantee=True,
        blocking_ids=[], blocked_intervals=[], free_intervals=[], target=None,
        navigation_valid=not reasons, target_valid=False, reasons=reasons,
    )
    if reasons:
        return features, diagnostic
    features[0] = 1.0
    features[8:10] = [_clip((low - lateral) / 65536.0), _clip((high - lateral) / 65536.0)]
    occupied, alongside = [], []
    for identity, (other_progress, other_lateral) in sorted(cars.items()):
        gap = (other_progress - progress + length // 2) % length - length // 2
        # O alcance usado para publicar tres regioes nao limita o planejador:
        # um carro hoje mais distante pode entrar na janela em ate 30 frames.
        valid_prediction = len(detector_samples) == 4
        lateral_history, gap_history, relative_lateral_history = [], [], []
        for historical, navigation in zip(detector_samples, parsed):
            other = ((navigation["p2_progress"], navigation["p2_lateral"])
                     if identity == 1 and navigation["identity_valid"] else historical[4].get(identity))
            if other is None:
                valid_prediction = False
                break
            lateral_history.append(other[1])
            gap_history.append((other[0] - historical[1] + length // 2) % length - length // 2)
            relative_lateral_history.append(other[1] - historical[2])
        valid_prediction = valid_prediction and all(
            all(abs(b - a) <= limit for a, b in zip(history, history[1:]))
            for history, limit in ((gap_history, SETTINGS['max_relative_delta']),
                                   (lateral_history, SETTINGS['max_lateral_delta']),
                                   (relative_lateral_history, SETTINGS['max_lateral_delta'])))
        vg = (gap_history[-1] - gap_history[0]) / 3.0 if valid_prediction else 0.0
        vl = (lateral_history[-1] - lateral_history[0]) / 3.0 if valid_prediction else 0.0
        times = _window(gap, vg)
        if times is None:
            continue
        # The corridor is in absolute WRAM lateral coordinates: use the other
        # car's motion, not its motion relative to a steering P1. Extrapolation
        # is bounded to 30 frames and representable signed lateral values.
        positions = [max(-32768.0, min(32767.0, other_lateral + vl * time)) for time in times]
        start, end = min(positions) - SETTINGS["lateral_margin"], max(positions) + SETTINGS["lateral_margin"]
        if end > low and start < high:
            occupied.append((start, end))
            diagnostic["blocking_ids"].append(identity)
            if abs(gap) <= SETTINGS["rear_gap"]:
                alongside.append((other_lateral, other_lateral - SETTINGS["lateral_margin"], other_lateral + SETTINGS["lateral_margin"]))
    free, blocked = _free_intervals(low, high, occupied)
    diagnostic["blocked_intervals"], diagnostic["free_intervals"] = blocked, free
    features[10] = max((max(0.0, min(end, lateral) - start) for start, end in free), default=0.0) / 65536.0
    features[11] = max((max(0.0, end - max(start, lateral)) for start, end in free), default=0.0) / 65536.0
    candidates = sorted(free, key=lambda pair: (max(pair[0] - lateral, lateral - pair[1], 0.0), (pair[0] + pair[1]) / 2))
    target = None
    for start, end in candidates:
        candidate = (start + end) / 2
        path_low, path_high = sorted((lateral, candidate))
        crosses_alongside = False
        for center, blocked_low, blocked_high in alongside:
            if blocked_low <= lateral <= blocked_high:
                crosses_alongside |= (candidate - lateral) * (center - lateral) > 0
            else:
                crosses_alongside |= max(path_low, blocked_low) < min(path_high, blocked_high)
        if not crosses_alongside:
            target = candidate
            break
    if target is not None:
        features[12:14] = [_clip((target - lateral) / 65536.0), 1.0]
        diagnostic["target"], diagnostic["target_valid"] = target, True
    else:
        diagnostic["reasons"].append("alongside_blocks_access" if free else "corridor_fully_occupied")
    return features, diagnostic
