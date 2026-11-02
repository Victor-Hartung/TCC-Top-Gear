import copy
import os
import unittest
from unittest.mock import patch
from test_reward import ROOT
from topgear_config import ProjectConfig
from experiment import contract, preflight_receipt_path
from manual_refinement import validate_contract_change, apply_optimizer_rate


class ManualRefinementTests(unittest.TestCase):
    def configs(self):
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_manual.ini'):
            old=ProjectConfig.load(ROOT)
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_manual_refine.ini'):
            new=ProjectConfig.load(ROOT)
        return old,new

    def test_only_lower_learning_rate_and_distinct_preflight(self):
        old,new=self.configs()
        self.assertEqual(validate_contract_change(contract(old),contract(new)),(.0003,.0001))
        self.assertNotEqual(preflight_receipt_path(old),preflight_receipt_path(new))
        self.assertEqual((new.action_count,new.bridge_revision),(30,6))

    def test_any_other_semantic_change_is_rejected(self):
        old,new=self.configs();source,target=contract(old),contract(new)
        for key,value in [('reward_version',8),('action_schema',4),('savestate_slot',1),('frame_repeat',8),('observation_schema',12)]:
            changed=copy.deepcopy(target);changed[key]=value
            with self.assertRaises(ValueError):validate_contract_change(source,changed)
        for key,value in [('gamma',.99),('n_epochs',5),('learning_rate',.0004),('learning_rate',float('nan'))]:
            changed=copy.deepcopy(target);changed['ppo'][key]=value
            with self.assertRaises(ValueError):validate_contract_change(source,changed)

    def test_rate_change_preserves_weights_adam_moments_counter_and_predictions(self):
        import torch
        import gymnasium as gym
        import numpy as np
        from stable_baselines3 import PPO
        old,new=self.configs()
        env=gym.make('CartPole-v1')  # Simulacao apenas do mecanismo PPO/Adam.
        torch.set_num_threads(1)
        model=PPO('MlpPolicy',env,n_steps=16,batch_size=16,n_epochs=1,learning_rate=.0003,seed=7,device='cpu')
        model.learn(32)
        weights={k:v.clone() for k,v in model.policy.state_dict().items()}
        optimizer=copy.deepcopy(model.policy.optimizer.state_dict())
        counter=model.num_timesteps
        obs=np.zeros(4,dtype=np.float32)
        action=int(model.predict(obs,deterministic=True)[0])
        meta=dict(contract=contract(old),model_sha256='fixture',contract_sha256='fixture',num_timesteps=counter)
        apply_optimizer_rate(model,meta,contract(new))
        self.assertEqual(model.lr_schedule(.25),.0001)
        self.assertTrue(all(g['lr']==.0001 for g in model.policy.optimizer.param_groups))
        self.assertTrue(all(torch.equal(v,model.policy.state_dict()[k]) for k,v in weights.items()))
        for idx,state in optimizer['state'].items():
            for key,value in state.items():
                self.assertTrue(torch.equal(value,model.policy.optimizer.state_dict()['state'][idx][key]))
        self.assertEqual(model.num_timesteps,counter)
        self.assertEqual(int(model.predict(obs,deterministic=True)[0]),action)
        env.close()
