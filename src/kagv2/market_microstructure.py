from __future__ import annotations

"""Small, exact market-execution utilities for Kaggriculture research.

These functions do not choose crops, animals, routes, or sale quantities. They
measure how expensive it is to delay an already-planned sale when another
seller may add inventory to the shared market first.
"""

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
    """Exact sequential revenue for one SELL order in the public engine."""
    product = str(product).upper()
    if product not in PRODUCTS:
        raise ValueError(product)
    inventory = int(inventory)
    quantity = max(0, int(quantity))
    revenue = 0
    for i in range(quantity):
        revenue += int(market_price(product, inventory + i))
    return revenue


def delay_loss(product: str, inventory: int, quantity: int, stress_units: int = 12) -> OrderUrgency:
    """Revenue lost if ``stress_units`` of supply hit the market before us."""
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


def external_pressure(previous_inventory: int | None, current_inventory: int,
                      own_previous_sell: int = 0) -> int:
    """Observed inventory change after removing our previous requested sale."""
    if previous_inventory is None:
        return 0
    return int(current_inventory) - int(previous_inventory) - max(0, int(own_previous_sell))


def stress_from_pressure(pressure: int, floor: int = 8, cap: int = 24) -> int:
    """Convert recent positive supply flow into a conservative delay scenario."""
    floor = max(0, int(floor)); cap = max(floor, int(cap))
    return min(cap, max(floor, max(0, int(pressure))))


def order_priority(product: str, inventory: int, quantity: int,
                   pressure: int = 0, premium_only: bool = False) -> tuple:
    """Sort key for slot-race execution: most delay-sensitive sale first.

    Returned tuple is suitable for ascending ``sorted``. The ordering uses
    only exact market mechanics and public state; it does not depend on an
    opponent identity classifier.
    """
    product = str(product).upper()
    if premium_only and product not in PREMIUM:
        return (1, 0.0, 0.0, product)
    u = delay_loss(product, inventory, quantity, stress_from_pressure(pressure))
    return (0, -float(u.delay_loss), -float(u.slope_loss_per_unit), product)
