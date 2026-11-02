import os
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from blue_auto import validate_wire
from experiment import contract, preflight_receipt_path
from protocol import ProtocolError
from policy_transfer import _blue_auto_outcome_transfer
from topgear_config import ProjectConfig
from outcome_objective import REWARD_VERSION
from reward_revision import legacy_outcome_contract


ROOT = Path(__file__).resolve().parents[1]


class BlueAutoProfileTests(unittest.TestCase):
    def test_separate_profile_keeps_automatic_action_and_observation_contract(self):
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_blue_auto.ini'):
            blue = ProjectConfig.load(ROOT)
        original = ProjectConfig.load(ROOT)
        new_contract, old_contract = contract(blue), contract(original)
        self.assertEqual(blue.integer('protocol', 'savestate_slot'), 3)
        self.assertEqual(new_contract['reward_profile'], 'road_v6_outcome')
        self.assertEqual(new_contract['reward_version'], REWARD_VERSION)
        self.assertEqual(new_contract['actions'], old_contract['actions'])
        self.assertEqual(new_contract['observation_names'], old_contract['observation_names'])
        self.assertNotEqual(preflight_receipt_path(blue), preflight_receipt_path(original))

    def test_reset_identity_rejects_wrong_car_or_shift_masks(self):
        fields = {'manual_mode': '0', 'car_table_offset_raw': '48',
                  'upshift_mask_raw': '0', 'downshift_mask_raw': '0'}
        validate_wire(fields)
        for key, value in [('manual_mode', '1'), ('car_table_offset_raw', '0'),
                           ('upshift_mask_raw', '16'), ('downshift_mask_raw', '32')]:
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                validate_wire({**fields, key: value})

    def test_actor_transfer_permits_only_known_auto_car_and_reward_change(self):
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_blue_auto.ini'):
            target = contract(ProjectConfig.load(ROOT))
        source = contract(ProjectConfig.load(ROOT), 'road_v3_turbo')
        self.assertTrue(_blue_auto_outcome_transfer(source, target))
        for changed in (
            lambda c: c['actions'].reverse(),
            lambda c: c['settings']['episode'].__setitem__('max_steps', '999'),
            lambda c: c['observation_names'].__setitem__(0, 'unknown'),
            lambda c: c.__setitem__('savestate_slot', 2),
            lambda c: c['ppo'].__setitem__('gamma', .5),
            lambda c: c['ppo'].__setitem__('gae_lambda', .95),
            lambda c: c.__setitem__('race_objective', {'unexpected': True}),
        ):
            with self.subTest(change=changed):
                altered = copy.deepcopy(target)
                changed(altered)
                self.assertFalse(_blue_auto_outcome_transfer(source, altered))

    def test_reward_revision_actor_transfer_rejects_extra_changes(self):
        with patch.dict(os.environ, TOPGEAR_PROFILE='game_profile_blue_auto.ini'):
            target = contract(ProjectConfig.load(ROOT))
        source = legacy_outcome_contract(target)
        self.assertTrue(_blue_auto_outcome_transfer(source, target))
        for changed in (
            lambda c: c['actions'].reverse(),
            lambda c: c['ppo'].__setitem__('learning_rate', .0001),
            lambda c: c['reward_weights'].__setitem__('progress', 40.0),
            lambda c: c['reward_weights'].__setitem__('rank_delta', 1.0),
            lambda c: c['outcome_objective'].__setitem__('rank_gain_multiplier', 3.0),
            lambda c: c['outcome_objective'].__setitem__('rank_loss_multiplier', 3.0),
            lambda c: c['outcome_objective'].__setitem__('preline_idle_grace_steps', 1),
        ):
            with self.subTest(change=changed):
                altered = copy.deepcopy(target)
                changed(altered)
                self.assertFalse(_blue_auto_outcome_transfer(source, altered))
