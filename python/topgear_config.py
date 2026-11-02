from __future__ import annotations

import configparser
import math
import os
import zlib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    """Erro de configuração que deve impedir treino silenciosamente inválido."""


@dataclass(frozen=True)
class ProjectConfig:
    project_dir: Path
    path: Path
    parser: configparser.ConfigParser

    @classmethod
    def load(cls, project_dir: str | Path | None = None) -> "ProjectConfig":
        root = (
            Path(project_dir).resolve()
            if project_dir is not None
            else Path(__file__).resolve().parents[1]
        )
        profile = os.environ.get("TOPGEAR_PROFILE", "game_profile.ini")
        if profile not in ("game_profile.ini", "game_profile_manual.ini", "game_profile_manual_refine.ini", "game_profile_blue_auto.ini"):
            raise ConfigError("TOPGEAR_PROFILE deve selecionar um perfil conhecido da v3.0")
        path = root / "config" / profile
        parser = configparser.ConfigParser(interpolation=None)
        loaded = parser.read(path, encoding="utf-8")
        if not loaded:
            raise ConfigError(f"Perfil não encontrado: {path}")
        config = cls(project_dir=root, path=path, parser=parser)
        config.validate_structure()
        return config

    def text(self, section: str, key: str) -> str:
        try:
            return self.parser[section][key].strip()
        except KeyError as exc:
            raise ConfigError(f"Chave obrigatória ausente: [{section}] {key}") from exc

    def integer(self, section: str, key: str) -> int:
        raw = self.text(section, key)
        try:
            return int(raw, 0)
        except ValueError as exc:
            raise ConfigError(f"Inteiro inválido em [{section}] {key}: {raw!r}") from exc

    def number(self, section: str, key: str) -> float:
        raw = self.text(section, key)
        try:
            result = float(raw)
            if not math.isfinite(result):
                raise ValueError("numero nao finito")
            return result
        except ValueError as exc:
            raise ConfigError(f"Número inválido em [{section}] {key}: {raw!r}") from exc

    def boolean(self, section: str, key: str) -> bool:
        try:
            return self.parser.getboolean(section, key)
        except (ValueError, configparser.Error) as exc:
            raise ConfigError(f"Booleano inválido em [{section}] {key}") from exc

    @property
    def frame_repeat(self) -> int:
        return self.integer("protocol", "frame_repeat")

    @property
    def manual_transmission(self) -> bool:
        return self.parser.getboolean("controls", "manual_transmission", fallback=False)

    @property
    def blue_auto_expected(self) -> bool:
        return self.parser.getboolean("controls", "blue_auto_expected", fallback=False)

    @property
    def bridge_revision(self) -> int:
        return 6 if self.manual_transmission else 5

    @property
    def action_names(self) -> tuple[str, ...]:
        if self.manual_transmission:
            return tuple(name + suffix for suffix in ("", "_SHIFT_UP", "_SHIFT_DOWN") for name in ACTION_NAMES)
        return ACTION_NAMES[:10 if self.boolean("controls", "enable_turbo") else 9]

    @property
    def action_count(self) -> int:
        return len(self.action_names)

    @property
    def profile_crc(self) -> int:
        # Mesmo Adler-32 do Lua. Identifica perfil errado; nao e assinatura de seguranca.
        data = self.path.read_bytes().replace(b"\r\n", b"\n")
        return zlib.adler32(data) & 0xFFFFFFFF

    def validate_structure(self) -> None:
        required_sections = {
            "identity",
            "validation",
            "protocol",
            "memory",
            "controls",
            "geometry",
            "normalization",
            "reward",
            "episode",
            "experiment",
            "ppo",
        }
        missing = sorted(required_sections.difference(self.parser.sections()))
        if missing:
            raise ConfigError(f"Seções obrigatórias ausentes: {', '.join(missing)}")

        if self.integer("identity", "profile_version") != 3:
            raise ConfigError("Esta distribuição exige profile_version=3")
        if self.integer("protocol", "protocol_version") != 2:
            raise ConfigError("Esta versão do Python exige protocol_version=2")
        if self.text("protocol", "transport") != "socket":
            raise ConfigError("Esta versão exige transport=socket")
        socket_host = self.text("protocol", "socket_host")
        if socket_host != "127.0.0.1":
            raise ConfigError("socket_host deve ser 127.0.0.1 nesta versão")
        if not 1 <= self.integer("protocol", "socket_port") <= 65535:
            raise ConfigError("socket_port deve estar entre 1 e 65535")
        if self.number("protocol", "startup_timeout_seconds") <= 0:
            raise ConfigError("startup_timeout_seconds deve ser positivo")
        max_repeat = self.integer("protocol", "max_repeat_frames")
        if max_repeat < 1:
            raise ConfigError("max_repeat_frames deve ser >= 1")
        if not 1 <= self.frame_repeat <= max_repeat:
            raise ConfigError("frame_repeat fora do intervalo permitido")
        post_reset = self.integer("protocol", "post_reset_frames")
        if not 0 <= post_reset <= max_repeat:
            raise ConfigError("post_reset_frames fora do intervalo permitido")
        if not 1 <= self.integer("protocol", "savestate_slot") <= 10:
            raise ConfigError("savestate_slot deve estar entre 1 e 10")
        if self.number("protocol", "timeout_seconds") <= 0:
            raise ConfigError("timeout_seconds deve ser positivo")
        if self.integer("memory", "racer_count") != 20:
            raise ConfigError("O perfil desta ROM deve declarar exatamente 20 corredores")
        if self.integer("memory", "racer_record_stride") != 0x12:
            raise ConfigError("Stride esperado para esta ROM: 0x12")
        if self.integer("memory", "surface_state_address") != 0x0727:
            raise ConfigError("Sensor de superfície validado esperado em 0x0727")
        if self.integer("memory", "curve_progress_address") != 0x0046:
            raise ConfigError("Posição suavizada de curva esperada em 0x0046")
        if self.integer("geometry", "lateral_curve_table") != 0x4C00:
            raise ConfigError("Tabela de curva validada esperada em 0x4C00")
        surface_values = (
            self.integer("geometry", "surface_left_value"),
            self.integer("geometry", "surface_road_value"),
            self.integer("geometry", "surface_right_value"),
        )
        if surface_values != (0, 1, 2):
            raise ConfigError(
                "Estados de superfície validados devem ser esquerda=0, pista=1, direita=2"
            )
        expected_hash = self.text("identity", "rom_sha1").lower()
        if len(expected_hash) != 40 or any(ch not in "0123456789abcdef" for ch in expected_hash):
            raise ConfigError("rom_sha1 deve conter exatamente 40 dígitos hexadecimais")
        for key in (
            "speed_scale",
            "lateral_scale",
            "fuel_scale",
            "nitro_scale",
            "gear_scale",
            "curve_scale",
            "closing_rate_scale",
        ):
            if self.number("normalization", key) <= 0:
                raise ConfigError(f"{key} deve ser positivo")
        sensor_fraction = self.number("geometry", "opponent_sensor_fraction")
        if not 0 < sensor_fraction < 0.5:
            raise ConfigError("opponent_sensor_fraction deve estar em (0, 0.5)")
        if self.integer("geometry", "same_lane_half_width") <= 0:
            raise ConfigError("same_lane_half_width deve ser positivo")
        max_progress_fraction = self.number(
            "reward", "max_progress_fraction_per_step"
        )
        if not 0 < max_progress_fraction <= 1:
            raise ConfigError("max_progress_fraction_per_step deve estar em (0, 1]")
        for key in (
            "progress_weight",
            "rank_delta_weight",
            "collision_penalty",
            "offtrack_penalty",
            "finish_bonus",
            "finish_rank_bonus",
            "first_place_bonus",
            "failure_penalty",
        ):
            if self.number("reward", key) < 0:
                raise ConfigError(f"{key} não pode ser negativo")
        if self.integer("episode", "prestart_max_steps") < 1:
            raise ConfigError("prestart_max_steps deve ser >= 1")
        if self.integer("episode", "max_steps") < 1:
            raise ConfigError("max_steps deve ser >= 1")
        if self.integer("episode", "no_progress_steps") < 1:
            raise ConfigError("no_progress_steps deve ser >= 1")
        if self.integer("episode", "progress_epsilon") < 0:
            raise ConfigError("progress_epsilon não pode ser negativo")
        if self.boolean("controls", "enable_turbo") and not self.text(
            "controls", "turbo_button"
        ):
            raise ConfigError("enable_turbo=true exige turbo_button preenchido")
        if self.boolean("controls", "enable_turbo") and self.number(
            "normalization", "nitro_scale"
        ) != 3:
            raise ConfigError(
                "enable_turbo=true exige nitro_scale=3 para o inventário validado"
            )

        keys: set[str] = set()
        for section in self.parser.sections():
            for key in self.parser[section]:
                if key in keys:
                    raise ConfigError(f"Chave repetida entre secoes, ambigua no Lua: {key}")
                keys.add(key)
        for key in self.parser["memory"]:
            if key.endswith("_address") or key == "racer_table_base":
                if not 0 <= self.integer("memory", key) < 131071:
                    raise ConfigError(f"Endereco fora da WRAM: {key}")
        if self.text("memory", "memory_domain") != "WRAM":
            raise ConfigError("O perfil suporta apenas WRAM")
        buttons = [self.text("controls", k) for k in ("accelerate_button", "brake_button", "turbo_button")]
        if len(set(buttons)) != 3 or not set(buttons) <= {"A", "B", "X", "Y", "L", "R"}:
            raise ConfigError("Botoes SNES devem ser validos e distintos")
        if self.text("experiment", "reward_profile") not in ("legacy_corrigido", "road_v1", "road_v2", "road_v3_turbo", "road_v4_driving", "road_v5_race", "road_v6_outcome"):
            raise ConfigError("Perfil de recompensa desconhecido")
        if self.integer("experiment", "track_length_expected") != 22528 or self.integer("experiment", "total_laps_expected") != 3:
            raise ConfigError("Esta base valida somente Las Vegas, 22528 unidades e 3 voltas")
        if self.manual_transmission:
            if buttons != ["X", "Y", "A"] or not self.boolean("controls", "enable_turbo"):
                raise ConfigError("Manual validado com Type A: X/Y/A e R/L; turbo habilitado")
            if self.integer("protocol", "savestate_slot") != 2 or self.frame_repeat != 4:
                raise ConfigError("Manual experimental exige slot 2 e quatro frames")
            if self.text("experiment", "reward_profile") != "road_v5_race":
                raise ConfigError("Manual exige objetivo road_v5_race")
        if self.blue_auto_expected:
            if self.manual_transmission or buttons != ["X", "Y", "A"]:
                raise ConfigError("Azul automatico exige cambio automatico e controles Type A")
            if self.integer("protocol", "savestate_slot") != 3 or self.frame_repeat != 4:
                raise ConfigError("Azul automatico experimental exige slot 3 e quatro frames")
            if self.text("experiment", "reward_profile") not in ("road_v5_race", "road_v6_outcome"):
                raise ConfigError("Azul automatico exige objetivo road_v5_race ou road_v6_outcome")
        if self.text("experiment", "reward_profile") == "road_v6_outcome" and not self.blue_auto_expected:
            raise ConfigError("road_v6_outcome experimental exige o perfil azul automatico")
        rollout, batch = self.integer("ppo", "n_steps"), self.integer("ppo", "batch_size")
        if rollout < 2 or batch < 2 or rollout % batch:
            raise ConfigError("n_steps >= 2 deve ser divisivel por batch_size >= 2 (um emulador)")
        for key in ("gamma", "gae_lambda"):
            if not 0 < self.number("ppo", key) <= 1:
                raise ConfigError(f"{key} fora de (0,1]")
        for key in ("learning_rate", "clip_range", "max_grad_norm", "target_kl"):
            if self.number("ppo", key) <= 0:
                raise ConfigError(f"{key} deve ser positivo")
        for key in ("n_epochs", "torch_threads"):
            if self.integer("ppo", key) < 1:
                raise ConfigError(f"{key} deve ser >= 1")
        for key in ("ent_coef", "vf_coef"):
            if self.number("ppo", key) < 0:
                raise ConfigError(f"{key} nao pode ser negativo")

    def training_blockers(self) -> list[str]:
        blockers: list[str] = []
        if not self.boolean("identity", "profile_validated"):
            blockers.append("profile_validated=false")
        if not self.boolean("validation", "opponent_telemetry_validated"):
            blockers.append("opponent_telemetry_validated=false")
        if not self.boolean("validation", "surface_telemetry_validated"):
            blockers.append("surface_telemetry_validated=false")
        if not self.boolean("validation", "curve_telemetry_validated"):
            blockers.append("curve_telemetry_validated=false")
        if not self.boolean("controls", "controls_validated"):
            blockers.append("controls_validated=false")
        if not self.text("controls", "accelerate_button"):
            blockers.append("accelerate_button vazio")
        if not self.text("controls", "brake_button"):
            blockers.append("brake_button vazio")
        return blockers

    def assert_training_ready(self) -> None:
        blockers = self.training_blockers()
        if blockers:
            joined = "; ".join(blockers)
            raise ConfigError(
                "Treinamento bloqueado pelo perfil de segurança: "
                f"{joined}. Execute os diagnósticos no BizHawk antes de liberar."
            )


ACTION_NAMES = (
    "COAST",
    "ACCELERATE",
    "BRAKE",
    "LEFT_ACCELERATE",
    "RIGHT_ACCELERATE",
    "LEFT",
    "RIGHT",
    "LEFT_BRAKE",
    "RIGHT_BRAKE",
    "TURBO_ACCELERATE",
)
