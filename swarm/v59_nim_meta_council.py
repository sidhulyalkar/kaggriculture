from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
from typing import Any

from swarm.providers import NvidiaNimProvider

EVIDENCE = {
    "live_submissions": {
        "SHAPE_PASTURE": 1962.0,
        "FARMING_V3": 1882.3,
    },
    "validated_findings": {
        "V52_market_flow": {"overall_exact": 0.9997817566, "sale_exact": 0.9904530139},
        "V53_reactive_failure": "1632 confirmed flow events but zero eligible interventions; 948 blocked because own inventory was already gone",
        "V54_executed_sale_prediction": {
            "CARROT": {"auc": 0.952, "top_decile_lift": 8.14},
            "EGG": {"auc": 0.899, "top_decile_lift": 6.33},
            "STRAWBERRY": {"auc": 0.862, "top_decile_lift": 4.50},
            "MELON": {"auc": 0.826, "top_decile_lift": 2.75},
            "WOOL": {"auc": 0.773, "top_decile_lift": 3.13},
        },
        "V55": "offline market prior beat recovered Soil but slightly regressed versus incumbent; online adaptation was worse",
        "V56": "Soil strawberry external-flow event rate 8.50%; incumbent <=4.46%, counter <=3.62%, tournament <=3.20%",
        "V58e": {"best_checkpoint": 72, "confident_family_accuracy": 0.70, "confident_coverage": 0.70},
        "meta_nontransitivity": "public 960-game study found strong rock-paper-scissors cycles; opponent identity plus opening predicted outcomes much better than either alone",
    },
    "hard_constraints": [
        "runtime uses public observation only",
        "no runtime network or LLM calls",
        "preserve a strong open-loop production backbone",
        "prefer bounded reversible or latched deviations over wholesale midgame route switching",
        "optimize match win probability / Bradley-Terry rating, not raw cash alone",
        "must work in kaggle-environments==1.32.7 and both seats",
    ],
}

ROLES = {
    "meta_strategist": "Design a non-transitive two-slot strategy portfolio and identify the highest-value opponent families to exploit.",
    "engine_economist": "Propose precise legal public-state economic interventions that can improve win probability without destabilizing farming choreography.",
    "recognition_scientist": "Improve early strategy-family recognition and specify uncertainty/hysteresis rules that reduce false activation.",
    "adversarial_critic": "Attack the proposed adaptive architecture: identify false-positive regimes, exploitability, and reasons it could lose to top static routes.",
    "search_scientist": "Propose an experiment/search design that can discover best responses to current top replay families under limited exact-engine compute.",
    "portfolio_synthesizer": "Synthesize the evidence into two concrete submission variants: one robust anchor improvement and one structurally different counter-meta hedge.",
}
MODELS = (
    "moonshotai/kimi-k3",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
)

SYSTEM = """You are one member of an NVIDIA NIM scientific council optimizing Kaggriculture competition win probability. Be concrete and falsifiable. Do not propose runtime LLM calls, private opponent information, or broad rewrites without evidence. Return JSON only with keys: thesis, target_families, observables, trigger, action_changes, hysteresis, failure_modes, experiments, promotion_gate, confidence. action_changes must name exact classes of actions (market timing, opening choice, production reserve, shop sequencing, etc.) and stay sparse. experiments must include paired both-seat tests. confidence is 0..1."""


def _extract_json(text: str) -> Any:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        for end in range(len(text), start, -1):
            if start >= 0:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
        raise


def run(output: str | Path) -> dict[str, Any]:
    provider = NvidiaNimProvider()
    raw: dict[str, Any] = {}
    proposals: list[dict[str, Any]] = []
    jobs = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for idx, (role, instruction) in enumerate(ROLES.items()):
            model = MODELS[idx % len(MODELS)]
            prompt = json.dumps({"role": role, "instruction": instruction, "evidence": EVIDENCE}, separators=(",", ":"))
            jobs.append((role, model, pool.submit(provider.complete, model=model, system=SYSTEM, prompt=prompt, timeout_s=240)))
        for role, model, future in jobs:
            try:
                response = future.result()
                parsed = _extract_json(response.text)
                if not isinstance(parsed, dict):
                    raise ValueError("council response was not a JSON object")
                confidence = float(parsed.get("confidence", 0.0) or 0.0)
                confidence = max(0.0, min(1.0, confidence))
                proposal = {"role": role, "model": model, **parsed, "confidence": confidence}
                proposals.append(proposal)
                raw[role] = {"status": "ok", "model": model, "metadata": response.metadata, "text": response.text}
            except Exception as exc:
                raw[role] = {"status": "error", "model": model, "error": f"{type(exc).__name__}: {exc}"[:1200]}

    proposals.sort(key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
    themes: dict[str, int] = {}
    for p in proposals:
        for family in p.get("target_families", []) if isinstance(p.get("target_families"), list) else []:
            themes[str(family)] = themes.get(str(family), 0) + 1
    result = {
        "experiment": "V59_NVIDIA_NIM_META_COUNCIL",
        "status": "ready" if len(proposals) >= 3 else "insufficient_council",
        "successful_roles": len(proposals),
        "evidence": EVIDENCE,
        "target_family_votes": dict(sorted(themes.items(), key=lambda kv: (-kv[1], kv[0]))),
        "proposals": proposals,
        "raw_responses": raw,
        "scientific_boundary": "NVIDIA NIM proposes offline hypotheses only; deterministic exact-engine experiments decide promotion",
    }
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="tmp/v59/V59_NIM_COUNCIL.json")
    args = ap.parse_args()
    result = run(args.output)
    print(json.dumps({"status": result["status"], "successful_roles": result["successful_roles"], "target_family_votes": result["target_family_votes"], "proposals": result["proposals"]}, indent=2, sort_keys=True))
    if result["status"] != "ready":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
