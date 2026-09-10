from __future__ import annotations

import argparse
import json
import pathlib
import statistics
from collections import defaultdict

PUBLIC_BAKERY = 10232.5
PUBLIC_PET = 64.5


def bt(m: float) -> float:
    return 1.0 if m > 0 else 0.5 if m == 0 else 0.0


def choose(row: dict, bakery: float, pet: float) -> int:
    f = row["features"]
    shop = f.get("first_shop", "NONE")
    if shop == "BAKERY" and float(f.get("market_FERTILIZER", 0)) <= bakery:
        return 1
    if shop == "PET_CAFE" and float(f.get("opp_plants", 0)) <= pet:
        return 1
    return 0


def margin_for(row: dict, route: int) -> float:
    return float(row[f"route{route}_margin"])


def metrics(rows: list[dict], bakery: float, pet: float) -> dict:
    vals = []
    margins = []
    route1 = 0
    by = defaultdict(list)
    flips = sacrifices = decision_diff = 0
    for r in rows:
        c = choose(r, bakery, pet)
        p = choose(r, PUBLIC_BAKERY, PUBLIC_PET)
        route1 += c
        decision_diff += int(c != p)
        m = margin_for(r, c)
        pm = margin_for(r, p)
        s = bt(m)
        vals.append(s)
        margins.append(m)
        by[r["opponent"]].append(s)
        flips += int(pm <= 0 and m > 0)
        sacrifices += int(pm > 0 and m <= 0)
    per = {k: sum(v) / len(v) for k, v in by.items()}
    return {
        "bakery": bakery,
        "pet": pet,
        "n": len(rows),
        "bt_score": sum(vals) / len(vals),
        "mean_margin": statistics.mean(margins),
        "median_margin": statistics.median(margins),
        "worst_opponent_bt": min(per.values()),
        "per_opponent_bt": per,
        "route1_fraction": route1 / len(rows),
        "decision_diff_fraction": decision_diff / len(rows),
        "flipped_nonwins_to_wins": flips,
        "sacrificed_wins": sacrifices,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rows = [json.loads(x) for x in pathlib.Path(args.data).read_text().splitlines() if x.strip()]
    if not rows:
        raise SystemExit("empty oracle")
    public = metrics(rows, PUBLIC_BAKERY, PUBLIC_PET)

    bakery_grid = [x + 0.5 for x in range(9800, 10601, 25)]
    pet_grid = [x + 0.5 for x in range(30, 91, 2)]
    candidates = []
    for b in bakery_grid:
        for p in pet_grid:
            m = metrics(rows, b, p)
            m["bt_gain"] = m["bt_score"] - public["bt_score"]
            m["worst_gain"] = m["worst_opponent_bt"] - public["worst_opponent_bt"]
            m["rank_key"] = [
                m["bt_score"],
                m["worst_opponent_bt"],
                m["flipped_nonwins_to_wins"] - m["sacrificed_wins"],
                m["mean_margin"],
            ]
            candidates.append(m)
    candidates.sort(key=lambda m: tuple(m["rank_key"]), reverse=True)
    best = candidates[0]

    oracle_vals = []
    public_vals = []
    route0_vals = []
    route1_vals = []
    oracle_flips = 0
    shop_stats = defaultdict(lambda: {"n": 0, "r0_bt": 0.0, "r1_bt": 0.0, "r0_margin": 0.0, "r1_margin": 0.0, "oracle_route1": 0})
    for r in rows:
        m0 = float(r["route0_margin"])
        m1 = float(r["route1_margin"])
        p = choose(r, PUBLIC_BAKERY, PUBLIC_PET)
        pm = margin_for(r, p)
        oracle = max(bt(m0), bt(m1))
        oracle_vals.append(oracle)
        public_vals.append(bt(pm))
        route0_vals.append(bt(m0))
        route1_vals.append(bt(m1))
        oracle_flips += int(pm <= 0 and max(m0, m1) > 0)
        s = shop_stats[r["features"].get("first_shop", "NONE")]
        s["n"] += 1
        s["r0_bt"] += bt(m0)
        s["r1_bt"] += bt(m1)
        s["r0_margin"] += m0
        s["r1_margin"] += m1
        s["oracle_route1"] += int(m1 > m0)
    for _, s in shop_stats.items():
        n = s["n"]
        for k in ("r0_bt", "r1_bt", "r0_margin", "r1_margin", "oracle_route1"):
            s[k] /= n

    promote = (
        best["bt_gain"] >= 0.01
        and best["decision_diff_fraction"] >= 0.01
        and best["sacrificed_wins"] <= best["flipped_nonwins_to_wins"]
        and all(best["per_opponent_bt"][o] >= public["per_opponent_bt"][o] - 0.085 for o in public["per_opponent_bt"])
    )
    report = {
        "public": public,
        "best_grid": best,
        "promote_to_fresh_field": promote,
        "oracle_bt": sum(oracle_vals) / len(oracle_vals),
        "oracle_headroom_over_public": sum(oracle_vals) / len(oracle_vals) - sum(public_vals) / len(public_vals),
        "oracle_flippable_public_nonwins": oracle_flips,
        "always_route0_bt": sum(route0_vals) / len(route0_vals),
        "always_route1_bt": sum(route1_vals) / len(route1_vals),
        "shop_counterfactuals": dict(sorted(shop_stats.items())),
        "top10": candidates[:10],
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    params = out.with_name("selected_params.json")
    params.write_text(json.dumps({"bakery": best["bakery"], "pet": best["pet"], "promote": promote}, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
