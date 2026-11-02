"""Integracao sintetica: mascaras, contrato e sem troca das acoes do agente."""
import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_reward import ROOT, telemetry
from test_live_detector import packet, navigation_packet
from test_v3_experiment import SyntheticBridge
from env_topgear import TopGearEnv
from experiment import contract, assert_live_preflight
from telemetry import ObservationBuilder
from topgear_config import ProjectConfig
from protocol import ProtocolError
import preflight_live


class NavigationIntegrationTests(unittest.TestCase):
    def test_runtime_requires_new_packet_and_allows_masked_identity(self):
        state = telemetry(track_length=22528, lateral=0)
        state = replace(state, detector_samples=packet(state))
        with self.assertRaisesRegex(ProtocolError, 'Navegacao sem historico'):
            state.assert_runtime_ready(require_detector=True)
        nav = navigation_packet(state)
        # Offset igual ao de P1: dados disponiveis, identidade inutilizavel.
        nav = ';'.join(','.join([s.split(',')[0], '0', '0', *s.split(',')[3:]]) for s in nav.split(';'))
        state = replace(state, navigation_samples=nav)
        state.assert_runtime_ready(require_detector=True)
        builder = ObservationBuilder(ProjectConfig.load(ROOT))
        obs = builder.build(state)
        self.assertEqual(obs.shape, (61,))
        self.assertEqual(obs[47], 0)
        self.assertEqual(obs[48], 0)
        self.assertEqual(obs[60], 0)
        self.assertFalse(any(r['id'] == 1 for r in builder.detector_rows))
        self.assertIn('player_offsets_invalid', builder.navigation['reasons'])

    def test_p2_is_visible_and_action_is_never_replaced(self):
        class SpyBridge(SyntheticBridge):
            def step(self, action):
                self.received_action = action
                return super().step(action)
        bridge = SpyBridge(terminate_after=100)
        with patch('env_topgear.BridgeClient', return_value=bridge), contextlib.redirect_stdout(io.StringIO()):
            env = TopGearEnv(ROOT)
        self.addCleanup(env.close)
        obs, info = env.reset()
        self.assertEqual(obs[48], 1)
        self.assertIn('navigation', info)
        for action in (0, 2, 3, 4, 9):
            obs, _, _, _, info = env.step(action)
            self.assertEqual(bridge.received_action, action)
            self.assertEqual(obs[47], 1)
            self.assertEqual(obs[53], 1)  # P2 prediction_valid
            self.assertIn('navigation_samples', info['raw_telemetry'])

    def test_preflight_does_not_approve_invalid_identity_masks(self):
        class InvalidBridge(SyntheticBridge):
            def response(self):
                response = super().response()
                nav = response.fields['navigation_samples']
                response.fields['navigation_samples'] = ';'.join(
                    ','.join([s.split(',')[0], '0', '0', *s.split(',')[3:]]) for s in nav.split(';'))
                return response
        with tempfile.TemporaryDirectory() as directory:
            cfg = replace(ProjectConfig.load(ROOT), project_dir=Path(directory))
            with patch('preflight_live.ProjectConfig.load', return_value=cfg), \
                 patch('preflight_live.BridgeClient', return_value=InvalidBridge(terminate_after=1000)), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'Preflight reprovado'):
                    preflight_live.main()
            receipt = json.loads((Path(directory)/'runs/preflight/latest.json').read_text(encoding='utf-8'))
            self.assertFalse(receipt['checks']['navigation_identity_and_corridor_every_frame'])
            self.assertFalse(receipt['checks']['p2_prediction_seen'])
            with self.assertRaises(ValueError):
                assert_live_preflight(cfg, contract(cfg))
