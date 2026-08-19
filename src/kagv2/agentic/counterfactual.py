from __future__ import annotations

from dataclasses import dataclass, asdict
import copy
from typing import Callable

from .interventions import intervention_grammar, mutate_market_once


@dataclass(frozen=True)
class BranchSpec:
    step: int
    market_index: int
    mutation: str
    op: str
    item: str = ""
    qty: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EpisodeOutcome:
    score: float
    cash: float
    opponent_cash: float
    margin: float
    activated: int

    def to_dict(self) -> dict:
        return asdict(self)


def runtime_state_features(obs: dict) -> dict:
    """Compact runtime-legal state snapshot for counterfactual supervision."""
    p = int(obs.get("player", 0))
    farms = obs.get("farms", []) or []
    opp = 1 - p
    if p >= len(farms) or opp >= len(farms):
        return {}
    me, other = farms[p], farms[opp]
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    market = obs.get("market", {}) or {}
    inv = market.get("inventory", {}) or {}
    prices = market.get("prices", {}) or {}

    out = {
        "step": int(obs.get("step", 0)),
        "day": int(obs.get("day", 0)),
        "hour": int(obs.get("hour", 0)),
        "seat": p,
        "our_money": float(me.get("money", 0)),
        "opp_money": float(other.get("money", 0)),
        "cash_margin": float(me.get("money", 0) - other.get("money", 0)),
        "our_hands": len(me.get("hands", []) or []),
        "opp_hands": len(other.get("hands", []) or []),
        "our_quads": len(me.get("unlocked_quadrants", []) or []),
        "opp_quads": len(other.get("unlocked_quadrants", []) or []),
    }
    for product in ("WHEAT", "STRAWBERRY", "MELON", "MILK", "WOOL"):
        out[f"shed_{product}"] = int(shed.get(product, 0))
        out[f"market_inv_{product}"] = int(inv.get(product, 10000))
        out[f"price_{product}"] = int(prices.get(product, 0))

    for prefix, farm in (("our", me), ("opp", other)):
        crops = {x: 0 for x in ("WHEAT", "STRAWBERRY", "MELON")}
        animals = {x: 0 for x in ("COW", "SHEEP", "GOOSE")}
        ready = {x: 0 for x in crops}
        for row in farm.get("tiles", []) or []:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                crop = tile.get("crop")
                if crop in crops:
                    crops[crop] += 1
                    if int(tile.get("yield_units", 0)) > 0:
                        ready[crop] += 1
                animal = tile.get("animal")
                if animal in animals:
                    animals[animal] += 1
        for k, v in crops.items():
            out[f"{prefix}_crop_{k}"] = v
            out[f"{prefix}_ready_{k}"] = ready[k]
        for k, v in animals.items():
            out[f"{prefix}_animal_{k}"] = v
    return out


def economic_branch_specs(action: dict, step: int) -> tuple[BranchSpec, ...]:
    """Enumerate bounded, fingerprinted alternatives for one champion action."""
    market = action.get("market", []) if isinstance(action, dict) else []
    if not isinstance(market, list):
        return ()
    specs: list[BranchSpec] = []
    for index, order in enumerate(market[:10]):
        if not isinstance(order, list) or not order:
            continue
        op = str(order[0])
        item = str(order[1]) if len(order) > 1 else ""
        qty = None
        if len(order) > 2:
            try:
                qty = int(order[2])
            except Exception:
                qty = None
        for intervention in intervention_grammar(order):
            specs.append(BranchSpec(
                step=int(step), market_index=index, mutation=intervention.mutation,
                op=op, item=item, qty=qty,
            ))
    return tuple(specs)


def _fingerprint_matches(order, spec: BranchSpec) -> bool:
    if not isinstance(order, list) or not order:
        return False
    op = str(order[0])
    item = str(order[1]) if len(order) > 1 else ""
    return op == spec.op and item == spec.item


def apply_branch(action: dict, spec: BranchSpec, pending=None):
    """Apply one branch to an action, returning action, pending order, activation."""
    out = copy.deepcopy(action)
    if not isinstance(out, dict):
        return out, pending, False
    market = list(out.get("market", []) or [])
    if not (0 <= spec.market_index < len(market)):
        return out, pending, False
    if not _fingerprint_matches(market[spec.market_index], spec):
        return out, pending, False
    market, delayed, activated = mutate_market_once(market, spec.market_index, spec.mutation)
    out["market"] = market[:10]
    return out, delayed, activated


def _default_game_factory(seed: int):
    from kagv2.simulator import Game
    return Game(seed=int(seed))


def run_episode(
    champion_factory: Callable[[], Callable],
    opponent_factory: Callable[[], Callable],
    *,
    seed: int,
    seat: int,
    branch: BranchSpec | None = None,
    game_factory: Callable[[int], object] | None = None,
) -> EpisodeOutcome:
    """Replay one deterministic game with at most one champion intervention."""
    champion = champion_factory()
    opponent = opponent_factory()
    game = (game_factory or _default_game_factory)(int(seed))
    activated = 0
    pending = None
    pending_index = None
    for _ in range(game.episode_steps - 1):
        obs0, obs1 = game.obs(0), game.obs(1)
        champ_obs = obs0 if seat == 0 else obs1
        opp_obs = obs1 if seat == 0 else obs0
        champ_action = champion(champ_obs)
        opp_action = opponent(opp_obs)

        if branch is not None and pending is not None and pending_index is not None and game.step == branch.step + 1:
            ca = copy.deepcopy(champ_action)
            market = list(ca.get("market", []) or []) if isinstance(ca, dict) else []
            if len(market) < 10:
                market.insert(min(pending_index, len(market)), pending)
                ca["market"] = market[:10]
                champ_action = ca
            pending = None
            pending_index = None

        if branch is not None and game.step == branch.step:
            champ_action, delayed, hit = apply_branch(champ_action, branch)
            activated += int(hit)
            if delayed is not None:
                pending = delayed
                pending_index = branch.market_index

        game.step_once([champ_action, opp_action] if seat == 0 else [opp_action, champ_action])

    cash = [float(f["money"]) for f in game.farms]
    our, theirs = (cash[0], cash[1]) if seat == 0 else (cash[1], cash[0])
    return EpisodeOutcome(
        score=1.0 if our > theirs else 0.5 if our == theirs else 0.0,
        cash=our,
        opponent_cash=theirs,
        margin=our - theirs,
        activated=activated,
    )


def discover_branch_opportunities(
    champion_factory: Callable[[], Callable],
    opponent_factory: Callable[[], Callable],
    *,
    seed: int,
    seat: int,
    max_events: int | None = None,
    game_factory: Callable[[int], object] | None = None,
) -> list[dict]:
    """Replay a baseline game and capture branchable economic decisions + state."""
    champion = champion_factory()
    opponent = opponent_factory()
    game = (game_factory or _default_game_factory)(int(seed))
    rows: list[dict] = []
    for _ in range(game.episode_steps - 1):
        obs0, obs1 = game.obs(0), game.obs(1)
        champ_obs = obs0 if seat == 0 else obs1
        opp_obs = obs1 if seat == 0 else obs0
        champ_action = champion(champ_obs)
        opp_action = opponent(opp_obs)
        state = runtime_state_features(champ_obs)
        for spec in economic_branch_specs(champ_action, game.step):
            rows.append({**state, **spec.to_dict()})
            if max_events is not None and len(rows) >= int(max_events):
                break
        game.step_once([champ_action, opp_action] if seat == 0 else [opp_action, champ_action])
    return rows


def build_counterfactual_rows(
    champion_factory: Callable[[], Callable],
    opponent_factory: Callable[[], Callable],
    *,
    seed: int,
    seat: int,
    max_events: int | None = None,
    game_factory: Callable[[int], object] | None = None,
) -> list[dict]:
    """Generate a complete one-decision counterfactual table for one game."""
    base = run_episode(champion_factory, opponent_factory, seed=seed, seat=seat, game_factory=game_factory)
    opportunities = discover_branch_opportunities(
        champion_factory, opponent_factory, seed=seed, seat=seat,
        max_events=max_events, game_factory=game_factory,
    )
    rows = []
    for event in opportunities:
        spec = BranchSpec(
            step=int(event["step"]), market_index=int(event["market_index"]),
            mutation=str(event["mutation"]), op=str(event["op"]), item=str(event.get("item", "")),
            qty=None if event.get("qty") is None else int(event["qty"]),
        )
        outcome = run_episode(
            champion_factory, opponent_factory, seed=seed, seat=seat,
            branch=spec, game_factory=game_factory,
        )
        rows.append({
            **event,
            "seed": int(seed), "seat": int(seat),
            "base_score": base.score, "base_cash": base.cash,
            "base_opp_cash": base.opponent_cash, "base_margin": base.margin,
            "score": outcome.score, "cash": outcome.cash,
            "opp_cash": outcome.opponent_cash, "margin": outcome.margin,
            "margin_delta": outcome.margin - base.margin,
            "score_delta": outcome.score - base.score,
            "activated": outcome.activated,
            "ok": True,
        })
    return rows
