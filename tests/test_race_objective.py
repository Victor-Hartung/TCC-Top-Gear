import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import torch
from stable_baselines3 import PPO

from test_reward import ROOT, telemetry
from test_policy_transfer import SpaceEnvironment
from test_v3_experiment import SyntheticBridge
from experiment import contract, save_checkpoint, validate_checkpoint
from policy_transfer import validate_policy_source, initialize_actor
from race_objective import PROFILE
from reward import RewardEngine, RewardWeights, profile_weights
from topgear_config import ProjectConfig
import compare_race_policies_live


class RaceCorrectionTests(unittest.TestCase):
    def engine(self, profile):
        return RewardEngine(profile_weights(RewardWeights.from_config(ProjectConfig.load(ROOT)),profile),profile)

    def test_identical_to_road_v2_after_launch_even_with_turbo_and_different_actions(self):
        old,new=self.engine('road_v2'),self.engine(PROFILE)
        p=telemetry(track_length=22528,nitro=3,curve_current=16)
        states=[replace(p,progress=1100,nitro=2,turbo_active=1),
                replace(p,progress=1200,nitro=2,turbo_active=1,collision=1,collision_events=1),
                replace(p,progress=1250,nitro=2,collision_events=1,offtrack=1),
                replace(p,progress=1300,nitro=1,collision_events=1),
                replace(p,progress=1400,nitro=1,collision_events=1)]
        for action,c in enumerate(states):
            a=old.calculate(p,c);b=new.calculate(p,c,action=action,navigation={'target_valid':False})
            self.assertAlmostEqual(a.total,b.total)
            self.assertFalse(any(k.startswith('turbo_') or k=='unnecessary_lift' for k in b.components))
            p=c

    def test_reserve_and_late_use_do_not_change_reward_for_same_progress(self):
        p=telemetry(track_length=22528,nitro=3)
        values=[]
        for nitro in (0,1,2,3):
            values.append(self.engine(PROFILE).calculate(p,replace(p,progress=1100,nitro=nitro)).total)
        self.assertTrue(all(v==values[0] for v in values))

    def test_start_cost_no_fake_finish_and_no_backtrack_farming(self):
        p=telemetry(lap=-1);self.assertEqual(self.engine(PROFILE).calculate(p,p).total,-.005)
        e=self.engine(PROFILE);p=telemetry(progress=1000);c=replace(p,progress=1100)
        self.assertGreater(e.calculate(p,c).components['progress'],0)
        self.assertEqual(e.calculate(c,p).components['progress'],0)
        self.assertEqual(e.calculate(p,c).components['progress'],0)
        self.assertEqual(e.calculate(c,replace(c,lap=2,finished=1,final_rank=0)).components['finish'],0)

    def test_known_reward_only_transfer_preserves_actor_and_rejects_other_changes(self):
        cfg=ProjectConfig.load(ROOT);target=copy.deepcopy(contract(cfg,PROFILE));torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as d:
            for profile in ('road_v3_turbo','road_v4_driving'):
                source=copy.deepcopy(contract(cfg,profile))
                old=PPO('MlpPolicy',SpaceEnvironment(source),n_steps=8,batch_size=8,seed=4)
                model=PPO('MlpPolicy',SpaceEnvironment(target),n_steps=8,batch_size=8,seed=9)
                path=save_checkpoint(old,Path(d)/profile,source,run='synthetic',reason='test')
                with self.assertRaisesRegex(ValueError,'incompativel'):validate_checkpoint(path,target)
                initialize_actor(model,path,target)
                observations=torch.zeros((2,61))
                with torch.no_grad():
                    self.assertTrue(torch.equal(old.policy.get_distribution(observations).distribution.probs,
                                                model.policy.get_distribution(observations).distribution.probs))
                self.assertEqual(model.num_timesteps,0);self.assertFalse(model.policy.optimizer.state)
                broken=copy.deepcopy(target);broken['navigation']['forward_gap']=999
                with self.assertRaisesRegex(ValueError,'recusada'):validate_policy_source(path,broken)

    def test_comparison_executes_two_deterministic_episodes_without_learning(self):
        self.run_comparison(2)

    def test_single_policy_play_without_learning(self):
        self.run_comparison(1)

    def test_brake_ablation_pair_without_learning(self):
        self.run_comparison(1, diagnose=True)

    def test_four_pace_variants_without_learning(self):
        self.run_comparison(1, diagnose=True, pace=True)

    def test_pace_interventions_preserve_steering_and_separate_turbo(self):
        from unittest.mock import Mock
        cases = ((compare_race_policies_live.ThrottleAblation, [1,1,1,3,4,3,4,3,4,9]),
                 (compare_race_policies_live.ThrottleWithoutTurboAblation, [1,1,1,3,4,3,4,3,4,1]))
        for controller, actions in cases:
            model = Mock()
            wrapper = controller(model)
            for requested, expected in enumerate(actions):
                model.predict.return_value = (np.array(requested), None)
                applied, _ = wrapper.predict(np.zeros(61))
                self.assertEqual(int(applied), expected)

    def test_brake_intervention_preserves_direction_and_other_actions(self):
        from unittest.mock import Mock
        model = Mock()
        wrapper = compare_race_policies_live.BrakeAblation(model)
        for requested, expected in enumerate([0,1,1,3,4,5,6,3,4,9]):
            model.predict.return_value = (np.array(requested), None)
            applied, state = wrapper.predict(np.zeros(61))
            self.assertEqual(int(applied), expected)
            self.assertIsNone(state)
        self.assertEqual([r['requested_action'] for r in wrapper.interventions], [2,7,8])

    def run_comparison(self, policy_count, diagnose=False, pace=False):
        cfg=ProjectConfig.load(ROOT)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);models=[]
            for profile in ('road_v3_turbo','road_v4_driving')[:policy_count]:
                c=contract(cfg,profile)
                model=PPO('MlpPolicy',SpaceEnvironment(c),n_steps=8,batch_size=8,seed=4)
                models.append(save_checkpoint(model,root/profile,c,run='synthetic',reason='test'))
            cfg=replace(cfg,project_dir=root)
            bridge=SyntheticBridge(terminate_after=3)
            from telemetry import Telemetry
            from dataclasses import asdict
            receipt={'reset_fingerprint':asdict(Telemetry.from_fields(bridge.reset().fields))}
            bridge.resets=0
            # Ambiente real com ponte sintetica; nenhuma alegacao de emulacao.
            with patch('compare_race_policies_live.ProjectConfig.load',return_value=cfg), \
                 patch('env_topgear.ProjectConfig.load',return_value=cfg), \
                 patch('compare_race_policies_live.assert_live_preflight',return_value=receipt), \
                 patch('env_topgear.BridgeClient',return_value=bridge), \
                 patch('sys.argv',['compare','--models',*map(str,models)]+(['--diagnose-pace' if pace else '--diagnose-braking'] if diagnose else [])), contextlib.redirect_stdout(io.StringIO()):
                compare_race_policies_live.main()
            report=json.loads(next((root/'runs/avaliacao_modelo').glob('comparacao*.json')).read_text(encoding='utf-8'))
            self.assertEqual(report['status'],'completed')
            self.assertFalse(report['training_enabled'])
            self.assertTrue(report['source_models_preserved'])
            self.assertTrue(report['identical_initial_state'])
            expected_count = policy_count * (4 if pace else 2 if diagnose else 1)
            self.assertEqual(bridge.resets,expected_count)
            self.assertEqual(len(report['comparisons']),expected_count)
            self.assertEqual(len(report['summary']),expected_count)
            if diagnose:
                self.assertFalse(report['comparisons'][0]['action_override'])
                self.assertTrue(report['comparisons'][1]['action_override'])
