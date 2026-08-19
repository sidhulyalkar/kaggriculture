from __future__ import annotations

import numpy as np
import pandas as pd


def prioritize_losses(
    regime_oof: pd.DataFrame,
    *,
    score_col: str = "score",
    risk_col: str = "loss_prob_oof",
    margin_col: str = "margin",
    max_known: int = 24,
    max_surprise: int = 12,
) -> pd.DataFrame:
    """Create a diverse replay queue from actual losses.

    The queue retains both high-risk known-hard losses and surprising low-risk
    losses so the research loop does not become blind to novel meta regimes.
    """
    d = regime_oof.copy()
    if not {score_col, risk_col} <= set(d.columns):
        raise KeyError(f"Need {score_col!r} and {risk_col!r}")
    loss = d[pd.to_numeric(d[score_col], errors="coerce") < 0.5].copy()
    if loss.empty:
        return loss
    if margin_col not in loss:
        loss[margin_col] = 0.0
    keys = [c for c in ("opponent", "seed", "seat") if c in loss]
    if keys:
        loss = loss.sort_values(risk_col, ascending=False).drop_duplicates(keys)
    risk = pd.to_numeric(loss[risk_col], errors="coerce").fillna(0.5)
    severity = -pd.to_numeric(loss[margin_col], errors="coerce").fillna(0.0)
    sev_scale = max(1.0, float(np.nanpercentile(np.abs(severity), 90)))
    loss["priority_known"] = risk + 0.15 * np.clip(severity / sev_scale, 0, 2)
    loss["priority_surprise"] = (1.0 - risk) + 0.10 * np.clip(severity / sev_scale, 0, 2)
    known = loss.sort_values("priority_known", ascending=False).head(max_known).copy()
    known["queue"] = "known_hard"
    surprise = loss[~loss.index.isin(known.index)].sort_values("priority_surprise", ascending=False).head(max_surprise).copy()
    surprise["queue"] = "surprise"
    return pd.concat([known, surprise], ignore_index=True).sort_values(
        ["queue", "priority_known"], ascending=[True, False]
    )
