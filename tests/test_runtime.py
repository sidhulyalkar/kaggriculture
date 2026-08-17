from submission.base_controller import HarvestMind
from submission.predictive_agent import agent
from src.kagv2.simulator import Game
from src.kagv2.runtime_features import runtime_feature_vector


def test_feature_shape_and_agent_runs():
    g = Game(seed=1)
    obs = g.obs(0)
    x = runtime_feature_vector(obs)
    assert len(x) > 40
    a = agent(obs)
    assert set(a) == {"farmer", "hands", "market"}


def test_short_game_no_exception():
    g = Game(seed=2, episode_steps=40)
    a = HarvestMind().act
    scores = g.run([a, a])
    assert len(scores) == 2
