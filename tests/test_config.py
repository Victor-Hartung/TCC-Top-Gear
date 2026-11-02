from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from topgear_config import ProjectConfig  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_profile_is_ready_after_live_validation(self) -> None:
        config = ProjectConfig.load(ROOT)
        blockers = config.training_blockers()
        self.assertEqual(blockers, [])
        self.assertTrue(config.boolean("identity", "profile_validated"))
        config.assert_training_ready()

    def test_rom_and_entity_layout(self) -> None:
        config = ProjectConfig.load(ROOT)
        self.assertEqual(
            config.text("identity", "rom_sha1"),
            "f686806c676a4b087a3627babbe3555d3704e3b1",
        )
        self.assertEqual(config.integer("memory", "racer_table_base"), 0x0212)
        self.assertEqual(config.integer("memory", "racer_record_stride"), 0x12)
        self.assertEqual(config.integer("memory", "racer_count"), 20)
        self.assertEqual(config.integer("memory", "progress_address"), 0x1ED7)
        self.assertEqual(config.text("protocol", "transport"), "socket")
        self.assertEqual(config.text("protocol", "socket_host"), "127.0.0.1")
        self.assertEqual(config.integer("protocol", "socket_port"), 55355)
        self.assertTrue(config.boolean("controls", "controls_validated"))
        self.assertTrue(
            config.boolean("validation", "opponent_telemetry_validated")
        )
        self.assertTrue(config.boolean("validation", "surface_telemetry_validated"))
        self.assertTrue(config.boolean("validation", "curve_telemetry_validated"))
        self.assertEqual(config.integer("memory", "curve_progress_address"), 0x0046)
        self.assertEqual(config.integer("memory", "surface_state_address"), 0x0727)
        self.assertEqual(config.integer("geometry", "surface_left_value"), 0)
        self.assertEqual(config.integer("geometry", "surface_road_value"), 1)
        self.assertEqual(config.integer("geometry", "surface_right_value"), 2)
        self.assertEqual(config.integer("geometry", "same_lane_half_width"), 4096)
        self.assertEqual(config.integer("geometry", "lateral_curve_table"), 0x4C00)
        self.assertEqual(config.integer("geometry", "road_type_table"), 0x5800)
        self.assertEqual(config.text("controls", "turbo_button"), "A")
        self.assertTrue(config.boolean("controls", "enable_turbo"))
        self.assertEqual(config.integer("normalization", "nitro_scale"), 3)
        self.assertEqual(config.integer("normalization", "curve_scale"), 32)
        self.assertEqual(config.action_count, 10)

        lua_source = (ROOT / "lua" / "Top Gear (USA).lua").read_text(
            encoding="utf-8"
        )
        self.assertIn("local function decode_nitro(raw)", lua_source)
        self.assertIn("nitro=nitro_available", lua_source)
        self.assertIn("turbo_active=turbo_active", lua_source)
        self.assertIn('surface=number("surface_state_address")', lua_source)
        self.assertIn("surface_direction=surface_direction", lua_source)
        self.assertIn("surface_unknown=surface_unknown", lua_source)
        self.assertNotIn("Estado de superficie inesperado", lua_source)
        self.assertIn("curve_current=curve_current", lua_source)
        self.assertIn("curve_ahead_2048=curve_ahead_2048", lua_source)
        self.assertIn("comm.socketServerResponse()", lua_source)
        self.assertIn("comm.socketServerSend", lua_source)
        self.assertIn("client.unpause()", lua_source)
        self.assertIn("emu.yield()", lua_source)
        self.assertNotIn("emu.frameadvance()", lua_source)
        self.assertNotIn("client.exactsleep", lua_source)

    def test_player_and_racer_progress_have_distinct_offsets(self) -> None:
        self.assertIn(
            "progress_address = 0x1ED7",
            (ROOT / "config" / "game_profile.ini").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "read_u16(base + 7)",
            (ROOT / "lua" / "Top Gear (USA).lua").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "signed_u8(read_u8(base + 9)) - 1",
            (ROOT / "lua" / "Top Gear (USA).lua").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "memory.read_u16_le(record + 7)",
            (ROOT / "lua" / "diagnostico_adversarios.lua").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
