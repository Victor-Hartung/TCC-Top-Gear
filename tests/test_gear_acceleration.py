import csv
from pathlib import Path
import tempfile
import unittest
from lupa import LuaRuntime, LuaError
from test_reward import ROOT
from analisar_ensaio_cambio import analyze


class GearAccelerationTests(unittest.TestCase):
    def simulate(self, collision=False, divergent=False, load_ok=True, ignore_measure_shift=False, legacy=False, wrong_car=False, previous_blue=False, rolling=False, slow_start=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'runs/diagnostics').mkdir(parents=True)
            profile=root/'config/game_profile.ini'
            profile.write_text('profile_version=3\naccelerate_button=X\nbrake_button=Y\nturbo_button=A\nrom_sha1=f686806c676a4b087a3627babbe3555d3704e3b1\n')
            lua=LuaRuntime(unpack_returned_tuples=True)
            state=dict(frame=0,gear=0,speed=0,fuel=43007,buttons={},up=False,trial=0)
            def read(a):
                return {0x1E72:state['gear'],0x1E5A:state['speed'],0x1E62:state['fuel'],
                        0x1E6C:3,0x1E5E:state['speed']//2,0x1F7A:16,0x1F7C:32,
                        0x1EE8:0 if legacy or wrong_car else 48,
                        0x0727:1,0x1EF5:128 if collision and state['frame']>(20 if rolling else 500) else 0,
                        0x0100:1 if divergent and state['trial']==2 else 0}.get(a,0)
            def advance():
                b=state['buttons'];up=b.get('R',False)
                if up and not state['up'] and not (ignore_measure_shift and state['gear']==3):
                    state['gear']=min(4,state['gear']+1)
                if rolling or state['frame']>=197:
                    state['speed']+=[30,25,20,15,6][state['gear']]
                    state['fuel']-=2 if state['gear']==4 else 3
                state.update(frame=state['frame']+1,up=up)
            loads=[]
            def load(slot,quiet):
                loads.append(slot)
                state.update(frame=0,gear=3 if rolling else 0,speed=(7000 if slow_start else 8000) if rolling else 0,
                             fuel=43007,buttons={},up=False,trial=state['trial']+1)
                return load_ok
            g=lua.globals()
            g.forms=lua.table_from(dict(openfile=lambda *a:str(profile)))
            g.gameinfo=lua.table_from(dict(getromhash=lambda:'f686806c676a4b087a3627babbe3555d3704e3b1'))
            g.memory=lua.table_from(dict(usememorydomain=lambda d:True,getcurrentmemorydomainsize=lambda:131072,read_u16_le=read,read_u8=lambda a:read(a)&255))
            g.joypad=lua.table_from(dict(set=lambda b,p:state.update(buttons=dict(b))))
            g.emu=lua.table_from(dict(frameadvance=advance,framecount=lambda:state['frame']))
            g.gui=lua.table_from(dict(text=lambda *a:None))
            g.console=lua.table_from(dict(log=lambda *a:None))
            g.event=lua.table_from(dict(onexit=lambda *a:None))
            g.savestate=lua.table_from(dict(loadslot=load))
            source=(ROOT/('lua/ensaio_cambio_lancado.lua' if rolling else 'lua/ensaio_cambio.lua')).read_text(encoding='utf-8')
            if legacy:
                source=source.replace('capture_version,prep_frames,measure_frames=7,360,24',
                                      'capture_version,prep_frames,measure_frames=1,240,180')
                source=source.replace('expected_car=48','expected_car=0')
            elif previous_blue:
                source=source.replace('capture_version,prep_frames,measure_frames=7,360,24',
                                      'capture_version,prep_frames,measure_frames=5,240,60')
            if not load_ok:
                with self.assertRaisesRegex(LuaError,'Nao foi possivel carregar slot [23]'):lua.execute(source)
            elif wrong_car:
                with self.assertRaisesRegex(LuaError,'Save difere do carro'):lua.execute(source)
            elif slow_start:
                with self.assertRaisesRegex(LuaError,'Slot 3 exige GEAR 4'):lua.execute(source)
            else:lua.execute(source)
            self.assertFalse(any(state['buttons'].values()))
            self.assertEqual(loads,[3 if rolling else 2]* (4 if load_ok and not wrong_car and not slow_start else 1))
            with next((root/'runs/diagnostics').glob('*.csv')).open() as f:
                rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
            if legacy:
                for row in rows:
                    for key in ('capture_version','prep_frames','measure_frames'):row.pop(key)
            return rows

    def test_actual_lua_paired_runs_simulated_no_training(self):
        report=analyze(self.simulate())
        self.assertEqual(report['status'],'paired_measurement_ok',report['errors'])
        self.assertGreater(report['hold_minus_shift']['speed_gain_raw'],0)
        self.assertFalse(report['training_authorized'])
        self.assertFalse(report['manual_vs_automatic_validated'])
        self.assertFalse(report['optimal_shift_point_validated'])
        self.assertEqual(report['measure_frames'],24)
        self.assertEqual(report['prep_frames'],360)
        self.assertEqual(report['capture_version'],7)
        self.assertEqual(report['car'],'blue')

    def test_first_blue_point_keeps_its_original_schedule(self):
        report=analyze(self.simulate(previous_blue=True))
        self.assertEqual(report['status'],'paired_measurement_ok',report['errors'])
        self.assertEqual(report['capture_version'],5)
        self.assertEqual(report['prep_frames'],240)

    def test_rolling_start_actual_lua_uses_only_slot_three(self):
        rows=self.simulate(rolling=True)
        result=analyze(rows)
        self.assertEqual(result['status'],'paired_measurement_ok',result['errors'])
        self.assertEqual(result['savestate_slot'],3)
        self.assertTrue(result['rolling_start'])
        self.assertEqual(len(rows),480)
        self.assertEqual(result['capture_version'],10)
        self.assertEqual(result['measure_frames'],120)
        self.assertTrue(all(r['phase']==2 for r in rows))
        self.assertGreater(result['hold_minus_shift']['speed_gain_raw'],0)

    def test_rolling_start_rejects_bad_save_and_collision(self):
        self.assertEqual(analyze(self.simulate(rolling=True,slow_start=True))['status'],'incomplete')
        self.assertEqual(analyze(self.simulate(rolling=True,load_ok=False))['status'],'incomplete')
        self.assertEqual(analyze(self.simulate(rolling=True,collision=True))['status'],'inconclusive')
        self.assertEqual(analyze(self.simulate(rolling=True,divergent=True))['status'],'inconclusive')

    def test_rolling_capture_cannot_claim_wrong_slot_or_low_speed(self):
        rows=self.simulate(rolling=True)
        rows[0]['slot']=2
        self.assertEqual(analyze(rows)['status'],'inconclusive')
        rows[0]['slot']=3;rows[0]['speed_before']=7000
        self.assertEqual(analyze(rows)['status'],'inconclusive')

    def test_wrong_car_save_is_rejected_and_csv_identity_is_checked(self):
        self.assertEqual(analyze(self.simulate(wrong_car=True))['status'],'incomplete')
        rows=self.simulate()
        for row in rows:row['car_raw']=0
        self.assertEqual(analyze(rows)['status'],'inconclusive')

    def test_old_capture_keeps_its_original_schedule(self):
        report=analyze(self.simulate(legacy=True))
        self.assertEqual(report['status'],'paired_measurement_ok',report['errors'])
        self.assertEqual(report['measure_frames'],180)
        self.assertEqual(report['capture_version'],1)

    def test_changed_metadata_cannot_reinterpret_a_capture(self):
        rows=self.simulate()
        rows[-1]['measure_frames']=180
        self.assertEqual(analyze(rows)['status'],'incomplete')

    def test_collision_makes_comparison_inconclusive(self):
        report=analyze(self.simulate(collision=True))
        self.assertEqual(report['status'],'inconclusive')
        self.assertNotIn('hold_minus_shift',report)
        self.assertEqual(len(report['interferences']),4)
        self.assertTrue(all(e['kind']=='impact' for e in report['interferences']))

    def test_different_wram_even_with_identical_car_telemetry_is_rejected(self):
        report=analyze(self.simulate(divergent=True))
        self.assertEqual(report['status'],'inconclusive')
        self.assertTrue(any('WRAM' in e for e in report['errors']))

    def test_ignored_shift_is_not_a_comparison_of_different_gears(self):
        report=analyze(self.simulate(ignore_measure_shift=True))
        self.assertEqual(report['status'],'inconclusive')

    def test_missing_save_and_partial_capture_cannot_pass(self):
        self.assertEqual(analyze(self.simulate(load_ok=False))['status'],'incomplete')
        self.assertEqual(analyze(self.simulate()[:-1])['status'],'incomplete')

    def test_coast_or_nitro_or_offroad_cannot_pass(self):
        rows=self.simulate()
        for field,value in [('accelerate',0),('nitro_after',2),('surface_after',2)]:
            with self.subTest(field=field):
                edited=[dict(r) for r in rows]
                edited[-1][field]=value
                self.assertEqual(analyze(edited)['status'],'inconclusive')
