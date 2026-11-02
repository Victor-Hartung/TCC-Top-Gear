"""Guarda de identidade para o experimento azul/automatico no slot 3.

Os enderecos sao os mesmos ja registrados no diagnostico de transmissao;
as mascaras sao pistas de configuracao, nao uma leitura direta do modo.
"""
from __future__ import annotations


def validate_wire(fields: dict) -> None:
    from protocol import ProtocolError, field_int

    expected = (
        ("manual_mode", 0),
        ("car_table_offset_raw", 48),
        ("upshift_mask_raw", 0),
        ("downshift_mask_raw", 0),
    )
    for key, value in expected:
        actual = field_int(fields, key)
        if actual != value:
            raise ProtocolError(
                f"Perfil azul/automatico divergente: {key}={actual}, esperado {value}; "
                "confira carro, cambio, Type A e save 3"
            )
