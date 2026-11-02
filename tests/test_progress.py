"""Progresso de terminal com PPO sintetico; nao executa BizHawk."""
import contextlib
import io
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
import gymnasium as gym
from stable_baselines3 import PPO
from callbacks import TrainingProgressCallback
from avaliar_modelo import show_evaluation_progress
from unittest.mock import patch
import os
import terminal_progress


class ProgressTests(unittest.TestCase):
    def test_updates_replace_same_line_without_newlines(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            terminal_progress.clear_progress()
            out.seek(0)
            out.truncate()
            terminal_progress.write_progress('50% [#####-----]')
            terminal_progress.write_progress('60% [######----]')
            self.assertNotIn('\n', out.getvalue())
            self.assertEqual(out.getvalue().count('\r'), 2)
            terminal_progress.finish_progress()
        self.assertTrue(out.getvalue().endswith('\n'))

    def test_shorter_update_erases_previous_text(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            terminal_progress.clear_progress()
            terminal_progress.write_progress('abcdefgh')
            terminal_progress.write_progress('abc')
            self.assertTrue(out.getvalue().endswith('\rabc     '))
            terminal_progress.clear_progress()

    def test_progress_does_not_wrap_at_terminal_width(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch('terminal_progress.shutil.get_terminal_size', return_value=os.terminal_size((20, 24))):
            terminal_progress.clear_progress()
            out.seek(0)
            out.truncate()
            terminal_progress.write_progress('x' * 50)
            self.assertEqual(out.getvalue(), '\r' + 'x' * 19)
            terminal_progress.finish_progress()

    def test_training_counts_additional_steps_with_real_ppo_resume(self):
        env = gym.make('CartPole-v1')
        try:
            model = PPO('MlpPolicy', env, n_steps=8, batch_size=8, n_epochs=1,
                        device='cpu', seed=42)
            for requested, expected in [(8, 8), (9, 16)]:
                start = model.num_timesteps
                callback = TrainingProgressCallback()
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    model.learn(requested, callback=callback, reset_num_timesteps=False)
                self.assertEqual(callback.start_steps, start)
                self.assertEqual(callback.target_steps, expected)
                self.assertEqual(model.num_timesteps - start, expected)
                self.assertIn('100.0%', out.getvalue())
                self.assertIn(f'{expected:,}/{expected:,} steps', out.getvalue())
        finally:
            env.close()

    def test_evaluation_percentage_counts_completed_episodes(self):
        report = {'requested_episodes': 1, 'compare_accelerate': True, 'episodes': []}
        for expected in ['0.0%', '50.0%', '100.0%']:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                show_evaluation_progress(report, 'model', 500)
            self.assertIn(expected, out.getvalue())
            self.assertIn('500 steps nesta corrida', out.getvalue())
            report['episodes'].append({'completed': True})

    def test_unfinished_evaluation_is_not_counted(self):
        report = {'requested_episodes': 1, 'episodes': [{'completed': False}]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            show_evaluation_progress(report, 'model', 1000)
        self.assertIn('0/1 episodios', out.getvalue())


if __name__ == '__main__':
    unittest.main()
