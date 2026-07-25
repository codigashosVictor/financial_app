from datetime import date

from app.core.reports import build_periods, build_monthly_series


def test_build_periods_ends_on_current_month():
    periods = build_periods(date(2026, 7, 6), months=3)

    assert periods == ["2026-05", "2026-06", "2026-07"]


def test_build_periods_clamps_to_max():
    periods = build_periods(date(2026, 7, 6), months=999)

    assert len(periods) == 36
    assert periods[-1] == "2026-07"


def test_build_periods_clamps_to_min_of_one():
    periods = build_periods(date(2026, 7, 6), months=0)

    assert periods == ["2026-07"]


def test_monthly_series_aggregates_income_and_expenses():
    periods = ["2026-06", "2026-07"]
    expenses = [
        {"billing_period": "2026-06", "amount": 500, "category": "Comida"},
        {"billing_period": "2026-07", "amount": 300, "category": "Comida"},
        {"billing_period": "2026-07", "amount": 100, "category": "Transporte"},
        {"billing_period": "2025-01", "amount": 999, "category": "Otro"},  # fuera de rango
    ]
    incomes = [
        {"income_date": "2026-06-15", "amount": 1000},
        {"income_date": "2026-07-01", "amount": 1000},
    ]

    result = build_monthly_series(periods, expenses, incomes)

    assert result["income_amounts"] == [1000, 1000]
    assert result["expense_amounts"] == [500, 400]
    assert result["net_amounts"] == [500, 600]
    assert result["category_totals"] == {"Comida": 800, "Transporte": 100}
    assert result["total_income"] == 2000
    assert result["total_expenses"] == 900
    assert result["total_net"] == 1100


def test_monthly_series_savings_rate_zero_when_no_income():
    periods = ["2026-07"]
    expenses = [{"billing_period": "2026-07", "amount": 100, "category": "Otro"}]

    result = build_monthly_series(periods, expenses, [])

    assert result["savings_rate"] == [0]
    assert result["avg_savings_rate"] == 0


def test_monthly_series_savings_rate_percentage():
    periods = ["2026-07"]
    expenses = [{"billing_period": "2026-07", "amount": 300, "category": "Otro"}]
    incomes = [{"income_date": "2026-07-01", "amount": 1000}]

    result = build_monthly_series(periods, expenses, incomes)

    assert result["savings_rate"] == [70.0]
    assert result["avg_savings_rate"] == 70.0


def test_monthly_series_missing_category_defaults_to_otro():
    periods = ["2026-07"]
    expenses = [{"billing_period": "2026-07", "amount": 50}]

    result = build_monthly_series(periods, expenses, [])

    assert result["category_totals"] == {"Otro": 50}
