"""Kaggriculture V1 comparison entry point."""
from .counter_agent import agent as _agent


def agent(observation, configuration=None):
    return _agent(observation, configuration)
