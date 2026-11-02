"""PPO CPU real em transicoes sinteticas: valida pipeline, nunca pilotagem."""
from __future__ import annotations
import contextlib
import copy
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from test_reward import ROOT, telemetry
from env_topgear import TopGearEnv
from experiment import (contract, contract_hash, save_checkpoint, validate_checkpoint,
                        atomic_json, assert_live_preflight, source_hashes, sha256, ppo_options)
from protocol import ProtocolError
from recording import RecordingEnv
from callbacks import RaceMetricsCallback
from promote_model import assess
from telemetry import Telemetry
from topgear_config import ProjectConfig
import preflight_live


class SyntheticBridge:
    address = ('127.0.0.1', 55355)
    def __init__(self, terminate_after=8):
        self.resets = 0
        self.closed = False
        self.terminate_after = terminate_after
        self.initial = telemetry(track_length=22528, speed=1000)
        self.current = self.initial
        self.counter = 0
    def response(self):
        from test_live_detector import packet, navigation_packet
        fields={k:str(v) for k,v in asdict(self.current).items()}
        fields['detector_samples']=packet(self.current, count=1 if self.counter==0 else 4)
        fields['navigation_samples']=navigation_packet(self.current, count=1 if self.counter==0 else 4)
        return SimpleNamespace(fields=fields)
    def wait_ready(self): return self.response()
    def reset(self):
        self.resets += 1
        self.current, self.counter = self.initial, 0
        return self.response()
    def step(self, action):
        self.counter += 1
        speed = max(0, self.current.speed + (100 if action in (1,3,4) else -100 if action == 2 else -30))
        done = self.counter >= self.terminate_after
        self.current = replace(self.current, frame=self.current.frame+4,
            speed=speed, progress=self.current.progress+int(speed>0)*20,
            lateral=self.current.lateral+(-100 if action==3 else 100 if action==4 else 0),
            finished=int(done), final_rank=19 if done else -1)
        return self.response()
    def close(self): self.closed=True


class ExperimentTests(unittest.TestCase):
    def test_ppo_update_checkpoint_resume_and_recorded_automatic_resets(self):
        cfg=ProjectConfig.load(ROOT)
        expected=contract(cfg)
        expected['ppo'].update(n_steps=16, batch_size=8, n_epochs=1)
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            bridge=SyntheticBridge()
            with patch('env_topgear.BridgeClient',return_value=bridge), contextlib.redirect_stdout(io.StringIO()):
                env=Monitor(RecordingEnv(TopGearEnv(ROOT),path/'logs'))
            try:
                model=PPO('MlpPolicy',env,**expected['ppo'],seed=3,device='cpu',
                          policy_kwargs={'net_arch':{'pi':[64,64],'vf':[64,64]}})
                initial=[p.detach().clone() for p in model.policy.parameters()]
                callback=RaceMetricsCallback(path/'checkpoints',expected,'synthetic_test',16,{},verbose=0)
                with contextlib.redirect_stdout(io.StringIO()):model.learn(64,callback=callback)
                self.assertTrue((path/'checkpoints/training_candidate.json').is_file())
                validate_checkpoint(path/'checkpoints/checkpoint_16_steps.zip',expected)
                self.assertTrue(any(not torch.equal(a,b) for a,b in zip(initial,model.policy.parameters())))
                self.assertGreaterEqual(bridge.resets,9)
                p=save_checkpoint(model,path/'model.zip',expected,run='synthetic_test',reason='unit_test')
                validate_checkpoint(p,expected)
                before=sha256(p)
                obs,_=env.reset()
                original_action=model.predict(obs,deterministic=True)[0]
                restored=PPO.load(p,env=env,device='cpu')
                self.assertEqual(int(original_action),int(restored.predict(obs,deterministic=True)[0]))
                restored.learn(16,reset_num_timesteps=False)
                self.assertEqual(restored.num_timesteps,80)
                self.assertEqual(sha256(p),before)
                with self.assertRaises(FileExistsError):
                    save_checkpoint(restored,p,expected,run='x',reason='do_not_overwrite')
                incompatible=copy.deepcopy(expected)
                incompatible['action_schema']+=1
                with self.assertRaisesRegex(ValueError,'incompativel'):validate_checkpoint(p,incompatible)
                p.write_bytes(p.read_bytes()[:-8]+b'badbytes')
                with self.assertRaisesRegex(ValueError,'SHA-256'):validate_checkpoint(p,expected)
            finally:env.close()
            records=[json.loads(x) for x in (path/'logs/episodes.jsonl').read_text().splitlines()]
            endings=[r for r in records if r['event']=='episode_end']
            self.assertGreaterEqual(len(endings),8)
            self.assertTrue(all(r['final_state']['race_completed']==0 for r in endings))
            self.assertTrue(bridge.closed)

    def test_historical_model_rejected_without_unpickling(self):
        path=ROOT/'archive/models/final_10240_steps.zip'
        with self.assertRaisesRegex(ValueError,'sem contrato'):validate_checkpoint(path,contract(ProjectConfig.load(ROOT)))

    def test_invalid_metadata_rejected_before_model_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'a.zip';path.write_bytes(b'not_a_model')
            path.with_suffix('.zip.json').write_text('{broken')
            with self.assertRaisesRegex(ValueError,'corrompido'):validate_checkpoint(path)

    def test_reset_fingerprint_rejects_changed_save(self):
        bridge=SyntheticBridge()
        expected=asdict(bridge.initial);expected['frame']+=1
        with patch('env_topgear.BridgeClient',return_value=bridge):
            env=TopGearEnv(ROOT,expected_reset=expected)
        try:
            with self.assertRaisesRegex(ProtocolError,'mudou'):env.reset()
        finally:env.close()

    def test_finish_alias_consistency_checked(self):
        fields={k:str(v) for k,v in asdict(telemetry()).items()}
        fields['race_completed']='1'
        with self.assertRaisesRegex(ProtocolError,'Alias'):Telemetry.from_fields(fields)

    def test_preflight_records_only_success_and_invalidates_after_code_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            cfg=replace(ProjectConfig.load(ROOT),project_dir=root)
            bridge=SyntheticBridge(terminate_after=1000)
            with patch('preflight_live.ProjectConfig.load',return_value=cfg), \
                 patch('preflight_live.BridgeClient',return_value=bridge), \
                 contextlib.redirect_stdout(io.StringIO()):
                preflight_live.main()
            receipt=assert_live_preflight(cfg,contract(cfg))
            self.assertEqual(len(receipt['branches']),5)
            self.assertEqual(bridge.resets,5)
            (root/'python').mkdir();(root/'python/protocol.py').write_text('# changed\n')
            with self.assertRaisesRegex(ValueError,'Preflight'):assert_live_preflight(cfg,contract(cfg))

    def test_same_save_repeated_twenty_times_cannot_promote(self):
        expected=contract(ProjectConfig.load(ROOT))
        initial={'frame':1,'speed':100,'lateral':0,'progress':100,'lap':0,'rank':19,'nitro':3}
        episode={'controller':'model','completed':True,'initial_state':initial,
                 'summary':{'race_completed':1,'is_first':1,'offtrack_fraction':0}}
        report={'evaluation_version':3,'status':'completed','deterministic':True,
                'training_enabled':False,'model_sha256_before':'abc','model_sha256_after':'abc',
                'contract':expected,'scenario_id':'save1','episodes':[episode]*20}
        metrics=assess([report]*3,'abc',expected)
        self.assertFalse(metrics['approved']);self.assertEqual(metrics['episodes'],1)
        self.assertEqual(metrics['duplicate_initial_states_ignored'],59)

    def test_failed_new_preflight_invalidates_old_receipt_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=replace(ProjectConfig.load(ROOT),project_dir=Path(directory))
            bridge=SyntheticBridge(terminate_after=1)
            old=Path(directory)/'runs/preflight/latest.json'
            atomic_json(old,{'status':'passed'})
            with patch('preflight_live.ProjectConfig.load',return_value=cfg), \
                 patch('preflight_live.BridgeClient',return_value=bridge), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):preflight_live.main()
            result=json.loads(old.read_text())
            self.assertEqual(result['status'],'failed')
            self.assertEqual(len(result['branches']['coast']['states']),1)
            with self.assertRaises(ValueError):assert_live_preflight(cfg,contract(cfg))


if __name__=='__main__':unittest.main()
