"""Executa o Lua real com APIs BizHawk simuladas. Nao valida memoria do jogo."""
from __future__ import annotations
from pathlib import Path
import unittest
from test_reward import ROOT
from topgear_config import ProjectConfig
from analyze_curve_map import load_map
from protocol import parse_message, STATE_PREFIX, encode_message, ACTION_PREFIX
try:
    from lupa import LuaRuntime
except ImportError:
    LuaRuntime=None


@unittest.skipIf(LuaRuntime is None,'Instale requirements-dev.txt para executar Lua simulado')
class LuaBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.curves=bytes(r['curve_low_u8'] for r in load_map(ROOT/'archive/evidence/diagnostico_mapa_curvas.csv'))

    def execute_bridge(self, commands, *, missing_save=False, skipped_frame=False, pulse=False, initial_turbo=3, initial_lap=0, script_path=None, script_as_text=False, initialize_hook=None, advance_hook=None, profile_path=None):
        lua=LuaRuntime(unpack_returned_tuples=True)
        ram=bytearray(131072)
        def word(addr,value):ram[addr:addr+2]=(value&65535).to_bytes(2,'little')
        def initialize():
            ram[:]=b'\0'*len(ram)
            word(0x0200,22528);word(0x1E56,3);word(0x1E5A,1000);word(0x1E7A,19);word(0x1F00,-1)
            word(0x1E76,initial_lap)
            word(0x1ED7,100);word(0x0046,100);word(0x1E6C,initial_turbo);ram[0x0727]=1
            # Os jogadores podem compartilhar ID bruto zero; os offsets os distinguem.
            p1_slot,p2_slot=6,14
            word(0x0204,p1_slot*18);word(0x0206,p2_slot*18)
            word(0x1EDA,800);word(0x1E8C,7000);word(0x1E5C,1500)
            opponent_id=2
            for slot in range(20):
                base=0x0212+slot*18
                if slot==p1_slot:
                    ram[base]=0;word(base+7,100);word(base+2,0)
                elif slot==p2_slot:
                    ram[base]=0;word(base+7,800);word(base+2,7000)
                else:
                    ram[base]=opponent_id;word(base+7,1000+(opponent_id-2)*100)
                    opponent_id+=1
                ram[base+9]=1
            for i,value in enumerate(self.curves):ram[0x4C00+2*i]=value
            for i in range(len(self.curves)):word(0x7002+2*i,0x28D8)
            if initialize_hook:initialize_hook(ram)
        initialize()
        frame=[100];buttons=[{}];history=[];states=[];messages=[];callbacks={};paused=[False]
        def set_buttons(value,port):buttons[0]=dict(value)
        def advance():
            history.append(dict(buttons[0]))
            frame[0]+=2 if skipped_frame else 1
            ram[0x1EF5]=128 if pulse and frame[0] in (101 + ProjectConfig.load(ROOT).integer("protocol", "post_reset_frames"), 103 + ProjectConfig.load(ROOT).integer("protocol", "post_reset_frames")) else 0
            if advance_hook:advance_hook(ram,frame[0])
        def loadslot(slot,*args):
            if missing_save:return False
            initialize();frame[0]=100
            if 'load' in callbacks:callbacks['load']()
            return True
        payloads=[encode_message(ACTION_PREFIX,c) for c in commands]
        def receive():return payloads.pop(0) if payloads else ''
        def send(value):states.append(parse_message(value,STATE_PREFIX));return len(value)
        table=lua.table_from
        g=lua.globals()
        if profile_path is not None: g.TOPGEAR_PROFILE_OVERRIDE = str(profile_path)
        g.forms=table({'openfile':lambda *args:str(profile_path or ROOT/'config/game_profile.ini')})
        g.gameinfo=table({'getromhash':lambda:'F686806C676A4B087A3627BABBE3555D3704E3B1'})
        g.memory=table({'usememorydomain':lambda domain:True,'getcurrentmemorydomainsize':lambda:131072,
            'read_u8':lambda a:ram[a], 'read_u16_le':lambda a:int.from_bytes(ram[a:a+2],'little'),
            'read_s16_le':lambda a:int.from_bytes(ram[a:a+2],'little',signed=True)})
        g.joypad=table({'set':set_buttons})
        g.emu=table({'framecount':lambda:frame[0],'yield':advance})
        g.client=table({'pause':lambda:paused.__setitem__(0,True),'unpause':lambda:paused.__setitem__(0,False)})
        g.event=table({'onloadstate':lambda f,name:callbacks.update(load=f),'onexit':lambda f,name:callbacks.update(exit=f)})
        g.savestate=table({'loadslot':loadslot})
        g.comm=table({'socketServerIsConnected':lambda:True,'socketServerSend':send,'socketServerResponse':receive})
        g.console=table({'log':lambda v:messages.append(v)})
        if script_path is None:
            lua.execute((ROOT/'lua/Top Gear (USA).lua').read_text(encoding='utf-8'))
        elif script_as_text:
            lua.eval('function(s) assert(load(s, "main"))() end')(script_path.read_text(encoding='utf-8'))
        else:
            lua.eval('function(p) assert(loadfile(p))() end')(str(script_path))
        return states,history,paused[0],messages

    @staticmethod
    def commands(action=1):
        return [{'episode':0,'seq':1,'kind':'hello','action':0,'frames':0},
                {'episode':1,'seq':2,'kind':'reset','action':0,'frames':0},
                {'episode':1,'seq':3,'kind':'step','action':action,'frames':4},
                {'episode':1,'seq':4,'kind':'close','action':0,'frames':0}]

    def test_actual_lua_reset_step_and_neutralization(self):
        states,history,paused,_=self.execute_bridge(self.commands())
        self.assertEqual([s['status'] for s in states],['ready','ok','ok','closed'])
        self.assertEqual(int(states[2]['frame'])-int(states[1]['frame']),4)
        self.assertTrue(all(h['X'] and not h['Y'] and not h['A'] for h in history[-4:]))
        self.assertEqual(int(states[1]['frame']), 100)
        self.assertEqual(len(history), 4)  # nenhum frame de controle escondido no reset
        self.assertTrue(paused)

    def test_blue_automatic_wrapper_exposes_identity_without_shift_actions(self):
        def blue_auto(ram):
            for address, value in ((0x1EE8, 48), (0x1F7A, 0), (0x1F7C, 0)):
                ram[address:address+2] = value.to_bytes(2, 'little')
        states, history, _, _ = self.execute_bridge(
            self.commands(), initialize_hook=blue_auto,
            profile_path=ROOT/'config/game_profile_blue_auto.ini',
            script_path=ROOT/'lua/Top Gear Azul Automatico (USA).lua')
        self.assertEqual([s['status'] for s in states], ['ready', 'ok', 'ok', 'closed'])
        self.assertEqual(states[1]['manual_mode'], '0')
        self.assertEqual(states[1]['car_table_offset_raw'], '48')
        self.assertEqual(states[1]['upshift_mask_raw'], '0')
        self.assertEqual(states[1]['downshift_mask_raw'], '0')
        self.assertEqual(int(states[1]['frame']), 100)
        self.assertTrue(all(not h['R'] and not h['L'] for h in history))

    def test_collision_pulses_accumulated_inside_action(self):
        states,_,_,_=self.execute_bridge(self.commands(),pulse=True)
        self.assertEqual(states[2]['collision_events'],'2')
        self.assertEqual(states[2]['collision'],'1')

    def test_failed_save_is_propagated(self):
        states,_,paused,_=self.execute_bridge(self.commands(),missing_save=True)
        self.assertEqual(states[-1]['status'],'error');self.assertTrue(paused)
        self.assertIn('falha_carregando',states[-1]['error'])

    def test_duplicate_sequence_wrong_episode_and_fractional_frames_rejected(self):
        for mutation in ({'seq':2},{'episode':9},{'frames':1.5}):
            c=self.commands();c[2].update(mutation)
            states,_,paused,_=self.execute_bridge(c)
            self.assertEqual(states[-1]['status'],'error');self.assertTrue(paused)

    def test_frame_skip_is_error(self):
        states,_,paused,_=self.execute_bridge(self.commands(),skipped_frame=True)
        self.assertEqual(states[-1]['status'],'error');self.assertTrue(paused)

    def test_turbo_guard_preserves_acceleration_without_charge(self):
        for raw,pressed in ((0,False),(0x8003,False),(3,True)):
            states,history,_,_=self.execute_bridge(self.commands(action=9),initial_turbo=raw)
            self.assertEqual(states[-1]['status'],'closed')
            self.assertTrue(all(h['X'] and h['A']==pressed for h in history[-4:]))

    def test_every_lua_file_parses(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        compile_source=lua.eval('function(s) local f,err=load(s); return f~=nil,err end')
        for path in (ROOT/'lua').glob('*.lua'):
            with self.subTest(file=path.name):
                ok,error=compile_source(path.read_text(encoding='utf-8'))
                self.assertTrue(ok,error)


if __name__=='__main__':unittest.main()
