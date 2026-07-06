from datetime import date

from app.core.alerts import build_payment_alerts, build_subscription_alerts, build_budget_alerts

CARD = {"id": "card-1", "name": "Nu", "cut_day": 15, "payment_due_day": 10}


def test_payment_alert_fires_when_due_today():
    today = date(2026, 7, 10)
    totals = {("card-1", "2026-06"): 1500}

    alerts = build_payment_alerts([CARD], totals, today)

    assert len(alerts) == 1
    assert "HOY" in alerts[0]["title"]
    assert alerts[0]["urgent"] is True
    assert "1,500.00" in alerts[0]["body"]


def test_payment_alert_silent_outside_threshold_days():
    today = date(2026, 7, 4)  # due date is 2026-07-10, 6 days out

    alerts = build_payment_alerts([CARD], {}, today)

    assert alerts == []


def test_payment_alert_one_per_card():
    today = date(2026, 7, 9)  # 1 day before due (07-10)

    alerts = build_payment_alerts([CARD], {}, today)

    assert len(alerts) == 1
    assert "MAÑANA" in alerts[0]["title"]


def test_subscription_alert_fires_on_charge_day():
    today = date(2026, 7, 5)
    subs = [
        {"name": "Netflix", "amount": 219, "charge_day": 5},
        {"name": "Spotify", "amount": 115, "charge_day": 20},
    ]

    alerts = build_subscription_alerts(subs, today)

    assert len(alerts) == 1
    assert "Netflix" in alerts[0]["body"]
    assert "Spotify" not in alerts[0]["body"]


def test_subscription_alert_empty_when_no_charge_today():
    alerts = build_subscription_alerts([{"name": "Netflix", "amount": 219, "charge_day": 20}], date(2026, 7, 5))

    assert alerts == []


def test_budget_alert_over_is_urgent():
    budgets = [{"category": "Comida", "amount": 1000}]
    spent = {"Comida": 1200}

    alerts = build_budget_alerts(budgets, spent)

    assert len(alerts) == 1
    assert alerts[0]["urgent"] is True
    assert "excedido" in alerts[0]["title"]


def test_budget_alert_warning_at_80_percent():
    budgets = [{"category": "Comida", "amount": 1000}]
    spent = {"Comida": 800}

    alerts = build_budget_alerts(budgets, spent)

    assert len(alerts) == 1
    assert alerts[0]["urgent"] is False
    assert "casi agotado" in alerts[0]["title"]


def test_budget_alert_silent_under_threshold():
    budgets = [{"category": "Comida", "amount": 1000}]
    spent = {"Comida": 500}

    assert build_budget_alerts(budgets, spent) == []


def test_budget_alert_skips_zero_budget():
    budgets = [{"category": "Comida", "amount": 0}]

    assert build_budget_alerts(budgets, {"Comida": 500}) == []
