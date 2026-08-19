from __future__ import annotations

from dataclasses import dataclass, asdict
import pandas as pd

from kagv2.equilibrium import payoff_from_results, robust_population_mix


@dataclass(frozen=True)
class PopulationReport:
    policies: tuple[str, ...]
    opponents: tuple[str, ...]
    payoff: tuple[tuple[float, ...], ...]
    counts: tuple[tuple[int, ...], ...]
    policy_mixture: tuple[float, ...]
    worst_archetype_value: float
    expected_meta_value: float
    duality_gap: float

    def to_dict(self) -> dict:
        return asdict(self)


def population_report(
    games: pd.DataFrame,
    *,
    policy_col: str = "candidate",
    opponent_col: str = "opponent",
    score_col: str = "score",
    shrink: float = 8.0,
    equilibrium_weight: float = 0.55,
    opponent_prior: list[float] | None = None,
) -> PopulationReport:
    if games.empty:
        raise ValueError("games is empty")
    policies, opponents, payoff, counts = payoff_from_results(
        games.rename(columns={policy_col: "policy", opponent_col: "opponent_archetype"}),
        policy_col="policy",
        opponent_col="opponent_archetype",
        score_col=score_col,
        shrink=shrink,
    )
    meta = robust_population_mix(
        payoff,
        opponent_prior=opponent_prior,
        equilibrium_weight=equilibrium_weight,
    )
    eq = meta["equilibrium"]
    return PopulationReport(
        policies=tuple(policies),
        opponents=tuple(opponents),
        payoff=tuple(tuple(float(x) for x in row) for row in payoff),
        counts=tuple(tuple(int(x) for x in row) for row in counts),
        policy_mixture=tuple(float(x) for x in meta["policy_mixture"]),
        worst_archetype_value=float(meta["worst_archetype_value"]),
        expected_meta_value=float(meta["expected_meta_value"]),
        duality_gap=float(eq["duality_gap"]),
    )


def policy_priority_table(report: PopulationReport) -> pd.DataFrame:
    return pd.DataFrame({"policy": report.policies, "meta_weight": report.policy_mixture}).sort_values(
        "meta_weight", ascending=False
    )
