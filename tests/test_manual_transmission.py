import csv
from pathlib import Path
import tempfile
import unittest
from lupa import LuaError, LuaRuntime
from test_reward import ROOT
from analisar_cambio_manual import analyze


class ManualTransmissionTests(unittest.TestCase):
    def simulate(self, automatic=False, load_ok=True, launch_delay=0, stuck=False,
                 ignore_first_up=False, speed_dip=False, screenshot_ok=True):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'runs/diagnostics').mkdir(parents=True)
            profile=root/'config/game_profile.ini'
            profile.write_text('profile_version=3\naccelerate_button=X\nbrake_button=Y\nturbo_button=A\nrom_sha1=f686806c676a4b087a3627babbe3555d3704e3b1\n')
            lua=LuaRuntime(unpack_returned_tuples=True)
            state=dict(frame=0,gear=0,up=False,down=False,buttons={},up_count=0)
            def speed():
                if stuck or (speed_dip and state['frame']==80): return 0
                return min(7000,max(0,state['frame']-launch_delay)*20)
            def read(address):
                return {0x1E72:state['gear'],0x1E5A:speed(),0x1E76:65535,
                        0x1E5E:1000+state['gear']*100,0x1E6C:3}.get(address,0)
            def buttons(value,player):state['buttons']=dict(value)
            def advance():
                b=state['buttons'];up=b.get('R',False);down=b.get('L',False)
                if automatic:
                    if state['frame'] in (100,200,300,400):state['gear']+=1
                else:
                    if up and not state['up'] and speed()>0:
                        state['up_count']+=1
                        if not (ignore_first_up and state['up_count']==1):
                            state['gear']=min(4,state['gear']+1)
                    if down and not state['down'] and speed()>0:state['gear']=max(0,state['gear']-1)
                state.update(frame=state['frame']+1,up=up,down=down)
            g=lua.globals()
            g.forms=lua.table_from(dict(openfile=lambda *a:str(profile)))
            g.gameinfo=lua.table_from(dict(getromhash=lambda:'f686806c676a4b087a3627babbe3555d3704e3b1'))
            g.memory=lua.table_from(dict(usememorydomain=lambda d:True,getcurrentmemorydomainsize=lambda:131072,read_u16_le=read,read_u8=read))
            g.joypad=lua.table_from(dict(set=buttons))
            g.emu=lua.table_from(dict(frameadvance=advance,framecount=lambda:state['frame']))
            g.gui=lua.table_from(dict(text=lambda *a:None))
            g.console=lua.table_from(dict(log=lambda *a:None))
            g.event=lua.table_from(dict(onexit=lambda *a:None))
            screenshots=[]
            def screenshot(path):
                screenshots.append((state['frame'],state['gear'],Path(path).name))
                if screenshot_ok:Path(path).write_bytes(b'\x89PNG\r\n\x1a\n')  # API simulation only.
            g.client=lua.table_from(dict(screenshot=screenshot))
            loaded=[]
            def loadslot(slot,quiet):
                loaded.append(slot)
                return load_ok
            g.savestate=lua.table_from(dict(loadslot=loadslot))
            source=(ROOT/'lua/diagnostico_cambio_manual.lua').read_text(encoding='utf-8')
            if stuck:
                with self.assertRaisesRegex(LuaError,'Sem movimento suficiente'):lua.execute(source)
            elif not screenshot_ok:
                with self.assertRaisesRegex(LuaError,'Captura de painel nao foi salva'):lua.execute(source)
            else:
                lua.execute(source)
            self.assertEqual(loaded,[2])
            with next((root/'runs/diagnostics').glob('*.csv')).open() as f:
                rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
            self.assertFalse(any(state['buttons'].values()))
            if not stuck and screenshot_ok:
                with next((root/'runs/diagnostics').glob('*_hud.tsv')).open() as f:
                    index=list(csv.DictReader(f,delimiter='\t'))
                self.assertEqual(len(index),8)
                self.assertEqual([int(x['sequence_frame']) for x in index],[0,84,144,204,264,324,384,444])
                for shot,(emu_frame,gear,name) in zip(index,screenshots):
                    sample=rows[int(shot['relative_frame'])]
                    self.assertEqual(int(shot['emu_frame']),emu_frame)
                    self.assertEqual(int(shot['gear_raw']),gear)
                    self.assertEqual(shot['filename'],name)
                    self.assertEqual(sample['gear_after'],gear)
                    self.assertEqual(sample['emu_frame'],emu_frame)
            return rows

    def test_real_lua_sequence_against_simulated_manual_controls(self):
        result=analyze(self.simulate())
        self.assertEqual(result['status'],'controls_observed_ok')
        self.assertEqual(len(result['pulses']),7)
        self.assertFalse(result['rpm_calibrated'])
        self.assertFalse(result['hud_mapping_validated'])
        self.assertFalse(result['training_authorized'])

    def test_automatic_selection_is_not_reported_as_manual_success(self):
        self.assertEqual(analyze(self.simulate(automatic=True))['status'],'failed')

    def test_partial_capture_cannot_pass(self):
        self.assertEqual(analyze(self.simulate()[:10])['status'],'incomplete')

    def test_missing_slot_two_is_not_ignored(self):
        with self.assertRaises(LuaError):self.simulate(load_ok=False)

    def test_screenshot_failure_releases_controls_and_preserves_partial_capture(self):
        rows=self.simulate(screenshot_ok=False)
        self.assertEqual(analyze(rows)['status'],'incomplete')

    def test_delayed_launch_waits_for_movement_even_with_sentinel_lap(self):
        for delay in (197,600):
            with self.subTest(delay=delay):
                rows=self.simulate(launch_delay=delay)
                result=analyze(rows)
                self.assertEqual(result['status'],'controls_observed_ok')
                self.assertEqual(result['warmup_frames'],delay+82)
                self.assertEqual(result['gears_raw_observed'],list(range(5)))
                self.assertTrue(all(r['speed_before']>=1500 for r in rows if r['shift_up']))
                self.assertTrue(all(r['lap']==-1 for r in rows))

    def test_wait_requires_consecutive_moving_frames(self):
        result=analyze(self.simulate(speed_dip=True))
        self.assertEqual(result['status'],'controls_observed_ok')
        self.assertEqual(result['warmup_frames'],88)

    def test_no_movement_times_out_preserves_csv_and_releases_controls(self):
        rows=self.simulate(stuck=True)
        self.assertEqual(len(rows),1200)
        self.assertTrue(all(r['shift_up']==r['shift_down']==0 for r in rows))
        self.assertEqual(analyze(rows)['status'],'incomplete')

    def test_ignored_upshift_cannot_pass(self):
        result=analyze(self.simulate(ignore_first_up=True))
        self.assertEqual(result['status'],'failed')
        self.assertFalse(result['pulses'][0]['passed'])

    def test_forged_readiness_and_phase_clock_cannot_pass(self):
        rows=self.simulate()
        last_warmup=next(i for i,r in enumerate(rows) if r['phase']==1)-1
        rows[last_warmup]['speed_after']=0
        self.assertEqual(analyze(rows)['status'],'failed')
        rows[last_warmup]['sequence_frame']=0
        self.assertEqual(analyze(rows)['status'],'incomplete')

    def test_legacy_stationary_first_pulse_remains_failed(self):
        from analisar_cambio_manual import LEGACY_PULSES
        rows=self.simulate()
        legacy=[]
        gear=0
        for frame in range(1020):
            r=dict(rows[0],relative_frame=frame,emu_frame=frame,gear_before=gear)
            for key in ('capture_version','phase','sequence_frame'):r.pop(key)
            r['shift_up']=int(any(f<=frame<f+4 and d==1 for f,d in LEGACY_PULSES))
            r['shift_down']=int(any(f<=frame<f+4 and d==-1 for f,d in LEGACY_PULSES))
            for f,d in LEGACY_PULSES:
                if frame==f and f!=180:gear+=d
            r['gear_after']=gear
            legacy.append(r)
        result=analyze(legacy)
        self.assertEqual(result['status'],'failed')
        self.assertFalse(result['pulses'][0]['passed'])
        self.assertTrue(all(p['passed'] for p in result['pulses'][1:]))
