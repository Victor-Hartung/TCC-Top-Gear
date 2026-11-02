import unittest
from test_reward import ROOT
from benchmark_manual import FirstNitroGate


class ManualBenchmarkTests(unittest.TestCase):
    def test_only_turbo_button_removed_preserving_acceleration_and_shift(self):
        gate = FirstNitroGate(3000)
        state = dict(speed=0, turbo_active=0, turbo_charges_used=0)
        self.assertEqual([gate.apply(a,state) for a in range(30)],
                         [1 if a==9 else 11 if a==19 else 21 if a==29 else a for a in range(30)])

    def test_gate_never_reblocks_after_speed_reached(self):
        gate = FirstNitroGate(3000)
        self.assertEqual(gate.apply(19,dict(speed=2999)),11)
        self.assertEqual(gate.apply(19,dict(speed=3000)),19)
        self.assertEqual(gate.apply(29,dict(speed=0)),29)

    def test_active_or_used_charge_is_not_interrupted(self):
        for state in [dict(speed=0,turbo_active=1),dict(speed=0,turbo_charges_used=1)]:
            self.assertEqual(FirstNitroGate(3000).apply(29,state),29)

    def test_baseline_preserves_all_actions(self):
        gate=FirstNitroGate()
        self.assertEqual([gate.apply(a,dict(speed=0)) for a in range(30)],list(range(30)))

    def test_invalid_manual_action_is_rejected(self):
        with self.assertRaises(ValueError):
            FirstNitroGate(3000).apply(30,dict(speed=0))
