import contextlib
from dataclasses import replace
import io
import unittest
from unittest.mock import patch

from test_reward import ROOT, telemetry
from driving_strategy import PROFILE, SETTINGS, DrivingObjective, opportunity
from reward import RewardEngine, RewardWeights, profile_weights
from topgear_config import ProjectConfig
from train_hermes_ppo import arguments

CLEAR = dict(navigation_valid=True,target_valid=True,blocked_intervals=[])


class DrivingTests(unittest.TestCase):
    def state(self, **kw):
        return telemetry(**dict(dict(track_length=22528,speed=7000,curve_current=0,
                          curve_ahead_512=0,nitro=3,nitro_raw=3),**kw))

    def engine(self):
        base=RewardWeights.from_config(ProjectConfig.load(ROOT))
        return RewardEngine(profile_weights(base,PROFILE),PROFILE)

    def calc(self, p, c, action=1, navigation=CLEAR):
        return self.engine().calculate(p,c,action=action,navigation=navigation)

    def test_penalizes_only_unnecessary_lift_without_paying_for_button(self):
        p=self.state();c=replace(p,progress=p.progress+50)
        for action in (0,2,5,6,7,8):
            self.assertEqual(self.calc(p,c,action).components['unnecessary_lift'],-.015)
        for action in (1,3,4,9):
            self.assertEqual(self.calc(p,c,action).components['unnecessary_lift'],0)
        self.assertEqual(self.calc(p,p,1).components['progress'],0)

    def test_braking_exceptions_for_curve_obstacle_unknown_surface_and_impact(self):
        p=self.state()
        cases=[(replace(p,curve_current=16),CLEAR),(replace(p,offtrack=1),CLEAR),
               (replace(p,surface_unknown=1),CLEAR),(p,dict(CLEAR,blocked_intervals=[[-100,100]])),
               (p,{}),(replace(p,collision=1),CLEAR)]
        for state,nav in cases:
            self.assertEqual(self.calc(state,state,2,nav).components['unnecessary_lift'],0)
        self.assertEqual(self.calc(p,replace(p,collision=1,collision_events=1),2).components['unnecessary_lift'],0)

    def test_turbo_opportunity_uses_state_before_action(self):
        good=self.state();boost=replace(good,nitro=2,nitro_raw=0x8003,turbo_active=1,progress=1100)
        self.assertEqual(self.calc(good,boost,9).components['turbo_bad_activation'],0)
        for previous in (replace(good,speed=0),replace(good,lap=-1),replace(good,curve_ahead_512=16)):
            self.assertEqual(self.calc(previous,boost,9).components['turbo_bad_activation'],-2)
        self.assertEqual(self.calc(good,boost,9,dict(CLEAR,blocked_intervals=[[-500,500]])).components['turbo_bad_activation'],-2)

    def test_actual_consumption_not_repeated_turbo_requests(self):
        p=self.state(nitro=0,nitro_raw=0)
        for _ in range(10):
            result=self.calc(p,p,9)
            self.assertEqual(result.components['turbo_activation'],0)
            self.assertEqual(result.components['turbo_useful_progress'],0)

    def test_exhausting_inventory_early_costs_more_without_fixed_schedule(self):
        p=self.state();c=replace(p,nitro=2,turbo_active=1)
        base=self.engine().calculate(p,c,action=9,navigation=CLEAR)
        first=DrivingObjective().calculate(p,c,base,0,action=9,navigation=CLEAR)
        last=DrivingObjective().calculate(replace(p,nitro=1),replace(c,nitro=0),base,0,action=9,navigation=CLEAR)
        late=DrivingObjective().calculate(replace(p,nitro=1),replace(c,nitro=0),base,22528*2.9,action=9,navigation=CLEAR)
        self.assertLess(last['turbo_reserve_deficit'],first['turbo_reserve_deficit'])
        self.assertLess(last['turbo_reserve_deficit'],late['turbo_reserve_deficit'])

    def test_useful_turbo_bonus_is_capped_and_no_backtrack_farming(self):
        e=self.engine();p=self.state();c=replace(p,nitro=2,turbo_active=1,progress=1100)
        result=e.calculate(p,c,action=9,navigation=CLEAR)
        bonus=result.components['turbo_useful_progress']
        self.assertGreater(bonus,0)
        back=replace(c,progress=1000)
        self.assertEqual(e.calculate(c,back,action=1,navigation=CLEAR).components['turbo_useful_progress'],0)
        self.assertEqual(e.calculate(back,c,action=1,navigation=CLEAR).components['turbo_useful_progress'],0)
        for _ in range(150):
            p,c=c,replace(c,progress=(c.progress+100)%22528)
            bonus+=e.calculate(p,c,action=1,navigation=CLEAR).components['turbo_useful_progress']
        self.assertLessEqual(bonus,SETTINGS['turbo_bonus_per_charge_cap']+1e-9)
        self.assertEqual(self.engine().driving.bonus_remaining,0)

    def test_turbo_crash_or_offroad_has_no_useful_bonus(self):
        p=self.state();c=replace(p,nitro=2,turbo_active=1,progress=1100,collision=1,collision_events=1)
        result=self.calc(p,c,9)
        self.assertEqual(result.components['turbo_useful_progress'],0)
        self.assertEqual(result.components['turbo_collision'],-.5)
        result=self.calc(p,replace(c,collision=0,collision_events=0,offtrack=1),9)
        self.assertEqual(result.components['turbo_useful_progress'],0)
        self.assertEqual(result.components['turbo_offroad_active'],-.03)

    def test_prestart_has_time_cost_and_no_invented_progress(self):
        p=self.state(lap=-1,speed=0);result=self.calc(p,p,0)
        self.assertEqual(result.total,-.005)
        self.assertEqual(result.components['progress'],0)
        self.assertEqual(result.components['finish'],0)

    def test_incomplete_never_pays_finish_and_unused_inventory_has_no_terminal_penalty(self):
        p=self.state(lap=2);c=replace(p,finished=1,final_rank=0)
        result=self.calc(p,c,0)
        self.assertEqual(result.components['finish'],0)
        self.assertEqual(result.components['incomplete'],-5)
        self.assertEqual(result.components['unnecessary_lift'],0)
        self.assertEqual(result.components['turbo_activation'],0)
        done=self.calc(p,replace(c,lap=3),1)
        self.assertEqual(done.components['finish'],20)

    def test_requires_actual_action_and_rejects_combining_fresh_with_resume(self):
        p=self.state()
        with self.assertRaisesRegex(ValueError,'acao real'):
            self.engine().calculate(p,p)
        with patch('sys.argv',['train','--from-scratch','--timesteps','500000']):
            args=arguments();self.assertTrue(args.from_scratch);self.assertIsNone(args.resume);self.assertIsNone(args.initialize_policy_from)
        with patch('sys.argv',['train','--from-scratch','--resume','old.zip']),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):arguments()
