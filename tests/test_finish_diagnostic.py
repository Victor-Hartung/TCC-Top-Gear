"""Replay e cauda do diagnostico com ponte simulada; sem emulacao real."""
import contextlib
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_reward import ROOT
import diagnose_finish_live
from experiment import contract
from telemetry import Telemetry
from topgear_config import ProjectConfig
from test_v3_experiment import SyntheticBridge


class FinishDiagnosticTests(unittest.TestCase):
    def make_source(self, root):
        cfg=replace(ProjectConfig.load(ROOT),project_dir=root)
        run=root/'source';run.mkdir()
        (run/'run_config.json').write_text(json.dumps({'contract':contract(cfg,'road_v2')}))
        bridge=SyntheticBridge(terminate_after=3)
        start=Telemetry.from_fields(bridge.reset().fields)
        rows=[{'episode_id':1,'event':'reset','state':{'raw_telemetry':asdict(start)}}]
        for action in [1,3,4]:
            t=Telemetry.from_fields(bridge.step(action).fields)
            rows.append({'episode_id':1,'event':'step','action':action,
                         'state':{'raw_telemetry':asdict(t),'race_ended':int(t.race_ended)}})
        (run/'steps.jsonl').write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
        return cfg,run

    def test_records_after_published_result_without_auto_reset(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cfg,run=self.make_source(root);bridge=SyntheticBridge(terminate_after=3)
            with patch('diagnose_finish_live.ProjectConfig.load',return_value=cfg), \
                 patch('diagnose_finish_live.BridgeClient',return_value=bridge), \
                 patch('sys.argv',['diagnose_finish_live.py','--run',str(run),'--episode','1','--tail-steps','2']), \
                 contextlib.redirect_stdout(io.StringIO()):
                diagnose_finish_live.main()
            report=json.loads(next((root/'runs/diagnostico_termino').glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual(report['status'],'completed')
            self.assertEqual(len(report['replay_states']),3)
            self.assertEqual(len(report['tail_states']),2)
            self.assertEqual(report['frames_after_first_result'],8)
            self.assertEqual(bridge.resets,1)
            self.assertTrue(bridge.closed)

    def test_divergence_is_saved_and_stops_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cfg,run=self.make_source(root)
            class ChangedBridge(SyntheticBridge):
                def step(self,action):
                    super().step(action)
                    self.current=replace(self.current,speed=self.current.speed+1)
                    return self.response()
            with patch('diagnose_finish_live.ProjectConfig.load',return_value=cfg), \
                 patch('diagnose_finish_live.BridgeClient',return_value=ChangedBridge(terminate_after=3)), \
                 patch('sys.argv',['diagnose_finish_live.py','--run',str(run),'--episode','1']), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'divergiu'):diagnose_finish_live.main()
            report=json.loads(next((root/'runs/diagnostico_termino').glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual(report['status'],'failed')
            self.assertIn('expected_at_divergence',report)
            self.assertEqual(report['tail_states'],[])
