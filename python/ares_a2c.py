"""A2C-specific setup for the independent Ares brain."""
from __future__ import annotations

import torch

from experiment import contract as environment_contract
from topgear_config import ProjectConfig


def a2c_options(config: ProjectConfig) -> dict:
    """Reuse PPO's applicable scenario values and A2C's RMSprop optimizer."""
    return {
        "n_steps": config.integer("ppo", "n_steps"),
        "gamma": config.number("ppo", "gamma"),
        "gae_lambda": config.number("ppo", "gae_lambda"),
        "learning_rate": config.number("ppo", "learning_rate"),
        "ent_coef": config.number("ppo", "ent_coef"),
        "vf_coef": config.number("ppo", "vf_coef"),
        "max_grad_norm": config.number("ppo", "max_grad_norm"),
        "rms_prop_eps": 1e-5,
        "use_rms_prop": True,
        "normalize_advantage": True,
    }


def a2c_policy_kwargs() -> dict:
    """Keep the same two 64-unit tanh actor and critic networks."""
    return {
        "net_arch": {"pi": [64, 64], "vf": [64, 64]},
        "activation_fn": torch.nn.Tanh,
    }


def a2c_contract(config: ProjectConfig) -> dict:
    """Bind Ares to the blue-auto game contract and its independent A2C setup."""
    value = environment_contract(config)
    value.pop("ppo")
    value["algorithm"] = "A2C"
    value["a2c"] = {**a2c_options(config), "device": "cpu"}
    value["policy"] = {
        "class": "MlpPolicy",
        "pi": [64, 64],
        "vf": [64, 64],
        "activation": "Tanh",
        "optimizer": "RMSprop",
        "normalize_advantage": True,
        "wrappers": ["Monitor", "DummyVecEnv"],
        "vecnormalize": False,
    }
    return value
