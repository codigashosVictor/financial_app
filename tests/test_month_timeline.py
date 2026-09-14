from datetime import date

from app.core.month_timeline import get_liquid_balance, build_cash_events, build_daily_balance


def test_get_liquid_balance_sums_latest_snapshot_per_account():
    account_balances = [
        {"account_id": "a1", "balance": 1000, "snapshot_date": "2026-05-01"},
        {"account_id": "a1", "balance": 1500, "snapshot_date": "2026-06-01"},
        {"account_id": "a2", "balance": 200, "snapshot_date": "2026-06-15"},
    ]
    assert get_liquid_balance(account_balances) == 1700


def test_get_liquid_balance_empty():
    assert get_liquid_balance([]) == 0


def test_build_cash_events_merges_income_and_card_due_events_in_order():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 31)
    income_rows = [{"income_date": "2026-05-10", "amount": 5100, "source": "Nomina semanal"}]
    card_due_events = [
        {"card_name": "Visa", "due_date": date(2026, 5, 5), "amount": 2000, "estimated": False},
    ]

    events = build_cash_events(income_rows, card_due_events, today, horizon_end)

    assert [e["type"] for e in events] == ["card_due", "income"]
    assert events[0]["amount"] == -2000
    assert events[1]["amount"] == 5100


def test_build_cash_events_excludes_events_outside_horizon():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 10)
    income_rows = [{"income_date": "2026-06-01", "amount": 5100, "source": "Nomina"}]
    card_due_events = [{"card_name": "Visa", "due_date": date(2026, 5, 20), "amount": 2000, "estimated": False}]

    events = build_cash_events(income_rows, card_due_events, today, horizon_end)

    assert events == []


def test_build_daily_balance_running_total_and_lowest_point():
    today = date(2026, 5, 1)
    horizon_end = date(2026, 5, 5)
    events = [
        {"date": date(2026, 5, 2), "type": "card_due", "label": "Visa", "amount": -300, "estimated": False},
        {"date": date(2026, 5, 4), "type": "income", "label": "Nomina", "amount": 100, "estimated": False},
    ]

    result = build_daily_balance(1000, events, today, horizon_end)

    assert result["dates"] == ["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05"]
    assert result["balances"] == [1000, 700, 700, 800, 800]
    assert result["lowest_point"] == {"date": "2026-05-02", "balance": 700}
    assert result["end_balance"] == 800


def test_build_daily_balance_no_events_stays_flat():
    result = build_daily_balance(500, [], date(2026, 5, 1), date(2026, 5, 2))
    assert result["balances"] == [500, 500]
    assert result["end_balance"] == 500
