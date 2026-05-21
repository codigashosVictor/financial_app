from app.core.card_payments import calculate_pending_balance


def test_pending_balance_for_partial_payment():
    result = calculate_pending_balance(total_expenses=1000, total_payments=250)

    assert result == {"pending": 750, "is_paid": False}


def test_pending_balance_marks_paid_when_covered():
    result = calculate_pending_balance(total_expenses=1000, total_payments=1000)

    assert result == {"pending": 0, "is_paid": True}
