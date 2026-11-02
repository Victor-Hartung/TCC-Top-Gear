import unittest
from test_reward import ROOT
from detect_proximity import Detector

def fixture(frame=1,progress=1000,lateral=0):
    p=dict(frame=frame,progress=progress,lateral=lateral,track_length=22528)
    rows=[dict(id=i,progress=1300+i*100,lateral=10000) for i in range(20)]
    return p,rows

class ProximityTests(unittest.TestCase):
    def test_front_rear_alongside_and_lateral_clearance(self):
        p,r=fixture();r[2].update(progress=1090,lateral=0);r[3].update(progress=910,lateral=0);r[4].update(progress=1000,lateral=4424)
        result={v['id']:v for v in Detector().update(p,r)}
        self.assertEqual(result[2]['region_candidate'],'front');self.assertEqual(result[3]['region_candidate'],'rear')
        self.assertEqual(result[4]['region_candidate'],'alongside');self.assertEqual(result[4]['proximity_warning'],0)
        self.assertEqual(result[2]['proximity_warning'],1);self.assertFalse(result[2]['validated'])
    def test_id_tracking_survives_reordering_and_detects_rear_approach(self):
        d=Detector();p,r=fixture();r[2].update(progress=800,lateral=0);d.update(p,r)
        p['frame']=2;r[2]['progress']=810
        result={v['id']:v for v in d.update(p,list(reversed(r)))}
        self.assertEqual(result[2]['closing_raw'],10);self.assertEqual(result[2]['frames_to_longitudinal_alignment'],19)
    def test_wrap_and_temporal_discontinuity(self):
        d=Detector();p,r=fixture(progress=22520);r[2].update(progress=10,lateral=0)
        self.assertEqual(next(v for v in d.update(p,r) if v['id']==2)['gap'],18)
        p['frame']=4
        with self.assertRaises(ValueError):d.update(p,r)
    def test_duplicate_ids_rejected(self):
        p,r=fixture();r[3]['id']=2
        with self.assertRaises(ValueError):Detector().update(p,r)
