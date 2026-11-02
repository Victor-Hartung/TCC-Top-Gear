from __future__ import annotations
import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from test_reward import telemetry, ROOT
from test_telemetry import telemetry as observed
from test_race_end import FakeBridge
from env_topgear import TopGearEnv
from protocol import ProtocolError
from reward import RewardEngine, RewardWeights, profile_weights
from telemetry import ObservationBuilder, OBSERVATION_NAMES
from topgear_config import ProjectConfig, ConfigError
from replay_rewards import analyze
from opponent_analysis import signed_track_gap, decode_records, candidates, Racer
from experiment import atomic_json


class V3LogicTests(unittest.TestCase):
    def setUp(self):
        self.cfg = ProjectConfig.load(ROOT)
        self.engine = RewardEngine(profile_weights(RewardWeights.from_config(self.cfg), 'road_v2'), 'road_v2')

    def test_recorded_trajectories_reconcile_old_reward_and_reverse_discounted_preference(self):
        result = analyze(ROOT / 'archive/evidence/avaliacao_20260908_181515_799660.json', self.cfg)
        model, accelerate = result['episodes']
        for ep in result['episodes']:
            self.assertAlmostEqual(ep['legacy_reconciliation_error'], 0)
        def score(ep, profile):
            return next(r['discounted_return'] for r in ep['results'] if r['profile']==profile and r['gamma']==.99)
        self.assertGreater(score(model, 'legacy_corrigido'), score(accelerate, 'legacy_corrigido'))
        self.assertGreater(score(accelerate, 'road_v2'), score(model, 'road_v2'))

    def test_progress_backtrack_and_recovery_cannot_pay_twice(self):
        a,b = telemetry(progress=1000),telemetry(progress=1100)
        first=self.engine.calculate(a,b)
        reverse=self.engine.calculate(b,a)
        recover=self.engine.calculate(a,b)
        self.assertGreater(first.components['progress'],0)
        self.assertEqual(reverse.components['progress'],0)
        self.assertEqual(recover.components['progress'],0)

    def test_collision_displacement_and_immediate_recovery_do_not_pay_progress(self):
        a=telemetry(progress=1000)
        b=telemetry(progress=1100,collision=1,collision_events=1)
        c=telemetry(progress=1200,collision=0,collision_events=1)
        self.assertEqual(self.engine.calculate(a,b).components['progress'],0)
        self.assertEqual(self.engine.calculate(b,c).components['progress'],0)

    def test_unknown_surface_never_earns_progress(self):
        r=self.engine.calculate(telemetry(),telemetry(progress=1050,surface_unknown=1,offtrack=1))
        self.assertEqual(r.components['progress'],0)

    def test_offroad_excursion_and_recovery_highwater(self):
        a=telemetry(progress=1000)
        b=telemetry(progress=1100,offtrack=1)
        c=telemetry(progress=1200)
        self.engine.calculate(a,b)
        self.engine.calculate(b,c)
        self.engine.calculate(c,a)
        self.assertEqual(self.engine.calculate(a,c).components['progress'],0)

    def test_rank_oscillation_cannot_pay_repeated_improvements(self):
        a,b=telemetry(rank=10),telemetry(rank=9)
        first=self.engine.calculate(a,b)
        loss=self.engine.calculate(b,a)
        second=self.engine.calculate(a,b)
        self.assertGreater(first.components['rank_delta'],0)
        self.assertLess(loss.components['rank_delta'],0)
        self.assertEqual(second.components['rank_delta'],0)

    def test_timeout_is_failure_not_completion(self):
        result=self.engine.calculate(telemetry(),telemetry(finished=1,final_rank=19,lap=0))
        self.assertEqual(result.components['finish'],0)
        self.assertLess(result.components['incomplete'],0)

    def test_receding_opponent_switch_resets_velocity_mask(self):
        builder=ObservationBuilder(self.cfg)
        builder.reset(observed(frame=100))
        same=builder.build(observed(frame=104,nearest_distance=600))
        self.assertLess(same[OBSERVATION_NAMES.index('closing_rate_norm')],0)
        self.assertEqual(same[OBSERVATION_NAMES.index('closing_rate_valid')],1)
        switched=builder.build(observed(frame=108,nearest_id=8,nearest_distance=5))
        self.assertEqual(switched[OBSERVATION_NAMES.index('closing_rate_valid')],0)

    def test_velocity_derivative_independent_of_frame_interval(self):
        a,b=ObservationBuilder(self.cfg),ObservationBuilder(self.cfg)
        a.reset(observed(frame=100,nearest_distance=500)); b.reset(observed(frame=100,nearest_distance=500))
        oa=a.build(observed(frame=104,nearest_distance=460))
        ob=b.build(observed(frame=108,nearest_distance=420))
        i=OBSERVATION_NAMES.index('closing_rate_norm')
        self.assertEqual(oa[i],ob[i])

    def test_backward_motion_is_visible(self):
        obs=ObservationBuilder(self.cfg).reset(observed(speed=-500))
        self.assertLess(obs[0],0)

    def test_circular_gap_sees_lapped_car_physically_behind(self):
        self.assertEqual(signed_track_gap(100,90,22528),-10)
        self.assertEqual(signed_track_gap(22520,10,22528),18)
        rear=candidates([Racer(7,90,500,3)],100,400,22528)[0]
        self.assertEqual(rear['region_candidate'],'rear')
        self.assertFalse(rear['validated'])

    def test_entity_ids_are_stable_while_records_reorder(self):
        raw=bytearray(360)
        for i in range(18):
            raw[i*18]=i+2
            raw[i*18+7:i*18+9]=(100+i).to_bytes(2,'little')
        original=decode_records(raw)
        raw[0:18],raw[18:36]=raw[18:36],raw[0:18]
        self.assertEqual(sorted(original,key=lambda r:r.identity),sorted(decode_records(raw),key=lambda r:r.identity))
        raw[0]=raw[18]
        with self.assertRaises(ValueError): decode_records(raw)

    def test_nonfinite_config_is_rejected(self):
        for key,value in [('gamma','NaN'),('learning_rate','inf')]:
            parser=copy.deepcopy(self.cfg.parser); parser.set('ppo',key,value)
            with self.assertRaises(ConfigError): replace(self.cfg,parser=parser).validate_structure()

    def test_atomic_write_retries_transient_windows_permission_error(self):
        with tempfile.TemporaryDirectory() as d:
            import os
            actual=os.replace
            calls=[]
            def intermittent(src,dst):
                calls.append(1)
                if len(calls)==1: raise PermissionError('sharing violation simulated')
                return actual(src,dst)
            with patch('experiment.os.replace',side_effect=intermittent): atomic_json(Path(d)/'result.json',{'whole':True})
            self.assertEqual(len(calls),2)

    def test_environment_rejects_float_bool_and_step_after_terminal(self):
        bridge=FakeBridge(telemetry(frame=104,finished=1,final_rank=19))
        with patch('env_topgear.BridgeClient',return_value=bridge): env=TopGearEnv(ROOT)
        env._telemetry=lambda state:state
        try:
            env.reset()
            for action in (True,1.5,11,-1):
                with self.assertRaises(ValueError): env.step(action)
            env.step(1)
            with self.assertRaises(ProtocolError): env.step(1)
        finally: env.close()

    def test_stall_is_truncation_in_new_objective(self):
        bridge=FakeBridge(telemetry(frame=104))
        with patch('env_topgear.BridgeClient',return_value=bridge): env=TopGearEnv(ROOT)
        env._telemetry=lambda state:state
        try:
            env.no_progress_limit=1
            env.reset()
            _,_,terminated,truncated,info=env.step(0)
            self.assertFalse(terminated); self.assertTrue(truncated)
            self.assertEqual(info['termination_reason'],'no_progress')
        finally: env.close()

    def test_terminal_savestate_is_rejected(self):
        bridge=FakeBridge(telemetry())
        with patch('env_topgear.BridgeClient',return_value=bridge): env=TopGearEnv(ROOT)
        env._telemetry=lambda state:telemetry(finished=1,final_rank=19)
        try:
            with self.assertRaisesRegex(ProtocolError,'Savestate'): env.reset()
        finally: env.close()


if __name__=='__main__': unittest.main()
