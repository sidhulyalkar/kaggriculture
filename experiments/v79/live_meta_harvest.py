from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"
REPLAY = "https://www.kaggle.com/competitions/episodes/{eid}/replay.json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

# Top-25 team ids from the frozen 2026-09-03 public leaderboard snapshot in
# sota1111/erl-kaggriculture.  We combine these with the freshest public
# submissions discovered live so the harvest is neither purely historical nor
# purely recency-biased.
SEP3_TOP25 = [
    16623608, 16721382, 16714457, 16633790, 16711752,
    16698308, 16768043, 16622898, 16665809, 16672315,
    16731686, 16779388, 16774712, 16756764, 16713262,
    16655098, 16659920, 16729280, 16780279, 16654266,
    16728071, 16635029, 16785523, 16749520, 16731186,
]


def post_json(url: str, body: dict, timeout=90):
    raw = json.dumps(body).encode()
    req = Request(url, data=raw, headers=HEADERS, method="POST")
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get_json(url: str, timeout=300):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def iso_key(x):
    return str(x or "")


def fingerprint(actions, end):
    blob = "\n".join(json.dumps(a or {}, sort_keys=True, separators=(",", ":")) for a in actions[:end])
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def seat_for_team(replay, team_id):
    info = replay.get("info") or {}
    # Replay does not always expose team ids in info, so caller supplies the seat
    # from ListEpisodes when possible.  This helper is only a fallback.
    tids = info.get("TeamIds") or info.get("teamIds")
    if isinstance(tids, list):
        for i, x in enumerate(tids):
            if int(x) == int(team_id):
                return i
    return None


def extract_actions(replay, seat):
    out = []
    for step in replay.get("steps") or []:
        if isinstance(step, list) and seat < len(step) and isinstance(step[seat], dict):
            out.append(step[seat].get("action") or {})
        else:
            out.append({})
    return out


def public_state_signature(replay, seat, cp):
    steps = replay.get("steps") or []
    if cp >= len(steps) or not isinstance(steps[cp], list) or seat >= len(steps[cp]):
        return {}
    obs = (steps[cp][seat] or {}).get("observation") or {}
    farms = obs.get("farms") or []
    farm = farms[seat] if seat < len(farms) else {}
    tiles = farm.get("tiles") or []
    values = Counter()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("crop", "kind") and isinstance(v, str):
                    values[v] += 1
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(tiles)
    town = obs.get("town") or {}
    shops = town.get("unlocked_shops") or []
    return {
        "money": farm.get("money"),
        "hands": len(farm.get("hands") or []),
        "land": len(farm.get("unlocked_quadrants") or []),
        "farmer": farm.get("farmer"),
        "tile_values": dict(values),
        "shops": list(shops),
        "market_prices": ((obs.get("market") or {}).get("prices") or {}),
    }


def replay_summary(eid, team_id, seat):
    replay = get_json(REPLAY.format(eid=eid))
    actions = extract_actions(replay, seat)
    rewards = replay.get("rewards") or [None, None]
    first_nonpass = None
    for i, a in enumerate(actions):
        if a and a != {"farmer": ["PASS"], "hands": [], "market": []}:
            first_nonpass = i
            break
    return {
        "episode_id": eid,
        "seat": seat,
        "reward": rewards[seat] if seat < len(rewards) else None,
        "opponent_reward": rewards[1-seat] if len(rewards) == 2 else None,
        "first_nonpass": first_nonpass,
        "h72": fingerprint(actions, 72),
        "h120": fingerprint(actions, 120),
        "h200": fingerprint(actions, 200),
        "h360": fingerprint(actions, 360),
        "full": fingerprint(actions, len(actions)),
        "cp72": public_state_signature(replay, seat, 72),
        "cp120": public_state_signature(replay, seat, 120),
        "cp200": public_state_signature(replay, seat, 200),
        "cp360": public_state_signature(replay, seat, 360),
        "engine": replay.get("module_version"),
    }


def completed_rows(d, team_id, submission_id):
    rows = []
    for e in d.get("episodes") or []:
        if e.get("state") != "COMPLETED":
            continue
        ags = e.get("agents") or []
        for seat, a in enumerate(ags):
            if int(a.get("teamId") or -1) == int(team_id) and int(a.get("submissionId") or -1) == int(submission_id):
                opp = ags[1-seat] if len(ags) == 2 else {}
                rows.append({
                    "episode_id": int(e["id"]),
                    "create_time": e.get("createTime"),
                    "seat": seat,
                    "reward": a.get("reward"),
                    "updated_score": a.get("updatedScore"),
                    "opponent_team_id": opp.get("teamId"),
                    "opponent_submission_id": opp.get("submissionId"),
                    "opponent_reward": opp.get("reward"),
                    "opponent_score": opp.get("updatedScore"),
                })
    return sorted(rows, key=lambda r: iso_key(r["create_time"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-submission", type=int, default=55260568)
    ap.add_argument("--budget", type=int, default=36)
    ap.add_argument("--fresh", type=int, default=10)
    ap.add_argument("--replay-top", type=int, default=6)
    ap.add_argument("--replays-per-team", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=2.6)
    ap.add_argument("--out", default="experiments/v79/results/live_meta")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    seed = post_json(API, {"submissionId": args.seed_submission})
    calls = 1
    teams = seed.get("teams") or []
    by_team = {int(t["id"]): t for t in teams if t.get("id") is not None and t.get("publicLeaderboardSubmissionId")}

    freshest = sorted(by_team.values(), key=lambda t: iso_key(t.get("lastSubmissionDate")), reverse=True)[:args.fresh]
    selected_ids = []
    for tid in SEP3_TOP25 + [int(t["id"]) for t in freshest]:
        if tid in by_team and tid not in selected_ids:
            selected_ids.append(tid)
    selected_ids = selected_ids[: max(0, args.budget - 1)]

    rows = []
    failures = []
    for i, tid in enumerate(selected_ids, 1):
        t = by_team[tid]
        sub = int(t["publicLeaderboardSubmissionId"])
        try:
            time.sleep(args.sleep)
            d = post_json(API, {"submissionId": sub})
            calls += 1
            eps = completed_rows(d, tid, sub)
            last = eps[-1] if eps else None
            rows.append({
                "team_id": tid,
                "team_name": t.get("teamName") or t.get("name"),
                "submission_id": sub,
                "last_submission_date": t.get("lastSubmissionDate"),
                "latest_score": (last or {}).get("updated_score"),
                "latest_episode": (last or {}).get("episode_id"),
                "episodes_current_submission": len(eps),
                "recent": eps[-6:],
            })
            print(f"META {i:02d}/{len(selected_ids)} team={tid} sub={sub} score={(last or {}).get('updated_score')} eps={len(eps)}")
        except Exception as exc:
            failures.append({"team_id": tid, "submission_id": sub, "error": repr(exc)})
            print("FAIL", tid, sub, repr(exc))

    ranked = sorted(
        [r for r in rows if isinstance(r.get("latest_score"), (int, float))],
        key=lambda r: float(r["latest_score"]), reverse=True,
    )
    print("\nLIVE SCORE SNAPSHOT")
    for i, r in enumerate(ranked[:20], 1):
        print(i, r["team_name"], r["latest_score"], r["submission_id"], r["latest_episode"])

    replay_rows = []
    for r in ranked[:args.replay_top]:
        recent = r.get("recent") or []
        for ep in recent[-args.replays_per_team:]:
            try:
                time.sleep(0.8)
                s = replay_summary(ep["episode_id"], r["team_id"], ep["seat"])
                s.update({
                    "team_id": r["team_id"],
                    "team_name": r["team_name"],
                    "submission_id": r["submission_id"],
                    "updated_score": ep["updated_score"],
                    "create_time": ep["create_time"],
                })
                replay_rows.append(s)
                print("REPLAY", r["team_name"], ep["episode_id"], s["h120"], s["full"])
            except Exception as exc:
                failures.append({"episode_id": ep["episode_id"], "error": repr(exc)})
                print("REPLAY_FAIL", ep["episode_id"], repr(exc))

    clusters = {}
    for horizon in ("h72", "h120", "h200", "h360", "full"):
        g = defaultdict(list)
        for r in replay_rows:
            g[r[horizon]].append({"team": r["team_name"], "episode": r["episode_id"]})
        clusters[horizon] = [
            {"fingerprint": fp, "n": len(xs), "members": xs}
            for fp, xs in sorted(g.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ]

    payload = {
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "seed_submission": args.seed_submission,
        "api_calls": calls,
        "team_table_size": len(teams),
        "queried_team_count": len(selected_ids),
        "ranked": ranked,
        "replay_summaries": replay_rows,
        "lineage_clusters": clusters,
        "failures": failures,
    }
    (out / "live_meta.json").write_text(json.dumps(payload, indent=2))
    (out / "live_scores.json").write_text(json.dumps(ranked, indent=2))
    (out / "lineage_clusters.json").write_text(json.dumps(clusters, indent=2))


if __name__ == "__main__":
    main()
