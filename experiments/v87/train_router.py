from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from sklearn.tree import DecisionTreeRegressor

CHECKPOINTS = (226, 360, 433)


def read_rows(path: str):
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def baseline_gate(cp: int, f: dict) -> bool:
    if cp == 226:
        return float(f.get("shop_YARN_STORE", 0)) >= 1.0
    if cp == 360:
        return float(f.get("price_CARROT", 0)) >= 42.0
    if cp == 433:
        return float(f.get("market_MILK", 0)) >= 10067.0
    raise KeyError(cp)


def bt(margin: float) -> float:
    if margin > 0: return 1.0
    if margin < 0: return 0.0
    return 0.5


def chosen_margin(cp: int, row: dict, take: bool) -> float:
    m = row["margins"]
    if cp == 226:
        # Family choice. The later sub-branch is treated as an oracle only for
        # diagnosing whether the early family gate contains useful information.
        return max(m["yarn"], m["yarn_carrot"]) if take else max(m["main"], m["milk_glut"])
    if cp == 360:
        return m["yarn_carrot"] if take else m["yarn"]
    if cp == 433:
        return m["milk_glut"] if take else m["main"]
    raise KeyError(cp)


def delta_for(cp: int, row: dict) -> float:
    return float(row[f"delta_{cp}"])


def features_for(cp: int, row: dict) -> dict:
    return row[f"features_{cp}"]


def metrics(cp: int, rows: list[dict], pred) -> dict:
    regrets = []
    bt_scores = []
    margins = []
    correct = 0
    for r in rows:
        f = features_for(cp, r)
        d = delta_for(cp, r)
        take = bool(pred(f))
        oracle_take = d > 0
        correct += int(take == oracle_take or d == 0)
        regrets.append(abs(d) if (d != 0 and take != oracle_take) else 0.0)
        cm = chosen_margin(cp, r, take)
        margins.append(cm)
        bt_scores.append(bt(cm))
    n = max(1, len(rows))
    return {
        "n": len(rows),
        "accuracy": correct / n,
        "mean_regret": float(np.mean(regrets)) if regrets else 0.0,
        "median_regret": float(np.median(regrets)) if regrets else 0.0,
        "bt_score": float(np.mean(bt_scores)) if bt_scores else 0.0,
        "mean_margin": float(np.mean(margins)) if margins else 0.0,
    }


def serialize_tree(model: DecisionTreeRegressor, names: list[str]) -> dict:
    t = model.tree_
    return {
        "feature_names": names,
        "feature": [int(x) for x in t.feature.tolist()],
        "threshold": [float(x) for x in t.threshold.tolist()],
        "left": [int(x) for x in t.children_left.tolist()],
        "right": [int(x) for x in t.children_right.tolist()],
        "value": [float(x[0][0]) for x in t.value.tolist()],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--train-opponents", required=True)
    ap.add_argument("--holdout-opponents", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = read_rows(args.data)
    train_names = {x for x in args.train_opponents.split(",") if x}
    hold_names = {x for x in args.holdout_opponents.split(",") if x}
    train = [r for r in rows if r.get("opponent") in train_names]
    hold = [r for r in rows if r.get("opponent") in hold_names]
    if not train or not hold:
        raise SystemExit(f"empty split train={len(train)} hold={len(hold)} opponents={sorted({r.get('opponent') for r in rows})}")

    payload = {"train_opponents": sorted(train_names), "holdout_opponents": sorted(hold_names), "checkpoints": {}}

    for cp in CHECKPOINTS:
        all_features = sorted({k for r in train for k in features_for(cp, r).keys()})
        X = np.array([[float(features_for(cp, r).get(k, 0.0)) for k in all_features] for r in train], dtype=float)
        y = np.array([delta_for(cp, r) for r in train], dtype=float)

        # Weight matchups where the two legal continuations change W/T/L much more
        # heavily than those where they merely change the winning margin.
        weights = []
        for r in train:
            m = r["margins"]
            if cp == 226:
                a = max(m["main"], m["milk_glut"]); b = max(m["yarn"], m["yarn_carrot"])
            elif cp == 360:
                a, b = m["yarn"], m["yarn_carrot"]
            else:
                a, b = m["main"], m["milk_glut"]
            weights.append(5.0 if bt(a) != bt(b) else 1.0)

        model = DecisionTreeRegressor(max_depth=2, min_samples_leaf=max(4, len(train)//16), random_state=87)
        model.fit(X, y, sample_weight=np.array(weights, dtype=float))
        tree = serialize_tree(model, all_features)

        def learned(f):
            node = 0
            while tree["left"][node] != tree["right"][node]:
                fi = tree["feature"][node]
                val = float(f.get(tree["feature_names"][fi], 0.0))
                node = tree["left"][node] if val <= tree["threshold"][node] else tree["right"][node]
            return tree["value"][node] > 0.0

        bm_train = metrics(cp, train, lambda f, c=cp: baseline_gate(c, f))
        lm_train = metrics(cp, train, learned)
        bm_hold = metrics(cp, hold, lambda f, c=cp: baseline_gate(c, f))
        lm_hold = metrics(cp, hold, learned)

        # The learned rule earns runtime control only if it improves held-out BT
        # score and does not increase regret.  Early-family cp226 is held to a
        # stronger bar because its offline metric uses an oracle downstream branch.
        min_bt_gain = 0.025 if cp == 226 else 0.01
        enabled = (
            lm_hold["bt_score"] >= bm_hold["bt_score"] + min_bt_gain
            and lm_hold["mean_regret"] <= bm_hold["mean_regret"]
            and lm_hold["mean_margin"] >= bm_hold["mean_margin"] - 1000.0
        )
        payload["checkpoints"][str(cp)] = {
            "enabled": bool(enabled),
            "baseline_train": bm_train, "learned_train": lm_train,
            "baseline_holdout": bm_hold, "learned_holdout": lm_hold,
            "tree": tree,
        }
        print(cp, "enabled", enabled, "holdout baseline", bm_hold, "learned", lm_hold)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
