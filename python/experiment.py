"""Versionamento, arquivos atomicos e contrato verificavel antes de PPO.load."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import tempfile
import time
import zipfile

from live_detector import SETTINGS as DETECTOR_SETTINGS
from native_navigation import SETTINGS as NAVIGATION_SETTINGS
from driving_strategy import PROFILE as DRIVING_PROFILE, SETTINGS as DRIVING_SETTINGS
from race_objective import PROFILE as RACE_PROFILE, SETTINGS as RACE_SETTINGS
from outcome_objective import PROFILE as OUTCOME_PROFILE, SETTINGS as OUTCOME_SETTINGS
from manual_transmission import SETTINGS as MANUAL_SETTINGS
from protocol import BRIDGE_REVISION
from reward import REWARD_VERSION, RewardWeights, profile_weights, reward_version
from turbo_strategy import PROFILE as TURBO_PROFILE, SETTINGS as TURBO_SETTINGS
from telemetry import OBSERVATION_NAMES, OBSERVATION_SCHEMA_VERSION, ObservationBuilder, observation_names
from topgear_config import ACTION_NAMES, ProjectConfig

PROJECT_VERSION = "3.0.0"
ACTION_SCHEMA_VERSION = 2
CONTRACT_VERSION = 1


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        deadline = time.monotonic() + 1.0
        while True:
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
    finally:
        tmp.unlink(missing_ok=True)


def unique_name(prefix: str) -> str:
    return prefix + '_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')


def ppo_options(config: ProjectConfig) -> dict:
    ints = ('n_steps', 'batch_size', 'n_epochs')
    floats = ('gamma', 'gae_lambda', 'learning_rate', 'clip_range', 'ent_coef',
              'vf_coef', 'max_grad_norm', 'target_kl')
    return {**{k: config.integer('ppo', k) for k in ints},
            **{k: config.number('ppo', k) for k in floats}}


def contract(config: ProjectConfig, reward_profile: str | None = None) -> dict:
    profile = reward_profile or config.text('experiment', 'reward_profile')
    sections = ('memory', 'controls', 'geometry', 'normalization', 'episode')
    return {
        'contract_version': CONTRACT_VERSION,
        'protocol_version': 2, 'bridge_revision': config.bridge_revision,
        'rom_sha1': config.text('identity', 'rom_sha1').lower(),
        'track': 'Las Vegas', 'track_length': 22528, 'total_laps': 3,
        'observation_schema': 11 if config.manual_transmission else OBSERVATION_SCHEMA_VERSION,
        'observation_names': list(observation_names(config)),
        'observation_low': ObservationBuilder.low(config).tolist(),
        'observation_high': ObservationBuilder.high(config).tolist(),
        'detector': DETECTOR_SETTINGS,
        'navigation': NAVIGATION_SETTINGS,
        'action_schema': 3 if config.manual_transmission else ACTION_SCHEMA_VERSION,
        'actions': list(config.action_names),
        **({'manual_transmission': MANUAL_SETTINGS} if config.manual_transmission else {}),
        'frame_repeat': config.frame_repeat,
        'post_reset_frames': config.integer('protocol', 'post_reset_frames'),
        'savestate_slot': config.integer('protocol', 'savestate_slot'),
        'curve_table_adler32': config.integer('experiment', 'curve_table_adler32'),
        'reward_version': reward_version(profile), 'reward_profile': profile,
        'reward_weights': asdict(profile_weights(RewardWeights.from_config(config), profile)),
        'reward_elapsed': (OUTCOME_SETTINGS['elapsed_cost'] if profile == OUTCOME_PROFILE else
                           0.002 if profile in ('road_v2', TURBO_PROFILE, DRIVING_PROFILE, RACE_PROFILE) else 0.0),
        **({'turbo_strategy': TURBO_SETTINGS} if profile == TURBO_PROFILE else {}),
        **({'driving_strategy': DRIVING_SETTINGS} if profile == DRIVING_PROFILE else {}),
        **({'race_objective': RACE_SETTINGS} if profile == RACE_PROFILE else {}),
        **({'outcome_objective': OUTCOME_SETTINGS} if profile == OUTCOME_PROFILE else {}),
        'settings': {s: dict(config.parser[s]) for s in sections},
        'ppo': ppo_options(config),
        'policy': {'class': 'MlpPolicy', 'pi': [64, 64], 'vf': [64, 64],
                   'activation': 'Tanh', 'normalize_advantage': True,
                   'wrappers': ['Monitor', 'DummyVecEnv'], 'vecnormalize': False},
    }


def contract_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def source_hashes(root: Path) -> dict:
    paths = sorted((root / 'python').glob('*.py')) + sorted((root / 'lua').glob('*.lua'))
    return {str(p.relative_to(root)).replace('\\', '/'): sha256(p) for p in paths}


def critical_sources(root: Path) -> dict:
    names={'python/protocol.py','python/telemetry.py','python/topgear_config.py',
           'python/env_topgear.py','python/reward.py','python/experiment.py',
           'python/preflight_live.py','python/live_detector.py','lua/Top Gear (USA).lua',
           'python/transition_errors.py','python/resilient_ppo.py',
           'python/turbo_strategy.py','python/policy_transfer.py',
           'python/native_navigation.py','lua/native_navigation.lua','python/driving_strategy.py',
           'python/race_objective.py','python/manual_transmission.py','lua/Top Gear Manual (USA).lua',
           'python/manual_refinement.py','python/blue_auto.py','lua/Top Gear Azul Automatico (USA).lua',
           'python/outcome_objective.py','python/reward_revision.py'}
    return {k:v for k,v in source_hashes(root).items() if k in names}


def environment_versions() -> dict:
    packages = {}
    names = {'numpy', 'gymnasium', 'stable-baselines3', 'torch', 'tensorboard'}
    root = Path(__file__).resolve().parents[1]
    for filename in ('requirements.txt', 'requirements-dev.txt', 'constraints.txt'):
        path = root / filename
        if path.is_file():
            names.update(re.findall(r'^([\w.-]+)==', path.read_text(encoding='utf-8'), flags=re.MULTILINE))
    for name in sorted(names):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = 'missing'
    return {'python': platform.python_version(), 'platform': platform.platform(), 'packages': packages}


def save_checkpoint(model, path: Path, expected: dict, *, run: str, reason: str,
                    provenance: dict | None = None) -> Path:
    path = path.with_suffix('.zip')
    if path.exists() or path.with_suffix('.zip.json').exists():
        raise FileExistsError(f'Checkpoint preservado, nao sobrescrito: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + '.writing.zip')
    try:
        model.save(str(temporary))
        os.replace(temporary, path)
        atomic_json(path.with_suffix('.zip.json'), {
            'project_version': PROJECT_VERSION, 'contract': expected,
            'contract_sha256': contract_hash(expected), 'model_sha256': sha256(path),
            'run': run, 'reason': reason, 'num_timesteps': int(model.num_timesteps),
            'environment': environment_versions(), 'provenance': provenance or {},
            'resume_semantics': 'weights_optimizer_and_counter; fresh_rollout_and_savestate; not_bit_exact',
        })
    finally:
        temporary.unlink(missing_ok=True)
    return path


def validate_checkpoint(path: Path, expected: dict | None = None) -> dict:
    path = path.resolve()
    metadata_path = path.with_suffix('.zip.json')
    if not path.is_file() or not metadata_path.is_file():
        raise ValueError('Modelo sem contrato v3: falta o arquivo .zip.json. Modelos v2 ficam em archive/models e exigem avaliador v2.')
    if metadata_path.stat().st_size > 2_000_000:
        raise ValueError('Metadados do modelo excessivamente grandes')
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        stored = metadata['contract']
        if stored['contract_version'] != CONTRACT_VERSION or metadata['contract_sha256'] != contract_hash(stored):
            raise ValueError('Contrato do modelo corrompido/incompativel')
        if metadata['model_sha256'] != sha256(path):
            raise ValueError('SHA-256 do modelo diverge do contrato')
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or sum(i.file_size for i in archive.infolist()) > 512_000_000:
                raise ValueError('ZIP de modelo invalido')
            if any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names):
                raise ValueError('Caminho inseguro no modelo')
            if not {'data', 'policy.pth'}.issubset(names) or archive.testzip():
                raise ValueError('Conteudo/CRC do modelo invalido')
    except (KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError(f'Modelo ou contrato corrompido: {exc}') from exc
    if expected is not None and stored != expected:
        changed = sorted(k for k in set(stored) | set(expected) if stored.get(k) != expected.get(k))
        raise ValueError('Modelo incompativel com esta execucao: ' + ', '.join(changed))
    return metadata


def validate_reward_compatible_checkpoint(path: Path, expected: dict) -> dict:
    """Full-state resume under one explicit reward revision, never a generic bypass."""
    from reward_revision import is_outcome_reward_revision

    metadata = validate_checkpoint(path)
    stored = metadata['contract']
    if stored != expected and not is_outcome_reward_revision(stored, expected):
        changed = sorted(k for k in set(stored) | set(expected)
                         if stored.get(k) != expected.get(k))
        raise ValueError('Modelo incompativel com esta execucao: ' + ', '.join(changed))
    return metadata


def preflight_receipt_path(config: ProjectConfig) -> Path:
    name = ('latest_blue_auto.json' if config.blue_auto_expected
            else 'latest_manual_refine.json' if config.path.name == 'game_profile_manual_refine.ini'
            else 'latest_manual.json' if config.manual_transmission else 'latest.json')
    return config.project_dir / 'runs' / 'preflight' / name


def assert_live_preflight(config: ProjectConfig, expected: dict) -> dict:
    path = preflight_receipt_path(config)
    try:
        receipt = json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError('Execute primeiro: .\\.venv\\Scripts\\python.exe python\\preflight_live.py') from exc
    if (receipt.get('status') != 'passed' or not isinstance(receipt.get('reset_fingerprint'), dict)
            or receipt.get('execution') != 'live_bizhawk' or receipt.get('contract_sha256') != contract_hash(expected)
            or receipt.get('critical_sources') != critical_sources(config.project_dir)):
        raise ValueError('Preflight ausente ou de outra configuracao/codigo; repita preflight_live.py')
    return receipt
