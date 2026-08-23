from kagv2.market_microstructure import delay_loss, external_pressure, order_priority, sale_revenue, stress_from_pressure


def test_sale_revenue_falls_when_delayed_by_supply():
    assert sale_revenue("STRAWBERRY", 10000, 12) > sale_revenue("STRAWBERRY", 10020, 12)


def test_delay_loss_is_exact_and_nonnegative():
    u = delay_loss("MILK", 10000, 10, stress_units=15)
    assert u.delay_loss == u.revenue_now - u.revenue_after_stress
    assert u.delay_loss > 0


def test_external_pressure_restores_known_demand():
    assert external_pressure(10000, 10015, own_previous_sell=6, demand=6) == 15


def test_stress_uses_visible_supply_but_is_bounded():
    assert stress_from_pressure(-5, 0) == 8
    assert stress_from_pressure(10, 8) == 14
    assert stress_from_pressure(100, 100) == 28


def test_priority_prefers_fragile_premium_sale():
    milk = order_priority("MILK", 10000, 8, pressure=12)
    wheat = order_priority("WHEAT", 10000, 100, pressure=12)
    assert milk < wheat
