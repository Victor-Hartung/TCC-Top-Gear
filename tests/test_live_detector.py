import unittest
from dataclasses import replace
from types import SimpleNamespace
from test_reward import ROOT,telemetry
from live_detector import evaluate,parse_samples
from protocol import ProtocolError

def packet(t,count=4):
    samples=[]
    for f in range(t.frame-count+1,t.frame+1):
        values=[f,t.progress,t.lateral,t.track_length]
        for i in range(2,20):values.extend([i,(t.progress+i*100)%t.track_length,0])
        samples.append(','.join(map(str,values)))
    return ';'.join(samples)

def navigation_packet(t,count=4):
    """Fixture sintetica: jogadores em registros distintos, P2 a frente."""
    word = (40 << 8) | 216  # limites internos [-10240, 10240]
    return ';'.join(','.join(map(str, [f,0,18,t.progress,t.lateral,
        (t.progress+150)%t.track_length,7000,(t.progress+150)%t.track_length,7000,
        word,word,0,0,0])) for f in range(t.frame-count+1,t.frame+1))

class LiveDetectorTests(unittest.TestCase):
    def test_packet_and_features(self):
        t=telemetry(track_length=22528)
        features,rows=evaluate(packet(t),t)
        self.assertEqual(len(features),21);self.assertTrue(all(-1<=v<=1 for v in features))
        self.assertTrue(all(r['prediction_valid'] for r in rows))
    def test_reset_does_not_inherit_velocity(self):
        t=telemetry(track_length=22528,lap=-1)
        _,rows=evaluate(packet(t,count=1),t)
        self.assertTrue(rows);self.assertTrue(all(r['prediction_valid']==0 for r in rows))
    def test_missing_duplicate_stale_and_partial_rejected(self):
        t=telemetry(track_length=22528);valid=packet(t)
        for bad in ['',valid.replace(',2,',',3,',1),packet(replace(t,frame=t.frame-1)), ';'.join(valid.split(';')[:2])]:
            with self.assertRaises(ProtocolError):evaluate(bad,t)
    def test_actual_lua_packet_matches_telemetry(self):
        from test_lua_bridge import LuaBridgeTests
        from telemetry import Telemetry,ObservationBuilder
        from topgear_config import ProjectConfig
        LuaBridgeTests.setUpClass();fixture=LuaBridgeTests()
        states,_,_,_=fixture.execute_bridge(fixture.commands())
        start=Telemetry.from_fields(states[1]);end=Telemetry.from_fields(states[2])
        self.assertEqual(len(parse_samples(start.detector_samples,start)),1)
        self.assertEqual(len(parse_samples(end.detector_samples,end)),4)
        builder=ObservationBuilder(ProjectConfig.load(ROOT));builder.reset(start)
        obs=builder.build(end);self.assertEqual(obs.shape,(61,))
        self.assertEqual(states[2]['bridge_revision'],'5')

    def test_lua_exposes_racers_before_first_lap(self):
        from test_lua_bridge import LuaBridgeTests
        from telemetry import Telemetry
        LuaBridgeTests.setUpClass();fixture=LuaBridgeTests()
        states,_,_,_=fixture.execute_bridge(fixture.commands(),initial_lap=-1)
        initial=Telemetry.from_fields(states[1]);end=Telemetry.from_fields(states[2])
        self.assertEqual(initial.opponent_count,0)  # campo legado ainda mascarado
        features,rows=evaluate(initial.detector_samples,initial)
        self.assertEqual(len(parse_samples(initial.detector_samples,initial)[0][4]),18)
        self.assertTrue(rows);self.assertTrue(all(r['prediction_valid']==0 for r in rows))
        _,rows=evaluate(end.detector_samples,end)
        self.assertTrue(all(r['prediction_valid']==1 for r in rows))

    def test_missing_sensor_blocks_runtime_readiness(self):
        t=telemetry(track_length=22528)
        with self.assertRaisesRegex(ProtocolError,'historico'):
            t.assert_runtime_ready(require_detector=True)

    def test_group_features_describe_same_threat_in_all_regions(self):
        for region_index,gaps in enumerate([(40,90),(-40,-90),(5,10)]):
            t=telemetry(track_length=22528,lateral=0)
            samples=[]
            for f in range(t.frame-3,t.frame+1):
                v=[f,t.progress,t.lateral,t.track_length]
                for identity in range(2,20):
                    gap=gaps[identity-2] if identity in (2,3) else 4000
                    lateral=9000 if identity==2 else 0
                    v.extend([identity,(t.progress+gap)%t.track_length,lateral])
                samples.append(','.join(map(str,v)))
            features,rows=evaluate(';'.join(samples),t)
            selected=[r for r in rows if r['selected_for_observation']]
            self.assertEqual([r['id'] for r in selected],[3])
            start=region_index*7
            self.assertEqual(features[start+2],0)
            self.assertAlmostEqual(features[start+1],gaps[1]/2252.8)
            self.assertEqual(features[start+6],1)
            self.assertEqual(next(r for r in rows if r['id']==2)['risk'],0)

    def test_zero_risk_falls_back_to_nearest_with_consistent_fields(self):
        t=telemetry(track_length=22528,lateral=0)
        features,rows=evaluate(packet(t,count=1),t)
        selected=[r for r in rows if r['selected_for_observation']]
        self.assertEqual([r['id'] for r in selected],[2])
        self.assertEqual(features[5:7],[0.,0.])
