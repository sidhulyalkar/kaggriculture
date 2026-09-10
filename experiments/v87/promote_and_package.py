from __future__ import annotations

import json
import pathlib
import shutil
import tarfile
import hashlib

ROOT = pathlib.Path("experiments/v87")


def bt_score(summary: dict) -> float:
    g = max(1, int(summary.get("games", 0)))
    return (float(summary.get("wins", 0)) + 0.5 * float(summary.get("ties", 0))) / g


def direct_bt(rows: list[dict], me: str, opp: str) -> float:
    points = games = 0.0
    for r in rows:
        if r.get("a") == me and r.get("b") == opp:
            m = float(r.get("r0", 0)) - float(r.get("r1", 0))
        elif r.get("b") == me and r.get("a") == opp:
            m = float(r.get("r1", 0)) - float(r.get("r0", 0))
        else:
            continue
        games += 1
        points += 1.0 if m > 0 else 0.5 if m == 0 else 0.0
    return points / games if games else 0.0


def main():
    field = json.loads((ROOT / "results/field/field_results.json").read_text())
    d = field["summary"]
    c = d["v87_counterfactual_shape"]
    b = d["shape_current"]
    rows = [json.loads(x) for x in (ROOT / "results/field/games.jsonl").read_text().splitlines() if x.strip()]
    c_bt = bt_score(c); b_bt = bt_score(b)
    mirror_bt = direct_bt(rows, "v87_counterfactual_shape", "shape_current")
    adaptive_bt = direct_bt(rows, "v87_counterfactual_shape", "adaptive_v2") if "adaptive_v2" in d else None

    # Promote only when the learned router adds real BT value over current Shape,
    # with no runtime errors and without materially worsening the downside tail.
    promote = (
        int(c.get("errors", 999)) == 0
        and c_bt >= b_bt + 0.015
        and float(c.get("margin_cvar10", -1e18)) >= float(b.get("margin_cvar10", -1e18)) - 2500.0
        and mirror_bt >= 0.50
    )
    report = {
        "candidate_bt": c_bt,
        "shape_bt": b_bt,
        "bt_gain": c_bt - b_bt,
        "direct_bt_vs_shape": mirror_bt,
        "direct_bt_vs_adaptive_v2": adaptive_bt,
        "candidate": c,
        "shape": b,
        "router_model": json.loads((ROOT / "results/router_model.json").read_text()),
        "promote": promote,
    }
    (ROOT / "results/promotion.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    sub = ROOT / "submission"; sub.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "generated/v87_counterfactual_shape.py", sub / "main.py")
    tar = ROOT / "Kaggriculture_V87_COUNTERFACTUAL_SHAPE_ROUTER.tar.gz"
    with tarfile.open(tar, "w:gz") as tf:
        tf.add(sub / "main.py", arcname="main.py")
    print("MAIN_SHA", hashlib.sha256((sub / "main.py").read_bytes()).hexdigest())
    print("TAR_SHA", hashlib.sha256(tar.read_bytes()).hexdigest())
    print("PROMOTE", promote)


if __name__ == "__main__":
    main()
