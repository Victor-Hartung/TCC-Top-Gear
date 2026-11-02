from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from protocol import ProtocolError, field_int
from topgear_config import ProjectConfig


from live_detector import FEATURE_NAMES as DETECTOR_NAMES, LOW as DETECTOR_LOW, evaluate as evaluate_detector
from live_detector import parse_samples as parse_detector_samples, evaluate_samples
from native_navigation import (FEATURE_NAMES as NAVIGATION_NAMES, LOW as NAVIGATION_LOW,
                               augment_samples, evaluate as evaluate_navigation)

OBSERVATION_SCHEMA_VERSION = 10


def observation_names(config=None):
    from manual_transmission import FEATURE_NAMES
    return OBSERVATION_NAMES + (FEATURE_NAMES if config is not None and config.manual_transmission else ())

OBSERVATION_NAMES = (
    "speed_norm",
    "lateral_norm",
    "progress_norm",
    "lap_norm",
    "rank_norm",
    "collision",
    "offtrack",
    "surface_direction",
    "fuel_norm",
    "nitro_norm",
    "turbo_active",
    "gear_norm",
    "curve_current_norm",
    "curve_ahead_512_norm",
    "curve_ahead_1024_norm",
    "curve_ahead_2048_norm",
    "nearest_valid",
    "nearest_distance_norm",
    "nearest_lateral_norm",
    "closing_rate_norm",
    "lane_negative_risk",
    "lane_center_risk",
    "lane_positive_risk",
    "surface_unknown",
    "closing_rate_valid",
    "race_ended",
) + DETECTOR_NAMES + NAVIGATION_NAMES


@dataclass(frozen=True)
class Telemetry:
    frame: int
    speed: int
    lateral: int
    progress_fraction: int
    progress: int
    lap: int
    rank: int
    final_rank: int
    finished: int
    collision: int
    collision_events: int
    offtrack: int
    surface_raw: int
    surface_unknown: int
    surface_state: int
    surface_direction: int
    fuel: int
    nitro: int
    nitro_raw: int
    turbo_active: int
    gear: int
    total_laps: int
    track_length: int
    curve_progress: int
    curve_current: int
    curve_ahead_512: int
    curve_ahead_1024: int
    curve_ahead_2048: int
    nearest_valid: int
    nearest_id: int
    nearest_distance: int
    nearest_lateral: int
    nearest_motion_raw: int
    lane_negative_distance: int
    lane_center_distance: int
    lane_positive_distance: int
    opponent_count: int
    profile_validated: int
    opponent_telemetry_validated: int
    surface_telemetry_validated: int
    curve_telemetry_validated: int
    controls_validated: int
    rom_ok: int
    domain_ok: int
    detector_samples: str = ""
    navigation_samples: str = ""
    engine_gauge_raw: int | None = None

    @classmethod
    def from_fields(cls, fields: Mapping[str, str]) -> "Telemetry":
        def value(name: str) -> int:
            return field_int(fields, name)

        telemetry = cls(
            frame=value("frame"),
            speed=value("speed"),
            lateral=value("lateral"),
            progress_fraction=value("progress_fraction"),
            progress=value("progress"),
            lap=value("lap"),
            rank=value("rank"),
            final_rank=value("final_rank"),
            finished=value("finished"),
            collision=value("collision"),
            collision_events=value("collision_events"),
            offtrack=value("offtrack"),
            surface_raw=value("surface_raw"),
            surface_unknown=value("surface_unknown"),
            surface_state=value("surface_state"),
            surface_direction=value("surface_direction"),
            fuel=value("fuel"),
            nitro=value("nitro"),
            nitro_raw=value("nitro_raw"),
            turbo_active=value("turbo_active"),
            gear=value("gear"),
            total_laps=value("total_laps"),
            track_length=value("track_length"),
            curve_progress=value("curve_progress"),
            curve_current=value("curve_current"),
            curve_ahead_512=value("curve_ahead_512"),
            curve_ahead_1024=value("curve_ahead_1024"),
            curve_ahead_2048=value("curve_ahead_2048"),
            nearest_valid=value("nearest_valid"),
            nearest_id=value("nearest_id"),
            nearest_distance=value("nearest_distance"),
            nearest_lateral=value("nearest_lateral"),
            nearest_motion_raw=value("nearest_motion_raw"),
            lane_negative_distance=value("lane_negative_distance"),
            lane_center_distance=value("lane_center_distance"),
            lane_positive_distance=value("lane_positive_distance"),
            opponent_count=value("opponent_count"),
            profile_validated=value("profile_validated"),
            opponent_telemetry_validated=value("opponent_telemetry_validated"),
            surface_telemetry_validated=value("surface_telemetry_validated"),
            curve_telemetry_validated=value("curve_telemetry_validated"),
            controls_validated=value("controls_validated"),
            rom_ok=value("rom_ok"),
            domain_ok=value("domain_ok"),
            detector_samples=fields.get("detector_samples", ""),
            navigation_samples=fields.get("navigation_samples", ""),
            engine_gauge_raw=(value("engine_gauge_raw") if fields.get("engine_gauge_raw") not in (None, "None") else None),
        )
        telemetry.validate()
        for name, computed in (("race_ended", telemetry.race_ended), ("race_completed", telemetry.race_completed)):
            if name in fields and value(name) != int(computed):
                raise ProtocolError(f"Alias de encerramento inconsistente: {name}")
        return telemetry

    def validate(self) -> None:
        if self.frame < 0 or not -32768 <= self.speed <= 32767 or not -32768 <= self.lateral <= 32767:
            raise ProtocolError("Frame/velocidade/lateral fora da representacao")
        for name in ("progress", "fuel", "gear", "total_laps", "track_length", "curve_progress"):
            if not 0 <= getattr(self, name) <= 65535:
                raise ProtocolError(f"{name} fora de u16")
        for name in (
            "finished",
            "collision",
            "offtrack",
            "surface_unknown",
            "turbo_active",
            "nearest_valid",
            "profile_validated",
            "opponent_telemetry_validated",
            "surface_telemetry_validated",
            "curve_telemetry_validated",
            "controls_validated",
            "rom_ok",
            "domain_ok",
        ):
            if getattr(self, name) not in (0, 1):
                raise ProtocolError(f"Flag {name} deve ser 0 ou 1")
        if not 0 <= self.surface_raw <= 0xFF:
            raise ProtocolError(f"surface_raw fora de u8: {self.surface_raw}")
        if self.surface_state not in (0, 1, 2):
            raise ProtocolError(
                f"surface_state fora dos estados validados 0..2: {self.surface_state}"
            )
        expected_direction = self.surface_state - 1
        expected_offtrack = int(self.surface_state != 1)
        if self.surface_unknown:
            valid_unknown = (
                self.surface_raw not in (0, 1, 2)
                and self.surface_state in (0, 2)
                and self.surface_direction in (-1, 1)
                and self.offtrack == 1
            )
            if not valid_unknown:
                raise ProtocolError(
                    "Fallback de superfície desconhecida inconsistente: "
                    f"raw={self.surface_raw}, state={self.surface_state}, "
                    f"direction={self.surface_direction}, offtrack={self.offtrack}"
                )
        elif (
            self.surface_raw != self.surface_state
            or self.surface_direction != expected_direction
            or self.offtrack != expected_offtrack
        ):
            raise ProtocolError(
                "Campos de superfície inconsistentes: "
                f"raw={self.surface_raw}, state={self.surface_state}, "
                f"direction={self.surface_direction}, "
                f"offtrack={self.offtrack}"
            )
        if not 0 <= self.nitro <= 3:
            raise ProtocolError(f"nitro disponível fora do intervalo 0..3: {self.nitro}")
        if not 0 <= self.nitro_raw <= 0xFFFF:
            raise ProtocolError(f"nitro_raw fora de u16: {self.nitro_raw}")
        expected_active = int(self.nitro_raw >= 0x8000)
        expected_nitro = self.nitro_raw % 4
        if expected_active and expected_nitro > 0:
            expected_nitro -= 1
        if self.turbo_active != expected_active or self.nitro != expected_nitro:
            raise ProtocolError(
                "Campos de turbo inconsistentes com nitro_raw: "
                f"raw={self.nitro_raw}, nitro={self.nitro}, ativo={self.turbo_active}"
            )
        if self.rank not in range(-1, 20):
            raise ProtocolError(f"rank fora do intervalo esperado: {self.rank}")
        for name in (
            "curve_current",
            "curve_ahead_512",
            "curve_ahead_1024",
            "curve_ahead_2048",
        ):
            if getattr(self, name) not in range(-128, 128):
                raise ProtocolError(f"{name} fora do intervalo s8")
        if self.track_length > 0 and not 0 <= self.curve_progress < self.track_length:
            raise ProtocolError("curve_progress fora do comprimento da pista")
        if self.collision_events < 0:
            raise ProtocolError("collision_events não pode ser negativo")
        if self.final_rank not in range(-1, 20):
            raise ProtocolError(f"final_rank fora do intervalo esperado: {self.final_rank}")
        if not 0 <= self.opponent_count <= 18:
            raise ProtocolError(f"opponent_count inválido: {self.opponent_count}")
        for name in (
            "lane_negative_distance",
            "lane_center_distance",
            "lane_positive_distance",
        ):
            if getattr(self, name) < -1:
                raise ProtocolError(f"{name} não pode ser menor que -1")
        if self.nearest_valid:
            if self.nearest_distance < 0:
                raise ProtocolError("nearest_valid=1 exige distância não negativa")
            if self.nearest_id not in range(2, 20):
                raise ProtocolError(
                    f"nearest_valid=1 exige ID de adversário 2..19: {self.nearest_id}"
                )
        elif self.nearest_id != -1 or self.nearest_distance != -1:
            raise ProtocolError(
                "nearest_valid=0 exige nearest_id=-1 e nearest_distance=-1"
            )
        if bool(self.finished) != (0 <= self.final_rank <= 19):
            raise ProtocolError("finished e final_rank são inconsistentes")

    @property
    def race_ended(self) -> bool:
        """Alias explicito do campo legado finished da mensagem TGSTATE2."""
        return bool(self.finished)

    @property
    def race_completed(self) -> bool:
        """Las Vegas: lap 0 no inicio, lap 3 ao concluir as tres voltas.

        finished no protocolo e apenas classificacao publicada (inclui tempo
        esgotado). Nao ha leitura de um temporizador validado neste perfil.
        """
        return bool(
            self.finished and 0 <= self.final_rank <= 19
            and self.total_laps > 0 and self.lap == self.total_laps
        )

    @property
    def absolute_progress(self) -> int | None:
        if self.track_length <= 0 or self.lap < 0:
            return None
        return self.lap * self.track_length + self.progress

    def assert_runtime_ready(self, *, allow_prestart: bool = False, require_detector: bool = False) -> None:
        if require_detector:
            samples = parse_detector_samples(self.detector_samples, self)
            # Ausencia ou malformacao e erro de protocolo. Uma leitura de
            # identidade/corredor inconsistente e representada por mascara.
            augment_samples(self.navigation_samples, samples)
        errors: list[str] = []
        if not self.rom_ok:
            errors.append("hash da ROM não confere")
        if not self.domain_ok:
            errors.append("domínio WRAM não foi confirmado")
        if not self.profile_validated:
            errors.append("profile_validated=0")
        if not self.opponent_telemetry_validated:
            errors.append("opponent_telemetry_validated=0")
        if not self.surface_telemetry_validated:
            errors.append("surface_telemetry_validated=0")
        if not self.curve_telemetry_validated:
            errors.append("curve_telemetry_validated=0")
        if not self.controls_validated:
            errors.append("controls_validated=0")
        if self.track_length <= 0:
            errors.append("track_length inválido")
        if self.total_laps <= 0:
            errors.append("total_laps inválido")
        prestart = allow_prestart and self.lap == -1 and not self.race_ended
        if self.lap < 0 and not prestart:
            errors.append("lap ainda está em valor sentinela")
        if self.rank < 0 and not (prestart and self.rank == -1):
            errors.append("rank ainda está em valor sentinela")
        if self.track_length > 0 and not 0 <= self.progress <= self.track_length:
            errors.append("progress fora do comprimento da pista")
        if errors:
            raise ProtocolError("Telemetria não liberada para treino: " + "; ".join(errors))


class ObservationBuilder:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.previous: Telemetry | None = None
        self.detector_rows = []
        self.navigation = {}

    @staticmethod
    def low(config=None) -> np.ndarray:
        return np.array(
            [
                -1, -1, 0, -1, 0, 0, 0, -1, 0, 0, 0, 0,
                -1, -1, -1, -1,
                0, 0, -1, -1, 0, 0, 0, 0, 0, 0,
            ] + DETECTOR_LOW + NAVIGATION_LOW + ([-1, -1] if config is not None and config.manual_transmission else []),
            dtype=np.float32,
        )

    @staticmethod
    def high(config=None) -> np.ndarray:
        return np.ones(len(observation_names(config)), dtype=np.float32)

    def reset(self, telemetry: Telemetry) -> np.ndarray:
        self.previous = None
        observation = self.build(telemetry)
        self.previous = telemetry
        return observation

    def build(self, telemetry: Telemetry, shift_command: int = 0) -> np.ndarray:
        cfg = self.config
        manual_features = []
        if cfg.manual_transmission:
            gauge = telemetry.engine_gauge_raw
            if gauge is None or not -32768 <= gauge <= 32767 or shift_command not in (-1, 0, 1):
                raise ProtocolError("Telemetria manual ausente/invalida")
            manual_features = [gauge / 32768.0, float(shift_command)]
        track_length = max(telemetry.track_length, 1)
        sensor_range = max(
            track_length * cfg.number("geometry", "opponent_sensor_fraction"),
            1.0,
        )
        speed = np.clip(
            telemetry.speed / cfg.number("normalization", "speed_scale"), -1.0, 1.0
        )
        lateral = np.clip(
            (
                telemetry.lateral
                - cfg.integer("geometry", "lateral_center")
            )
            / cfg.number("normalization", "lateral_scale"),
            -1.0,
            1.0,
        )
        progress = np.clip(telemetry.progress / track_length, 0.0, 1.0)
        lap = -1.0 if telemetry.lap == -1 else np.clip(telemetry.lap / max(telemetry.total_laps, 1), 0.0, 1.0)
        rank = np.clip((telemetry.rank if telemetry.rank >= 0 else 19) / 19.0, 0.0, 1.0)
        fuel = np.clip(
            telemetry.fuel / cfg.number("normalization", "fuel_scale"), 0.0, 1.0
        )
        nitro = np.clip(
            telemetry.nitro / cfg.number("normalization", "nitro_scale"), 0.0, 1.0
        )
        gear = np.clip(
            telemetry.gear / cfg.number("normalization", "gear_scale"), 0.0, 1.0
        )
        curve_scale = cfg.number("normalization", "curve_scale")
        curve_current = np.clip(telemetry.curve_current / curve_scale, -1.0, 1.0)
        curve_ahead_512 = np.clip(
            telemetry.curve_ahead_512 / curve_scale, -1.0, 1.0
        )
        curve_ahead_1024 = np.clip(
            telemetry.curve_ahead_1024 / curve_scale, -1.0, 1.0
        )
        curve_ahead_2048 = np.clip(
            telemetry.curve_ahead_2048 / curve_scale, -1.0, 1.0
        )

        nearest_valid = float(telemetry.nearest_valid)
        nearest_distance = 1.0
        nearest_lateral = 0.0
        closing_rate = 0.0
        closing_valid = 0.0
        if telemetry.nearest_valid:
            nearest_distance = float(np.clip(telemetry.nearest_distance / sensor_range, 0, 1))
            nearest_lateral = float(
                np.clip(
                    telemetry.nearest_lateral
                    / cfg.number("normalization", "lateral_scale"),
                    -1,
                    1,
                )
            )
            if (
                self.previous is not None
                and self.previous.nearest_valid
                and self.previous.nearest_id == telemetry.nearest_id
                and telemetry.frame > self.previous.frame
            ):
                distance_change = (
                    self.previous.nearest_distance - telemetry.nearest_distance
                )
                elapsed = telemetry.frame - self.previous.frame
                closing_rate = float(np.clip(
                    distance_change / elapsed / cfg.number("normalization", "closing_rate_scale"), -1, 1))
                closing_valid = 1.0

        def risk(distance: int) -> float:
            if distance < 0:
                return 0.0
            return float(np.clip(1.0 - distance / sensor_range, 0.0, 1.0))

        navigation_features = [0.] * len(NAVIGATION_NAMES)
        self.navigation = {'navigation_valid': False, 'target_valid': False,
                           'p2_present': False, 'reasons': ['navigation_packet_absent']}
        if telemetry.navigation_samples:
            samples = parse_detector_samples(telemetry.detector_samples, telemetry)
            augmented, navigation = augment_samples(telemetry.navigation_samples, samples)
            detector_features, self.detector_rows = evaluate_samples(augmented)
            navigation_features, self.navigation = evaluate_navigation(navigation, samples, self.detector_rows)
        else:
            # Leitura offline de evidencias historicas continua possivel.
            # O ambiente operacional exige ambos os pacotes em _telemetry().
            detector_features, self.detector_rows = evaluate_detector(telemetry.detector_samples, telemetry) if telemetry.detector_samples else ([0.] * len(DETECTOR_NAMES), [])
        observation = np.array(
            [
                speed,
                lateral,
                progress,
                lap,
                rank,
                telemetry.collision,
                telemetry.offtrack,
                telemetry.surface_direction,
                fuel,
                nitro,
                telemetry.turbo_active,
                gear,
                curve_current,
                curve_ahead_512,
                curve_ahead_1024,
                curve_ahead_2048,
                nearest_valid,
                nearest_distance,
                nearest_lateral,
                closing_rate,
                risk(telemetry.lane_negative_distance),
                risk(telemetry.lane_center_distance),
                risk(telemetry.lane_positive_distance),
                telemetry.surface_unknown,
                closing_valid,
                int(telemetry.race_ended),
            ] + detector_features + navigation_features + manual_features,
            dtype=np.float32,
        )
        if not np.all(np.isfinite(observation)):
            raise ProtocolError("Observação contém NaN ou infinito")
        if np.any(observation < self.low(cfg)) or np.any(observation > self.high(cfg)):
            raise ProtocolError(f"Observação fora dos limites: {observation}")
        self.previous = telemetry
        return observation
