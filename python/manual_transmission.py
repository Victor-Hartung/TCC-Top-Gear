"""Manual experimental: dados brutos comprovados, sem limiar RPM inventado."""
from __future__ import annotations

FEATURE_NAMES = ("engine_gauge_raw_norm", "previous_shift_command")
SETTINGS = {
    "version": 2, "gear_wram": "0x1E72", "engine_gauge_wram": "0x1E5E",
    "gauge_semantics": "signed raw input to ROM HUD routine 00:D3CF; not physical RPM",
    "gauge_scale": 32768, "shift_up": "R", "shift_down": "L",
    "actions": "base=action%10; action//10: 0 hold, 1 up, 2 down",
    "release": "choose a command without that shift button for an emulated step",
    "car_offset": 48, "savestate_slot": 2,
}


def decode_action(action: int) -> tuple[int, int]:
    if not 0 <= action < 30:
        raise ValueError("Acao manual fora de 0..29")
    return action % 10, (0, 1, -1)[action // 10]


def validate_wire(fields: dict) -> None:
    from protocol import ProtocolError, field_int
    for key, expected in (("manual_mode", 1), ("car_table_offset_raw", 48),
                          ("upshift_mask_raw", 16), ("downshift_mask_raw", 32)):
        if field_int(fields, key) != expected:
            raise ProtocolError(f"Perfil manual/azul divergente: {key}; confira save 2 e Type A")
    if not 0 <= field_int(fields, "gear") <= 4:
        raise ProtocolError("Marcha manual fora de 0..4")
    if not -32768 <= field_int(fields, "engine_gauge_raw") <= 32767:
        raise ProtocolError("Conta-giro bruto fora de s16")
