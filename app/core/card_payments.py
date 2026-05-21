def calculate_pending_balance(total_expenses: float, total_payments: float) -> dict:
    pending = round(total_expenses - total_payments, 2)
    return {
        "pending": pending,
        "is_paid": pending <= 0,
    }
