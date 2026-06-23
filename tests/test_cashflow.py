from datetime import date

from app.core.cashflow import (
    calculate_30d_projection,
    calculate_net_cashflow,
    month_bounds,
)


def test_month_bounds_regular_month():
    start, end = month_bounds("2026-05")
    assert start == date(2026, 5, 1)
    assert end == date(2026, 5, 31)


def test_month_bounds_february_non_leap():
    start, end = month_bounds("2026-02")
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_calculate_net_cashflow():
    assert calculate_net_cashflow(5000, 3200) == 1800
    assert calculate_net_cashflow(1200, 1800) == -600


def test_calculate_30d_projection_positive():
    result = calculate_30d_projection(8000, 3000)
    assert result["income_30d"] == 8000
    assert result["expenses_30d"] == 3000
    assert result["net_30d"] == 5000
    assert result["is_negative"] is False


def test_calculate_30d_projection_negative():
    result = calculate_30d_projection(1500, 4000)
    assert result["net_30d"] == -2500
    assert result["is_negative"] is True
