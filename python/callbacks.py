from __future__ import annotations
from pathlib import Path
from collections import deque
from stable_baselines3.common.callbacks import BaseCallback
from experiment import atomic_json, save_checkpoint
from terminal_progress import write_progress, clear_progress, finish_progress


class RaceMetricsCallback(BaseCallback):
    """Candidato de treino separado da promocao por avaliacao sem aprendizado."""
    def __init__(self, model_dir: Path, expected: dict, run: str, checkpoint_every: int, provenance: dict, verbose=1):
        super().__init__(verbose=verbose)
        self.model_dir, self.expected, self.run = model_dir, expected, run
        self.checkpoint_every, self.provenance = checkpoint_every, provenance
        self.last_checkpoint = 0
        self.best_score = None
        self.episodes = self.wins = 0
        self.recent_episodes = deque(maxlen=100)

    def _on_training_start(self):
        self.last_checkpoint = self.num_timesteps

    def _on_rollout_start(self):
        if self.num_timesteps - self.last_checkpoint >= self.checkpoint_every:
            save_checkpoint(self.model, self.model_dir / f'checkpoint_{self.num_timesteps}_steps.zip',
                            self.expected, run=self.run, reason='periodic_after_update', provenance=self.provenance)
            self.last_checkpoint = self.num_timesteps

    def _on_step(self) -> bool:
        for done, info in zip(self.locals.get('dones', []), self.locals.get('infos', [])):
            for key, value in info.get('driving_context_before_action', {}).items():
                self.logger.record_mean('driving/' + key, float(value))
            if 'shift_command' in info:
                for key in ('shift_command', 'gear', 'gear_changed', 'engine_gauge_raw', 'speed_delta'):
                    self.logger.record_mean('manual/' + key, float(info[key]))
            if 'action_name' in info:
                self.logger.record_mean('driving/accelerating_action', float('ACCELERATE' in info['action_name']))
            navigation = info.get('navigation', {})
            if navigation:
                for key in ('navigation_valid', 'target_valid', 'p2_present'):
                    self.logger.record_mean('navigation/' + key, float(navigation.get(key, False)))
                self.logger.record_mean('navigation/blocked_car_count', len(navigation.get('blocking_ids', [])))
                if navigation.get('target_valid'):
                    self.logger.record_mean('navigation/target_distance_raw',
                        abs(navigation['target'] - info['lateral']))
            for key in ('rank', 'collisions_total', 'offtrack_fraction', 'stopped_fraction', 'net_progress'):
                if key in info:
                    self.logger.record('race/current_' + key, float(info[key]))
            for key, value in info.items():
                if key.startswith('reward_'):
                    self.logger.record_mean('reward_components/' + key[7:], float(value))
            if not done:
                continue
            self.episodes += 1
            self.wins += info['is_first']
            self.logger.record('race/episodes', self.episodes)
            self.logger.record('race/win_rate', self.wins / self.episodes)
            self.logger.record_mean('race/completion_rate', info['race_completed'])
            self.recent_episodes.append(dict(info))
            for key in ('turbo_charges_used', 'turbo_prestart_charges', 'turbo_offroad_active_steps', 'nitro'):
                if key in info:
                    self.logger.record('turbo/rolling100_' + key,
                        sum(float(r.get(key, 0)) for r in self.recent_episodes) / len(self.recent_episodes))
            first_uses = [r['turbo_first_activation_step'] for r in self.recent_episodes
                          if r.get('turbo_first_activation_step', -1) >= 0]
            if first_uses:
                self.logger.record('turbo/rolling100_first_activation_step', sum(first_uses) / len(first_uses))
            for key in ('race_completed', 'is_first', 'offtrack_fraction',
                        'collisions_total', 'net_progress', 'stopped_fraction'):
                self.logger.record('race/rolling100_' + key,
                    sum(float(r[key]) for r in self.recent_episodes) / len(self.recent_episodes))
            completed = [r for r in self.recent_episodes if r['race_completed']]
            if completed:
                self.logger.record('race/rolling100_finish_position',
                    sum(r['final_rank'] + 1 for r in completed) / len(completed))
            score = (info['race_completed'], info['is_first'],
                     -info['final_rank'] if info['race_completed'] else info['net_progress'],
                     -info['offtrack_fraction'], -info['collisions_total'])
            if self.best_score is None or score > self.best_score:
                self.best_score = score
                path = save_checkpoint(self.model, self.model_dir / f'training_candidate_{self.num_timesteps}_steps.zip',
                                       self.expected, run=self.run, reason='training_candidate_not_evaluation', provenance=self.provenance)
                atomic_json(self.model_dir / 'training_candidate.json', {'path': path.name, 'score': score,
                    'note': 'Episodio estocastico pode usar politica anterior a ultima atualizacao. Avaliar separadamente.'})
                clear_progress()
                print(f'Candidato de treino salvo para avaliacao: {path}', flush=True)
        return True


class TrainingProgressCallback(BaseCallback):
    """Progresso da coleta nesta execucao; nao altera politica ou recompensa."""

    def _on_training_start(self):
        import time
        self.started_at = time.monotonic()
        self.last_display = self.started_at
        self.start_steps = self.num_timesteps
        requested = max(0, self.model._total_timesteps - self.start_steps)
        block = self.model.n_steps * self.model.n_envs
        self.target_steps = ((requested + block - 1) // block) * block
        print(f'Passos solicitados nesta execucao: {requested:,}; '
              f'coleta prevista: {self.target_steps:,} (blocos de {block:,}).', flush=True)
        self._display()

    def _display(self):
        import time
        done = max(0, self.num_timesteps - self.start_steps)
        fraction = min(1.0, done / max(1, self.target_steps))
        filled = int(30 * fraction)
        bar = '#' * filled + '-' * (30 - filled)
        elapsed = max(time.monotonic() - self.started_at, 0.001)
        rate = done / elapsed
        eta = f'{max(0, self.target_steps - done) / rate / 60:.1f} min' if rate else '--'
        write_progress(f'COLETA [{bar}] {fraction:6.1%} | '
              f'{done:,}/{self.target_steps:,} steps | '
              f'{rate:.1f} steps/s | restante estimado: {eta}')

    def _on_step(self):
        import time
        now = time.monotonic()
        if now - self.last_display >= 0.5 or self.num_timesteps - self.start_steps == self.target_steps:
            self._display()
            self.last_display = now
        return True

    def _on_rollout_end(self):
        clear_progress()  # Deixa as tabelas do SB3 em linhas separadas.

    def _on_training_end(self):
        self._display()
        finish_progress()
        print('Aprendizado encerrado; o script salvara o modelo a seguir.', flush=True)
