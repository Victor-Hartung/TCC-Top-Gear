"""Ponte Lua executada com RAM sintetica: nao e validacao no BizHawk."""
import unittest

import test_lua_bridge as bridge_tests

LuaRuntime = bridge_tests.LuaRuntime
from test_reward import ROOT


def word(ram,address,value):
    ram[address:address+2]=(value&65535).to_bytes(2,'little')


def samples(state):
    return [list(map(int,row.split(','))) for row in state['navigation_samples'].split(';') if row]


@unittest.skipIf(LuaRuntime is None,'Instale requirements-dev.txt para executar Lua simulado')
class NavigationLuaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bridge_tests.LuaBridgeTests.setUpClass()

    def bridge(self,*args,**kwargs):
        return bridge_tests.LuaBridgeTests().execute_bridge(*args,**kwargs)

    def test_navigation_and_legacy_have_same_frames_and_reset_history(self):
        commands=bridge_tests.LuaBridgeTests.commands()[:-1]
        commands += [{'episode':2,'seq':4,'kind':'reset','action':0,'frames':0},
                     {'episode':2,'seq':5,'kind':'step','action':1,'frames':4},
                     {'episode':2,'seq':6,'kind':'close','action':0,'frames':0}]
        states,_,paused,_=self.bridge(commands)
        self.assertTrue(paused)
        self.assertEqual([s['status'] for s in states],['ready','ok','ok','ok','ok','closed'])
        self.assertEqual(samples(states[0]),[])
        self.assertEqual([len(samples(s)) for s in states[1:5]],[1,4,1,4])
        self.assertEqual(samples(states[1]),samples(states[3]))
        for state in states[1:]:
            navigation=samples(state)
            legacy=[list(map(int,row.split(','))) for row in state['detector_samples'].split(';')]
            self.assertEqual([r[0] for r in navigation],[r[0] for r in legacy])
            self.assertTrue(all(len(r)==14 for r in navigation))
            self.assertTrue(all(len(r)==58 for r in legacy))
            self.assertEqual(state['bridge_revision'],'5')

    def test_dynamic_offsets_identify_both_players_despite_duplicate_raw_ids(self):
        def reorder(ram,frame):
            old=int.from_bytes(ram[0x0206:0x0208],'little')
            new=(frame-100)*18
            a,b=0x0212+old,0x0212+new
            first,second=bytes(ram[a:a+18]),bytes(ram[b:b+18])
            ram[a:a+18],ram[b:b+18]=second,first
            word(ram,0x0206,new)
            word(ram,0x1EDA,800+frame-100);word(ram,b+7,800+frame-100)
            word(ram,0x1E8C,7000+frame);word(ram,b+2,7000+frame)
        states,_,_,_=self.bridge(bridge_tests.LuaBridgeTests.commands(),advance_hook=reorder)
        initial=samples(states[1])[0]
        self.assertEqual(initial[:9],[100,108,252,100,0,800,7000,800,7000])
        for row in samples(states[2]):
            self.assertEqual(row[1],108)
            self.assertEqual(row[2],(row[0]-100)*18)
            self.assertEqual(row[5:7],row[7:9])
        # Somente os IDs 2..19 continuam no pacote historico, sem incluir P2 por ID.
        legacy=list(map(int,states[2]['detector_samples'].split(';')[-1].split(',')))
        self.assertEqual(legacy[4::3],list(range(2,20)))

    def test_exact_raw_corridor_wrap_curve_sign_and_auto_word(self):
        def setup(ram):
            progress=22500
            word(ram,0x1ED7,progress);word(ram,0x0212+108+7,progress)
            word(ram,0x7002+2*(progress//32),0x25DE)
            word(ram,0x7002+2*(((progress+128)%22528)//32),0x30D0)
            ram[0x4C00+2*(((progress+128)%22528)//32)]=249
            word(ram,0x1EF3,0x80FF);word(ram,0x1F04,2)
        ram=bytearray(131072)
        word(ram,0x0204,108);word(ram,0x0206,252);word(ram,0x0200,22528)
        setup(ram)
        runtime=LuaRuntime(unpack_returned_tuples=True)
        module=runtime.eval('dofile')(str(ROOT/'lua/native_navigation.lua'))
        row=list(map(int,module.capture(100,lambda a:ram[a],
            lambda a:int.from_bytes(ram[a:a+2],'little'),
            lambda a:int.from_bytes(ram[a:a+2],'little',signed=True)).split(',')))
        self.assertEqual(row[9:],[0x25DE,0x30D0,-7,0x80FF,2])

    def test_bad_offsets_are_preserved_but_never_dereferenced(self):
        module=LuaRuntime(unpack_returned_tuples=True).eval('dofile')(str(ROOT/'lua/native_navigation.lua'))
        for offsets in ((65535,252),(108,65535),(1,252),(108,108)):
            with self.subTest(offsets=offsets):
                reads=[]
                values={0x0204:offsets[0],0x0206:offsets[1],0x0200:22528,
                        0x1ED7:100,0x1EDA:800,0x1E8C:7000}
                def read(address):
                    reads.append(address)
                    self.assertTrue(0<=address<131072)
                    self.assertFalse(0x0212<=address<0x037A)
                    return values.get(address,0)
                row=list(map(int,module.capture(9,read,read,read).split(',')))
                self.assertEqual(row[1:3],list(offsets))
                self.assertEqual(row[3:5],[0,0])
                self.assertEqual(row[7:9],[0,0])

    def test_finish_probe_instrumentation_still_loads_navigation(self):
        commands=bridge_tests.LuaBridgeTests.commands();commands[0]['finish_probe']='1'
        states,_,paused,_=self.bridge(commands,
            script_path=ROOT/'lua/diagnostico_fim_corrida.lua',script_as_text=True)
        self.assertTrue(paused)
        self.assertEqual(states[-1]['status'],'closed')
        self.assertEqual(states[2]['finish_probe'],'1')
        self.assertEqual(len(samples(states[2])),4)
        self.assertEqual(len(states[2]['finish_samples'].split(';')),4)


if __name__=='__main__':
    unittest.main()
