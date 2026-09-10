from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import tarfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", required=True)
    ap.add_argument("--field", required=True)
    ap.add_argument("--generated", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    oracle = json.loads(pathlib.Path(args.oracle).read_text())
    field = json.loads(pathlib.Path(args.field).read_text())
    selected = field["summary"]["selected"]
    public = field["summary"]["public_control"]
    direct = selected["per_opponent"].get("public_control", {}).get("bt", 0.5)
    promote = (
        bool(oracle.get("promote_to_fresh_field"))
        and selected["errors"] == 0
        and public["errors"] == 0
        and selected["bt_score"] >= public["bt_score"] + 0.01
        and selected["worst_opponent_bt"] >= public["worst_opponent_bt"] - 0.05
        and direct >= 0.5
    )
    report = {
        "promote": promote,
        "selected_bt": selected["bt_score"],
        "public_bt": public["bt_score"],
        "bt_gain": selected["bt_score"] - public["bt_score"],
        "selected_worst": selected["worst_opponent_bt"],
        "public_worst": public["worst_opponent_bt"],
        "direct_bt_vs_public": direct,
        "oracle_promote": oracle.get("promote_to_fresh_field"),
        "selected_params": oracle.get("best_grid"),
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    generated = pathlib.Path(args.generated)
    for src, name in [
        (generated / "public_control", "Kaggriculture_V90_1_ADAPTIVE_ROUTE_V2_PUBLIC_CONTROL.tar.gz"),
        (generated / "selected", "Kaggriculture_V90_2_SHOPFORGE_RECALIBRATED.tar.gz"),
    ]:
        dest = out.parent.parent / name
        with tarfile.open(dest, "w:gz") as tf:
            tf.add(src / "main.py", arcname="main.py")
            tf.add(src / "agent.so", arcname="agent.so")
        report[name] = {"sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "bytes": dest.stat().st_size}
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
