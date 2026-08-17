"""Small deterministic tournament harness for local agents."""
from __future__ import annotations
import argparse
import importlib
import json
from pathlib import Path
import statistics

from kagv2.simulator import Game


def resolve(path: str):
    """Resolve `module:callable` into an agent function."""
    mod_name, attr = path.split(":", 1)
    return getattr(importlib.import_module(mod_name), attr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="submission.predictive_agent:agent")
    ap.add_argument("--b", default="baselines.v1.main:agent")
    ap.add_argument("-n", "--seeds", type=int, default=16)
    ap.add_argument("--seed-start", type=int, default=20260816)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    A, B = resolve(args.a), resolve(args.b)
    rows = []
    for k in range(args.seeds):
        seed = args.seed_start + k
        for seat in (0, 1):
            agents = [A, B] if seat == 0 else [B, A]
            money = Game(seed=seed).run(agents)
            a_cash, b_cash = (money[0], money[1]) if seat == 0 else (money[1], money[0])
            rows.append({"seed": seed, "a_seat": seat, "a_cash": a_cash, "b_cash": b_cash,
                         "margin": a_cash - b_cash, "win": int(a_cash > b_cash), "tie": int(a_cash == b_cash)})
    score = sum(r["win"] + 0.5 * r["tie"] for r in rows) / len(rows)
    margins = [r["margin"] for r in rows]
    summary = {"games": len(rows), "a_score_rate": score, "mean_margin": statistics.mean(margins),
               "median_margin": statistics.median(margins), "a": args.a, "b": args.b}
    print(json.dumps(summary, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "games": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
