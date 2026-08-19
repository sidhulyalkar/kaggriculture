from kagv2.micro_patches import (
    MarketTimingConfig,
    decide_sale_units,
    external_inventory_pressure,
    impact_limited_units,
    minimum_terminal_release,
    timing_signal,
)
from kagv2.simulator import market_price


def test_external_pressure_removes_our_own_sale():
    assert external_inventory_pressure(10000, 10018, own_last_sell=8) == 10
    assert external_inventory_pressure(10000, 9992, own_last_sell=0) == -8
    assert external_inventory_pressure(None, 9992, own_last_sell=5) == 0


def test_elastic_drip_respects_exact_price_guard():
    n = impact_limited_units(
        "STRAWBERRY", inventory=10000, quantity=50,
        floor_ratio=.72, max_price_drop_ratio=.10,
    )
    assert 0 < n < 50
    start = market_price("STRAWBERRY", 10000)
    after = market_price("STRAWBERRY", 10000 + n)
    assert start - after <= .10 * 120


def test_crowd_front_run_inverts_failed_shock_deferral():
    cfg = MarketTimingConfig(crowd_threshold=12, scarcity_threshold=0)
    d = decide_sale_units(
        "STRAWBERRY",
        current_inventory=10010,
        previous_inventory=9990,
        own_last_sell=0,
        proposed_units=2,
        available_units=12,
        remaining_steps=400,
        shed_load=30,
        config=cfg,
    )
    assert d["crowd_front_run"] is True
    assert d["allowed_units"] == 12
    assert d["reason"] == "crowd_front_run"


def test_scarcity_harvest_releases_inventory_into_high_price_market():
    cfg = MarketTimingConfig(crowd_threshold=0, scarcity_threshold=10)
    signal = timing_signal(
        "STRAWBERRY",
        current_inventory=9950,
        previous_inventory=9970,
        own_last_sell=0,
        config=cfg,
    )
    assert signal["scarcity_harvest"] is True

    d = decide_sale_units(
        "STRAWBERRY",
        current_inventory=9950,
        previous_inventory=9970,
        own_last_sell=0,
        proposed_units=1,
        available_units=9,
        remaining_steps=400,
        shed_load=30,
        config=cfg,
    )
    assert d["allowed_units"] == 9
    assert d["reason"] == "scarcity_harvest"


def test_terminal_vwap_progressively_forces_release():
    cfg = MarketTimingConfig(crowd_threshold=0, scarcity_threshold=0)
    assert minimum_terminal_release(20, 90, cfg) == 5
    assert minimum_terminal_release(20, 40, cfg) == 10
    assert minimum_terminal_release(20, 8, cfg) == 20

    d = decide_sale_units(
        "MELON",
        current_inventory=10000,
        previous_inventory=10000,
        own_last_sell=0,
        proposed_units=0,
        available_units=20,
        remaining_steps=40,
        shed_load=20,
        config=cfg,
    )
    assert d["allowed_units"] == 10
    assert d["reason"] == "terminal_vwap"


def test_shed_hard_override_wins_over_market_timing():
    cfg = MarketTimingConfig(crowd_threshold=0, scarcity_threshold=0, shed_hard=90)
    d = decide_sale_units(
        "MILK",
        current_inventory=10100,
        previous_inventory=10100,
        own_last_sell=0,
        proposed_units=0,
        available_units=13,
        remaining_steps=400,
        shed_load=94,
        config=cfg,
    )
    assert d["allowed_units"] == 13
    assert d["reason"] == "shed_hard_release"
