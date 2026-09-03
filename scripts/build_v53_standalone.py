from __future__ import annotations

from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "submission"
OUT_DIR = ROOT / "artifacts" / "v53"


def _without_future(source: str) -> str:
    return "\n".join(
        line for line in source.splitlines()
        if line.strip() != "from __future__ import annotations"
    ) + "\n"


def _parametric_body(source: str) -> str:
    marker = "DEFAULT_PARAMS={"
    start = source.find(marker)
    if start < 0:
        raise RuntimeError("could not locate DEFAULT_PARAMS in parametric_agent.py")
    return source[start:]


HARD_FLOW_RUNTIME = r'''
FLOW_PRODUCTS = ("STRAWBERRY", "MELON", "MILK", "WOOL")
FLOW_MIN_UNITS = 4
FLOW_MIN_PRICE_RATIO = 0.42
FLOW_MIN_LOSS_FRAC = 0.08
FLOW_MIN_LOSS_ABS = 40
FLOW_STRESS_CAP = 24


def _v53_sale_revenue(product, inventory, quantity):
    return sum(int(model_price(product, int(inventory) + i)) for i in range(max(0, int(quantity))))


def normalize_observation_step(obs):
    if not isinstance(obs, dict):
        return 0
    step = int(obs.get("day", 0) or 0) * 24 + int(obs.get("hour", 0) or 0)
    obs["step"] = step
    return step


class HardFlowMind(ParametricMind):
    def __init__(self):
        super().__init__(DEFAULT_PARAMS)
        self._previous_obs = None
        self._previous_action = None
        self._confirmed_flow = {p: 0 for p in NONBUYABLE_PRODUCTS}

    def _observe_confirmed_flow(self, obs):
        self._confirmed_flow = {p: 0 for p in NONBUYABLE_PRODUCTS}
        if self._previous_obs is None or self._previous_action is None:
            return
        for product in NONBUYABLE_PRODUCTS:
            units = infer_external_supply(self._previous_obs, obs, self._previous_action, product)
            if units is not None:
                self._confirmed_flow[product] = max(0, int(units))

    def _sell_orders(self, obs, counts):
        orders = super()._sell_orders(obs, counts)
        if len(orders) >= 10:
            return orders[:10]
        shed = ((obs.get("private", {}) or {}).get("shed", {}) or {})
        market = obs.get("market", {}) or {}
        inventory = market.get("inventory", {}) or {}
        prices = market.get("prices", {}) or {}
        already = {
            str(order[1]) for order in orders
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL"
        }
        for product in FLOW_PRODUCTS:
            if product in already or len(orders) >= 10:
                continue
            shock = int(self._confirmed_flow.get(product, 0) or 0)
            quantity = int(shed.get(product, 0) or 0)
            if shock < FLOW_MIN_UNITS or quantity <= 0:
                continue
            inv = int(inventory.get(product, 10000) or 10000)
            price = float(prices.get(product, model_price(product, inv)) or 0)
            if price < FLOW_MIN_PRICE_RATIO * BASE[product]:
                continue
            stress = min(FLOW_STRESS_CAP, shock)
            sell_now = min(quantity, shock)
            now = _v53_sale_revenue(product, inv, sell_now)
            later = _v53_sale_revenue(product, inv + stress, sell_now)
            loss = max(0, now - later)
            if loss < FLOW_MIN_LOSS_ABS or loss < FLOW_MIN_LOSS_FRAC * max(1, now):
                continue
            orders.append(["SELL", product, sell_now])
        return orders[:10]

    def act(self, obs):
        self._observe_confirmed_flow(obs)
        action = super().act(obs)
        import copy
        self._previous_obs = copy.deepcopy(obs)
        self._previous_action = copy.deepcopy(action)
        return action


_POLICY = None


def agent(obs, configuration=None):
    global _POLICY
    step = normalize_observation_step(obs)
    if _POLICY is None or step == 0:
        _POLICY = HardFlowMind()
    return _POLICY.act(obs)
'''


def build() -> tuple[Path, Path]:
    base = _without_future((SUB / "base_controller.py").read_text(encoding="utf-8"))
    parametric = _parametric_body((SUB / "parametric_agent.py").read_text(encoding="utf-8"))
    flow = _without_future((SUB / "market_flow_runtime.py").read_text(encoding="utf-8"))
    source = "from __future__ import annotations\n\n" + base + "\n" + parametric + "\n" + flow + "\n" + HARD_FLOW_RUNTIME

    if "__file__" in source:
        raise RuntimeError("standalone source must not depend on __file__")
    code = compile(source, "main.py", "exec")
    env: dict[str, object] = {}
    exec(code, env)
    callable_names = [name for name, value in env.items() if callable(value)]
    if not callable_names or callable_names[-1] != "agent":
        raise RuntimeError(f"last callable is not agent: {callable_names[-5:]}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    main_path = OUT_DIR / "main.py"
    main_path.write_text(source, encoding="utf-8")
    archive = OUT_DIR / "submission_v53.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(main_path, arcname="main.py")
    with tarfile.open(archive, "r:gz") as tf:
        names = [m.name for m in tf.getmembers() if m.isfile()]
        if names != ["main.py"]:
            raise RuntimeError(f"unexpected archive members: {names}")
    return main_path, archive


if __name__ == "__main__":
    main_path, archive = build()
    print(main_path)
    print(archive)
    print("main_bytes", main_path.stat().st_size)
    print("archive_bytes", archive.stat().st_size)
