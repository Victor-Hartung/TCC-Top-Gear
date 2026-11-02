"""Erros semanticos com evidencia; nao alteram nem consertam a telemetria."""
from protocol import ProtocolError


class LapSentinelRegression(ProtocolError):
    def __init__(self, diagnostic: dict):
        super().__init__("Volta voltou ao sentinela durante o episodio")
        self.diagnostic = diagnostic
