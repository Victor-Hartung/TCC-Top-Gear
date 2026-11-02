import unittest,tempfile,json,zipfile
from pathlib import Path
from test_reward import ROOT
from checkpoint_provenance import preflight_reference
from experiment import save_checkpoint,validate_checkpoint,contract,sha256
from topgear_config import ProjectConfig
class ProvenanceTests(unittest.TestCase):
    def test_large_receipt_preserved_and_checkpoint_remains_loadable_by_validator(self):
        class Model:
            num_timesteps=4096
            def save(self,path):
                with zipfile.ZipFile(path,'w') as z:
                    z.writestr('data','{}');z.writestr('policy.pth',b'test fixture')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);expected=contract(ProjectConfig.load(ROOT))
            receipt={'status':'synthetic','execution':'synthetic','contract_sha256':'test','payload':'x'*5_300_000}
            ref=preflight_reference(root,receipt)
            self.assertEqual(json.loads(Path(ref['path']).read_text()),receipt)
            self.assertEqual(sha256(Path(ref['path'])),ref['sha256'])
            path=save_checkpoint(Model(),root/'model.zip',expected,run='test',reason='synthetic',provenance={'preflight':ref})
            self.assertLess(path.with_suffix('.zip.json').stat().st_size,2_000_000)
            validate_checkpoint(path,expected)
            with self.assertRaises(FileExistsError):preflight_reference(root,receipt)
