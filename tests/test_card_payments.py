from app.core.card_payments import calculate_pending_balance


def test_pending_balance_for_partial_payment():
    result = calculate_pending_balance(total_expenses=1000, total_payments=250)

    assert result == {"pending": 750, "is_paid": False}


def test_pending_balance_marks_paid_when_covered():
    result = calculate_pending_balance(total_expenses=1000, total_payments=1000)

    assert result == {"pending": 0, "is_paid": True}


def test_pending_balance_overpayment():
    result = calculate_pending_balance(total_expenses=500, total_payments=600)

    assert result["pending"] == -100.0
    assert result["is_paid"] is True


def test_pending_balance_zero_expenses():
    result = calculate_pending_balance(total_expenses=0, total_payments=0)

    assert result["pending"] == 0.0
    assert result["is_paid"] is True


def test_pending_balance_rounding():
    result = calculate_pending_balance(total_expenses=333.333, total_payments=100)

    assert result["pending"] == 233.33
