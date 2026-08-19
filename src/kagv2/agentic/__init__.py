"""Loss-driven agent evolution framework for Kaggriculture."""

from .counterfactual import BranchSpec, EpisodeOutcome, build_counterfactual_rows
from .forecast import ForecastGeneralizationReport, generalization_report
from .loop import EvolutionConfig, LossDrivenEvolutionLoop
from .promotion import PromotionDecision, PromotionThresholds
from .regime import RegimeMetrics, grouped_oof_regime_predictions
from .regret import RegretMetrics, grouped_oof_distributional_regret

__all__ = [
    "BranchSpec",
    "EpisodeOutcome",
    "build_counterfactual_rows",
    "ForecastGeneralizationReport",
    "generalization_report",
    "EvolutionConfig",
    "LossDrivenEvolutionLoop",
    "PromotionDecision",
    "PromotionThresholds",
    "RegimeMetrics",
    "RegretMetrics",
    "grouped_oof_regime_predictions",
    "grouped_oof_distributional_regret",
]
