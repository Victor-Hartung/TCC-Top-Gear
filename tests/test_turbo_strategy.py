import contextlib
import copy
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor

from test_reward import ROOT, telemetry
from test_v3_experiment import SyntheticBridge
from env_topgear import TopGearEnv
from experiment import contract, save_checkpoint, validate_checkpoint
from policy_transfer import validate_policy_source, initialize_actor
from reward import RewardEngine, RewardWeights, profile_weights
from topgear_config import ProjectConfig
from turbo_strategy import PROFILE, TurboUsage, turbo_costs


class TurboStrategyTests(unittest.TestCase):
    def engine(self, profile=PROFILE):
        w=profile_weights(RewardWeights.from_config(ProjectConfig.load(ROOT)),profile)
        return RewardEngine(w,profile)

    def test_charge_consumed_before_lap_zero_is_no_longer_free(self):
        p=telemetry(lap=-1,nitro=3,turbo_active=0)
        c=replace(p,frame=p.frame+4,nitro=2,turbo_active=1)
        self.assertEqual(self.engine('road_v2').calculate(p,c).total,0)
        r=self.engine().calculate(p,c)
        self.assertAlmostEqual(r.total,-1.25)
        self.assertEqual(r.components['progress'],0)
        self.assertEqual(r.components['finish'],0)

    def test_same_active_turbo_is_not_charged_again(self):
        p=telemetry(nitro=2,turbo_active=1)
        c=replace(p,frame=p.frame+4)
        self.assertTrue(all(v==0 for v in turbo_costs(p,c,0).values()))
        r=self.engine().calculate(p,c)
        old=self.engine('road_v2').calculate(p,c)
        self.assertEqual(r.total,old.total)

    def test_early_reserve_cost_is_larger_but_late_use_is_not_free(self):
        p=telemetry(nitro=3,track_length=22528,total_laps=3)
        c=replace(p,nitro=2,turbo_active=1)
        early=sum(turbo_costs(p,c,0).values())
        late=sum(turbo_costs(p,c,22528*2.5).values())
        self.assertLess(early,late)
        self.assertLess(late,0)
        self.assertAlmostEqual(sum(turbo_costs(p,c,22528*3).values()),-.25)

    def test_offroad_consumption_and_waste_cost_more(self):
        p=telemetry(nitro=3,offtrack=0)
        c=replace(p,nitro=2,turbo_active=1)
        clean=turbo_costs(p,c,0)
        dirty=turbo_costs(replace(p,offtrack=1),replace(c,offtrack=1),0)
        self.assertAlmostEqual(dirty['turbo_offroad_activation'],-.75)
        self.assertAlmostEqual(dirty['turbo_offroad_active'],-.01)
        self.assertLess(sum(dirty.values()),sum(clean.values()))

    def test_no_reward_for_hoarding_or_spending_and_no_fake_finish(self):
        p=telemetry(lap=2,nitro=3)
        for end in [replace(p,finished=1,final_rank=19),replace(p,lap=3,finished=1,final_rank=0)]:
            result=self.engine().calculate(p,end)
            old=self.engine('road_v2').calculate(p,end)
            self.assertEqual(result.total,old.total)
        incomplete=self.engine().calculate(p,replace(p,finished=1,final_rank=0))
        self.assertEqual(incomplete.components['finish'],0)

    def test_usage_counts_charges_not_repeated_button_requests(self):
        usage=TurboUsage();p=telemetry(nitro=3,lap=-1)
        c=replace(p,nitro=2,turbo_active=1)
        usage.update(p,c,30)
        for i in range(10):usage.update(c,c,31+i)
        self.assertEqual(usage.info()['turbo_charges_used'],1)
        self.assertEqual(usage.info()['turbo_prestart_charges'],1)
        self.assertEqual(usage.info()['turbo_first_activation_step'],30)
        self.assertEqual(TurboUsage().info()['turbo_charges_used'],0)

    def test_new_profile_preserves_truncation_and_restarts_usage(self):
        bridge=SyntheticBridge(terminate_after=10000)
        with patch('env_topgear.BridgeClient',return_value=bridge), contextlib.redirect_stdout(io.StringIO()):
            env=TopGearEnv(ROOT,reward_profile=PROFILE)
        self.addCleanup(env.close)
        env.max_steps=1;env.reset()
        _,_,terminated,truncated,info=env.step(1)
        self.assertFalse(terminated);self.assertTrue(truncated)
        self.assertEqual(info['termination_reason'],'time_limit')
        self.assertNotIn('reward_time_limit',info)
        self.assertEqual(info['episode_elapsed_frames'],4)
        _,info=env.reset();self.assertEqual(info['episode_elapsed_frames'],0)

    def test_transfer_is_explicit_and_preserves_actor_only(self):
        d=self.enterContext(tempfile.TemporaryDirectory());root=Path(d)
        bridge=SyntheticBridge(terminate_after=10000)
        with patch('env_topgear.BridgeClient',return_value=bridge), contextlib.redirect_stdout(io.StringIO()):
            env=Monitor(TopGearEnv(ROOT,reward_profile=PROFILE))
        self.addCleanup(env.close);torch.set_num_threads(1)
        options=dict(n_steps=8,batch_size=8,n_epochs=1,device='cpu')
        old=PPO('MlpPolicy',env,seed=4,**options)
        old.learn(8)
        cfg=ProjectConfig.load(ROOT);source=contract(cfg,'road_v2');target=contract(cfg,PROFILE)
        for c in [source,target]:c['ppo'].update(n_steps=8,batch_size=8,n_epochs=1)
        path=save_checkpoint(old,root/'source.zip',source,run='synthetic',reason='test')
        with self.assertRaisesRegex(ValueError,'incompativel'):validate_checkpoint(path,target)
        validate_policy_source(path,target)
        new=PPO('MlpPolicy',env,seed=9,**options)
        critic={k:v.clone() for k,v in new.policy.state_dict().items() if k.startswith(('value_net.','mlp_extractor.value_net.'))}
        initialize_actor(new,path,target)
        for key,value in critic.items():self.assertTrue(torch.equal(value,new.policy.state_dict()[key]))
        self.assertEqual(new.num_timesteps,0);self.assertFalse(new.policy.optimizer.state)
        obs=np.zeros((1,len(target['observation_names'])),dtype=np.float32)
        with torch.no_grad():
            a=old.policy.get_distribution(torch.as_tensor(obs)).distribution.probs
            b=new.policy.get_distribution(torch.as_tensor(obs)).distribution.probs
        self.assertTrue(torch.equal(a,b))
        broken=copy.deepcopy(target);broken['observation_schema']+=1
        with self.assertRaisesRegex(ValueError,'recusada'):validate_policy_source(path,broken)
