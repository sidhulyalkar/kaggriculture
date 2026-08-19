#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from kagv2.agentic import EvolutionConfig, LossDrivenEvolutionLoop


def main():
    ap = argparse.ArgumentParser(description="Run the Kaggriculture loss-driven evolution lab")
    ap.add_argument("--counterfactuals", required=True)
    ap.add_argument("--regime-games", required=True)
    ap.add_argument("--forecast-lofo")
    ap.add_argument("--candidate-games")
    ap.add_argument("--hard-seed-suite")
    ap.add_argument("--champion", default="V32")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    suite = json.loads(Path(a.hard_seed_suite).read_text()) if a.hard_seed_suite else None
    manifest = LossDrivenEvolutionLoop(EvolutionConfig(champion=a.champion)).run(
        counterfactuals=pd.read_csv(a.counterfactuals),
        regime_games=pd.read_csv(a.regime_games),
        forecast_lofo=pd.read_csv(a.forecast_lofo) if a.forecast_lofo else None,
        candidate_games=pd.read_csv(a.candidate_games) if a.candidate_games else None,
        hard_seed_suite=suite,
        output_dir=a.out,
    )
    print(json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
