from __future__ import annotations

from dataclasses import dataclass, asdict
import copy


@dataclass(frozen=True)
class InterventionSpec:
    mutation: str
    description: str

    def to_dict(self):
        return asdict(self)


def intervention_grammar(order) -> tuple[InterventionSpec, ...]:
    """Return a conservative offline counterfactual grammar for one market order."""
    if not isinstance(order, list) or not order:
        return ()
    op = str(order[0])
    item = str(order[1]) if len(order) > 1 else ""
    qty = int(order[2]) if len(order) > 2 and isinstance(order[2], (int, float)) else None
    out: list[InterventionSpec] = []
    if op in {"HIRE", "BUY_LAND"}:
        out.append(InterventionSpec("suppress", f"suppress one {op}"))
        out.append(InterventionSpec("delay1", f"delay one {op} by one turn"))
    elif op in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL"}:
        out.append(InterventionSpec("suppress", f"suppress {op} {item}"))
        if qty is not None and qty >= 2:
            out.append(InterventionSpec("half", f"halve {op} {item} quantity"))
    elif op == "SELL":
        if qty is not None and qty >= 2:
            out.append(InterventionSpec("half", f"halve SELL {item}"))
        out.append(InterventionSpec("delay1", f"delay SELL {item} by one turn"))
    return tuple(out)


def mutate_market_once(market, index: int, mutation: str):
    """Pure single-step mutation helper used by counterfactual wrappers."""
    out = copy.deepcopy(list(market or []))
    if not (0 <= int(index) < len(out)):
        return out, None, False
    order = out[int(index)]
    if not isinstance(order, list) or not order:
        return out, None, False
    if mutation == "suppress":
        out.pop(int(index))
        return out, None, True
    if mutation == "half":
        if len(order) < 3:
            return out, None, False
        try:
            q = int(order[2])
        except Exception:
            return out, None, False
        n = q // 2
        if n <= 0:
            out.pop(int(index))
        else:
            out[int(index)][2] = n
        return out, None, True
    if mutation == "delay1":
        delayed = out.pop(int(index))
        return out, delayed, True
    raise ValueError(f"Unknown mutation {mutation!r}")
