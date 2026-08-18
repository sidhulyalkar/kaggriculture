#!/usr/bin/env python3
from __future__ import annotations

"""Paired CPU tournament for the V35 live-probe pack.

Run this after ``v35_live_probe_pack.py``. It compares the exact generated V35
archives with the runtime-verified V32 anchor using fresh paired seeds and both
seats. Stage 1 is a compact hard set; Stage 2 expands the top two probes to all
discovered public-agent families.
"""

from pathlib import Path
import argparse
import json
import os
import shutil

import numpy as np
import pandas as pd

import soil_route_counter_lab as base
import v35_live_probe_pack as pack

CONTROL = "V32_ANCHOR"
PROBES = ["V35A_SHADOW_PRIORITY", "V35B_SLOT_RACE", "V35C_FRONT_RUN_LIGHT"]
ADAPTIVE = {"adaptive", "score3094"}


def _extract_archive(archive: Path, root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    main = base.safe_extract(archive, root)
    if main is None:
        raise RuntimeError(f"No main.py found in {archive}")
    # The production archives are expected to have a root main.py. Preserve a
    # shallow fallback for diagnostics, but fail if the root file is absent so
    # we test the same layout that Kaggle will receive.
    root_main = root / "main.py"
    if not root_main.exists():
        raise RuntimeError(f"{archive} does not contain root main.py")
    return root_main


def prepare_candidates(input_root: Path, probe_root: Path, work: Path):
    archive_by_name = {CONTROL: pack.find_anchor(input_root)}
    for name in PROBES:
        p = probe_root / f"SUBMIT_{name}.tar.gz"
        if not p.exists():
            raise FileNotFoundError(
                f"Missing {p}. Run scripts/v35_live_probe_pack.py first."
            )
        archive_by_name[name] = p

    roots = {}
    for name, archive in archive_by_name.items():
        root = work / "candidates" / name
        _extract_archive(archive, root)
        roots[name] = root
    return roots, archive_by_name


def summarize(df: pd.DataFrame, control: str = CONTROL) -> pd.DataFrame:
    keys = ["opponent", "seed", "seat"]
    ctl = df[df.candidate == control][keys + ["score", "margin", "ok"]].rename(
        columns={"score": "control_score", "margin": "control_margin", "ok": "control_ok"}
    )
    rows = []
    for name, g in df.groupby("candidate"):
        m = g.merge(ctl, on=keys, how="left")
        valid = m[(m.ok == True) & (m.control_ok == True)].copy()  # noqa: E712
        if len(valid):
            valid["delta"] = valid.score - valid.control_score
            valid["margin_delta"] = valid.margin - valid.control_margin
            per_opp = valid.groupby("opponent").delta.mean()
            adaptive = valid[valid.opponent.isin(ADAPTIVE)]
            robust_delta = float(valid.delta.mean())
            adaptive_delta = float(adaptive.delta.mean()) if len(adaptive) else 0.0
            worst = float(per_opp.min()) if len(per_opp) else -1.0
            margin_delta = float(valid.margin_delta.mean())
        else:
            robust_delta, adaptive_delta, worst, margin_delta = -1.0, 0.0, -1.0, float("nan")
        valid_scores = pd.to_numeric(g.loc[g.ok == True, "score"], errors="coerce")  # noqa: E712
        rows.append({
            "candidate": name,
            "games": int(len(g)),
            "valid_pairs": int(len(valid)),
            "invalid_games": int((g.ok != True).sum()),  # noqa: E712
            "mean_score": float(valid_scores.mean()) if len(valid_scores) else float("nan"),
            "robust_delta": robust_delta,
            "adaptive_delta": adaptive_delta,
            "worst_opponent_delta": worst,
            "mean_margin_delta": margin_delta,
        })
    out = pd.DataFrame(rows)
    out["utility"] = (
        out.robust_delta
        + 0.75 * out.adaptive_delta
        + 0.25 * np.minimum(out.worst_opponent_delta, 0.0)
    )
    return out.sort_values(["utility", "robust_delta"], ascending=False).reset_index(drop=True)


def live_recommendation(table: pd.DataFrame):
    probes = table[(table.candidate != CONTROL) & (table.invalid_games == 0)].copy()
    passed = probes[
        (probes.robust_delta >= 0.010)
        & (probes.adaptive_delta >= 0.030)
        & (probes.worst_opponent_delta >= -0.030)
    ]
    if len(passed):
        r = passed.sort_values(["utility", "robust_delta"], ascending=False).iloc[0]
        return str(r.candidate), (
            f"cleared offline live-probe gate: robust {r.robust_delta:+.4f}, "
            f"adaptive {r.adaptive_delta:+.4f}, worst {r.worst_opponent_delta:+.4f}"
        )

    # Shadow Priority is safe enough to remain an information probe when its
    # result is statistically neutral, but only if it shows no material broad
    # regression. This is NOT a promotion of V32, just permission for one live
    # experiment slot.
    a = probes[probes.candidate == "V35A_SHADOW_PRIORITY"]
    if len(a):
        r = a.iloc[0]
        if r.robust_delta >= -0.005 and r.worst_opponent_delta >= -0.030:
            return "V35A_SHADOW_PRIORITY", (
                "no probe cleared promotion, but V35A remained essentially neutral offline; "
                "use only as a single live information probe"
            )
    return CONTROL, "No V35 probe justified a leaderboard slot after held-out paired testing."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default="/kaggle/input")
    ap.add_argument("--probe-root", default="/kaggle/working/v35_live_probes")
    ap.add_argument("--work", default="/kaggle/working/v35_offline")
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 2))
    args = ap.parse_args()

    input_root = Path(args.input_root)
    probe_root = Path(args.probe_root)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]

    roots, archives = prepare_candidates(input_root, probe_root, work)
    agents = base.discover(input_root, work)
    if not agents:
        raise RuntimeError(
            "No public agents discovered. Attach the same public-agent Kaggle inputs "
            "used by the Soil/V33 labs."
        )
    worker = work / "worker.py"
    worker.write_text(base.WORKER)

    hard = [x for x in ("adaptive", "score3094", "soil", "v16") if x in agents]
    if len(hard) < 2:
        hard = list(agents)[: min(4, len(agents))]
    screen_seeds = [3601, 3613, 3629, 3643, 3659, 3671]
    names = [CONTROL, *PROBES]
    print("V35 SCREEN", names, "opponents", hard, "seeds", screen_seeds)
    jobs = base.jobs_for(roots, agents, names, screen_seeds, hard)
    screen = base.parallel(jobs, worker, repo, args.workers)
    screen.to_csv(work / "v35_screen_games.csv", index=False)
    screen_table = summarize(screen)
    screen_table.to_csv(work / "v35_screen_summary.csv", index=False)
    print(screen_table.to_string(index=False))

    finalists = (
        screen_table[(screen_table.candidate != CONTROL) & (screen_table.invalid_games == 0)]
        .head(2)
        .candidate.tolist()
    )
    held_names = [CONTROL, *finalists]
    held_seeds = [3719, 3733, 3761, 3779, 3793, 3803]
    opponents = list(agents)
    print("V35 HELDOUT", held_names, "opponents", opponents, "seeds", held_seeds)
    jobs = base.jobs_for(roots, agents, held_names, held_seeds, opponents)
    held = base.parallel(jobs, worker, repo, args.workers)
    held.to_csv(work / "v35_heldout_games.csv", index=False)
    held_table = summarize(held)
    held_table.to_csv(work / "v35_heldout_summary.csv", index=False)
    print(held_table.to_string(index=False))

    recommended, reason = live_recommendation(held_table)
    decision = {
        "version": 35,
        "control": CONTROL,
        "screen_seeds": screen_seeds,
        "heldout_seeds": held_seeds,
        "screen_opponents": hard,
        "heldout_opponents": opponents,
        "finalists": finalists,
        "recommended_live_probe": recommended,
        "reason": reason,
        "archives": {k: str(v) for k, v in archives.items()},
        "gate": {
            "min_robust_delta": 0.010,
            "min_adaptive_delta": 0.030,
            "min_worst_opponent_delta": -0.030,
            "invalid_games": 0,
        },
        "note": "A live-probe recommendation is not a champion promotion. Leaderboard evidence remains an additional experiment.",
    }
    (work / "V35_OFFLINE_DECISION.json").write_text(json.dumps(decision, indent=2, sort_keys=True))
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
