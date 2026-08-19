"""Loss-driven agent evolution framework for Kaggriculture."""

from .loop import EvolutionConfig, LossDrivenEvolutionLoop
from .promotion import PromotionDecision, PromotionThresholds
from .regime import RegimeMetrics, grouped_oof_regime_predictions
from .regret import RegretMetrics, grouped_oof_distributional_regret

__all__ = [
    "EvolutionConfig",
    "LossDrivenEvolutionLoop",
    "PromotionDecision",
    "PromotionThresholds",
    "RegimeMetrics",
    "RegretMetrics",
    "grouped_oof_regime_predictions",
    "grouped_oof_distributional_regret",
]
