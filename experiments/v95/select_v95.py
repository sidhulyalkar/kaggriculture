from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import tarfile


def sign(m: float) -> float:
    return 1.0 if m > 0 else 0.5 if m == 0 else 0.0


def paired(rows, candidate: str, control: str) -> dict:
    by = {(r["candidate"], r["opponent"], r["seed"], r["seat"], r["clock_fault"]): r for r in rows}
    rescued = sacrificed = margin_better = margin_worse = 0
    delta = []
    for r in rows:
        if r["candidate"] != candidate or r["clock_fault"]:
            continue
        c = by.get((control, r["opponent"], r["seed"], r["seat"], False))
        if c is None:
            continue
        rs, cs = sign(r["margin"]), sign(c["margin"])
        if cs < 1 and rs == 1:
            rescued += 1
        if cs == 1 and rs < 1:
            sacrificed += 1
        d = float(r["margin"]) - float(c["margin"])
        delta.append(d)
        margin_better += d > 0
        margin_worse += d < 0
    return {
        "rescued_control_nonwins": rescued,
        "sacrificed_control_wins": sacrificed,
        "mean_margin_delta": sum(delta) / len(delta) if delta else 0.0,
        "margin_better": margin_better,
        "margin_worse": margin_worse,
        "n": len(delta),
    }


def load_rows(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def package(main: pathlib.Path, out: pathlib.Path) -> None:
    with tarfile.open(out, "w:gz") as tf:
        tf.add(main, arcname="main.py")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discovery", required=True)
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--generated", required=True)
    ap.add_argument("--packages", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    dp = pathlib.Path(args.discovery)
    hp = pathlib.Path(args.holdout)
    disc = json.loads(dp.read_text())["summary"]
    hold = json.loads(hp.read_text())["summary"]
    drows = load_rows(dp.with_suffix(".jsonl"))
    hrows = load_rows(hp.with_suffix(".jsonl"))
    control = "smart_t54"

    names = sorted(n for n in hold if n.startswith("smart_t"))
    audit = {}
    for name in names:
        audit[name] = {
            "discovery": disc[name],
            "holdout": hold[name],
            "paired_discovery_vs_t54": paired(drows, name, control) if name != control else None,
            "paired_holdout_vs_t54": paired(hrows, name, control) if name != control else None,
        }

    eligible = []
    for name in names:
        if name == control:
            eligible.append(name)
            continue
        d = audit[name]
        pd = d["paired_discovery_vs_t54"]
        ph = d["paired_holdout_vs_t54"]
        if d["discovery"]["bt"] < audit[control]["discovery"]["bt"]:
            continue
        if d["holdout"]["bt"] < audit[control]["holdout"]["bt"]:
            continue
        if ph["sacrificed_control_wins"] > ph["rescued_control_nonwins"]:
            continue
        if pd["sacrificed_control_wins"] > pd["rescued_control_nonwins"]:
            continue
        eligible.append(name)

    winner = max(
        eligible,
        key=lambda n: (
            min(audit[n]["discovery"]["bt"], audit[n]["holdout"]["bt"]),
            audit[n]["holdout"]["worst_opponent_bt"],
            audit[n]["holdout"]["mean_margin"],
        ),
    )
    improved = winner != control

    packages = pathlib.Path(args.packages)
    packages.mkdir(parents=True, exist_ok=True)
    winner_out = packages / "Kaggriculture_V95_3_SMARTLAB_CAUSAL_LATE_ROUTER.tar.gz"
    package(pathlib.Path(args.generated) / winner / "main.py", winner_out)

    report = {
        "control": control,
        "winner": winner,
        "late_router_improved": improved,
        "eligible": eligible,
        "smart_audit": audit,
        "live_calibration_controls": {
            "v85_exact": {"discovery": disc.get("v85_exact"), "holdout": hold.get("v85_exact")},
            "smart_t54": {"discovery": disc.get("smart_t54"), "holdout": hold.get("smart_t54")},
            "sparse_v43_exact": {"discovery": disc.get("sparse_v43_exact"), "holdout": hold.get("sparse_v43_exact")},
        },
    }
    pathlib.Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
