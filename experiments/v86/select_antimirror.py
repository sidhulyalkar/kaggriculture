from __future__ import annotations

import json
import pathlib
import shutil
import tarfile
import hashlib

ROOT = pathlib.Path("experiments/v86")
MODES = (
    "suppress_226",
    "force_226",
    "suppress_360",
    "force_360",
    "suppress_433",
    "force_433",
)


def load_summary(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())["summary"]


def select() -> str:
    rows = []
    for mode in MODES:
        name = f"v86_{mode}"
        d = load_summary(ROOT / "results" / "mirror" / mode / "field_results.json")
        s = d[name]
        per = s.get("per_opponent", {})
        wr_shape = per.get("shape_current", {}).get("win_rate", 0.0)
        wr_math = per.get("farming_math", {}).get("win_rate", 0.0)
        m_shape = per.get("shape_current", {}).get("margin_mean", 0.0)
        m_math = per.get("farming_math", {}).get("margin_mean", 0.0)
        direct = 0.5 * (wr_shape + wr_math)
        margin = 0.5 * (m_shape + m_math)
        rows.append({"mode": mode, "direct_win_rate": direct, "direct_margin": margin,
                     "wr_shape": wr_shape, "wr_math": wr_math, "errors": s.get("errors", 999)})
    rows.sort(key=lambda r: (r["errors"] == 0, r["direct_win_rate"], r["direct_margin"]), reverse=True)
    (ROOT / "results" / "mirror_ranking.json").write_text(json.dumps(rows, indent=2) + "\n")
    best = rows[0]["mode"]
    (ROOT / "results" / "selected.txt").write_text(best + "\n")
    print(json.dumps(rows, indent=2))
    print("SELECTED", best)
    return best


def promote() -> None:
    mode = (ROOT / "results" / "selected.txt").read_text().strip()
    name = f"v86_{mode}"
    d = load_summary(ROOT / "results" / "holdout" / "field_results.json")
    c = d[name]
    b = d["shape_current"]
    per = c.get("per_opponent", {})
    wr_shape = per.get("shape_current", {}).get("win_rate", 0.0)
    wr_math = per.get("farming_math", {}).get("win_rate", 0.0)
    direct = 0.5 * (wr_shape + wr_math)

    # Two-slot portfolio gate: flip the dominant mirror while preserving Shape's
    # non-mirror field quality and downside.  Candidate can trade a tiny amount of
    # aggregate WR for a large mirror edge, but not more than 3 percentage points.
    decision = (
        c.get("errors", 999) == 0
        and direct >= 0.55
        and c.get("win_rate", 0.0) >= b.get("win_rate", 0.0) - 0.03
        and c.get("margin_cvar10", -1e18) >= b.get("margin_cvar10", -1e18) - 2500
    )
    report = {
        "selected": mode,
        "candidate": c,
        "base_shape": b,
        "direct_shape_math_win_rate": direct,
        "promote": decision,
    }
    (ROOT / "results" / "promotion.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    sub = ROOT / "submission"
    sub.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "generated" / f"{name}.py", sub / "main.py")
    tar = ROOT / f"Kaggriculture_V86_SHAPE_ANTIMIRROR_{mode.upper()}.tar.gz"
    with tarfile.open(tar, "w:gz") as tf:
        tf.add(sub / "main.py", arcname="main.py")
    print("MAIN_SHA", hashlib.sha256((sub / "main.py").read_bytes()).hexdigest())
    print("TAR_SHA", hashlib.sha256(tar.read_bytes()).hexdigest())
    print("PROMOTE", decision)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in {"select", "promote"}:
        raise SystemExit("usage: select_antimirror.py select|promote")
    select() if sys.argv[1] == "select" else promote()
