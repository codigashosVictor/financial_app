from datetime import date

from app.core.billing_cycle import get_billing_period, get_payment_due_date


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
