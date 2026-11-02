"""Logs incrementais: terminal preservado antes do reset automatico do SB3."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import gymnasium as gym


class RecordingEnv(gym.Wrapper):
    def __init__(self, env, directory: Path, log_steps: bool = True):
        super().__init__(env)
        directory.mkdir(parents=True, exist_ok=True)
        self.episodes_stream = (directory / 'episodes.jsonl').open('x', encoding='utf-8')
        try:
            self.steps_stream = (directory / 'steps.jsonl').open('x', encoding='utf-8') if log_steps else None
        except OSError:
            self.episodes_stream.close()
            raise
        self.episode_id = 0
        self.total = 0.0
        self.components = Counter()
        self.actions = Counter()

    def write(self, stream, record):
        if stream is not None:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self.episode_id += 1
        self.total = 0.0
        self.components.clear()
        self.actions.clear()
        self.write(self.steps_stream, {'event': 'reset', 'episode_id': self.episode_id, 'state': info})
        return obs, info

    def step(self, action):
        try:
            obs, reward, terminated, truncated, info = self.env.step(action)
        except Exception as exc:
            record = {'event': 'bridge_or_environment_failure', 'episode_id': self.episode_id,
                      'action': int(action), 'error': repr(exc),
                      'diagnostic': getattr(exc, 'diagnostic', None)}
            self.write(self.episodes_stream, record)
            self.episodes_stream.flush()
            if self.steps_stream is not None:
                self.steps_stream.flush()
            raise
        self.total += reward
        self.actions[info['action_name']] += 1
        for key, value in info.items():
            if key.startswith('reward_'):
                self.components[key] += value
        self.write(self.steps_stream, {'event': 'step', 'episode_id': self.episode_id, 'action': int(action),
                   'reward': reward, 'terminated': terminated, 'truncated': truncated, 'state': info})
        if info['steps'] % 64 == 0 and self.steps_stream is not None:
            self.steps_stream.flush()
        if terminated or truncated:
            self.write(self.episodes_stream, {'event': 'episode_end', 'episode_id': self.episode_id,
                       'reward': self.total, 'components': dict(self.components), 'actions': dict(self.actions),
                       'terminated': terminated, 'truncated': truncated, 'final_state': info})
            self.episodes_stream.flush()
            if self.steps_stream is not None:
                self.steps_stream.flush()
        return obs, reward, terminated, truncated, info

    def close(self):
        try:
            self.env.close()
        finally:
            self.episodes_stream.close()
            if self.steps_stream is not None:
                self.steps_stream.close()
