from __future__ import annotations

import argparse
from pathlib import Path

from protocol import BridgeClient
from telemetry import Telemetry
from topgear_config import ProjectConfig


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Testa seq/ack/frames da ponte v2")
    parser.add_argument("--reset", action="store_true", help="Também testa o savestate do slot configurado")
    parser.add_argument("--steps", type=int, default=3, help="Quantidade de ações neutras")
    return parser.parse_args()


def describe(label: str, fields: dict[str, str]) -> None:
    telemetry = Telemetry.from_fields(fields)
    print(
        f"{label}: frame={telemetry.frame} speed={telemetry.speed} "
        f"lateral={telemetry.lateral} lap={telemetry.lap} rank={telemetry.rank} "
        f"surface={telemetry.surface_state} raw={telemetry.surface_raw} "
        f"unknown={telemetry.surface_unknown} direction={telemetry.surface_direction} "
        f"offtrack={telemetry.offtrack} "
        f"curve={telemetry.curve_current}/"
        f"{telemetry.curve_ahead_512}/"
        f"{telemetry.curve_ahead_1024}/"
        f"{telemetry.curve_ahead_2048} "
        f"opponents={telemetry.opponent_count} nearest={telemetry.nearest_distance}"
    )


def main() -> None:
    args = arguments()
    if args.steps < 1:
        raise ValueError("--steps deve ser >= 1")
    project_dir = Path(__file__).resolve().parents[1]
    config = ProjectConfig.load(project_dir)
    bridge = BridgeClient(config)
    host, port = bridge.address
    print(f"Servidor da ponte pronto em {host}:{port}.")
    print("Agora abra o BizHawk com --socket-ip/--socket-port e execute somente")
    print("lua/Top Gear (USA).lua. Aguardando conexão...")
    try:
        ready = bridge.wait_ready()
        print(
            "Ponte encontrada: "
            f"status={ready.status}, frame={ready.frame}, "
            f"rom={ready.fields.get('rom_hash')}, domain_size={ready.fields.get('domain_size')}"
        )
        describe("estado inicial", ready.fields)

        blockers = config.training_blockers()
        if blockers:
            print("Treino ainda bloqueado: " + "; ".join(blockers))

        if args.reset:
            describe("reset confirmado", bridge.reset().fields)
        for index in range(args.steps):
            state = bridge.step(action=0)
            describe(f"ack neutro {index + 1}", state.fields)
        print("OK: sequência, ack e delta fixo de frames estão corretos.")
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
