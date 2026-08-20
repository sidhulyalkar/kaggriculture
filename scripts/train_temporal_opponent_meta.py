#!/usr/bin/env python3
from __future__ import annotations

"""Train replay-derived temporal opponent motifs.

Example:

    python scripts/train_temporal_opponent_meta.py \
      --replay-dir data/replays \
      --out artifacts/temporal_opponent_v1.json \
      --segments-out artifacts/temporal_segments.parquet

The runtime artifact contains public-only features.  Opponent action columns are
used only during offline motif discovery.
"""

import argparse
import json
from pathlib import Path

from kagv2.replay import paths_to_turn_frame, add_outcome_labels
from kagv2.temporal_meta import train_temporal_motifs, save_temporal_artifact


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay-dir", type=Path, action="append", required=True)
    ap.add_argument("--glob", default="**/*.json")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--motifs", type=int, default=8)
    ap.add_argument("--smooth", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--out", type=Path, default=Path("artifacts/temporal_opponent_v1.json"))
    ap.add_argument("--segments-out", type=Path, default=Path("artifacts/temporal_segments.parquet"))
    return ap.parse_args()


def main():
    args = parse_args()
    paths = []
    for root in args.replay_dir:
        paths.extend(sorted(root.glob(args.glob)))
    # Episode files can be large; limit before parsing, not after concatenation.
    if args.limit is not None:
        paths = paths[: args.limit]
    if not paths:
        raise SystemExit("No replay JSON files found")
    print(f"replays={len(paths)} stride={args.stride} motifs={args.motifs} smooth={args.smooth}")
    turns = paths_to_turn_frame(paths, stride=args.stride)
    turns = add_outcome_labels(turns)
    print(f"turn_rows={len(turns)} episodes={turns.episode_id.nunique() if not turns.empty else 0}")
    result = train_temporal_motifs(turns, n_motifs=args.motifs, smooth=args.smooth, seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.segments_out.parent.mkdir(parents=True, exist_ok=True)
    save_temporal_artifact(args.out, result)
    result.segment_frame.to_parquet(args.segments_out, index=False)
    print(json.dumps(result.metrics, indent=2, sort_keys=True))
    print(f"artifact={args.out}")
    print(f"segments={args.segments_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
