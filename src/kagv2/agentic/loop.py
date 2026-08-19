from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path

import pandas as pd

from .forecast import generalization_report
from .losses import prioritize_losses
from .population import population_report
from .promotion import PromotionThresholds, evaluate_promotion, paired_candidate_metrics
from .regime import grouped_oof_regime_predictions, hard_seed_table
from .regret import grouped_oof_distributional_regret, residual_library, residual_threshold_sweep


@dataclass(frozen=True)
class EvolutionConfig:
    champion: str = "V32"
    target_opponents: tuple[str, ...] = ("adaptive", "ranker")
    guard_opponents: tuple[str, ...] = ("soil", "v16", "melon", "strict", "findings")
    random_seed: int = 20260819
    min_regret_groups: int = 12
    min_regret_policy_events: int = 8


class LossDrivenEvolutionLoop:
    """Offline research loop that turns losses into promotion-ready evidence.

    This class has no submission side effect. A separate runtime-verified
    builder may consume only candidates that survive these evidence gates.
    """

    def __init__(self, config: EvolutionConfig | None = None):
        self.config = config or EvolutionConfig()

    def run(
        self,
        *,
        counterfactuals: pd.DataFrame,
        regime_games: pd.DataFrame,
        forecast_lofo: pd.DataFrame | None = None,
        candidate_games: pd.DataFrame | None = None,
        hard_seed_suite: dict | None = None,
        output_dir: str | Path | None = None,
    ) -> dict:
        regime_oof, regime_metrics = grouped_oof_regime_predictions(
            regime_games,
            random_state=self.config.random_seed,
        )
        seed_table = hard_seed_table(regime_oof)
        loss_queue = prioritize_losses(regime_oof)

        regret_oof, regret_metrics = grouped_oof_distributional_regret(
            counterfactuals,
            group_cols=("seed",),
            random_state=self.config.random_seed,
        )
        sweep = residual_threshold_sweep(regret_oof)
        library = residual_library(regret_oof)
        viable_sweep = sweep[
            (sweep["selected_events"] >= self.config.min_regret_policy_events)
            & (sweep["mean_realized_delta"] > 0)
            & (sweep["positive_rate"] >= 0.70)
        ]
        regret_ready = bool(
            regret_metrics.n_groups >= self.config.min_regret_groups
            and not viable_sweep.empty
        )

        forecast = None
        if forecast_lofo is not None and not forecast_lofo.empty:
            forecast = generalization_report(forecast_lofo).to_dict()

        manifest = {
            "version": 2,
            "framework": "loss-driven-evolution",
            "config": asdict(self.config),
            "forecast": forecast,
            "regime": regime_metrics.to_dict(),
            "loss_queue_size": int(len(loss_queue)),
            "regret": {
                **regret_metrics.to_dict(),
                "ready_for_runtime_gate": regret_ready,
                "readiness_reason": (
                    "sufficient independent groups and positive OOF policy gate"
                    if regret_ready
                    else "insufficient independent seeds and/or no positive conservative OOF policy gate"
                ),
            },
            "best_oof_residual_gate": viable_sweep.head(1).to_dict("records")[0] if len(viable_sweep) else None,
            "top_residual_families": library.head(12).to_dict("records"),
            "population": None,
            "promotion": [],
        }

        if candidate_games is not None and not candidate_games.empty:
            pop = population_report(candidate_games)
            manifest["population"] = pop.to_dict()
            candidates = [
                c for c in sorted(candidate_games["candidate"].astype(str).unique())
                if c != self.config.champion
            ]
            hs = set((hard_seed_suite or {}).get("hard_seeds", []))
            ss = set((hard_seed_suite or {}).get("safe_control_seeds", []))
            for candidate in candidates:
                metrics = paired_candidate_metrics(
                    candidate_games,
                    candidate=candidate,
                    control=self.config.champion,
                    target_opponents=set(self.config.target_opponents),
                    guard_opponents=set(self.config.guard_opponents),
                    hard_seeds=hs,
                    safe_seeds=ss,
                )
                manifest["promotion"].append(
                    evaluate_promotion(metrics, PromotionThresholds()).to_dict()
                )

        if output_dir is not None:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            regime_oof.to_csv(out / "regime_oof.csv", index=False)
            seed_table.to_csv(out / "seed_difficulty.csv", index=False)
            loss_queue.to_csv(out / "loss_queue.csv", index=False)
            regret_oof.to_csv(out / "regret_oof.csv", index=False)
            sweep.to_csv(out / "residual_threshold_sweep.csv", index=False)
            library.to_csv(out / "residual_library.csv", index=False)
            if manifest["population"]:
                pd.DataFrame({
                    "policy": manifest["population"]["policies"],
                    "meta_weight": manifest["population"]["policy_mixture"],
                }).to_csv(out / "population_weights.csv", index=False)
            (out / "EVOLUTION_MANIFEST.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True, default=str)
            )
        return manifest
