"""PPO real e ponte sintetica: nao equivalem a validacao no BizHawk."""
import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor

from test_v3_experiment import SyntheticBridge, ROOT
from env_topgear import TopGearEnv
from protocol import ProtocolError
from recording import RecordingEnv
from resilient_ppo import ResilientPPO
from transition_errors import LapSentinelRegression


class RegressionBridge(SyntheticBridge):
    def __init__(self, repeated=False, reset_fails=False, generic=False):
        super().__init__(terminate_after=1000)
        self.attempts = 0
        self.repeated, self.reset_fails, self.generic = repeated, reset_fails, generic

    def reset(self):
        if self.reset_fails and self.resets:
            raise ProtocolError('Savestate mudou')
        return super().reset()

    def step(self, action):
        self.attempts += 1
        super().step(action)
        if self.attempts == 5 or (self.repeated and self.counter == 5):
            if self.generic:
                raise ProtocolError('ACK invalido')
            self.current = replace(self.current, lap=-1)
        return self.response()


class SpyPPO(ResilientPPO):
    def train(self):
        if not hasattr(self, 'buffers_seen'):
            self.buffers_seen = []
        self.buffers_seen.append((self.rollout_buffer.observations.copy(),
                                  self.rollout_buffer.episode_starts.copy()))
        super().train()


class RecoveryTests(unittest.TestCase):
    def make(self, root, bridge, cls=ResilientPPO):
        with patch('env_topgear.BridgeClient', return_value=bridge):
            raw = TopGearEnv(ROOT)
        env = Monitor(RecordingEnv(raw, root/'logs'))
        self.addCleanup(env.close)
        torch.set_num_threads(1)
        model = cls('MlpPolicy', env, n_steps=8, batch_size=8, n_epochs=1,
                    seed=42, device='cpu')
        model.configure_recovery(root/'recoveries')
        return model, env

    def test_raw_environment_rejects_further_steps_until_reset(self):
        bridge=RegressionBridge()
        with patch('env_topgear.BridgeClient',return_value=bridge), contextlib.redirect_stdout(io.StringIO()):
            env=TopGearEnv(ROOT)
        self.addCleanup(env.close)
        env.reset()
        for _ in range(4):env.step(1)
        with self.assertRaises(LapSentinelRegression):env.step(1)
        with self.assertRaisesRegex(ProtocolError,'reset'):env.step(1)
        self.assertEqual(bridge.attempts,5)
        env.reset();env.step(1)

    def test_discards_partial_rollout_and_resets_without_fake_terminal(self):
        d = self.enterContext(tempfile.TemporaryDirectory())
        with contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);bridge=RegressionBridge();model,env=self.make(root,bridge,SpyPPO)
            before=[p.detach().clone() for p in model.policy.parameters()]
            model.learn(16)
            env.close()
            self.assertEqual(model.num_timesteps,20)
            self.assertEqual(model.trained_steps_this_run,16)
            self.assertEqual(model.discarded_rollout_steps,4)
            self.assertEqual(model.recovery_count,1)
            self.assertEqual(bridge.resets,2)
            self.assertEqual(len(model.buffers_seen),2)
            first_obs,starts=model.buffers_seen[0]
            self.assertTrue(starts[0,0])
            self.assertTrue(np.all(first_obs[:,:,3]>=0))
            self.assertTrue(any(not torch.equal(a,b) for a,b in zip(before,model.policy.parameters())))
            record=json.loads(next((root/'recoveries').glob('*.json')).read_text())
            self.assertEqual(record['status'],'reset_ok')
            self.assertEqual(record['diagnostic']['previous']['lap'],0)
            self.assertEqual(record['diagnostic']['rejected']['lap'],-1)
            self.assertIn('detector_samples',record['diagnostic']['wire_fields'])
            episodes=[json.loads(s) for s in (root/'logs/episodes.jsonl').read_text().splitlines()]
            self.assertEqual(len(episodes),1)
            self.assertEqual(episodes[0]['event'],'bridge_or_environment_failure')
            self.assertEqual(episodes[0]['diagnostic'],record['diagnostic'])
            steps=[json.loads(s) for s in (root/'logs/steps.jsonl').read_text().splitlines()]
            self.assertEqual(sum(s['event']=='reset' for s in steps),2)
            self.assertTrue(all(s.get('reward',0)<20 for s in steps))

    def test_repeated_regression_is_bounded_and_logged(self):
        d = self.enterContext(tempfile.TemporaryDirectory())
        with contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);model,_=self.make(root,RegressionBridge(repeated=True))
            with self.assertRaisesRegex(ProtocolError,'limite de 3'):
                model.learn(64)
            self.assertEqual(model.recovery_count,3)
            self.assertEqual(model.trained_steps_this_run,0)
            records=[json.loads(p.read_text()) for p in (root/'recoveries').glob('*.json')]
            self.assertEqual(len(records),4)
            self.assertEqual(sum(r['status']=='rate_limit_exceeded' for r in records),1)

    def test_reset_mismatch_still_stops(self):
        d = self.enterContext(tempfile.TemporaryDirectory())
        with contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);model,_=self.make(root,RegressionBridge(reset_fails=True))
            with self.assertRaisesRegex(ProtocolError,'Savestate mudou'):model.learn(16)
            record=json.loads(next((root/'recoveries').glob('*.json')).read_text())
            self.assertEqual(record['status'],'reset_failed')
            self.assertEqual(model.recovery_count,0)

    def test_other_protocol_errors_are_never_retried(self):
        d = self.enterContext(tempfile.TemporaryDirectory())
        with contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);bridge=RegressionBridge(generic=True);model,_=self.make(root,bridge)
            with self.assertRaisesRegex(ProtocolError,'ACK invalido'):model.learn(16)
            self.assertEqual(bridge.resets,1)
            self.assertEqual(model.recovery_count,0)
            self.assertFalse((root/'recoveries').exists())

    def test_old_ppo_weights_can_load_and_resume_in_resilient_trainer(self):
        d = self.enterContext(tempfile.TemporaryDirectory())
        with contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);model,env=self.make(root,SyntheticBridge(terminate_after=1000))
            old=PPO('MlpPolicy',env,n_steps=8,batch_size=8,n_epochs=1,device='cpu',seed=5)
            old.learn(8);old.save(root/'old.zip')
            resumed=ResilientPPO.load(root/'old.zip',env=env,device='cpu')
            for a,b in zip(old.policy.parameters(),resumed.policy.parameters()):
                self.assertTrue(torch.equal(a,b))
            resumed.configure_recovery(root/'resume_recoveries')
            resumed.learn(8,reset_num_timesteps=False)
            self.assertEqual(resumed.num_timesteps,16)
            resumed.save(root/'new.zip')
            evaluated=PPO.load(root/'new.zip',device='cpu')
            for a,b in zip(resumed.policy.parameters(),evaluated.policy.parameters()):
                self.assertTrue(torch.equal(a,b))
