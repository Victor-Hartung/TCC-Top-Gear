from pathlib import Path
import tempfile
import unittest
from test_reward import ROOT
from analyze_context import analyze


class ContextTests(unittest.TestCase):
    def fixture(self,root,frames):
        binary,index=root/'a.wram.bin',root/'a_snapshots.csv'
        rows=['frame,reason,byte_offset,size']
        data=bytearray()
        for i,frame in enumerate(frames):
            ram=bytearray(131072);ram[500]=100-i
            data.extend(ram);rows.append(f'{frame},periodic,{i*131072},131072')
        binary.write_bytes(data);index.write_text('\n'.join(rows)+'\n')
        return binary,index
    def test_candidate_is_not_declared_timer(self):
        with tempfile.TemporaryDirectory() as d:
            result=analyze(*self.fixture(Path(d),[60,120,180,240,300]))
            candidate=next(c for c in result['candidates'] if c['address']=='0x001F4')
            self.assertFalse(candidate['validated'])
            self.assertIn('not_proven',candidate['hypothesis'])
    def test_savestate_rewind_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'frames'):
                analyze(*self.fixture(Path(d),[60,120,180,90,150]))
    def test_truncated_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            binary,index=self.fixture(Path(d),[60,120,180,240,300])
            binary.write_bytes(binary.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'tamanho'):analyze(binary,index)


if __name__=='__main__':unittest.main()
