"""Cenarios sinteticos: nao constituem validacao da contagem no BizHawk."""
import contextlib
import io
import unittest
from pathlib import Path
from dataclasses import replace, asdict
from unittest.mock import patch
from test_v3_experiment import SyntheticBridge
from test_telemetry import telemetry, ROOT
from env_topgear import TopGearEnv
from telemetry import ObservationBuilder
from topgear_config import ProjectConfig
from protocol import ProtocolError
from reward import RewardEngine, RewardWeights
from preflight_live import prepare_controls

class CountdownBridge(SyntheticBridge):
    def __init__(self, stuck=False):
        super().__init__(terminate_after=10000)
        self.initial = telemetry(track_length=22528, lap=-1, rank=-1, speed=0,
            nearest_valid=0, nearest_id=-1, nearest_distance=-1, opponent_count=0)
        self.current = self.initial
        self.actions = []
        self.stuck = stuck
    def step(self, action):
        self.actions.append(action)
        super().step(action)
        self.current = replace(self.current, speed=0 if self.stuck else min(self.current.speed,16000), lap=-1 if self.stuck or self.counter < 4 else 0,
                               rank=-1 if self.stuck or self.counter < 4 else 19)
        return self.response()

class CountdownTests(unittest.TestCase):
    def env(self, bridge):
        with patch('env_topgear.BridgeClient', return_value=bridge):
            env = TopGearEnv(ROOT)
        self.addCleanup(env.close)
        return env

    def test_start_actions_transition_and_repeated_reset(self):
        b=CountdownBridge();env=self.env(b)
        for _ in range(2):
            obs, info=env.reset()
            self.assertEqual(obs.shape,(61,));self.assertEqual(obs[3],-1)
            self.assertEqual(info['prestart'],1)
            for action in [0,2,4,1]:
                obs,reward,terminated,truncated,info=env.step(action)
                self.assertEqual(reward,-0.005);self.assertFalse(terminated or truncated)
            self.assertEqual(b.actions[-4:],[0,2,4,1])
            self.assertEqual(obs[3],0);self.assertEqual(info['net_progress'],0)
            self.assertEqual(env._no_progress_count,0)
        self.assertEqual(b.resets,2)

    def test_stuck_start_truncates_without_finish_bonus(self):
        env=self.env(CountdownBridge(stuck=True));env.reset()
        limit=env.config.integer('episode','prestart_max_steps')
        for i in range(limit):
            _,reward,terminated,truncated,info=env.step(0)
            self.assertFalse(terminated);self.assertEqual(truncated,i==limit-1)
            self.assertEqual(reward,-0.005)
        self.assertEqual(info['termination_reason'],'prestart_timeout')
        self.assertEqual(info['race_completed'],0)

    def test_regression_to_sentinel_is_rejected(self):
        b=CountdownBridge();env=self.env(b);env.reset()
        for _ in range(4):env.step(1)
        b.stuck=True
        with self.assertRaisesRegex(ProtocolError,'sentinela'):env.step(1)

    def test_sentinel_requires_explicit_permission_and_valid_profile(self):
        t=CountdownBridge().initial
        with self.assertRaises(ProtocolError):t.assert_runtime_ready()
        t.assert_runtime_ready(allow_prestart=True)
        for broken in [replace(t,rom_ok=0),replace(t,track_length=0),replace(t,lap=-2)]:
            with self.assertRaises(ProtocolError):broken.assert_runtime_ready(allow_prestart=True)

    def test_launch_prefix_is_bounded_and_recorded(self):
        b=CountdownBridge();cfg=ProjectConfig.load(ROOT);b.reset();states=[]
        with contextlib.redirect_stdout(io.StringIO()):
            end=prepare_controls(b,cfg,b.initial,states)
        self.assertEqual(end.lap,0);self.assertGreaterEqual(end.speed,1500)
        self.assertEqual(len(states),len(b.actions));self.assertTrue(all(a==1 for a in b.actions))
        b=CountdownBridge(stuck=True);b.reset();states=[]
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'limite'):prepare_controls(b,cfg,b.initial,states)
        self.assertEqual(len(states),cfg.integer('episode','prestart_max_steps'))

    def test_no_fake_progress_or_finish_at_start(self):
        cfg=ProjectConfig.load(ROOT)
        for profile in ['legacy_corrigido','road_v1','road_v2']:
            engine=RewardEngine(RewardWeights.from_config(cfg),profile)
            prev=telemetry(lap=-1,progress=22500,track_length=22528)
            current=replace(prev,lap=0,progress=30,rank=0)
            result=engine.calculate(prev,current)
            self.assertEqual(result.total,0);self.assertEqual(result.progress_delta,0)
            result=engine.calculate(current,replace(current,finished=1,final_rank=0,lap=1))
            self.assertFalse(result.finish_event);self.assertEqual(result.components['finish'],0)


class LaunchImpactTests(unittest.TestCase):
    def test_old_launch_impact_does_not_invalidate_clean_control_branches(self):
        import tempfile
        import json
        import preflight_live
        class ImpactBridge(CountdownBridge):
            def step(self, action):
                super().step(action)
                self.current=replace(self.current, collision=int(self.counter==2),
                                     collision_events=int(self.counter>=2))
                return self.response()
        with tempfile.TemporaryDirectory() as directory:
            cfg=replace(ProjectConfig.load(ROOT),project_dir=Path(directory))
            with patch('preflight_live.ProjectConfig.load',return_value=cfg), \
                 patch('preflight_live.BridgeClient',return_value=ImpactBridge()), \
                 contextlib.redirect_stdout(io.StringIO()):
                preflight_live.main()
            report=json.loads((Path(directory)/'runs/preflight/latest.json').read_text())
            self.assertEqual(report['status'],'passed')
            self.assertEqual(report['launch_collision_events'],dict.fromkeys(['coast','accelerate','brake','left','right'],1))

    def test_new_impact_in_control_window_still_fails(self):
        import tempfile
        import preflight_live
        class ImpactBridge(CountdownBridge):
            def step(self, action):
                super().step(action)
                self.current=replace(self.current, collision=int(self.counter==16),
                                     collision_events=int(self.counter>=16))
                return self.response()
        with tempfile.TemporaryDirectory() as directory:
            cfg=replace(ProjectConfig.load(ROOT),project_dir=Path(directory))
            with patch('preflight_live.ProjectConfig.load',return_value=cfg), \
                 patch('preflight_live.BridgeClient',return_value=ImpactBridge()), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'Ramo teve impacto'):
                    preflight_live.main()
