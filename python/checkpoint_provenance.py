"""Guarda preflight completo uma vez, sem inflar cada metadado de modelo."""
from pathlib import Path
from experiment import atomic_json,sha256

def preflight_reference(run_dir:Path,receipt:dict)->dict:
    path=run_dir/'preflight_receipt.json'
    if path.exists():raise FileExistsError(path)
    atomic_json(path,receipt)
    return {'path':str(path.resolve()),'sha256':sha256(path),
            'contract_sha256':receipt['contract_sha256'],
            'status':receipt['status'],'execution':receipt['execution'],
            'note':'Full immutable receipt stored once in run directory; reference is provenance, not a training authorization.'}
