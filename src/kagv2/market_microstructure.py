from __future__ import annotations

"""Exact shared-market execution utilities used by V44 research."""

from dataclasses import dataclass

from .constants import BASE, PRODUCTS
from .simulator import market_price

PREMIUM = ("STRAWBERRY", "MELON", "MILK", "WOOL")


@dataclass(frozen=True)
class OrderUrgency:
    product: str
    quantity: int
    market_inventory: int
    stress_units: int
    revenue_now: int
    revenue_after_stress: int
    delay_loss: int
    price_ratio: float
    slope_loss_per_unit: float


def sale_revenue(product: str, inventory: int, quantity: int) -> int:
    product = str(product).upper()
    if product not in PRODUCTS:
        raise ValueError(product)
    inventory = int(inventory)
    quantity = max(0, int(quantity))
    return sum(int(market_price(product, inventory + i)) for i in range(quantity))


def delay_loss(product: str, inventory: int, quantity: int, stress_units: int = 12) -> OrderUrgency:
    product = str(product).upper()
    if product not in PRODUCTS:
        raise ValueError(product)
    quantity = max(0, int(quantity))
    inventory = int(inventory)
    stress_units = max(0, int(stress_units))
    now = sale_revenue(product, inventory, quantity)
    later = sale_revenue(product, inventory + stress_units, quantity)
    loss = max(0, now - later)
    price = float(market_price(product, inventory))
    return OrderUrgency(
        product=product,
        quantity=quantity,
        market_inventory=inventory,
        stress_units=stress_units,
        revenue_now=now,
        revenue_after_stress=later,
        delay_loss=loss,
        price_ratio=price / float(BASE[product]),
        slope_loss_per_unit=(loss / quantity) if quantity else 0.0,
    )


def external_pressure(previous_inventory: int | None, current_inventory: int, own_previous_sell: int = 0, demand: int = 0) -> int:
    """Infer external supply after removing our sale and restoring known demand."""
    if previous_inventory is None:
        return 0
    return int(current_inventory) - int(previous_inventory) - max(0, int(own_previous_sell)) + max(0, int(demand))


def stress_from_pressure(pressure: int, visible_supply: int = 0, floor: int = 8, cap: int = 28) -> int:
    floor = max(0, int(floor))
    cap = max(floor, int(cap))
    raw = max(0, int(pressure)) + min(12, max(0, int(visible_supply)) // 2)
    return min(cap, max(floor, raw))


def order_priority(product: str, inventory: int, quantity: int, pressure: int = 0, visible_supply: int = 0, premium_only: bool = False) -> tuple:
    product = str(product).upper()
    if premium_only and product not in PREMIUM:
        return (1, 0.0, 0.0, product)
    urgency = delay_loss(product, inventory, quantity, stress_from_pressure(pressure, visible_supply))
    return (0 if product in PREMIUM else 1, -float(urgency.delay_loss), -float(urgency.slope_loss_per_unit), product)
