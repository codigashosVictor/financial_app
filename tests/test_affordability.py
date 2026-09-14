from datetime import date

from app.core.affordability import build_purchase_breakdown, find_safe_purchase_date


def _daily_balance(dates, balances):
    return {"dates": dates, "balances": balances}


def test_can_buy_today_when_floor_stays_non_negative():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 3)
    daily_balance = _daily_balance(
        ["2026-05-01", "2026-05-02", "2026-05-03"],
        [5000, 5000, 5000],
    )

    result = find_safe_purchase_date(daily_balance, cost=1000, target_date=today, today=today, horizon_end=horizon_end)

    assert result["status"] == "ok"
    assert result["can_buy_now"] is True
    assert result["safe_date"] == "2026-05-01"
    assert result["floor_after_purchase"] == 4000


def test_must_wait_for_future_income_event():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 5)
    daily_balance = _daily_balance(
        ["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05"],
        [500, 500, 500, 5600, 5600],
    )
    events = [{"date": date(2026, 5, 4), "type": "income", "label": "Nomina semanal", "amount": 5100}]

    result = find_safe_purchase_date(daily_balance, cost=1000, target_date=today, today=today, horizon_end=horizon_end, events=events)

    assert result["status"] == "ok"
    assert result["can_buy_now"] is False
    assert result["safe_date"] == "2026-05-04"
    assert result["reason"] == {"type": "income", "label": "Nomina semanal", "date": "2026-05-04"}


def test_already_negative_without_the_purchase():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 2)
    daily_balance = _daily_balance(["2026-05-01", "2026-05-02"], [500, -200])

    result = find_safe_purchase_date(daily_balance, cost=100, target_date=today, today=today, horizon_end=horizon_end)

    assert result["status"] == "already_negative"
    assert result["floor_balance"] == -200


def test_no_safe_date_within_horizon():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 3)
    daily_balance = _daily_balance(
        ["2026-05-01", "2026-05-02", "2026-05-03"],
        [500, 500, 500],
    )

    result = find_safe_purchase_date(daily_balance, cost=10000, target_date=today, today=today, horizon_end=horizon_end)

    assert result["status"] == "no_safe_date_in_horizon"
    assert result["shortfall"] == 9500


def test_exact_zero_floor_is_safe():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 1)
    daily_balance = _daily_balance(["2026-05-01"], [1000])

    result = find_safe_purchase_date(daily_balance, cost=1000, target_date=today, today=today, horizon_end=horizon_end)

    assert result["status"] == "ok"
    assert result["floor_after_purchase"] == 0


def test_breakdown_lists_events_in_order_with_running_balance():
    horizon_end = date(2026, 5, 5)
    cash_events = [
        {"date": date(2026, 5, 4), "type": "income", "label": "Nomina semanal", "amount": 5100},
        {"date": date(2026, 5, 2), "type": "card_due", "label": "BANORTE ORO", "amount": -1500},
    ]

    breakdown = build_purchase_breakdown(2000, cash_events, cost=3000, horizon_end=horizon_end)

    assert breakdown["starting_balance"] == 2000
    assert [line["label"] for line in breakdown["lines"]] == ["BANORTE ORO", "Nomina semanal"]
    assert breakdown["lines"][0]["balance_after"] == 500
    assert breakdown["lines"][1]["balance_after"] == 5600
    assert breakdown["end_balance"] == 5600
    assert breakdown["end_balance_after_purchase"] == 2600


def test_breakdown_with_no_events_stays_at_starting_balance():
    breakdown = build_purchase_breakdown(1000, [], cost=200, horizon_end=date(2026, 5, 1))

    assert breakdown["lines"] == []
    assert breakdown["end_balance"] == 1000
    assert breakdown["end_balance_after_purchase"] == 800
