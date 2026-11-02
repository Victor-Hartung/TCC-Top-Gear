"""PPO com recuperacao limitada de regressao de lap, sem transicao artificial.

Somente o bloco de coleta ainda nao treinado e descartado. ACK, socket, reset,
ROM, detector, progresso invalido e outros erros continuam fatais.
"""
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

from experiment import atomic_json, unique_name
from protocol import ProtocolError
from terminal_progress import clear_progress
from transition_errors import LapSentinelRegression


RECOVERY_POLICY = {
    'version': 1, 'error': 'LapSentinelRegression',
    'strategy': 'discard_partial_rollout_then_validated_savestate_reset',
    'max_recoveries': 3, 'window_steps': 10000,
}


class ResilientPPO(PPO):
    def configure_recovery(self, directory: Path) -> None:
        self._recovery_dir = Path(directory)
        self._recovery_steps = []
        self.recovery_count = 0
        self.discarded_rollout_steps = 0
        self.trained_steps_this_run = 0
        # O contador de um checkpoint antigo pode incluir coleta nao treinada.
        self.last_update_timesteps_this_run = None

    def _excluded_save_params(self):
        return super()._excluded_save_params() + ['_recovery_dir', '_recovery_steps']

    def train(self) -> None:
        super().train()
        self.trained_steps_this_run += self.rollout_buffer.size() * self.n_envs
        self.last_update_timesteps_this_run = int(self.num_timesteps)

    def collect_rollouts(self, env, callback, rollout_buffer, n_rollout_steps):
        while True:
            try:
                return super().collect_rollouts(env, callback, rollout_buffer, n_rollout_steps)
            except LapSentinelRegression as exc:
                # Um unico BizHawk por processo; nao recuperar vetores parcialmente
                # avancados, avaliadores ou instancias sem destino de diagnostico.
                if env.num_envs != 1 or not hasattr(self, '_recovery_dir'):
                    raise
                now = int(self.num_timesteps)
                self._recovery_steps = [s for s in self._recovery_steps
                                        if now - s < RECOVERY_POLICY['window_steps']]
                allowed = len(self._recovery_steps) < RECOVERY_POLICY['max_recoveries']
                discarded = int(rollout_buffer.pos * env.num_envs)
                record = {
                    'event': 'lap_sentinel_recovery', 'num_timesteps': now,
                    'policy': RECOVERY_POLICY, 'diagnostic': exc.diagnostic,
                    'discarded_rollout_steps': discarded,
                    'last_update_timesteps_this_run': self.last_update_timesteps_this_run,
                    'status': 'reset_pending' if allowed else 'rate_limit_exceeded',
                    'note': 'Rejected action is not counted or rewarded. Earlier accepted '
                            'steps in this partial rollout remain logged but are not trained.',
                }
                path = self._recovery_dir / (unique_name('recovery') + '.json')
                atomic_json(path, record)  # Persistir antes de tocar no emulador.
                if not allowed:
                    raise ProtocolError('Regressao de lap repetida: limite de 3 recuperacoes '
                                        'em 10000 passos; diagnostico: ' + str(path)) from exc
                self._recovery_steps.append(now)
                self.discarded_rollout_steps += discarded
                rollout_buffer.reset()
                clear_progress()
                print(f'RECUPERACAO: lap regrediu; {discarded} passos do bloco descartados. '
                      f'Recarregando savestate. Diagnostico: {path}', flush=True)
                try:
                    self._last_obs = env.reset()
                except Exception as reset_error:
                    record.update(status='reset_failed', reset_error=repr(reset_error))
                    atomic_json(path, record)
                    raise
                self._last_episode_starts = np.ones((env.num_envs,), dtype=bool)
                self.recovery_count += 1
                record.update(status='reset_ok', recovery_count=self.recovery_count)
                atomic_json(path, record)
                self.logger.record('recovery/count', self.recovery_count)
                self.logger.record('recovery/discarded_rollout_steps', self.discarded_rollout_steps)
                # A proxima chamada inicia coleta vazia. Nenhum bootstrap de
                # valor nem recompensa de chegada e criado para o pacote recusado.
