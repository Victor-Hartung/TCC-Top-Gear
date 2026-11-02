"""Integracao manual offline. APIs simuladas nao validam novo treino no BizHawk."""
from __future__ import annotations
import contextlib
import copy
import io
import os
import tempfile
import zipfile
from pathlib import Path
import unittest
from dataclasses import replace
from unittest.mock import patch
import numpy as np
from test_reward import ROOT, telemetry
from topgear_config import ProjectConfig, ConfigError
from telemetry import ObservationBuilder, observation_names
from experiment import contract, validate_checkpoint, assert_live_preflight, atomic_json, contract_hash, sha256
from manual_transmission import decode_action, validate_wire
from protocol import ProtocolError
import test_lua_bridge
from env_topgear import TopGearEnv
from test_race_end import FakeBridge


def manual_config():
    with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_manual.ini'):
        return ProjectConfig.load(ROOT)


class ManualPPOTests(unittest.TestCase):
    def test_contract_separation_and_shapes(self):
        auto=ProjectConfig.load(ROOT); manual=manual_config()
        self.assertEqual((auto.action_count,len(observation_names(auto)),auto.bridge_revision),(10,61,5))
        self.assertEqual((manual.action_count,len(observation_names(manual)),manual.bridge_revision),(30,63,6))
        self.assertNotEqual(contract(auto),contract(manual))
        self.assertEqual(contract(manual)['savestate_slot'],2)
        for action in range(30):
            base,shift=decode_action(action)
            self.assertEqual(base,action%10)
            self.assertEqual(shift,(0,1,-1)[action//10])

    def test_old_checkpoint_rejected_without_loading_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            old=Path(directory)/'old.zip'
            with zipfile.ZipFile(old,'w') as archive:
                archive.writestr('data','{}');archive.writestr('policy.pth',b'offline fixture')
            previous=contract(ProjectConfig.load(ROOT))
            atomic_json(old.with_suffix('.zip.json'),dict(contract=previous,contract_sha256=contract_hash(previous),model_sha256=sha256(old)))
            with self.assertRaisesRegex(ValueError,'incompativel'):
                validate_checkpoint(old,contract(manual_config()))

    def test_old_preflight_cannot_unlock_manual(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=replace(manual_config(),project_dir=Path(directory))
            atomic_json(cfg.project_dir/'runs/preflight/latest.json',dict(status='passed',execution='live_bizhawk'))
            with self.assertRaises(ValueError):
                assert_live_preflight(cfg,contract(cfg))

    def test_missing_and_signed_gauge_and_button_state(self):
        cfg=manual_config(); b=ObservationBuilder(cfg)
        with self.assertRaises(ProtocolError):b.reset(telemetry())
        for raw in (-32768,0,2048,32767):
            t=telemetry(engine_gauge_raw=raw)
            obs=b.reset(t)
            self.assertEqual(obs.shape,(63,))
            self.assertEqual(obs[-1],0)
            for shift in (-1,0,1):
                obs=b.build(t,shift_command=shift)
                self.assertEqual(obs[-2],raw/32768)
                self.assertEqual(obs[-1],shift)
                self.assertTrue(np.all(obs>=b.low(cfg)))
                self.assertTrue(np.all(obs<=b.high(cfg)))

    def test_wrong_manual_identity_refused(self):
        fields=dict(manual_mode='1',car_table_offset_raw='48',upshift_mask_raw='16',downshift_mask_raw='32',gear='4',engine_gauge_raw='2048')
        validate_wire(fields)
        for key,value in [('manual_mode','0'),('car_table_offset_raw','0'),('upshift_mask_raw','0'),('gear','5'),('engine_gauge_raw','32768')]:
            with self.assertRaises(ProtocolError):validate_wire({**fields,key:value})
        with self.assertRaises(ProtocolError):validate_wire({k:v for k,v in fields.items() if k!='engine_gauge_raw'})

    def test_environment_sends_composite_and_rewards_base(self):
        cfg=manual_config()
        class ManualBridge(FakeBridge):
            def reset(self):return replace(super().reset(),engine_gauge_raw=1600)
            def step(self,action):self.action=action;return super().step(action)
        bridge=ManualBridge(telemetry(frame=104,engine_gauge_raw=1700,gear=4,speed=3300))
        with patch('env_topgear.ProjectConfig.load',return_value=cfg),patch('env_topgear.BridgeClient',return_value=bridge),contextlib.redirect_stdout(io.StringIO()):
            env=TopGearEnv(ROOT)
        env._telemetry=lambda state:state
        try:
            env.reset()
            with patch.object(env._reward_engine,'calculate',wraps=env._reward_engine.calculate) as calculate:
                obs,reward,terminated,truncated,info=env.step(19)
            self.assertEqual(bridge.action,19)
            self.assertEqual(calculate.call_args.kwargs['action'],9)
            self.assertEqual(info['action_name'],'TURBO_ACCELERATE_SHIFT_UP')
            self.assertEqual(info['shift_command'],1)
            self.assertEqual(obs[-1],1)
            self.assertNotIn('reward_manual_speed_potential',info)
            self.assertAlmostEqual(reward, sum(value for key,value in info.items()
                                               if key.startswith('reward_') and key!='reward_invalid_progress_jump'))
            self.assertEqual(env.reset()[0][-1],0)
        finally:env.close()

    def test_actual_lua_all_combinations_no_extra_frames(self):
        if test_lua_bridge.LuaRuntime is None:self.skipTest('lupa unavailable')
        harness=test_lua_bridge.LuaBridgeTests()
        harness.setUpClass()
        def initialize(ram):
            for addr,value in [(0x1EE8,48),(0x1F7A,16),(0x1F7C,32),(0x1E5E,2048)]:
                ram[addr:addr+2]=value.to_bytes(2,'little')
        for action in range(30):
            with self.subTest(action=action):
                states,history,paused,messages=harness.execute_bridge(harness.commands(action),initialize_hook=initialize,profile_path=ROOT/'config/game_profile_manual.ini')
                self.assertEqual([s['status'] for s in states],['ready','ok','ok','closed'],messages)
                self.assertEqual(states[0]['bridge_revision'],'6')
                validate_wire(states[1]);validate_wire(states[2])
                self.assertEqual(len(history),4)
                for buttons in history:
                    base,shift=decode_action(action)
                    self.assertEqual(buttons['R'],shift==1)
                    self.assertEqual(buttons['L'],shift==-1)
                    self.assertEqual(buttons['X'],base in (1,3,4,9))
                    self.assertEqual(buttons['Y'],base in (2,7,8))
                    self.assertEqual(buttons['A'],base==9)
                    self.assertEqual(buttons['Left'],base in (3,5,7))
                    self.assertEqual(buttons['Right'],base in (4,6,8))
        states,_,_,_=harness.execute_bridge(harness.commands(30),initialize_hook=initialize,profile_path=ROOT/'config/game_profile_manual.ini')
        self.assertEqual(states[-1]['status'],'error')

    def test_manual_wrapper_selects_profile_in_lua_console(self):
        if test_lua_bridge.LuaRuntime is None:self.skipTest('lupa unavailable')
        harness=test_lua_bridge.LuaBridgeTests();harness.setUpClass()
        states,_,_,messages=harness.execute_bridge(harness.commands(),
            script_path=ROOT/'lua/Top Gear Manual (USA).lua',script_as_text=True,
            profile_path=ROOT/'config/game_profile_manual.ini')
        self.assertEqual([s['status'] for s in states],['ready','ok','ok','closed'],messages)
        self.assertEqual(states[0]['bridge_revision'],'6')

    def test_manual_preflight_rejects_missing_shift_and_accepts_edge_controls(self):
        from test_v3_experiment import SyntheticBridge
        from preflight_live import check_manual_controls
        class GearBridge(SyntheticBridge):
            def __init__(self,respond=True):
                super().__init__(terminate_after=1000)
                self.initial=replace(self.initial,gear=0,engine_gauge_raw=1200)
                self.last=0;self.respond=respond
            def step(self,action):
                base,shift=decode_action(action)
                gear=self.current.gear
                if self.respond and shift and shift!=self.last:gear=max(0,min(4,gear+shift))
                self.last=shift
                super().step(base)
                self.current=replace(self.current,gear=gear,engine_gauge_raw=1200+self.counter)
                return self.response()
        report={'checks':{}}
        check_manual_controls(GearBridge(),manual_config(),report)
        self.assertTrue(all(report['checks'].values()))
        failed={'checks':{}}
        with self.assertRaisesRegex(ValueError,'Troca manual'):
            check_manual_controls(GearBridge(respond=False),manual_config(),failed)
        self.assertNotIn('manual_R_L_release_and_limits',failed['checks'])

    def test_manual_config_rejects_wrong_slot_and_buttons(self):
        cfg=manual_config()
        for section,key,value in [('protocol','savestate_slot','1'),('controls','accelerate_button','R'),('controls','enable_turbo','false')]:
            parser=copy.deepcopy(cfg.parser);parser.set(section,key,value)
            with self.assertRaises(ConfigError):replace(cfg,parser=parser).validate_structure()

if __name__=='__main__':unittest.main()
