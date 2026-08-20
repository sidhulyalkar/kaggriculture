#!/usr/bin/env python3
"""Paired both-seat screen for V33 against the exact V32 champion.

This is intentionally a direct control test, not a replacement for the broad
opponent-family promotion suite. Each game loads V32 into two independent
namespaces so the champion and the champion wrapped by V33 cannot share globals.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

from kagv2.simulator import Game
from submission.v33_workgraph_agent import V33WorkGraphOverlay
from scripts.build_v33_workgraph_submission import load_base_from_tar, last_callable


def load_agent(source: str):
    env: dict = {}
    exec(compile(source, "v32_exact.py", "exec"), env, env)
    return last_callable(env)[1]


def run_game(source: str, seed: int, v33_seat: int) -> dict:
    wrapped_base = load_agent(source)
    control = load_agent(source)
    overlay = V33WorkGraphOverlay(wrapped_base)

    def v33(obs, configuration=None):
        return overlay.act(obs, configuration)

    agents = [v33, control] if v33_seat == 0 else [control, v33]
    money = Game(seed=seed).run(agents)
    v33_cash = float(money[v33_seat])
    v32_cash = float(money[1 - v33_seat])
    return {
        "seed": seed,
        "v33_seat": v33_seat,
        "v33_cash": v33_cash,
        "v32_cash": v32_cash,
        "margin": v33_cash - v32_cash,
        "score": 1.0 if v33_cash > v32_cash else 0.5 if v33_cash == v32_cash else 0.0,
        "suppressions": int(overlay.total_suppressions),
        "capital_latch": overlay.capital_latch,
        "latched_lead": overlay.latched_lead,
    }


def summarize(rows: list[dict]) -> dict:
    margins = [r["margin"] for r in rows]
    changed = [r for r in rows if r["suppressions"] > 0]
    return {
        "games": len(rows),
        "v33_direct_score": sum(r["score"] for r in rows) / max(1, len(rows)),
        "mean_margin": statistics.mean(margins) if margins else 0.0,
        "median_margin": statistics.median(margins) if margins else 0.0,
        "min_margin": min(margins) if margins else 0.0,
        "max_margin": max(margins) if margins else 0.0,
        "games_with_intervention": len(changed),
        "intervention_rate": len(changed) / max(1, len(rows)),
        "total_suppressions": sum(r["suppressions"] for r in rows),
        "changed_game_score": (sum(r["score"] for r in changed) / len(changed)) if changed else None,
        "changed_game_mean_margin": (statistics.mean(r["margin"] for r in changed)) if changed else None,
        "negative_changed_games": sum(r["margin"] < 0 for r in changed),
        "positive_changed_games": sum(r["margin"] > 0 for r in changed),
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v32-tar", type=Path, required=True)
    ap.add_argument("--seeds", type=int, default=64)
    ap.add_argument("--seed-start", type=int, default=20260833)
    ap.add_argument("--out", type=Path, default=Path("artifacts/v33_direct_v32.json"))
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    source, base_meta = load_base_from_tar(args.v32_tar)
    rows = []
    for k in range(args.seeds):
        seed = args.seed_start + k
        rows.append(run_game(source, seed, 0))
        rows.append(run_game(source, seed, 1))
    report = {"base": base_meta, "summary": summarize(rows), "games": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
