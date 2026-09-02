from kagv2.market_microstructure import (
    delay_loss,
    external_pressure,
    order_priority,
    sale_revenue,
    stress_from_pressure,
)


def test_sale_revenue_falls_when_delayed_by_supply():
    now = sale_revenue("STRAWBERRY", 10000, 12)
    later = sale_revenue("STRAWBERRY", 10020, 12)
    assert now > later


def test_delay_loss_is_exact_and_nonnegative():
    u = delay_loss("MILK", 10000, 10, stress_units=15)
    assert u.delay_loss == u.revenue_now - u.revenue_after_stress
    assert u.delay_loss > 0
    assert u.slope_loss_per_unit > 0


def test_external_pressure_removes_own_sale():
    assert external_pressure(10000, 10021, 6) == 15
    assert external_pressure(10000, 9990, 0) == -10


def test_stress_is_bounded():
    assert stress_from_pressure(-5) == 8
    assert stress_from_pressure(13) == 13
    assert stress_from_pressure(100) == 24


def test_order_priority_prefers_more_delay_sensitive_sale():
    strawberry = order_priority("STRAWBERRY", 10000, 15, pressure=18)
    wheat = order_priority("WHEAT", 10000, 15, pressure=18)
    assert strawberry < wheat


def test_premium_only_keeps_nonpremium_behind_premium():
    premium = order_priority("MILK", 10000, 8, pressure=8, premium_only=True)
    nonpremium = order_priority("WHEAT", 10000, 100, pressure=24, premium_only=True)
    assert premium < nonpremium
