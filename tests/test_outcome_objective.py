"""Propriedades de recompensa/contrato offline; nao comprovam boa pilotagem."""
import contextlib
import copy
import io
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from stable_baselines3 import PPO

from test_reward import ROOT, telemetry
from test_policy_transfer import SpaceEnvironment
from test_v3_experiment import SyntheticBridge
from env_topgear import TopGearEnv
from experiment import contract, save_checkpoint, validate_checkpoint, sha256
from outcome_objective import (PROFILE, SETTINGS, REWARD_VERSION, LEGACY_VERSION,
                               LEGACY_SETTINGS, PREVIOUS_VERSION, PREVIOUS_SETTINGS,
                               PRIOR_VERSION, PRIOR_SETTINGS, PREVIOUS_REWARD_VERSION,
                               PREVIOUS_REWARD_SETTINGS, PREVIOUS_TIME_VERSION,
                               PREVIOUS_TIME_SETTINGS, SOURCE_GAE_LAMBDA)
from policy_transfer import initialize_actor
from race_objective import SETTINGS as RACE_SETTINGS
from reward import RewardEngine, RewardWeights, profile_weights, reward_version
from topgear_config import ProjectConfig
from turbo_strategy import TurboUsage


class OutcomeRewardTests(unittest.TestCase):
    def engine(self, profile=PROFILE):
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_blue_auto.ini'):
            weights = RewardWeights.from_config(ProjectConfig.load(ROOT))
        return RewardEngine(profile_weights(weights, profile), profile)

    def test_real_position_delta_in_sentinel_and_at_wrap_not_absolute_position(self):
        engine = self.engine()
        a = telemetry(lap=-1, progress=21856, track_length=22528)
        self.assertEqual(engine.calculate(a, a).components['progress'], 0)
        b = replace(a, progress=22500)
        c = replace(a, lap=0, progress=30)
        r1, r2 = engine.calculate(a, b), engine.calculate(b, c)
        self.assertEqual((r1.progress_delta, r2.progress_delta), (644, 58))
        self.assertAlmostEqual(r1.components['progress']+r2.components['progress'], 702*20/22528)
        self.assertEqual(engine.net_progress, 702)
        self.assertEqual(self.engine('road_v5_race').calculate(a, b).progress_delta, 0)
        self.assertEqual(engine.calculate(c, replace(c, lap=1)).progress_delta, 0)

    def test_preline_grace_has_no_progress_or_fake_first_rank_gain(self):
        e = self.engine()
        a = telemetry(lap=-1, speed=0, rank=-1)
        for _ in range(30):
            r = e.calculate(a, a, action=9)
            self.assertAlmostEqual(r.total, -.005)
            self.assertEqual(r.components['idle'], 0)
        b = replace(a, rank=10)
        self.assertEqual(e.calculate(a, b).components['rank_delta'], 0)
        c = replace(b, rank=9)
        self.assertEqual(e.calculate(b, c).components['rank_delta'], 1.1)

    def test_elapsed_cost_increased_only_for_blue_auto_outcome(self):
        a = telemetry(lap=0, speed=100)
        outcome = self.engine().calculate(a, a)
        self.assertEqual(outcome.components['elapsed'], -.005)
        for profile in ('road_v2', 'road_v3_turbo', 'road_v4_driving', 'road_v5_race'):
            with self.subTest(profile=profile):
                result = self.engine(profile).calculate(a, a, action=0)
                self.assertEqual(result.components['elapsed'], -.002)

    def test_idle_penalty_starts_after_phase_grace_and_repeats(self):
        for lap, grace in ((-1, 30), (0, 15), (2, 15)):
            with self.subTest(lap=lap):
                e = self.engine()
                a = telemetry(lap=lap, speed=0)
                for decision in range(1, grace + 1):
                    r = e.calculate(a, a)
                    self.assertEqual(r.components['idle'], 0)
                    self.assertEqual(e.idle.consecutive_steps, decision)
                    self.assertAlmostEqual(r.total, -.005)
                for decision in (grace + 1, grace + 2):
                    r = e.calculate(a, a)
                    self.assertEqual(r.components['idle'], -.25)
                    self.assertEqual(e.idle.consecutive_steps, decision)
                    self.assertAlmostEqual(r.total, -.255)

    def test_bridge_speed_one_is_not_classified_as_stationary(self):
        e = self.engine()
        a = telemetry(lap=-1, speed=1)
        for _ in range(300):
            self.assertEqual(e.calculate(a, a).components['idle'], 0)
            self.assertEqual(e.idle.consecutive_steps, 0)

    def test_idle_counter_resets_on_motion_progress_impact_or_race_end(self):
        for lap, grace in ((-1, 30), (0, 15)):
            a = telemetry(lap=lap, speed=0)
            outcomes = (
                replace(a, speed=20),
                replace(a, progress=a.progress + 1),
                replace(a, collision=1),
                replace(a, collision_events=1),
                replace(a, finished=1, final_rank=19),
                replace(a, finished=1, final_rank=0, lap=3),
            )
            for b in outcomes:
                with self.subTest(lap=lap, outcome=b):
                    e = self.engine()
                    for _ in range(grace + 1):
                        e.calculate(a, a)
                    self.assertGreater(e.idle.consecutive_steps, grace)
                    self.assertEqual(e.calculate(a, b).components['idle'], 0)
                    self.assertEqual(e.idle.consecutive_steps, 0)

    def test_new_episode_and_line_crossing_reset_idle_grace(self):
        a = telemetry(lap=-1, speed=0, progress=22527, track_length=22528)
        e = self.engine()
        for _ in range(31):
            e.calculate(a, a)
        b = replace(a, lap=0, progress=0)
        self.assertEqual(e.calculate(a, b).components['idle'], 0)
        self.assertEqual(e.idle.consecutive_steps, 0)
        for _ in range(15):
            self.assertEqual(e.calculate(b, b).components['idle'], 0)
        self.assertEqual(e.calculate(b, b).components['idle'], -.25)
        fresh = self.engine()
        self.assertEqual(fresh.idle.consecutive_steps, 0)
        self.assertEqual(fresh.calculate(a, a).components['idle'], 0)

    def test_only_new_best_positions_receive_larger_gain(self):
        for lap in (-1, 0):
            with self.subTest(lap=lap):
                e = self.engine()
                a = telemetry(lap=lap, rank=10)
                b = replace(a, rank=9)
                c = replace(a, rank=11)
                d = replace(a, rank=7)
                self.assertEqual(e.calculate(a, b).components['rank_delta'], 1.1)
                self.assertEqual(e.calculate(b, c).components['rank_delta'], -2.0)
                self.assertEqual(e.calculate(c, b).components['rank_delta'], 0)
                self.assertEqual(e.calculate(b, d).components['rank_delta'], 2.2)
                self.assertEqual(e.calculate(d, d).components['rank_delta'], 0)

    def test_rank_oscillation_cannot_farm_the_larger_gain(self):
        e = self.engine()
        a = telemetry(rank=10)
        b = replace(a, rank=9)
        self.assertEqual(e.calculate(a, b).components['rank_delta'], 1.1)
        for _ in range(10):
            loss = e.calculate(b, a).components['rank_delta']
            recovery = e.calculate(a, b).components['rank_delta']
            self.assertEqual(loss, -1.0)
            self.assertEqual(recovery, 0)
            self.assertLessEqual(loss + recovery, 0)

    def test_rank_loss_costs_one_per_position_including_before_first_line(self):
        for lap in (-1, 0, 2):
            for positions in (1, 3, 9):
                with self.subTest(lap=lap, positions=positions):
                    a = telemetry(lap=lap, rank=10)
                    b = replace(a, rank=a.rank + positions)
                    result = self.engine().calculate(a, b)
                    self.assertEqual(result.components['rank_delta'], -float(positions))
                    self.assertAlmostEqual(result.total, -positions - .005)

    def test_unknown_rank_publication_does_not_invent_position_loss(self):
        for lap in (-1, 0):
            with self.subTest(lap=lap):
                e = self.engine()
                unknown = telemetry(lap=lap, rank=-1)
                current = replace(unknown, rank=19)
                self.assertEqual(e.calculate(unknown, current).components['rank_delta'], 0)
                best = replace(current, rank=17)
                self.assertEqual(e.calculate(current, best).components['rank_delta'], 2.2)
                self.assertEqual(e.calculate(best, unknown).components['rank_delta'], 0)
                self.assertEqual(e.calculate(unknown, current).components['rank_delta'], 0)

    def test_rank_publication_after_unknown_value_does_not_pay(self):
        e = self.engine()
        a = telemetry(lap=-1, rank=-1)
        b = replace(a, rank=9)
        self.assertEqual(e.calculate(a, b).components['rank_delta'], 0)
        unknown = replace(b, rank=-1)
        self.assertEqual(e.calculate(b, unknown).components['rank_delta'], 0)
        c = replace(b, rank=8)
        self.assertEqual(e.calculate(unknown, c).components['rank_delta'], 0)
        self.assertEqual(e.calculate(c, replace(c, rank=7)).components['rank_delta'], 1.1)

    def test_other_reward_profiles_preserve_idle_and_position_weights(self):
        profiles = ('legacy_corrigido', 'road_v1', 'road_v2', 'road_v3_turbo',
                    'road_v4_driving', 'road_v5_race')
        for profile in profiles:
            with self.subTest(profile=profile):
                e = self.engine(profile)
                expected_idle = 0 if profile == 'legacy_corrigido' else -.02
                a = telemetry(lap=0, speed=0)
                for _ in range(15):
                    self.assertEqual(e.calculate(a, a, action=0).components['idle'], 0)
                self.assertEqual(e.calculate(a, a, action=0).components['idle'], expected_idle)
                self.assertEqual(self.engine(profile).calculate(
                    telemetry(rank=10), telemetry(rank=9), action=0).components['rank_delta'], .5)
                self.assertEqual(self.engine(profile).calculate(
                    telemetry(rank=10), telemetry(rank=13), action=0).components['rank_delta'], -1.5)
                preline = self.engine(profile)
                stopped = telemetry(lap=-1, speed=0)
                for _ in range(40):
                    self.assertEqual(preline.calculate(stopped, stopped, action=0).components.get('idle', 0), 0)

    def test_reward_revision_is_recorded_and_legacy_settings_remain_available(self):
        self.assertEqual(reward_version(PROFILE), 14)
        self.assertEqual(REWARD_VERSION, 14)
        self.assertEqual(LEGACY_VERSION, 8)
        self.assertEqual(LEGACY_SETTINGS['version'], 1)
        self.assertNotIn('idle_penalty', LEGACY_SETTINGS)
        self.assertEqual(PREVIOUS_VERSION, 10)
        self.assertEqual(PREVIOUS_SETTINGS['version'], 3)
        self.assertNotIn('rank_loss_multiplier', PREVIOUS_SETTINGS)
        self.assertEqual(PREVIOUS_SETTINGS, dict(LEGACY_SETTINGS, version=3,
                         idle_penalty=.1, idle_grace_steps=15,
                         preline_idle_grace_steps=30,
                         preline_idle_grace_basis='consecutive_stationary_observations_not_go_detection',
                         rank_gain_multiplier=2.0))
        self.assertEqual(PRIOR_VERSION, 11)
        self.assertEqual(PRIOR_SETTINGS, dict(PREVIOUS_SETTINGS, version=4,
                         rank_loss_multiplier=2.0))
        self.assertEqual(PREVIOUS_REWARD_VERSION, 12)
        self.assertEqual(PREVIOUS_REWARD_SETTINGS, dict(PRIOR_SETTINGS, version=5,
                         idle_penalty=.25, rank_gain_multiplier=2.2))
        self.assertEqual(PREVIOUS_TIME_VERSION, 13)
        self.assertEqual(PREVIOUS_TIME_SETTINGS, dict(PREVIOUS_REWARD_SETTINGS, version=6,
                         finish_bonus=40.0, failure_penalty=10.0))
        self.assertEqual(SETTINGS, dict(PREVIOUS_TIME_SETTINGS, version=7,
                         elapsed_cost=.005))
        self.assertEqual(SETTINGS['rank_loss_multiplier'], 2.0)
        self.assertEqual(self.engine().weights.idle_penalty, .25)
        self.assertEqual(self.engine().weights.finish, 40.0)
        self.assertEqual(self.engine().weights.failure, 10.0)
        self.assertEqual(self.engine().weights.idle_grace_steps, 15)
        self.assertEqual(reward_version('road_v5_race'), 7)

    def test_preline_impact_and_offroad_count_but_returning_to_same_distance_does_not_pay(self):
        a = telemetry(lap=-1, progress=1000)
        b = replace(a, progress=1100, offtrack=1, collision_events=1, collision=1)
        e = self.engine()
        r = e.calculate(a, b)
        self.assertEqual(r.components['progress'], 0)
        self.assertEqual(r.components['collision'], -.25)
        self.assertEqual(r.components['offtrack'], -.005)
        self.assertEqual(r.collision_count, 1)
        c = replace(a, collision_events=1)
        d = replace(c, progress=1100)
        self.assertEqual(e.calculate(b, c).components['progress'], 0)
        self.assertEqual(e.calculate(c, d).components['progress'], 0)
        self.assertGreater(e.calculate(d, replace(d, progress=1200)).components['progress'], 0)

    def test_unknown_surface_and_implausible_jump_never_pay(self):
        e = self.engine(); a = telemetry(lap=-1)
        r = e.calculate(a, replace(a, progress=5000))
        self.assertEqual(r.components['invalid_progress_jump'], 1)
        self.assertEqual(e.high_water, 0)
        r = e.calculate(a, replace(a, progress=1100, surface_unknown=1))
        self.assertEqual(r.components['progress'], 0)

    def test_reward_for_same_outcomes_is_independent_of_turbo_button_inventory_and_sensors(self):
        for lap in (-1, 0, 2):
            a = telemetry(lap=lap, nitro=3)
            b = replace(a, progress=1100)
            expected = self.engine().calculate(a, b)
            for nitro in range(4):
                for action in range(10):
                    r = self.engine().calculate(a, replace(b, nitro=nitro, turbo_active=int(nitro<3)),
                                               action=action, navigation={'target_valid': False})
                    self.assertEqual(r, expected)

    def test_finish_requires_actual_three_laps_and_never_pays_unused_turbo(self):
        a = telemetry(lap=2)
        for lap in (-1, 0, 2, 3):
            values=[]
            for nitro in (0, 3):
                b = replace(a, lap=lap, finished=1, final_rank=0, nitro=nitro)
                r = self.engine().calculate(a, b)
                self.assertEqual(r.components['finish'], 40 if lap==3 else 0)
                self.assertEqual(r.components['first_place'], 30 if lap==3 else 0)
                values.append(r.total)
            self.assertEqual(values[0], values[1])

    def test_incomplete_race_penalty_is_applied_when_finish_line_is_not_reached(self):
        a = telemetry(lap=2)
        b = replace(a, finished=1, final_rank=19)
        result = self.engine().calculate(a, b)
        self.assertFalse(b.race_completed)
        self.assertEqual(result.components['finish'], 0)
        self.assertEqual(result.components['incomplete'], -10.0)

    def test_time_limit_and_no_progress_remain_truncations_with_no_fake_finish(self):
        for mode in ('max_steps', 'no_progress'):
            bridge=SyntheticBridge(terminate_after=10000)
            with patch('env_topgear.BridgeClient',return_value=bridge), contextlib.redirect_stdout(io.StringIO()):
                env=TopGearEnv(ROOT,reward_profile=PROFILE)
            try:
                env.reset()
                if mode=='max_steps': env.max_steps=1
                else: env.no_progress_limit=1;env.progress_epsilon=100000
                _,_,terminated,truncated,info=env.step(1)
                self.assertFalse(terminated);self.assertTrue(truncated)
                self.assertEqual(info['reward_finish'],0)
                self.assertNotIn('reward_failure',info)
                self.assertNotIn('reward_time_limit',info)
            finally: env.close()

    def test_turbo_windows_measure_outcomes_without_equating_sentinel_with_waste(self):
        usage=TurboUsage()
        a=telemetry(lap=-1,nitro=3,progress=22500,track_length=22528,frame=100)
        b=replace(a,nitro=2,turbo_active=1,progress=10,frame=104)
        usage.update(a,b,1)
        snapshot=usage.info()
        c=replace(b,progress=30,offtrack=1,collision=1,collision_events=1,frame=108)
        usage.update(b,c,2)
        d=replace(c,turbo_active=0,progress=50,frame=112)
        usage.update(c,d,3)
        e=usage.info()['turbo_activations'][0]
        self.assertEqual(e['charges'],1)
        self.assertEqual(e['observed_steps'],3)
        self.assertEqual(e['observed_frames'],12)
        self.assertEqual(e['clean_new_progress_units'],38)
        self.assertEqual(e['net_progress_units'],78)
        self.assertEqual(e['collision_events'],1)
        self.assertEqual(e['offtrack_or_unknown_steps'],2)
        self.assertEqual(e['window_status'],'boost_ended')
        self.assertEqual(snapshot['turbo_activations'][0]['observed_steps'],1)
        self.assertEqual(snapshot['turbo_lap_sentinel_charges'],1)
        usage.update(d,replace(d,nitro=1,turbo_active=1,frame=116),4)
        usage.end('time_limit')
        self.assertEqual(usage.info()['turbo_activations'][-1]['window_status'],'censored_time_limit')

    def test_explicit_actor_transfer_preserves_probabilities_but_not_old_value_or_optimizer(self):
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_blue_auto.ini'):
            target=copy.deepcopy(contract(ProjectConfig.load(ROOT)))
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile.ini'):
            red_source=copy.deepcopy(contract(ProjectConfig.load(ROOT),'road_v3_turbo'))
        race_source=copy.deepcopy(target)
        race_source.pop('outcome_objective')
        race_source.update(reward_profile='road_v5_race', reward_version=7,
                           race_objective=copy.deepcopy(RACE_SETTINGS))
        race_source['reward_weights']['idle_penalty']=.02
        race_source['reward_weights']['finish']=20.0
        race_source['reward_weights']['failure']=5.0
        race_source['reward_elapsed']=.002
        race_source['ppo']['gae_lambda']=SOURCE_GAE_LAMBDA
        torch.set_num_threads(1)
        for source in (red_source, race_source):
            with self.subTest(source=source['reward_profile']):
                old=PPO('MlpPolicy',SpaceEnvironment(source),seed=1,**source['ppo'])
                new=PPO('MlpPolicy',SpaceEnvironment(target),seed=2,**target['ppo'])
                critic={k:v.clone() for k,v in new.policy.state_dict().items() if k.startswith(('value_net.','mlp_extractor.value_net.'))}
                with tempfile.TemporaryDirectory() as d:
                    path=save_checkpoint(old,Path(d)/'old',source,run='synthetic',reason='test')
                    before=sha256(path)
                    with self.assertRaisesRegex(ValueError,'incompativel'): validate_checkpoint(path,target)
                    transfer=initialize_actor(new,path,target)
                    obs=np.random.default_rng(4).uniform(target['observation_low'],target['observation_high'],(64,61)).astype(np.float32)
                    with torch.no_grad():
                        self.assertTrue(torch.equal(old.policy.get_distribution(torch.from_numpy(obs)).distribution.probs,
                                                    new.policy.get_distribution(torch.from_numpy(obs)).distribution.probs))
                    self.assertEqual(sha256(path),before)
                    self.assertEqual(new.num_timesteps,0);self.assertFalse(new.policy.optimizer.state)
                    self.assertEqual(new.gae_lambda,.995)
                    self.assertEqual(transfer['source_gae_lambda'],.95)
                    for key,value in critic.items():self.assertTrue(torch.equal(value,new.policy.state_dict()[key]))
