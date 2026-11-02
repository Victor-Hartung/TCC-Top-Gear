"""Verificacao offline: interpretador, dependencias, imports, perfil e manifesto."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.metadata
from pathlib import Path
import platform
import sys

ROOT=Path(__file__).resolve().parents[1]
VERSIONS={'numpy':'2.0.2','gymnasium':'1.3.0','stable-baselines3':'2.9.0',
          'torch':'2.8.0+cpu','tensorboard':'2.20.0','lupa':'2.6'}


def manifest_errors(root:Path) -> list[str]:
    manifest=root/'MANIFEST.sha256'
    if not manifest.is_file():return ['MANIFEST.sha256 ausente']
    errors=[]
    for line in manifest.read_text(encoding='utf-8').splitlines():
        expected,relative=line.split('  ',1)
        path=(root/relative).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append('Caminho fora do projeto no manifesto');continue
        if not path.is_file():errors.append(f'Ausente: {relative}');continue
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected:errors.append(f'Alterado: {relative}')
    return errors


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',action='store_true',help='Confere o pacote original; atualizacoes intencionais mudam hashes')
    args=parser.parse_args()
    print(f'Python: {sys.executable}\nVersao: {platform.python_version()}\nProjeto: {ROOT}')
    failures=[]
    if sys.version_info[:2] not in ((3,11),(3,12)):
        failures.append('Use Python 3.11 x64 no Windows; 3.12 foi usado nos testes Linux')
    if sys.maxsize<=2**32:failures.append('Python precisa ser de 64 bits')
    for name,expected in VERSIONS.items():
        try:
            actual=importlib.metadata.version(name)
            print(f'{name}: {actual}')
            if actual!=expected:failures.append(f'{name}: esperado {expected}, recebido {actual}')
        except importlib.metadata.PackageNotFoundError:
            failures.append(f'Falta {name}')
    if not failures:
        for path in sorted((ROOT/'python').glob('*.py')):
            if path.stem==Path(__file__).stem:continue
            try:importlib.import_module(path.stem)
            except Exception as exc:failures.append(f'Import {path.name}: {exc}')
        from topgear_config import ProjectConfig
        from telemetry import ObservationBuilder,OBSERVATION_NAMES
        cfg=ProjectConfig.load(ROOT);cfg.assert_training_ready()
        print(f'Perfil estrutural OK; {len(OBSERVATION_NAMES)} observacoes, {cfg.action_count} acoes.')
        if ROOT.joinpath('.venv').resolve() != Path(sys.prefix).resolve():
            print('AVISO: este interpretador nao e a .venv desta pasta. No Windows use .\\.venv\\Scripts\\python.exe')
    if args.manifest:failures.extend(manifest_errors(ROOT))
    if failures:
        print('\n'.join('ERRO: '+s for s in failures))
        print('Na raiz da v3.0 execute: .\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt')
        raise SystemExit(1)
    print('INSTALACAO OK. Isto nao verifica BizHawk, savestate ou pilotagem.')


if __name__=='__main__':main()
