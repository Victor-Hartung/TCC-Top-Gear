"""Cenarios sinteticos para identidade, trajetoria e previsao; nao corridas reais."""
import unittest

from test_reward import ROOT
from live_detector import evaluate_samples
from native_navigation import augment_samples, evaluate, decode_corridor
from protocol import ProtocolError


def scene(*, gaps=None, lateral=None, player_lateral=None, progress=None, count=4, mutate=None):
    gaps, lateral = gaps or {}, lateral or {}
    player_lateral = player_lateral or [0] * count
    progress = progress or [1000] * count
    at = lambda value, i: value[i] if isinstance(value, list) else value
    samples, wire = [], []
    for i in range(count):
        frame, p, lat = 100+i, progress[i], player_lateral[i]
        racers = {identity: ((p+at(gaps.get(identity, 8000+identity*100),i))%22528,
                              at(lateral.get(identity, 0),i)) for identity in range(2,20)}
        samples.append((frame,p,lat,22528,racers))
        p2_progress = (p+at(gaps.get(1,9000),i))%22528
        p2_lateral = at(lateral.get(1,0),i)
        # Dois jogadores com offsets dinamicos, sem inferir identidade pelo ID.
        values = [frame,0,18,p,lat,p2_progress,p2_lateral,p2_progress,p2_lateral,
                  0x28D8,0x28D8,0,0,0]
        if mutate:
            mutate(i, values)
        wire.append(','.join(map(str,values)))
    text = ';'.join(wire)
    augmented, parsed = augment_samples(text,samples)
    _, rows = evaluate_samples(augmented)
    features, diagnostic = evaluate(parsed,samples,rows)
    return features, diagnostic, rows, samples, parsed, text


class NativeNavigationTests(unittest.TestCase):
    def test_signed_bounds_and_empty_road_candidate(self):
        self.assertEqual(decode_corridor(0x28D8),(-10240,10240))
        features, diagnostic, *_ = scene()
        self.assertEqual(features[0],1)
        self.assertEqual(diagnostic['target'],0)
        self.assertEqual(diagnostic['free_intervals'],[[-10240,10240]])
        self.assertFalse(diagnostic['is_physical_road_edge'])

    def test_all_car_intervals_affect_target_even_when_not_selected(self):
        features, diagnostic, rows, *_ = scene(gaps={2:300,3:400},lateral={2:-3000,3:3000})
        self.assertEqual(diagnostic['blocking_ids'],[2,3])
        self.assertEqual(len([r for r in rows if r['selected_for_observation']]),1)
        self.assertLess(diagnostic['target'],-8120)
        self.assertEqual(features[13],1)

    def test_close_center_car_gives_symmetric_space_with_deterministic_left_target(self):
        features, diagnostic, *_ = scene(gaps={2:250})
        self.assertEqual(diagnostic['blocked_intervals'],[[-5120,5120]])
        self.assertEqual(diagnostic['target'],-7680)
        self.assertEqual(features[10],features[11])

    def test_full_corridor_occupied_never_claims_valid_target(self):
        features, diagnostic, *_ = scene(gaps={2:200,3:200,4:200},lateral={2:-7000,3:0,4:7000})
        self.assertEqual(features[0],1)  # leitura valida, caminho indisponivel
        self.assertEqual(features[13],0)
        self.assertEqual(diagnostic['free_intervals'],[])
        self.assertIsNone(diagnostic['target'])

    def test_stationary_car_absolute_sweep_is_not_player_steering(self):
        _, diagnostic, *_ = scene(gaps={2:200},player_lateral=[-300,-200,-100,0])
        self.assertEqual(diagnostic['blocked_intervals'],[[-5120,5120]])

    def test_approach_outside_published_sensor_radius_is_predicted(self):
        features, diagnostic, rows, *_ = scene(gaps={2:[2510,2440,2370,2300]})
        self.assertFalse(any(r['id']==2 for r in rows))
        self.assertIn(2,diagnostic['blocking_ids'])
        self.assertNotEqual(diagnostic['target'],0)
        self.assertEqual(features[13],1)

    def test_far_car_receding_behind_does_not_block(self):
        _, diagnostic, *_ = scene(gaps={2:[-450,-470,-490,-510]})
        self.assertNotIn(2,diagnostic['blocking_ids'])
        self.assertEqual(diagnostic['target'],0)

    def test_car_approaching_from_behind_blocks_forecast_interval(self):
        _, diagnostic, *_ = scene(gaps={2:[-650,-600,-550,-500]})
        self.assertIn(2,diagnostic['blocking_ids'])

    def test_p2_wrap_and_slot_reorder_preserve_identity_and_prediction(self):
        def reorder(i, values):
            values[1:3] = [18*i,18*(i+1)]
        features, diagnostic, rows, *_ = scene(gaps={1:80},progress=[22520,22524,0,4],mutate=reorder)
        p2 = next(row for row in rows if row['id']==1)
        self.assertEqual(p2['gap'],80)
        self.assertEqual(p2['long_velocity'],0)
        self.assertEqual(features[1],1)
        self.assertEqual(features[6],1)
        self.assertTrue(diagnostic['identity_valid'])

    def test_invalid_previous_p2_frame_does_not_inherit_velocity(self):
        def invalid_first(i, values):
            if i==0: values[2]=values[1]
        features, _, rows, *_ = scene(gaps={1:80},mutate=invalid_first)
        self.assertEqual(features[1],1)
        self.assertEqual(features[6],0)
        self.assertEqual(next(r for r in rows if r['id']==1)['prediction_valid'],0)

    def test_reset_has_no_prediction_history(self):
        features, diagnostic, *_ = scene(gaps={1:80},count=1)
        self.assertEqual(features[0],1)
        self.assertEqual(features[6:8],[0.,0.])
        self.assertTrue(diagnostic['identity_valid'])

    def test_invalid_corridor_masks_hints(self):
        features, diagnostic, *_ = scene(mutate=lambda i,v:v.__setitem__(9,0))
        self.assertEqual(features[0],0)
        self.assertEqual(features[8:],[0.]*6)
        self.assertIn('corridor_bounds_invalid',diagnostic['reasons'])

    def test_malformed_or_unsynchronized_packet_is_rejected(self):
        _, _, _, samples, _, text = scene()
        for broken in ('',text+';'+text.split(';')[0],text.replace('100,0,18','99,0,18',1),text.replace('100,0,18','100,0,18,99',1)):
            with self.subTest(packet=broken[:40]), self.assertRaises(ProtocolError):
                augment_samples(broken,samples)

    def test_alongside_target_moves_away_from_car(self):
        _, diagnostic, *_ = scene(gaps={2:0},lateral={2:3000})
        self.assertLess(diagnostic['target'],0)
        self.assertNotIn('alongside_blocks_access',diagnostic['reasons'])

    def test_jump_does_not_create_long_range_forecast(self):
        _, diagnostic, *_ = scene(gaps={2:[6000,5500,5000,2300]})
        self.assertNotIn(2,diagnostic['blocking_ids'])


if __name__=='__main__':
    unittest.main()
