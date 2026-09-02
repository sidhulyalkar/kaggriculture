from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from typing import Any

COMPETITION = "kaggriculture"
EPISODE_INDEX = "kaggle/kaggriculture-episodes-index"


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _csv_rows(text: str) -> list[dict[str, str]]:
    text = text.lstrip("\ufeff").strip()
    if not text:
        return []
    return [dict(row) for row in csv.DictReader(text.splitlines())]


def _norm_key(key: str) -> str:
    return "".join(ch.lower() for ch in key if ch.isalnum())


def _first(row: dict[str, Any], *names: str) -> Any:
    by_norm = {_norm_key(str(k)): v for k, v in row.items()}
    for name in names:
        key = _norm_key(name)
        if key in by_norm and by_norm[key] not in (None, ""):
            return by_norm[key]
    return None


def _credentials_present() -> bool:
    if os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY"):
        return True
    home = Path.home() / ".kaggle"
    return (home / "access_token").exists() or (home / "kaggle.json").exists()


def _run_cli(args: list[str], *, timeout: int = 120) -> dict[str, Any]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"ok": False, "error": "kaggle CLI not installed", "args": args}
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": f"timeout after {timeout}s",
            "args": args,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "args": args,
    }


def _resolve_download(result: str | Path | None, dest: Path, name: str) -> Path:
    if result:
        p = Path(result)
        if p.is_file():
            return p
        candidate = p / name
        if candidate.exists():
            return candidate
        hits = sorted(p.rglob(Path(name).name))
        if hits:
            return hits[0]
    candidate = dest / name
    if candidate.exists():
        return candidate
    hits = sorted(dest.rglob(Path(name).name))
    if hits:
        return hits[0]
    raise FileNotFoundError(f"downloaded file not found: {name}")


def _dataset_file(handle: str, path: str, dest: Path, *, refresh: bool) -> Path:
    import kagglehub

    dest.mkdir(parents=True, exist_ok=True)
    existing = dest / path
    if existing.exists() and not refresh:
        return existing
    if refresh and existing.exists():
        existing.unlink()
    try:
        got = kagglehub.dataset_download(handle, path=path, output_dir=str(dest), force_download=refresh)
    except FileExistsError:
        return _resolve_download(None, dest, path)
    return _resolve_download(got, dest, path)


def _select_manifest_rows(rows: list[dict[str, str]], top_n: int, diverse_n: int) -> list[tuple[dict[str, str], str]]:
    ranked = sorted(rows, key=lambda r: float(r.get("avg_score", 0) or 0), reverse=True)
    selected: list[tuple[dict[str, str], str]] = []
    seen: set[str] = set()
    for row in ranked[: max(0, top_n)]:
        eid = str(row.get("episode_id", ""))
        if eid and eid not in seen:
            selected.append((row, "top"))
            seen.add(eid)

    # Diversify only within the high-Elo band. This avoids spending bandwidth on
    # clearly weak episodes while reducing duplicate-team / duplicate-route bias.
    band = ranked[: max(top_n + diverse_n, min(len(ranked), max(24, len(ranked) // 4)))]
    remaining = [r for r in band if str(r.get("episode_id", "")) not in seen]
    if diverse_n > 0 and remaining:
        for i in range(diverse_n):
            pos = round(i * (len(remaining) - 1) / max(1, diverse_n - 1))
            row = remaining[pos]
            eid = str(row.get("episode_id", ""))
            if eid and eid not in seen:
                selected.append((row, "upper_band_diverse"))
                seen.add(eid)
    return selected


def _obs(state: dict[str, Any]) -> dict[str, Any]:
    value = state.get("observation", {}) if isinstance(state, dict) else {}
    return value if isinstance(value, dict) else {}


def _farm_comp(farm: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            key = tile.get("animal") or tile.get("crop") or tile.get("kind")
            if key:
                counts[str(key)] = counts.get(str(key), 0) + 1
    return counts


def episode_fingerprint(rep: dict[str, Any]) -> dict[str, Any]:
    steps = rep.get("steps", []) or []
    info = rep.get("info", {}) or {}
    names = list(info.get("TeamNames") or ["p0", "p1"])
    rewards = rep.get("rewards")
    if not isinstance(rewards, list) or len(rewards) < 2:
        try:
            rewards = [steps[-1][0].get("reward"), steps[-1][1].get("reward")]
        except Exception:
            rewards = [None, None]
    numeric = []
    for value in rewards[:2]:
        try:
            numeric.append(float(value or 0))
        except Exception:
            numeric.append(0.0)
    winner = 0 if numeric[0] >= numeric[1] else 1

    shop_sequence: list[str] = []
    action_counts: dict[str, int] = {}
    market_counts: dict[str, int] = {}
    if steps:
        for turn in steps:
            if winner >= len(turn) or not isinstance(turn[winner], dict):
                continue
            state = turn[winner]
            ob = _obs(state)
            shops = (((ob.get("town") or {}).get("unlocked_shops")) or [])
            for shop in shops:
                shop = str(shop)
                if shop not in shop_sequence:
                    shop_sequence.append(shop)
            act = state.get("action")
            if not isinstance(act, dict):
                continue
            for op in [act.get("farmer")] + list(act.get("hands") or []):
                if isinstance(op, (list, tuple)) and op:
                    key = str(op[0])
                    action_counts[key] = action_counts.get(key, 0) + 1
            for op in act.get("market") or []:
                if isinstance(op, (list, tuple)) and op:
                    key = str(op[0])
                    market_counts[key] = market_counts.get(key, 0) + 1

    final_comp: dict[str, int] = {}
    final_hands = 0
    final_quads = 0
    if steps:
        for seat in range(min(2, len(steps[-1]))):
            ob = _obs(steps[-1][seat])
            farms = ob.get("farms") or []
            if winner < len(farms) and isinstance(farms[winner], dict):
                farm = farms[winner]
                final_comp = _farm_comp(farm)
                final_hands = len(farm.get("hands") or [])
                final_quads = len(farm.get("unlocked_quadrants") or [])
                break

    signature = {
        "shop_prefix": shop_sequence[:3],
        "final_hands": final_hands,
        "final_quads": final_quads,
        "final_comp": dict(sorted(final_comp.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "market_counts": dict(sorted(market_counts.items())),
    }
    sig_text = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    return {
        "episode_id": str(info.get("EpisodeId", rep.get("id", "unknown"))),
        "date": rep.get("_meta_date"),
        "avg_score": rep.get("_meta_avg_score"),
        "seed": info.get("seed", (rep.get("configuration") or {}).get("seed")),
        "teams": names,
        "winner_seat": winner,
        "winner_team": names[winner] if winner < len(names) else f"p{winner}",
        "winner_cash": numeric[winner],
        "loser_cash": numeric[1 - winner],
        "signature": signature,
        "signature_sha256": sha256(sig_text.encode()).hexdigest(),
    }


def mirror_public_meta(
    root: Path,
    *,
    days: int = 3,
    top_per_day: int = 8,
    diverse_per_day: int = 4,
    refresh_manifests: bool = True,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    index = _dataset_file(EPISODE_INDEX, "manifest.csv", root / "episode_index", refresh=refresh_manifests)
    rows = list(csv.DictReader(index.open(encoding="utf-8")))
    dated = sorted((r for r in rows if r.get("date")), key=lambda r: r["date"], reverse=True)[: max(1, days)]
    report: dict[str, Any] = {"index_sha256": _sha256_file(index), "days": [], "fingerprints": []}

    for day in dated:
        date = day["date"]
        handle = f"kaggle/kaggriculture-episodes-{date}"
        day_root = root / "days" / date
        try:
            manifest = _dataset_file(handle, "manifest.csv", day_root, refresh=refresh_manifests)
            mrows = list(csv.DictReader(manifest.open(encoding="utf-8")))
        except Exception as exc:
            report["days"].append({"date": date, "status": "manifest_failed", "error": f"{type(exc).__name__}: {exc}"})
            continue

        picked = _select_manifest_rows(mrows, top_per_day, diverse_per_day)
        day_row: dict[str, Any] = {
            "date": date,
            "handle": handle,
            "manifest_sha256": _sha256_file(manifest),
            "manifest_rows": len(mrows),
            "episodes": [],
        }
        for row, reason in picked:
            eid = str(row.get("episode_id", "")).strip()
            if not eid:
                continue
            try:
                fp = _dataset_file(handle, f"{eid}.json", day_root / "episodes", refresh=False)
                rep = json.loads(fp.read_text(encoding="utf-8"))
                rep["_meta_date"] = date
                rep["_meta_avg_score"] = float(row.get("avg_score", 0) or 0)
                fingerprint = episode_fingerprint(rep)
                report["fingerprints"].append(fingerprint)
                day_row["episodes"].append({
                    "episode_id": eid,
                    "avg_score": float(row.get("avg_score", 0) or 0),
                    "selection_reason": reason,
                    "path": str(fp),
                    "bytes": fp.stat().st_size,
                    "sha256": _sha256_file(fp),
                    "signature_sha256": fingerprint["signature_sha256"],
                    "winner_team": fingerprint["winner_team"],
                })
            except Exception as exc:
                day_row["episodes"].append({
                    "episode_id": eid,
                    "selection_reason": reason,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                })
        day_row["status"] = "ready" if any("sha256" in x for x in day_row["episodes"]) else "empty"
        report["days"].append(day_row)

    clusters: dict[str, dict[str, Any]] = {}
    for row in report["fingerprints"]:
        key = row["signature_sha256"]
        entry = clusters.setdefault(key, {"count": 0, "teams": {}, "avg_scores": [], "signature": row["signature"]})
        entry["count"] += 1
        team = row["winner_team"]
        entry["teams"][team] = entry["teams"].get(team, 0) + 1
        if row.get("avg_score") is not None:
            entry["avg_scores"].append(float(row["avg_score"]))
    cluster_rows = []
    for key, entry in clusters.items():
        scores = entry.pop("avg_scores")
        entry["mean_avg_score"] = sum(scores) / len(scores) if scores else None
        cluster_rows.append({"signature_sha256": key, **entry})
    cluster_rows.sort(key=lambda r: (r["count"], r["mean_avg_score"] or 0), reverse=True)
    report["clusters"] = cluster_rows
    _atomic_json(root / "PUBLIC_META.json", report)
    return report


def _write_cli_capture(root: Path, name: str, result: dict[str, Any]) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    out = root / f"{name}.stdout.txt"
    err = root / f"{name}.stderr.txt"
    out.write_text(result.get("stdout", ""), encoding="utf-8")
    err.write_text(result.get("stderr", ""), encoding="utf-8")
    return {
        "ok": bool(result.get("ok")),
        "returncode": result.get("returncode"),
        "stdout_path": str(out),
        "stderr_path": str(err),
        "stdout_sha256": _sha256_file(out),
        "error": result.get("error"),
    }


def _submission_id(row: dict[str, Any]) -> int | None:
    value = _first(row, "id", "submission_id", "submissionId", "ref", "submission_ref")
    try:
        return int(str(value))
    except Exception:
        return None


def mirror_authenticated_meta(
    root: Path,
    *,
    competition: str = COMPETITION,
    submission_limit: int = 8,
    episodes_per_submission: int = 12,
    download_replays: bool = True,
    top_team_limit: int = 12,
) -> dict[str, Any]:
    report: dict[str, Any] = {"available": _credentials_present(), "competition": competition, "commands": {}, "submissions": []}
    root.mkdir(parents=True, exist_ok=True)
    if not report["available"]:
        report["reason"] = "No KAGGLE_API_TOKEN / Kaggle credential file detected. Public mirror still works."
        _atomic_json(root / "AUTH_META.json", report)
        return report

    commands = {
        "submission_limits": ["kaggle", "competitions", "submission-limits", competition, "--json", "-q"],
        "submissions": ["kaggle", "competitions", "submissions", competition, "-v", "-q"],
        "leaderboard": ["kaggle", "competitions", "leaderboard", competition, "--show", "-v", "-q", "--page-size", "100"],
        "topics_recent": ["kaggle", "competitions", "topics", "list", competition, "--sort-by", "recent", "-v", "-q"],
        "topics_top": ["kaggle", "competitions", "topics", "list", competition, "--sort-by", "top", "-v", "-q"],
    }
    raw: dict[str, dict[str, Any]] = {}
    for name, args in commands.items():
        result = _run_cli(args, timeout=120)
        raw[name] = result
        report["commands"][name] = _write_cli_capture(root / "captures", name, result)

    if raw["submission_limits"].get("ok"):
        try:
            report["submission_limits"] = json.loads(raw["submission_limits"]["stdout"])
        except Exception:
            report["submission_limits_raw"] = raw["submission_limits"]["stdout"].strip()

    submission_rows = _csv_rows(raw["submissions"].get("stdout", "")) if raw["submissions"].get("ok") else []
    report["submission_rows"] = submission_rows
    for row in submission_rows[: max(0, submission_limit)]:
        sid = _submission_id(row)
        item: dict[str, Any] = {"row": row, "submission_id": sid}
        if sid is None:
            item["status"] = "unresolved_submission_id"
            report["submissions"].append(item)
            continue
        episodes = _run_cli(["kaggle", "competitions", "episodes", str(sid), "-v", "-q"], timeout=120)
        item["episodes_capture"] = _write_cli_capture(root / "captures", f"episodes_{sid}", episodes)
        erows = _csv_rows(episodes.get("stdout", "")) if episodes.get("ok") else []
        item["episode_rows"] = erows
        if download_replays:
            item["replays"] = []
            for erow in erows[: max(0, episodes_per_submission)]:
                value = _first(erow, "episode_id", "episodeId", "id")
                try:
                    eid = int(str(value))
                except Exception:
                    continue
                dest = root / "own_replays" / str(sid) / str(eid)
                if any(dest.glob("*")):
                    item["replays"].append({"episode_id": eid, "status": "cached", "path": str(dest)})
                    continue
                dest.mkdir(parents=True, exist_ok=True)
                result = _run_cli(["kaggle", "competitions", "replay", str(eid), "-p", str(dest), "-q"], timeout=180)
                paths = [p for p in dest.rglob("*") if p.is_file()]
                item["replays"].append({
                    "episode_id": eid,
                    "ok": result.get("ok", False),
                    "files": [{"path": str(p), "bytes": p.stat().st_size, "sha256": _sha256_file(p)} for p in paths],
                    "error": result.get("stderr", "")[-500:] if not result.get("ok") else None,
                })
        report["submissions"].append(item)

    leaderboard_rows = _csv_rows(raw["leaderboard"].get("stdout", "")) if raw["leaderboard"].get("ok") else []
    report["leaderboard_rows"] = leaderboard_rows
    team_ids: list[int] = []
    for row in leaderboard_rows:
        value = _first(row, "team_id", "teamId", "id")
        try:
            tid = int(str(value))
        except Exception:
            continue
        if tid not in team_ids:
            team_ids.append(tid)
        if len(team_ids) >= top_team_limit:
            break
    report["top_team_submissions"] = []
    for tid in team_ids:
        result = _run_cli(["kaggle", "competitions", "team-submissions", str(tid), "-v", "-q"], timeout=120)
        capture = _write_cli_capture(root / "captures", f"team_submissions_{tid}", result)
        report["top_team_submissions"].append({
            "team_id": tid,
            "capture": capture,
            "rows": _csv_rows(result.get("stdout", "")) if result.get("ok") else [],
        })

    _atomic_json(root / "AUTH_META.json", report)
    return report


def mirror_all(
    output_root: str | Path,
    *,
    days: int = 3,
    top_per_day: int = 8,
    diverse_per_day: int = 4,
    refresh_manifests: bool = True,
    include_authenticated: bool = True,
) -> dict[str, Any]:
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    public = mirror_public_meta(
        root / "public",
        days=days,
        top_per_day=top_per_day,
        diverse_per_day=diverse_per_day,
        refresh_manifests=refresh_manifests,
    )
    auth = mirror_authenticated_meta(root / "authenticated") if include_authenticated else {"available": False, "reason": "disabled"}
    manifest = {
        "version": 1,
        "competition": COMPETITION,
        "public": {
            "days": [d.get("date") for d in public.get("days", [])],
            "episode_count": sum(1 for d in public.get("days", []) for e in d.get("episodes", []) if e.get("sha256")),
            "fingerprint_count": len(public.get("fingerprints", [])),
            "cluster_count": len(public.get("clusters", [])),
            "path": str(root / "public" / "PUBLIC_META.json"),
        },
        "authenticated": {
            "available": bool(auth.get("available")),
            "submission_count": len(auth.get("submissions", [])),
            "path": str(root / "authenticated" / "AUTH_META.json"),
            "submission_limits": auth.get("submission_limits"),
        },
    }
    _atomic_json(root / "MIRROR_MANIFEST.json", manifest)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Resumable Kaggriculture meta/submission mirror")
    ap.add_argument("--output-root", default="artifacts/kaggle_mirror")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--top-per-day", type=int, default=8)
    ap.add_argument("--diverse-per-day", type=int, default=4)
    ap.add_argument("--no-refresh-manifests", action="store_true")
    ap.add_argument("--public-only", action="store_true")
    args = ap.parse_args()
    result = mirror_all(
        args.output_root,
        days=args.days,
        top_per_day=args.top_per_day,
        diverse_per_day=args.diverse_per_day,
        refresh_manifests=not args.no_refresh_manifests,
        include_authenticated=not args.public_only,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
