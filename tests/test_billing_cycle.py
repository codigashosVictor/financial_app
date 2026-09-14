from datetime import date

from app.core.billing_cycle import get_billing_period, get_payment_due_date, get_next_due_dates


def test_expense_before_cut_day_stays_in_current_month():
    assert get_billing_period(date(2026, 5, 14), 15) == "2026-05"


def test_expense_on_cut_day_stays_in_current_month():
    assert get_billing_period(date(2026, 5, 15), 15) == "2026-05"


def test_expense_after_cut_day_moves_to_next_month():
    assert get_billing_period(date(2026, 5, 16), 15) == "2026-06"


def test_payment_due_date_caps_to_short_month():
    due = get_payment_due_date("2026-01", cut_day=31, payment_due_day=31)
    assert due == date(2026, 2, 28)


def test_payment_due_date_31_in_february_does_not_break():
    due = get_payment_due_date("2026-02", cut_day=31, payment_due_day=31)
    assert due == date(2026, 3, 31)


def test_get_next_due_dates_returns_requested_number_of_cycles():
    result = get_next_due_dates(cut_day=15, payment_due_day=10, today=date(2026, 5, 20), cycles_ahead=3)
    assert len(result) == 3
    periods = [r["billing_period"] for r in result]
    assert periods == sorted(periods)


def test_get_next_due_dates_flags_open_cycle():
    # Hoy cae antes del corte (día 20 < corte 25): el periodo actual sigue abierto.
    result = get_next_due_dates(cut_day=25, payment_due_day=10, today=date(2026, 5, 20), cycles_ahead=2)
    assert result[0]["is_open"] is True
    assert result[0]["cut_date"] > date(2026, 5, 20)


def test_get_next_due_dates_flags_closed_cycle_still_unpaid():
    # Hoy cae después del corte (día 20 > corte 15): ya cerró, pero el pago sigue pendiente.
    result = get_next_due_dates(cut_day=15, payment_due_day=10, today=date(2026, 5, 20), cycles_ahead=1)
    assert result[0]["is_open"] is False
    assert result[0]["cut_date"] <= date(2026, 5, 20)
    assert result[0]["due_date"] >= date(2026, 5, 20)


def test_get_next_due_dates_excludes_past_due_dates():
    result = get_next_due_dates(cut_day=15, payment_due_day=10, today=date(2026, 5, 20), cycles_ahead=5)
    assert all(r["due_date"] >= date(2026, 5, 20) for r in result)


def test_get_next_due_dates_no_duplicate_periods_across_short_months():
    result = get_next_due_dates(cut_day=31, payment_due_day=31, today=date(2026, 2, 1), cycles_ahead=4)
    periods = [r["billing_period"] for r in result]
    assert len(periods) == len(set(periods))
