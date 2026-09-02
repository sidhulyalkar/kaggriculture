from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
from typing import Any

from swarm.providers import NvidiaNimProvider

ROUTES = {
    "10c4s_3q",
    "8c6s_3q",
    "6c8s_3q",
    "6c12s_4q_first_yarn",
    "6c12s_4q_second_yarn",
}
PARAMETERS = {
    "_PREEMPT_FRACTION": (0.0, 3.0),
    "_PREEMPT_MAX_BATCH": (1, 40),
    "_PREEMPT_MIN_PRICE_RATIO": (0.0, 1.5),
    "_PREEMPT_MIN_FUTURE_QUANTITY": (1, 12),
    "_PREEMPT_START": (48, 300),
    "_PREEMPT_STOP": (400, 718),
    "_ADAPT_MIN_EVIDENCE": (0.5, 6.0),
}
ROLES = {
    "adversary": "Find one current-meta counter that can improve win probability against the strongest opponent family without rewriting the controller.",
    "mechanism": "Identify one causal route/shop or market-timing change supported by the measured family-wise results.",
    "auditor": "Look for evaluator/replay leakage and propose only a mutation that remains meaningful under executable cross-play.",
}


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
        start = min(starts, default=-1)
        if start < 0:
            raise
        for end in range(len(text), start, -1):
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                continue
        raise


def _validate_one(raw: Any, role: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("mutation_type", "")).lower()
    hypothesis = str(raw.get("hypothesis", ""))[:800]
    evidence = str(raw.get("evidence", ""))[:800]
    if kind == "route":
        prefix = raw.get("prefix")
        route = str(raw.get("route", ""))
        if not isinstance(prefix, list) or not (1 <= len(prefix) <= 3) or not all(isinstance(x, str) and x for x in prefix):
            return None
        if route not in ROUTES:
            return None
        return {"role": role, "mutation_type": "route", "prefix": prefix, "route": route, "hypothesis": hypothesis, "evidence": evidence}
    if kind == "parameter":
        field = str(raw.get("field", ""))
        if field not in PARAMETERS:
            return None
        try:
            value = float(raw.get("value"))
        except Exception:
            return None
        lo, hi = PARAMETERS[field]
        if not (float(lo) <= value <= float(hi)):
            return None
        if isinstance(lo, int) and isinstance(hi, int):
            value = int(round(value))
        return {"role": role, "mutation_type": "parameter", "field": field, "value": value, "hypothesis": hypothesis, "evidence": evidence}
    return None


def _compact_packet(slate: dict[str, Any], public_meta: dict[str, Any], auth_meta: dict[str, Any] | None) -> dict[str, Any]:
    ranking = []
    for row in slate.get("ranking", [])[:10]:
        ranking.append({k: row.get(k) for k in (
            "candidate", "family", "replay_win_score", "replay_delta_vs_base", "static_win_score",
            "static_delta_vs_base", "worst_static_family_score", "composite", "delta_composite_vs_base", "recommendation"
        )})
    clusters = []
    for row in public_meta.get("clusters", [])[:12]:
        clusters.append({k: row.get(k) for k in ("count", "teams", "mean_avg_score", "signature")})
    auth_summary = None
    if auth_meta:
        auth_summary = {
            "submission_limits": auth_meta.get("submission_limits"),
            "latest_submissions": [x.get("row") for x in auth_meta.get("submissions", [])[:8]],
        }
    return {
        "parent": slate.get("parent"),
        "ranking": ranking,
        "learned_maps": slate.get("learned_maps"),
        "static_opponents": slate.get("static_opponents"),
        "clusters": clusters,
        "authenticated": auth_summary,
    }


def run(slate_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    slate_path = Path(slate_path)
    slate = json.loads(slate_path.read_text(encoding="utf-8"))
    mirror = slate.get("mirror") or {}
    public_path = Path(str((mirror.get("public") or {}).get("path", "")))
    auth_path = Path(str((mirror.get("authenticated") or {}).get("path", "")))
    if not public_path.exists():
        raise FileNotFoundError(f"public mirror evidence missing: {public_path}")
    public_meta = json.loads(public_path.read_text(encoding="utf-8"))
    auth_meta = json.loads(auth_path.read_text(encoding="utf-8")) if auth_path.exists() else None
    packet = _compact_packet(slate, public_meta, auth_meta)

    if not os.environ.get("NVIDIA_API_KEY"):
        result = {"status": "skipped", "reason": "NVIDIA_API_KEY not set", "proposals": []}
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    system = (
        "You are a Kaggriculture experiment scientist. Optimize rating win probability, not cash margin. "
        "Return JSON only. You may propose exactly ONE sparse mutation. Allowed mutation types are: "
        "route: {mutation_type:'route', prefix:[1-3 shop names], route:<allowed route>, hypothesis, evidence}; "
        "parameter: {mutation_type:'parameter', field:<allowed field>, value:<in-range number>, hypothesis, evidence}. "
        "Do not propose arbitrary code, new dependencies, or multiple simultaneous edits."
    )
    allowed = {"routes": sorted(ROUTES), "parameters": PARAMETERS}
    provider = NvidiaNimProvider()
    model = "nvidia/nemotron-3.5-lightning-30b-a3b"

    raw_responses: dict[str, Any] = {}
    proposals: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {}
        for role, instruction in ROLES.items():
            prompt = json.dumps({"role": role, "instruction": instruction, "allowed": allowed, "evidence_packet": packet}, separators=(",", ":"))
            futures[ex.submit(provider.complete, model=model, system=system, prompt=prompt, timeout_s=180)] = role
        for future in as_completed(futures):
            role = futures[future]
            try:
                response = future.result()
                raw_responses[role] = {"text": response.text, "metadata": response.metadata, "model": response.model}
                parsed = _extract_json(response.text)
                proposal = _validate_one(parsed, role)
                if proposal:
                    proposals.append(proposal)
            except Exception as exc:
                raw_responses[role] = {"error": f"{type(exc).__name__}: {exc}"[:1000]}

    merged: dict[str, dict[str, Any]] = {}
    for proposal in proposals:
        if proposal["mutation_type"] == "route":
            key = f"route:{'|'.join(proposal['prefix'])}:{proposal['route']}"
        else:
            key = f"parameter:{proposal['field']}:{proposal['value']}"
        if key not in merged:
            merged[key] = {**proposal, "votes": 1, "roles": [proposal["role"]]}
        else:
            merged[key]["votes"] += 1
            merged[key]["roles"].append(proposal["role"])
    ranked = sorted(merged.values(), key=lambda p: (p["votes"], p["mutation_type"] == "route"), reverse=True)
    result = {"status": "ready", "proposals": ranked[:6], "raw_responses": raw_responses, "packet": packet}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Bounded NVIDIA council for the next Kaggriculture sweep")
    ap.add_argument("--slate", default="artifacts/overnight/TOMORROW_SLATE.json")
    ap.add_argument("--output", default="artifacts/overnight/COUNCIL_PROPOSALS.json")
    args = ap.parse_args()
    result = run(args.slate, args.output)
    print(json.dumps({"status": result["status"], "proposals": result.get("proposals", [])}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
