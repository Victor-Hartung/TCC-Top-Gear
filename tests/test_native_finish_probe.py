"""Offline Lua/Python probe checks; no BizHawk/game-memory validation."""
import unittest
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from test_reward import ROOT
import test_lua_bridge
import test_finish_diagnostic
import test_v3_experiment
import diagnose_finish_live
from native_finish_probe import FIELDS, parse_samples, summarize, NativeFinishBridge
from protocol import ProtocolError, parse_message, ACTION_PREFIX


class NativeFinishProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_lua_bridge.LuaBridgeTests.setUpClass()

    def execute(self, commands):
        return test_lua_bridge.LuaBridgeTests().execute_bridge(commands,
            script_path=ROOT/'lua/diagnostico_fim_corrida.lua')

    def test_probe_does_not_change_controls_reset_or_original_telemetry(self):
        commands=test_lua_bridge.LuaBridgeTests.commands(action=3)
        baseline, controls, paused, _=test_lua_bridge.LuaBridgeTests().execute_bridge(commands)
        commands[0]['finish_probe']=1
        actual, probe_controls, probe_paused, _=self.execute(commands)
        self.assertEqual(probe_controls, controls)
        self.assertEqual(probe_paused, paused)
        for old, new in zip(baseline, actual):
            self.assertEqual(old,{k:v for k,v in new.items() if k not in ('finish_probe','finish_samples')})
        reset=parse_samples(actual[1]);step=parse_samples(actual[2],100)
        self.assertEqual([s['frame'] for s in reset+step],list(range(100,105)))
        self.assertEqual(step[-1]['lap'],0)
        self.assertEqual(step[-1]['final_rank'],-1)

    def test_ordinary_training_hello_is_refused_before_any_action(self):
        states, controls, paused, _=self.execute(test_lua_bridge.LuaBridgeTests.commands())
        self.assertEqual(states[-1]['status'],'error')
        self.assertIn('apenas de diagnostico',states[-1]['error'])
        self.assertEqual(controls,[])
        self.assertTrue(paused)

    def test_nlua_main_chunk_from_foreign_directory_uses_profile_picker(self):
        commands=test_lua_bridge.LuaBridgeTests.commands();commands[0]['finish_probe']=1
        with tempfile.TemporaryDirectory() as d, contextlib.chdir(d):
            states, controls, paused, _=test_lua_bridge.LuaBridgeTests().execute_bridge(
                commands, script_path=ROOT/'lua/diagnostico_fim_corrida.lua',script_as_text=True)
        self.assertEqual([s['status'] for s in states],['ready','ok','ok','closed'])
        self.assertEqual(len(parse_samples(states[2],100)),4)
        self.assertEqual(len(controls),4)
        self.assertTrue(paused)

    def test_reset_clears_previous_probe_history(self):
        commands=test_lua_bridge.LuaBridgeTests.commands()
        commands[0]['finish_probe']=1
        commands[3]={'episode':2,'seq':4,'kind':'reset','action':0,'frames':0}
        commands.append({'episode':2,'seq':5,'kind':'close','action':0,'frames':0})
        states, _, _, _=self.execute(commands)
        self.assertEqual(len(parse_samples(states[3])),1)
        self.assertEqual(parse_samples(states[1]),parse_samples(states[3]))

    def test_invalid_or_missing_frame_samples_fail_closed(self):
        commands=test_lua_bridge.LuaBridgeTests.commands();commands[0]['finish_probe']=1
        states, _, _, _=self.execute(commands);good=states[2]
        cases=[{**good,'finish_probe':'0'},
               {**good,'finish_samples':good['finish_samples'].split(';')[-1]},
               {**good,'speed':'2000'},
               {**good,'finish_samples':'1,2,3'}]
        for fields in cases:
            with self.subTest(fields=fields),self.assertRaises(ProtocolError):
                parse_samples(fields,100)

    def test_summary_keeps_cutoff_and_late_crossing_separate(self):
        blank=dict.fromkeys(FIELDS,0)
        before={**blank,'frame':10,'finishers':9,'lap':2,'total_laps':3,'final_rank':-1}
        for i in range(20):before[f'finish_order_{i}']=i+1
        cutoff={**before,'frame':11,'finishers':10,'final_rank':11,'message_id':35}
        late={**cutoff,'frame':123,'finishers':11,'lap':3,'final_rank':10,'finish_order_10':0}
        result=summarize([before,cutoff,late])
        self.assertEqual(result['first_ten_finishers']['frame'],11)
        self.assertEqual(result['first_result']['frame'],11)
        self.assertEqual(result['first_lap_three']['frame'],123)
        self.assertEqual(result['first_p1_in_finish_order']['frame'],123)
        self.assertNotIn('race_completed',result)

    def test_native_hello_is_explicit_and_does_not_change_step(self):
        bridge=object.__new__(NativeFinishBridge)
        for kind in ['hello','step']:
            text=bridge._command_text(kind=kind,action=0,frames=0,episode=0,seq=1)
            fields=parse_message(text,ACTION_PREFIX)
            self.assertEqual(fields.get('finish_probe'),'1' if kind=='hello' else None)

    def test_native_replay_cli_saves_all_samples_and_provenance(self):
        class ProbeBridge(test_v3_experiment.SyntheticBridge):
            def response(self, **kwargs):
                state=super().response(**kwargs)
                fields=state.fields
                frame=int(fields['frame'])
                frames=range(frame-3,frame+1) if self.counter else [frame]
                samples=[]
                for f in frames:
                    sample=dict.fromkeys(FIELDS,0)
                    for key in ('lap','final_rank','rank','speed','fuel','progress','total_laps'):
                        sample[key]=int(fields[key])
                    sample['frame']=f
                    samples.append(','.join(str(sample[k]) for k in FIELDS))
                fields.update(finish_probe='1',finish_samples=';'.join(samples))
                return state
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cfg,run=test_finish_diagnostic.FinishDiagnosticTests().make_source(root)
            (root/'lua').mkdir()
            for name in ('diagnostico_fim_corrida.lua','Top Gear (USA).lua'):
                (root/'lua'/name).write_bytes((ROOT/'lua'/name).read_bytes())
            bridge=ProbeBridge(terminate_after=3)
            with patch('diagnose_finish_live.ProjectConfig.load',return_value=cfg), \
                 patch('diagnose_finish_live.NativeFinishBridge',return_value=bridge), \
                 patch('sys.argv',['diagnose_finish_live.py','--native-probe','--run',str(run),
                                   '--episode','1','--tail-steps','2']), \
                 contextlib.redirect_stdout(io.StringIO()):
                diagnose_finish_live.main()
            report=json.loads(next((root/'runs/diagnostico_termino').glob('*.json')).read_text())
            self.assertEqual(report['status'],'completed')
            self.assertEqual(len(report['native_samples']),21)
            self.assertEqual(report['native_probe_version'],1)
            self.assertIn('probe_lua_sha256',report)
            self.assertIn('native_summary',report)
            self.assertEqual(bridge.resets,1)


if __name__=='__main__':unittest.main()
