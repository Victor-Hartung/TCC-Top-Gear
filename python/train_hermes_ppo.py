from __future__ import annotations
import argparse
import shutil
from pathlib import Path
import torch
from resilient_ppo import ResilientPPO, RECOVERY_POLICY
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.env_checker import check_env
from callbacks import RaceMetricsCallback, TrainingProgressCallback
from env_topgear import TopGearEnv
from recording import RecordingEnv
from terminal_progress import clear_progress
from experiment import (contract, assert_live_preflight, validate_checkpoint, save_checkpoint,
                        ppo_options, atomic_json, unique_name, environment_versions, source_hashes,
                        contract_hash, validate_reward_compatible_checkpoint)
from topgear_config import ProjectConfig
from checkpoint_provenance import preflight_reference
from policy_transfer import validate_policy_source, initialize_actor
from manual_refinement import validate_refinement_source, apply_optimizer_rate
from named_brain import NamedBrain, NamedBrainCallback


def arguments():
    parser = argparse.ArgumentParser(description='Treina PPO v3; retoma somente checkpoints compativeis')
    parser.add_argument('--timesteps', type=int, default=10240,
                        help='Passos adicionais nesta execucao; PPO completa blocos de coleta')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--named-brain', help='Retoma e atualiza models/<nome>.zip')
    parser.add_argument('--checkpoint-every', type=int, default=25000)
    initialization = parser.add_mutually_exclusive_group()
    initialization.add_argument('--from-scratch', action='store_true',
        help='Rede, critico, otimizador e contador novos; nenhum modelo importado')
    initialization.add_argument('--resume', type=Path)
    initialization.add_argument('--refine-from', type=Path,
        help='Manual: conserva ator/critico/Adam/contador; permite somente reduzir learning_rate explicitamente')
    initialization.add_argument('--initialize-policy-from', type=Path,
        help='Migracao explicita de ator compativel (recompensa ou sensor); critico/otimizador/contador novos')
    parser.add_argument('--skip-env-check', action='store_true')
    parser.add_argument('--no-step-log', action='store_true')
    return parser.parse_args()


def main():
    args = arguments()
    if args.timesteps < 1 or args.checkpoint_every < 1:
        raise ValueError('Quantidades de passos devem ser positivas')
    cfg = ProjectConfig.load()
    cfg.assert_training_ready()
    expected = contract(cfg)
    receipt = assert_live_preflight(cfg, expected)
    if args.named_brain:
        if args.from_scratch or args.refine_from or args.initialize_policy_from:
            raise ValueError('Cerebro fixo exige retomada; use outro nome para um novo experimento.')
        with NamedBrain(cfg.project_dir, args.named_brain, expected) as brain:
            if brain.metadata is None:
                raise FileNotFoundError(f'Cerebro fixo nao encontrado: {brain.path}')
            if args.resume:
                brain.require_current(args.resume)
            args.resume = brain.path
            return train(args, cfg, expected, receipt, brain)
    return train(args, cfg, expected, receipt)


def train(args, cfg, expected, receipt, brain=None):
    resume_metadata = None
    if args.resume:
        resume_metadata = validate_reward_compatible_checkpoint(args.resume, expected)
        # Integridade e revisao exata sao verificadas antes de carregar pickle/abrir servidor.
    refinement_metadata = validate_refinement_source(args.refine_from, expected) if args.refine_from else None
    if args.initialize_policy_from:
        validate_policy_source(args.initialize_policy_from, expected)
    torch.set_num_threads(cfg.integer('ppo', 'torch_threads'))
    run = unique_name('hermes-ppo')
    run_dir, model_dir = cfg.project_dir / 'runs' / run, cfg.project_dir / 'models' / run
    run_dir.mkdir(parents=True, exist_ok=False)
    model_dir.mkdir(parents=True, exist_ok=False)
    provenance = {'source_hashes': source_hashes(cfg.project_dir), 'preflight': preflight_reference(run_dir, receipt),
                  'environment': environment_versions(), 'training_recovery': RECOVERY_POLICY}
    if brain is not None:
        provenance['named_brain'] = {'name': brain.name, 'source_sha256': brain.source_sha256}
    if resume_metadata is not None and resume_metadata['contract'] != expected:
        provenance['reward_revision'] = {
            'source_model': str(args.resume.resolve()),
            'source_checkpoint': resume_metadata.get('named_brain', {}).get(
                'source_checkpoint', str(args.resume.resolve())),
            'source_model_sha256': resume_metadata['model_sha256'],
            'source_contract': resume_metadata['contract'],
            'source_contract_sha256': resume_metadata['contract_sha256'],
            'target_contract': expected,
            'target_contract_sha256': contract_hash(expected),
            'source_num_timesteps': resume_metadata['num_timesteps'],
            'actor_preserved': True, 'critic_preserved': True,
            'optimizer_state_preserved': True, 'counter_preserved': True,
            'semantics': ('full_resume; exact_reward_revision_'
                          f"{resume_metadata['contract']['reward_version']}_to_{expected['reward_version']}; "
                          'fresh_rollout_and_savestate; '
                          'critic_and_adam_moments_adapt_to_new_returns'),
        }
    shutil.copy2(cfg.path, run_dir / 'game_profile.ini')
    for filename in ('requirements.txt', 'requirements-dev.txt', 'constraints.txt', 'VERSION.txt'):
        shutil.copy2(cfg.project_dir / filename, run_dir / filename)
    atomic_json(run_dir / 'run_config.json', {'run': run, 'contract': expected,
        'provenance': provenance, 'seed': args.seed, 'timesteps_requested': args.timesteps,
        'resume': str(args.resume.resolve()) if args.resume else None,
        'refine_from': str(args.refine_from.resolve()) if args.refine_from else None,
        'initialize_policy_from': str(args.initialize_policy_from.resolve()) if args.initialize_policy_from else None,
        'from_scratch': not bool(args.resume or args.initialize_policy_from or args.refine_from),
        'checkpoint_every': args.checkpoint_every, 'step_log': not args.no_step_log,
        'named_brain': brain.name if brain is not None else None})
    env = None
    model = None
    reason = 'final'
    named_callback = None
    saved_path = None
    try:
        raw = TopGearEnv(cfg.project_dir, expected_reset=receipt['reset_fingerprint'])
        env = raw
        if not args.skip_env_check:
            check_env(raw, warn=True, skip_render_check=True)
        recorded = RecordingEnv(raw, run_dir, log_steps=not args.no_step_log)
        env = recorded
        info_keys = ('race_ended', 'race_completed', 'lap', 'total_laps', 'progress',
                     'rank', 'final_rank', 'is_first', 'collisions_total', 'overtakes_total',
                     'net_progress', 'offtrack_fraction', 'stopped_fraction', 'termination_reason')
        env = Monitor(recorded, filename=str(run_dir / 'monitor.csv'), info_keywords=info_keys)
        if args.resume or args.refine_from:
            source = args.resume or args.refine_from
            model = ResilientPPO.load(source, env=env, device='cpu', tensorboard_log=str(run_dir))
            if args.refine_from:
                refinement = apply_optimizer_rate(model, refinement_metadata, expected)
                refinement['source_model'] = str(source.resolve())
                provenance['manual_refinement'] = refinement
                atomic_json(run_dir / 'manual_refinement.json', refinement)
                print('REFINAMENTO: pesos/critico/momentos Adam preservados; learning_rate reduzido explicitamente.', flush=True)
            model.set_random_seed(args.seed)
            if 'reward_revision' in provenance:
                atomic_json(run_dir / 'reward_revision.json', provenance['reward_revision'])
                print(f"REVISAO DE RECOMPENSA {resume_metadata['contract']['reward_version']} -> "
                      f"{expected['reward_version']}: ator/critico/Adam/contador preservados; "
                      'critico e momentos Adam se adaptarao aos novos retornos.', flush=True)
        else:
            print('TREINO DO ZERO: rede nova, sem pesos de modelos anteriores.' if not args.initialize_policy_from
                  else 'Inicializacao explicita de ator solicitada.', flush=True)
            model = ResilientPPO('MlpPolicy', env, verbose=1, tensorboard_log=str(run_dir),
                        **ppo_options(cfg), normalize_advantage=True,
                        policy_kwargs={'net_arch': {'pi': [64, 64], 'vf': [64, 64]}},
                        seed=args.seed, device='cpu')
            if args.initialize_policy_from:
                transfer = initialize_actor(model, args.initialize_policy_from, expected)
                provenance['policy_initialization'] = transfer
                atomic_json(run_dir / 'policy_initialization.json', transfer)
                print('ATOR IMPORTADO. Novo contrato; critico, otimizador e contador reiniciados. Consulte policy_initialization.json.', flush=True)
        model.configure_recovery(run_dir / 'recoveries')
        callback = RaceMetricsCallback(model_dir, expected, run, args.checkpoint_every, provenance)
        callbacks = [callback, TrainingProgressCallback()]
        if brain is not None:
            named_callback = NamedBrainCallback(brain, model_dir, run, provenance)
            callbacks.append(named_callback)
        model.learn(total_timesteps=args.timesteps, callback=callbacks, tb_log_name='PPO',
                    reset_num_timesteps=not bool(args.resume or args.refine_from))
    except KeyboardInterrupt:
        reason = 'interrupted'
        clear_progress()
        print('Interrompido; preservando pesos e registros.')
    except Exception:
        reason = 'failed'
        raise
    finally:
        clear_progress()
        try:
            if model is not None:
                if 'reward_revision' in provenance:
                    provenance['reward_revision'].update(
                        counter_at_save=int(model.num_timesteps),
                        trained_steps_this_run=getattr(model, 'trained_steps_this_run', 0),
                        last_update_timesteps_this_run=getattr(model, 'last_update_timesteps_this_run', None),
                        discarded_rollout_steps=getattr(model, 'discarded_rollout_steps', 0),
                        recovery_count=getattr(model, 'recovery_count', 0))
                    atomic_json(run_dir / 'reward_revision.json', provenance['reward_revision'])
                path = save_checkpoint(model, model_dir / f'{reason}_{model.num_timesteps}_steps.zip',
                                       expected, run=run, reason=reason, provenance=provenance)
                saved_path = path
                print(f'MODELO: {path.resolve()}', flush=True)
            atomic_json(run_dir / 'status.json', {'status': reason, 'timesteps': int(model.num_timesteps) if model else 0,
                'recovery_count': getattr(model, 'recovery_count', 0),
                'discarded_rollout_steps': getattr(model, 'discarded_rollout_steps', 0),
                'trained_steps_this_run': getattr(model, 'trained_steps_this_run', 0),
                'last_update_timesteps_this_run': getattr(model, 'last_update_timesteps_this_run', None)})
            if named_callback is not None and saved_path is not None:
                if named_callback.publish_final(saved_path, reason):
                    print(f'CEREBRO FIXO: {brain.path.resolve()}', flush=True)
                else:
                    print(f'CEREBRO FIXO PRESERVADO: {brain.path.resolve()}; ultima atualizacao concluida.', flush=True)
        finally:
            if env is not None:
                env.close()
            print(f'REGISTROS: {run_dir.resolve()}', flush=True)


if __name__ == '__main__':
    main()
