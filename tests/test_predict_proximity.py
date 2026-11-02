import unittest
from test_proximity import fixture
from predict_proximity import PredictiveDetector,interval
class PredictiveTests(unittest.TestCase):
    def test_interval_requires_simultaneous_overlap(self):
        self.assertIsNone(interval(5000,0,4096,30))
        self.assertEqual(interval(0,0,100,30),(0,30))
        self.assertIsNone(interval(200,10,100,30))
    def sequence(self,lats,gaps):
        d=PredictiveDetector()
        for i,(lat,gap) in enumerate(zip(lats,gaps)):
            p,r=fixture(frame=i+1);r[2].update(lateral=lat,progress=1000+gap)
            result=next(v for v in d.update(p,r) if v['id']==2)
        return result
    def test_lateral_approach_precedes_current_alignment(self):
        r=self.sequence([7000,6800,6600,6400],[160,150,140,130])
        self.assertEqual(r['proximity_warning'],0);self.assertEqual(r['predicted_warning'],1)
        self.assertGreater(r['predicted_entry_frames'],0)
    def test_lateral_departure_is_not_future_overlap(self):
        r=self.sequence([6400,6600,6800,7000],[160,150,140,130])
        self.assertEqual(r['predicted_warning'],0)
    def test_jump_masks_prediction(self):
        r=self.sequence([0,0,0,15000],[150,140,130,120])
        self.assertEqual(r['prediction_valid'],0)
    def test_new_detector_has_no_inherited_history(self):
        p,r=fixture();out=PredictiveDetector().update(p,r)
        self.assertTrue(all(x['prediction_valid']==0 for x in out))
    def test_different_axis_arrival_times_do_not_warn(self):
        r=self.sequence([20000,19500,19000,18500],[200,150,100,50])
        self.assertEqual(r['predicted_warning'],0)
